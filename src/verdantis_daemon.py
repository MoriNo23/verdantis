import json
import os
import subprocess
import time
os.environ.setdefault('GDK_BACKEND', 'wayland')

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, GtkLayerShell, GLib, Gio

from app_info import APP_ID, APP_NAME, VENDOR
from wayland_popup import (
    WaylandPopup,
    _extract_markup_url,
    _get_app_icon_from_desktop,
    _icon_from_theme,
)
import history_store

VERSION = "0.11.1"
# Versión del spec freedesktop que el daemon realmente sirve (posición 4 de
# GetServerInformation). 1.2 es lo que declaran dunst/mako/Plasma 6.3.6: no
# hay features de 1.3 implementadas, no se anuncia.
SPEC_VERSION = "1.2"

# Fuente simbólica del cierre → razón NotificationClosed del spec 1.2
# (1=expiró, 2=usuario, 3=CloseNotification). Único mapeo del contrato:
# la UI comunica la fuente ("timeout"/"user"/"action"/"dbus-close"), nunca
# el número. None como fuente = cierre silencioso (replaces/dedup/replay).
_RAZONES = {"timeout": 1, "user": 2, "action": 2, "dbus-close": 3}


def _reason_for(source):
    """Fuente simbólica → razón del spec; None = no emitir señal."""
    return _RAZONES.get(source)


def _is_browser(app_name, desktop_entry):
    """¿El sender es un navegador? Detección por desktop-entry (brave-browser,
    firefox, chromium...) o por app_name conocido. Para navegadores la línea de
    app muestra "Navegador - <tab>" y el título se pliega ahí."""
    blob = "{} {}".format(app_name or "", desktop_entry or "").lower()
    return any(b in blob for b in (
        "brave", "chrome", "chromium", "firefox", "edge", "vivaldi",
        "opera", "browser",
    ))


def _local_path(p):
    """Convierte file:///ruta → /ruta (Brave/Chrome mandan el icono del tab como
    file:// URI; os.path.exists falla con el prefijo)."""
    if p and p.startswith("file://"):
        return p[len("file://"):]
    return p


def _dedup_key(app_name, summary, body, sender=""):
    """Clave de duplicado para una notificación, normalizada.

    El problema real que resuelve la dedup: varias apps (pestañas web,
    PWAs, scripts que spamean) NO usan replaces_id y emiten la MISMA
    notificación N veces seguidas -> N toasts idénticos encimados.

    La clave se basa en lo que el usuario percibe como "el mismo evento":
    app + contenido (summary+body). Se normaliza a minúsculas y se colapsan
    espacios/tabs para que variaciones triviales (mayúsculas, dobles saltos)
    no rompan la igualdad; la app_name se normaliza igual (vars "WhatsApp Web"
    vs "whatsapp web").

    sender (el D-Bus unique name) NO forma parte de la clave: dos emisores
    distintos con el mismo contenido son, casi siempre, la misma pestaña
    compartiendo el bus. Sobresele nosotros discriminarlo; el dedup es sobre
    lo que el usuario ve.
    """
    def norm(s):
        return " ".join((s or "").lower().split())

    return "{}|{}|{}".format(norm(app_name), norm(summary), norm(body))


def _pick_action_key(actions):
    """Devuelve la action key que el sender registró (spec 1.2):
    - "default" si el sender la proveyó (click en el cuerpo del toast),
    - la primera key real si hay actions pero no "default",
    - None si no hay actions (no emitir ActionInvoked inventando keys).
    """
    if not actions or len(actions) < 2:
        return None
    for i in range(0, len(actions) - 1, 2):
        if actions[i] == "default":
            return "default"
    return actions[0]


def _is_pwa(desktop_entry):
    """¿La notificación viene de una PWA instalada (webapp del navegador)?

    Chromium/Brave crean un .desktop propio al instalar la webapp, con
    `Exec=.../brave --app-id=<id>` y `StartupWMClass=crx_<id>`. El navegador
    manda ese .desktop en el hint `desktop-entry`. Distinguirlo del navegador
    genérico (brave-browser.desktop / firefox.desktop) permite no disparar
    xdg-open (que abriría una ventana-PWA duplicada): la PWA ya re-enfoca su
    propia ventana al recibir ActionInvoked.
    """
    if not desktop_entry:
        return False
    name = desktop_entry
    if not name.endswith(".desktop"):
        name = name + ".desktop"
    candidates = [
        os.path.expanduser(os.path.join("~/.local/share/applications", name)),
        os.path.join("/usr/share/applications", name),
        os.path.expanduser(os.path.join("~/.local/share/applications", desktop_entry)),
    ]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if not path:
        base = desktop_entry.lower()
        if ("brave-" in base or "chrome-" in base) and "browser" not in base:
            return True
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return False
    return ("--app-id=" in content) or ("crx_" in content)


