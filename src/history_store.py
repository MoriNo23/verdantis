"""Persistencia del historial de notificaciones (JSONL) + bytes de iconos.

Cada `Notify` se archiva como una línea JSON en
`$XDG_DATA_HOME/verdantis/history.jsonl` (default `~/.local/share/verdantis/`),
MÁS los bytes del icono/imagen cuando el sender los manda como archivo — así
`verdantis replay` puede volver a mostrar "cómo se veía X app tal cual" en
producción (antes lo consumía el dashboard, retirado en v0.12.0).

EXCEPCIÓN DE TERMINOLOGÍA: las claves del registro (`avatar_file`,
`banner_file`) y el nombre de los PNG (`n<id>_avatar.png`) conservan el término
"avatar" a propósito: son un esquema de PERSISTENCIA ya escrito en el historial
de disco (1000 registros reales), no vocabulario del layout (que es "imagen
izquierda"), y renombrarlas dejaría huérfano ese historial.

Reglas duras:
- NUNCA debe tumbar una notificación: todo es best-effort en try/except.
- Iconos de /tmp son efímeros (favicons de Brave): se COPIAN bytes al dir.
- Tope de tamaño por icono (MAX_ICON_BYTES) y rotación a MAX_ENTRIES.
- transient no se archiva (lo decide el daemon; aquí solo append/read).
"""
import json
import os
import shutil

MAX_ENTRIES = 1000
MAX_ICON_BYTES = 256 * 1024  # 256KB por icono (tmpfs de /tmp es 1.9G)

_DATA_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
    "verdantis",
)


def set_data_dir(path):
    """Inyecta el directorio base (los tests nunca tocan ~/.local)."""
    global _DATA_DIR
    _DATA_DIR = path


def _base_dir():
    return _DATA_DIR


def _history_path():
    return os.path.join(_base_dir(), "history.jsonl")


def _icon_dir():
    return os.path.join(_base_dir(), "icons")


def append(record):
    """Archiva un registro en el JSONL (append atómico por línea)."""
    try:
        os.makedirs(_base_dir(), exist_ok=True)
        with open(_history_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _rotate()
    except Exception:
        pass  # best-effort: un fallo de disco no puede romper Notify


def read():
    """Devuelve los registros en orden de llegada (más viejo primero)."""
    path = _history_path()
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except Exception:
        return []
    return out


def copy_icon(nid, src, kind):
    """Copia bytes de src → icons/n<id>_<kind>.<ext> con tope MAX_ICON_BYTES.

    `src` es una ruta que puede estar en /tmp (efímera): se copia al dir
    propio para que el replay no dependa de archivos que ya no existen."""
    try:
        if not src or not os.path.isfile(src):
            return None
        if os.path.getsize(src) > MAX_ICON_BYTES:
            return None
        os.makedirs(_icon_dir(), exist_ok=True)
        ext = os.path.splitext(src)[1].lower() or ".png"
        fname = "n{}_{}{}".format(nid, kind, ext)
        shutil.copyfile(src, os.path.join(_icon_dir(), fname))
        return fname
    except Exception:
        return None


def icon_path(fname):
    """Ruta absoluta de un archivo de icono guardado."""
    return os.path.join(_icon_dir(), fname)


def clear():
    """Borra el historial y los iconos archivados.

    Devuelve (registros_borrados, iconos_borrados) para que `verdantis clear`
    pueda reportar qué se llevó."""
    n = len(read())
    icons = 0
    if os.path.isdir(_icon_dir()):
        for fname in os.listdir(_icon_dir()):
            try:
                os.remove(os.path.join(_icon_dir(), fname))
                icons += 1
            except OSError:
                pass
    try:
        os.remove(_history_path())
    except OSError:
        pass
    return n, icons


def _rotate():
    """Mantiene las últimas MAX_ENTRIES; elimina los iconos descartados."""
    path = _history_path()
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    if len(lines) <= MAX_ENTRIES:
        return
    keep = lines[-MAX_ENTRIES:]
    dropped = []
    for line in lines[:-MAX_ENTRIES]:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for key in ("avatar_file", "banner_file", "image_file"):
            fname = rec.get(key)
            if fname:
                dropped.append(fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(keep)
    except OSError:
        return
    for fname in dropped:
        try:
            os.remove(icon_path(fname))
        except OSError:
            pass