NOTIFICATIONS_XML = '''
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg type="s" name="app_name" direction="in"/>
      <arg type="u" name="replaces_id" direction="in"/>
      <arg type="s" name="app_icon" direction="in"/>
      <arg type="s" name="summary" direction="in"/>
      <arg type="s" name="body" direction="in"/>
      <arg type="as" name="actions" direction="in"/>
      <arg type="a{sv}" name="hints" direction="in"/>
      <arg type="i" name="expire_timeout" direction="in"/>
      <arg type="u" name="id" direction="out"/>
    </method>
    <method name="CloseNotification">
      <arg type="u" name="id" direction="in"/>
    </method>
    <method name="GetCapabilities">
      <arg type="as" name="caps" direction="out"/>
    </method>
    <method name="GetServerInformation">
      <arg type="s" name="name" direction="out"/>
      <arg type="s" name="vendor" direction="out"/>
      <arg type="s" name="version" direction="out"/>
      <arg type="s" name="spec_version" direction="out"/>
    </method>
    <signal name="NotificationClosed">
      <arg type="u" name="id"/>
      <arg type="u" name="reason"/>
    </signal>
    <signal name="ActionInvoked">
      <arg type="u" name="id"/>
      <arg type="s" name="action_key"/>
    </signal>
  </interface>
</node>
'''


def _is_local_url(url):
    """True si la URL apunta a la maquina local o red privada (RFC1918).

    localhost / 127.0.0.0/8 / ::1 / 0.0.0.0 / 192.168.x / 10.x / 172.16-31.x.
    Jamas es un destino legitimo de una notificacion: abrirlo con xdg-open
    suele ser un bug o una url inyectada (p.ej. el propio servidor del tester).
    """
    if not url:
        return True
    hostport = url.split("://", 1)[-1].split("/", 1)[0]
    # IPv6 entre corchetes: [::1] o [::1]:puerto -> host = ::1
    if hostport.startswith("["):
        host = hostport.split("]", 1)[0].strip("[]")
    else:
        host = hostport.split(":", 1)[0]
    host = host.lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    if host.startswith("127."):
        return True
    parts = host.split(".")
    if len(parts) == 4:
        try:
            a, b, c, _ = (int(p) for p in parts)
            return (a == 10
                    or (a == 192 and b == 168)
                    or (a == 172 and 16 <= b <= 31))
        except ValueError:
            return False
    return False


class NotificationManager:
    # Cuántos toasts conviven en pantalla. El resto ESPERA en la cola FIFO hasta
    # que se libere un hueco (spec `toast-stack`, "La pila muestra dos toasts a
    # la vez"): la capacidad es la misma para cualquier `urgency`.
    MAX_VISIBLE = 2
    # Gap entre cards de la pila, en px. Autoridad única: lo suman `_stack_offsets`
    # al calcular el offset de cada card (spec `toast-stack`, "El reflow es
    # estable": el de abajo arranca a `alto_de_arriba + 12`). Antes este valor
    # estaba hardcodeado en `WaylandPopup._apply_margins` (12) y la constante de
    # acá (8) no la usaba nadie: dos fuentes de verdad, la equivocada muerta.
    STACK_GAP = 12
    # Delay entre notificaciones de un mismo burst: evita que lleguen todas a la
    # vez cuando el sender dispara un flood (ej: 10 notis en <100ms). La cola se
    # drena una por vez, cada STAGGER_MS, en orden de LLEGADA (spec
    # `toast-orden-llegada`).
    STAGGER_MS = 400
    # Holdback del auto-close por posición en el stack: evita que un burst de
    # notificaciones (misma urgencia, llegadas juntas) venza TODAS a la vez.
    # Cada popup suma idx * CLOSE_STAGGER_MS a su duration, donde idx es su
    # posición en el stack al momento de mostrarse (ver _show_popup). Así
    # desaparecen escalonadas en vez de colapsar en una ventana de ~1.2s.
    CLOSE_STAGGER_MS = 800
    # Todo contenido idéntico emitido dentro de esta ventana (seg) se considera
    # el MISMO evento y se reemplaza en vez de apilar un duplicado. Pasada la
    # ventana, dos notificaciones iguales vuelven a ser eventos legitimos
    # (p.ej. dos avisos separados con el mismo texto 30s después).
    DEDUP_WINDOW = 10.0

    def __init__(self, corner="top-right", scheduler=None):
        self.corner = corner
        self._active = []
        # Cola de entrada pendiente de mostrar: lista de (nid, kwargs, urgency).
        self._pending = []
        # scheduler inyectable (tests sin GLib): callable(ms, cb) -> id.
        # None => GLib.timeout_add sobre el MainLoop del daemon.
        self._scheduler = scheduler
        self._pump_scheduled = False
        self._next_id = 1
        self._corner = corner
        self._dbus_bus = None
        self._notifications = {}
        # dedup key -> (nid, timestamp): rastrea la última emisión de cada
        # contenido para detectar duplicados dentro de DEDUP_WINDOW.
        self._dedup = {}
        # Ids reproducidos por el dashboard: su cierre/acción no toca el bus
        # (spec `contrato-dbus`, escenario replay).
        self._replay = set()
        # Ring buffer of recent notifications for the dashboard + replay
        self.history = []
        self.MAX_HISTORY = 200

    def set_dbus(self, bus):
        self._dbus_bus = bus

    def _schedule(self, ms, cb):
        if self._scheduler is not None:
            return self._scheduler(ms, cb)
        return GLib.timeout_add(ms, cb)

    def _ensure_pump(self):
        """Agenda (una sola vez) el drenado de la cola con el stagger fijo."""
        if self._pump_scheduled or not self._pending:
            return
        self._pump_scheduled = True
        self._schedule(self.STAGGER_MS, self._pump)

    def _pump(self):
        """Muestra a lo sumo UNA notificación pendiente por tick, respetando
        MAX_VISIBLE y el orden de llegada (FIFO, sin reordenar por `urgency`).
        Re-agenda si queda pendiente y hay hueco. Un-shot: retorna False para que
        GLib no lo repita."""
        self._pump_scheduled = False
        if self._pending and len(self._active) < self.MAX_VISIBLE:
            nid, kwargs, _urg = self._pending.pop(0)
            self._show_popup(nid, kwargs)
        if self._pending and len(self._active) < self.MAX_VISIBLE:
            self._pump_scheduled = True
            self._schedule(self.STAGGER_MS, self._pump)
        return False

    def _extract_url(self, hints):
        url = None
        try:
            kde_urls = hints.get("x-kde-urls")
            if kde_urls and len(kde_urls) > 0:
                url = kde_urls[0]
        except Exception:
            pass
        if not url:
            try:
                url = hints.get("url", "")
            except Exception:
                pass
        if not url:
            try:
                data = hints.get("data")
                if data:
                    if isinstance(data, bytes):
                        data = json.loads(data.decode("utf-8", errors="replace"))
                    if isinstance(data, dict):
                        url = data.get("url", "")
                    elif isinstance(data, str):
                        try:
                            url = json.loads(data).get("url", "")
                        except Exception:
                            url = data
            except Exception:
                pass
        if url and not url.startswith(("http://", "https://", "mailto:", "tel:")):
            url = ""
        # Jamas abrir urls apuntando a la maquina local/red privada: no es un
        # destino legitimo de notificacion y suele ser una url inyectada (p.ej.
        # el propio server del tester). Ver _is_local_url.
        if url and _is_local_url(url):
            url = ""
        return url

    def notify(self, app_name="", app_icon="", summary="", body="",
               actions=None, hints=None, expire_timeout=-1, replaces_id=0,
               sender="", replay=False):
        if hints is None:
            hints = {}
        if actions is None:
            actions = []

        if replaces_id > 0:
            # Reemplazo in-place: el card sigue vivo, NO es un cierre (spec
            # `contrato-dbus`) — fuente None = sin emisión.
            self._close_id(replaces_id, source=None)

        nid = self._next_id
        self._next_id += 1
        if replay:
            self._replay.add(nid)

        # Dedup por contenido: si la MISMA notificación (app + summary + body)
        # ya fue emitida en la ventana de DEDUP_WINDOW, reemplazamos la anterior
        # en vez de apilar un duplicado. Sirve para apps que spamean contenido
        # idéntico sin usar replaces_id (pestañas web, PWAs, scripts).
        now = time.time()
        key = _dedup_key(app_name, summary, body, sender)
        if key in self._dedup:
            old_id, old_ts = self._dedup[key]
            if now - old_ts <= self.DEDUP_WINDOW and old_id not in self._notifications:
                # La entrada quedó huérfana (p.ej. cerraron el popup) -> limpiar
                self._dedup.pop(key, None)
            elif now - old_ts <= self.DEDUP_WINDOW:
                # Duplicado real dentro de la ventana: cerrar el anterior para
                # que el nuevo lo reemplace sin dejar dos toasts iguales. No es
                # un cierre del contrato (spec `contrato-dbus`): fuente None.
                self._close_id(old_id, source=None)
                self._dedup.pop(key, None)
        self._dedup[key] = (nid, now)

        url = self._extract_url(hints)
        # URL de hyperlink en el body (body-hyperlinks): <a href="...">
        markup_url = _extract_markup_url(body)
        if not url and markup_url:
            url = markup_url
        desktop_entry = hints.get("desktop-entry", "") or app_name
        # Urgency: BYTE 0=low, 1=normal, 2=critical (spec freedesktop 1.2)
        urgency = hints.get("urgency", 1)
        try:
            urgency = int(urgency)
        except (TypeError, ValueError):
            urgency = 1
        if urgency not in (0, 1, 2):
            urgency = 1
        # Hints del spec freedesktop 1.2 que verdantis no parseaba (gaps):
        #   resident      : bool — la app cierra la noti; el daemon NO la
        #                  auto-expira (forza duration=0). Confirmado en
        #                  KDE (notification.cpp:423) y mako.
        #   transient     : bool — no guardar en historial (verdantis no
        #                  tiene historial, se guarda para future-proofing).
        #   category      : str — agrupacion ("im", "email", "presence"...).
        #   suppress-sound: bool — NO reproducir sonido (no implementado yet).
        #   sound-name    : str — nombre en el freedesktop sound theme.
        is_resident = bool(hints.get("resident", False))
        is_transient = bool(hints.get("transient", False))
        category = hints.get("category", "") or ""
        suppress_sound = bool(hints.get("suppress-sound", False))
        sound_name = hints.get("sound-name", "") or ""
        self._notifications[nid] = {
            "actions": actions,
            "hints": hints,
            "url": url,
            "app_name": app_name,
            "desktop_entry": desktop_entry,
            "urgency": urgency,
            "sender": sender,
            "is_resident": is_resident,
            "is_transient": is_transient,
            "category": category,
            "suppress_sound": suppress_sound,
            "sound_name": sound_name,
        }

        image_left_path = _local_path(hints.get("image-path", ""))
        if not image_left_path or not os.path.exists(image_left_path):
            image_left_path = _local_path(app_icon) if app_icon and os.path.exists(_local_path(app_icon)) else ""

        app_icon_file = _local_path(app_icon) if app_icon and os.path.exists(_local_path(app_icon)) else ""

        image_data = hints.get("image-data", None)
        image_path = _local_path(hints.get("image-path", ""))
        banner_path = ""
        if image_path and os.path.exists(image_path) and image_path != image_left_path:
            banner_path = image_path

        kwargs = {
            "titulo": summary,
            "cuerpo": body,
            "icon_path": image_left_path if image_left_path else None,
            "image_path": banner_path if banner_path else None,
            "image_data_raw": image_data,
            # expire_timeout (spec freedesktop 1.2):
            #   == 0 -> persistente (requireInteraction del navegador: nunca expirar)
            #    > 0 -> ese valor en ms
            #    < 0 -> default del server (6000ms, ej -1 = "server default")
            # Confirmado en mako/dunst/KDE: 0 = sticky, -1 = default.
            # resident (hint): la app gestiona el cierre; el daemon NO auto-expira.
            # Igual que expire_timeout=0 (KDE notification.cpp:423).
            "duration": (0 if expire_timeout == 0 or is_resident
                         else expire_timeout if expire_timeout > 0
                         else 6000),
            "corner": self._corner,
            "accent": hints.get("accent", "#80cbc4"),
            "urgency": urgency,
            "app_name": app_name,
            # Path normalizado si el icono es un archivo existente; si no, el
            # string CRUDO del sender. Sin este "or app_icon" el 43.5% de las
            # notificaciones reales que mandan un nombre de tema pelado
            # ("network-wireless-disconnected", "dialog-warning", ...) llegaba
            # como "" y el popup no podía resolver el logo por tema.
            "app_icon": app_icon_file or app_icon,
            # Fuente simbólica de cierre ("timeout"/"user"/"action"): la razón
            # del spec la resuelve el daemon (único mapeo, ver _RAZONES). El
            # popup llama cb(source) con UN solo argumento posicional.
            "on_close": lambda source="timeout", nid=nid: self._on_closed(nid, source),
            # La key viaja como PRIMER posicional (el widget llama
            # `on_click(key)`): si el lambda la declarara después de nid, se
            # la comería como nid (bug del live: el toast no se cerraba y
            # notify-send nunca recibía la action). nid queda por closure.
            "on_click": lambda action_key=None, nid=nid: self._on_action_invoked(nid, action_key),
            # Botones de acción (spec toast-acciones): la lista plana cruda
            # la parsea el widget (default fuera, dedup, cap 3). El hint
            # action-icons pide interpretar cada key como icono del tema.
            "actions": actions,
            "action_icons": bool(hints.get("action-icons", False)),
        }

        # Navegadores: la línea de app = "Brave - <tab>" (el tab = summary, que es
        # el nombre de la notificación/pestaña) y el título se pliega ahí.
        if _is_browser(app_name, desktop_entry):
            kwargs["app_label"] = "{} - {}".format(app_name, summary)
            kwargs["hide_title"] = True

        # Batching: toda notificación entra a la cola pendiente y se muestra
        # una por vez cada STAGGER_MS (ver _pump). Así un burst no aparece
        # todo de golpe: se van espaciando con delay controlado.
        #
        # La cola es FIFO POR LLEGADA y nada la reordena (spec
        # `toast-orden-llegada`): antes `_sort_pending` la ordenaba por
        # `urgency`, y la pila terminaba apilándose por tipo — un critical
        # tardío adelantaba a los que ya esperaban y un low se iba al fondo.
        # La `urgency` sigue viva donde sirve: duración y opacidad del card
        # (WaylandPopup.__init__), nunca la posición.
        self._pending.append((nid, kwargs, urgency))
        self._ensure_pump()

        # Capture for dashboard history + replay
        import time as _time
        self.history.append({
            "id": nid,
            "timestamp": _time.time(),
            "app_name": app_name,
            "app_icon": app_icon,
            "summary": summary,
            "body": body,
            "actions": list(actions) if actions else [],
            "hints": {k: (v if isinstance(v, (str, int, float, bool)) else str(v))
                      for k, v in hints.items()},
            "expire_timeout": expire_timeout,
            "sender": sender,
        })
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

        # ── Persistencia a disco (historial JSONL + bytes de iconos) ──────
        # El archivo nunca debe tumbar una notificación: best-effort total.
        if not is_transient:
            self._persist_to_disk(
                nid, app_name, app_icon, summary, body, actions, hints,
                expire_timeout, sender, url,
                image_left_path, app_icon_file, banner_path, image_data,
                kwargs["duration"],
            )

        return nid

    def _persist_to_disk(self, nid, app_name, app_icon, summary, body, actions,
                         hints, expire_timeout, sender, url,
                         image_left_path, app_icon_file, banner_path, image_data,
                         duration):
        """Archiva la notificación en history_store (JSONL en el XDG data
        home) con los bytes de la imagen izquierda del sender.

        Los favicons de los navegadores viven en /tmp y mueren con la sesión
        que los creó: se COPIAN al directorio propio para que el replay del
        dashboard pueda reproducir "cómo se veía X app tal cual".
        image_left_source documenta de dónde salió el slot izquierdo.

        EXCEPCIÓN DE TERMINOLOGÍA: las claves del registro y los nombres de los
        PNG en disco (`avatar_source`, `avatar_file`, `n<id>_avatar.png`) NO se
        renombran — son un esquema de PERSISTENCIA ya escrito en el historial de
        disco; renombrarlas lo dejaría huérfano (y es lo que fija
        tests/test_history_store.py). El vocabulario del layout, en cambio, es
        "imagen izquierda" en todo src/."""
        try:
            image_left_file = None
            if image_data is not None:
                image_left_file = history_store.save_image_data(nid, image_data)
            elif image_left_path:
                image_left_file = history_store.copy_icon(nid, image_left_path, "avatar")
            elif app_icon_file:
                image_left_file = history_store.copy_icon(nid, app_icon_file, "avatar")
            banner_file = None
            if banner_path:
                banner_file = history_store.copy_icon(nid, banner_path, "banner")
            history_store.append({
                "id": nid,
                "timestamp": time.time(),
                "app_name": app_name,
                "app_icon": app_icon,
                "summary": summary,
                "body": body,
                "actions": list(actions) if actions else [],
                "hints": {k: (v if isinstance(v, (str, int, float, bool)) else str(v))
                          for k, v in hints.items()},
                "expire_timeout": expire_timeout,
                "sender": sender,
                "url": url or "",
                "duration": duration,
                "avatar_source": self._image_left_source_for(
                    app_name, image_left_path, app_icon, image_data, hints),
                "avatar_file": image_left_file,
                "banner_file": banner_file,
            })
        except Exception:
            pass  # best-effort: un fallo de disco nunca puede romper Notify

    @staticmethod
    def _image_left_source_for(app_name, image_left_path, app_icon, image_data,
                               hints):
        """Diagnóstico de proveniencia del slot de imagen izquierda (para el
        historial): image-path / app_icon (sender), image-data (tab),
        app-icon-fallback (desktop exacto o tema), none (nada resolvió — el slot
        cae al placeholder con la inicial)."""
        if image_data is not None:
            return "image-data"
        if image_left_path:
            img_hint = _local_path(hints.get("image-path", ""))
            return "image-path" if image_left_path == img_hint else "app_icon"
        if (_get_app_icon_from_desktop(app_name, 16)
                or _icon_from_theme(app_icon, 16)
                or _icon_from_theme(app_name, 16)):
            return "app-icon-fallback"
        return "none"

    def _stack_offsets(self):
        """Offset vertical (px) de cada popup activo, en orden de pila.

        Es la suma de las alturas REALES de las cards de arriba + el gap entre
        ellas: la altura de cada uno se pide en el momento, así el offset ya
        incluye cualquier cambio de alto reciente (expandir/contraer, re-wrap por
        hover). Con un índice y la altura propia (`índice × (alto + gap)`) las
        cards solapaban en cuanto sus alturas diferían — spec `toast-stack`.
        """
        offsets, offset = [], 0
        for _, p in self._active:
            offsets.append(offset)
            offset += p.stack_height() + self.STACK_GAP
        return offsets

    def _reflow_stack(self):
        """Re-flowea TODA la pila con los offsets de `_stack_offsets`.

        Se llama al mostrar, al cerrar y al cambiar de alto cualquier card (el
        popup avisa por `on_resized`): en los tres casos las cards de abajo
        pueden haber cambiado de alto y necesitan su hueco recalculado para no
        solaparse.
        """
        for offset, (_, p) in zip(self._stack_offsets(), self._active):
            p.set_stack_margin(offset)

    def _show_popup(self, nid, kwargs):
        popup = WaylandPopup(**kwargs)
        idx = len(self._active)
        # Stagger del auto-close: la posición 0 mantiene su duration base; las
        # siguientes suman un holdback creciente (idx * CLOSE_STAGGER_MS) para no
        # vencer todas a la vez cuando llegan en burst. La posición 0 NO se
        # modifica para preservar el default del server (6000ms) en el caso
        # aislado. Los popups persistentes (duration=0) no aplican holdback.
        if popup.duration > 0 and idx > 0:
            popup.duration += idx * self.CLOSE_STAGGER_MS
        # La pila se re-flowea con cada resize de este card (spec `toast-stack`):
        # sin esto, expandir "Ver más" deja a los de abajo con el margen viejo.
        popup.on_resized = self._reflow_stack
        # El hueco se reserva ANTES de MAPEAR: `prepare()` crea la superficie y
        # la commitea con el offset que tenga puesto, así que si se entra a la
        # pila después de mapear, el primer frame aparece encima del toast de
        # arriba (el que "la tapa"). `set_stack_margin` sin window todavía solo
        # guarda el valor, y `_build_ui` → `_apply_margins` lo usa al crear la
        # superficie: el primer frame ya llega en su hueco (spec `toast-stack`,
        # "Un toast que entra no tapa al que ya estaba").
        self._active.append((nid, popup))
        popup.set_stack_margin(self._stack_offsets()[-1])
        popup.prepare()
        self._reflow_stack()

    def _drenar_cola(self):
        """Si quedó un hueco en la pila, deja entrar a la primera de la cola.

        La siguiente en entrar es la primera en LLEGAR (FIFO, sin reordenar por
        `urgency` — spec `toast-orden-llegada`). Lo comparten los DOS caminos de
        cierre: el explícito (`_close_id`: cierre del usuario, replaces_id,
        dedup) y el vencimiento por timer (`_on_closed`).
        """
        if self._pending and len(self._active) < self.MAX_VISIBLE:
            nid2, qk2, _ = self._pending.pop(0)
            self._show_popup(nid2, qk2)
            self._ensure_pump()

    def _close_id(self, nid, source="dbus-close"):
        """Cierre explícito por id. `source` es la fuente simbólica del
        contrato ("dbus-close" desde el bus; None = silencio para
        replaces/dedup): la emisión la hace `_on_closed` vía el callback del
        popup, así hay UN solo trazado y los ids sin popup en pantalla
        (desconocidos o en cola) no emiten nada (spec `contrato-dbus`)."""
        for i, (aid, popup) in enumerate(self._active):
            if aid == nid:
                popup._close(source)
                break
        self._pending = [(qid, qk, q) for qid, qk, q in self._pending if qid != nid]
        # Reflow inmediato: remover de _active y re-posicionar el stack AHORA
        # (no depender del callback del popup, que puede no dispararse en
        # algunos paths de cierre). Esto garantiza que las toasts restantes
        # suban a llenar el hueco y las que esperaban en _pending aparezcan.
        self._active = [(aid, p) for aid, p in self._active if aid != nid]
        self._notifications.pop(nid, None)
        # Sincroniza la tabla de dedup: si el toast que se cierra era el último
        # portador de una clave, esa entrada queda libre para el próximo contenido.
        self._dedup = {k: v for k, v in self._dedup.items() if v[0] != nid}
        self._replay.discard(nid)
        self._reflow_stack()
        self._drenar_cola()

    def _on_action_invoked(self, nid, action_key=None):
        info = self._notifications.get(nid, {})
        actions = info.get("actions", [])
        url = info.get("url", "")

        # BUG-2: emitir la key REAL del sender, no "default" inventada.
        # DIRIGIDO al sender (no broadcast None): la spec freedesktop manda que
        # ActionInvoked vaya a la conexion que emitio Notify. Chromium/Brave solo
        # re-enfoca la PWA/tab si recibe la señal en su propia conexion.
        # Con action_key (click en un BOTON, spec toast-acciones) se emite ESA
        # key directa; None = click del cuerpo → la default como siempre.
        action_key = action_key or _pick_action_key(actions)
        sender = info.get("sender", "") or None

        # Replay del dashboard: no emite ActionInvoked al bus (spec
        # `contrato-dbus`, escenario replay). El xdg-open de abajo sí puede
        # correr: es local, no toca el bus.
        es_replay = nid in self._replay
        if action_key and self._dbus_bus and not es_replay:
            try:
                self._dbus_bus.emit_signal(
                    sender, "/org/freedesktop/Notifications",
                    "org.freedesktop.Notifications", "ActionInvoked",
                    GLib.Variant("(us)", (nid, action_key)),
                )
            except Exception:
                pass

        # El click NO lanza ventanas de la app (evita abrir navegadores a lo loco).
        # Regla estilo dunst (mutuamente excluyente):
        #   - SI el sender registró actions: emitir ActionInvoked y YA (el sender
        #     se activa solo: navegador re-enfoca tab/PWA, app nativa corre su
        #     callback). NUNCA xdg-open en ese caso -> evita doble-abierto.
        #   - SOLO si NO hay actions PERO sí URL: xdg-open (apps nativas que no
        #     manejan ActionInvoked).
        # El navegador SIEMPRE manda actions=["default",...], así que Pinterest/
        # Slack/WhatsApp Web caen en la rama ActionInvoked y no abren página extra.
        desktop_entry = info.get("desktop_entry", "")
        is_pwa = _is_pwa(desktop_entry)
        has_actions = bool(actions)
        # Jamas abrir urls a la maquina local/red privada (ver _is_local_url).
        # Es la ultima linea de defensa: ni siquiera con PWA borra esto.
        if url and _is_local_url(url):
            url = ""
        if url and not has_actions:
            try:
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        # Cierre inmediato del popup visual con fuente "action": su callback
        # dispara _on_closed, que emite NotificationClosed razón 2 — DESPUÉS
        # del ActionInvoked de arriba (orden fijo del spec `contrato-dbus`).
        for aid, popup in list(self._active):
            if aid == nid:
                popup._close("action")
                break

    def _on_closed(self, nid, source="timeout"):
        """Cierre de un popup vivo (timer por defecto; la UI pasa "user"
        desde la franja/teclado y "action" desde el click).

        Además de limpiar el dict hay que re-flowear la pila y darle el hueco a
        la primera de la cola: sin eso, con la pila llena las pendientes esperan
        para siempre (nadie más agenda el drenado) y los toasts de abajo quedan
        con el hueco del que venció (spec `toast-stack`).

        La emisión del contrato vive acá (único trazado): fuente → razón en
        _RAZONES; fuente None o replay = silencio.
        """
        self._notifications.pop(nid, None)
        self._active = [(aid, p) for aid, p in self._active if aid != nid]
        self._reflow_stack()
        self._drenar_cola()
        es_replay = nid in self._replay
        self._replay.discard(nid)
        reason = _reason_for(source)
        if reason is not None and not es_replay and self._dbus_bus:
            self._dbus_bus.emit_signal(
                None, "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", "NotificationClosed",
                GLib.Variant("(uu)", (nid, reason)),
            )

    def close_all(self):
        for _, popup in self._active:
            # Apagado/limpieza interna: sin emisión (fuente None) — no es un
            # cierre con razón para el cliente (spec `contrato-dbus`).
            popup._close(None)
        self._active = []
        self._pending = []
        self._pump_scheduled = False
        self._notifications = {}


class NotificationDaemon:
    def __init__(self, corner="top-right"):
        self._corner = corner
        self._manager = NotificationManager(corner)
        self._bus = None
        self._loop = None
        self._owned = False

    def _on_bus_acquired(self, conn, name):
        node = Gio.DBusNodeInfo.new_for_xml(NOTIFICATIONS_XML)
        conn.register_object(
            "/org/freedesktop/Notifications",
            node.interfaces[0],
            self._handle_method_call,
            self._handle_get_property,
            None,
        )
        self._bus = conn
        self._manager.set_dbus(conn)

    def _handle_method_call(self, conn, sender, obj_path, iface_name, method_name, params, invocation):
        if method_name == "Notify":
            app_name, replaces_id, app_icon, summary, body, actions, hints, timeout = params
            nid = self._manager.notify(
                app_name=app_name, app_icon=app_icon,
                summary=summary, body=body,
                actions=actions, hints=hints,
                expire_timeout=timeout, replaces_id=replaces_id,
                sender=sender,
            )
            invocation.return_value(GLib.Variant("(u)", (nid,)))
        elif method_name == "CloseNotification":
            nid = params[0]
            self._manager._close_id(nid)
            invocation.return_value(None)
        elif method_name == "GetCapabilities":
            # caps honestas (spec toast-acciones): "actions" ahora SE RINDE
            # (fila de botones renderizada) y "action-icons" es real (hint →
            # icono del tema por key, con fallback a label). "sound" NO se
            # anuncia: los hints sound-* se siguen ignorando.
            caps = ["actions", "action-icons", "body", "body-markup",
                    "body-hyperlinks", "icon-static", "persistence"]
            invocation.return_value(GLib.Variant("(as)", (caps,)))
        elif method_name == "GetServerInformation":
            invocation.return_value(GLib.Variant("(ssss)", (
                APP_NAME, VENDOR, VERSION, SPEC_VERSION,
            )))

    def _handle_get_property(self, conn, sender, obj_path, iface_name, prop_name):
        raise GLib.GError(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND, "no props")

    def _on_name_acquired(self, conn, name):
        self._owned = True

    def _on_name_lost(self, conn, name):
        self._owned = False

    def run(self):
        Gio.bus_own_name(
            Gio.BusType.SESSION,
            "org.freedesktop.Notifications",
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )
        self._loop = GLib.MainLoop()
        self._loop.run()

    def stop(self):
        if self._loop:
            self._loop.quit()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Daemon de notificaciones Wayland (DBus)")
    parser.add_argument("--corner", default="top-right",
                        choices=["top-right", "top-left", "bottom-right", "bottom-left"])
    parser.add_argument("--dashboard", action="store_true", default=True,
                        help="Start the Flask dashboard on 127.0.0.1:8777")
    args = parser.parse_args()

    daemon = NotificationDaemon(corner=args.corner)

    if args.dashboard:
        from dashboard import start_dashboard
        start_dashboard(daemon)
        print(f"[{APP_ID}] Dashboard: http://127.0.0.1:8777")

    try:
        daemon.run()
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    main()
