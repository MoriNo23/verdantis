"""
Caracterización de `_draw` por PÍXELES: el render actual, fijado como hashes.

Un refactor puro no cambia comportamiento, así que no hay un RED que provocar:
el ciclo correcto acá es "suite verde antes → refactor → suite verde después", y
esta fixture es la que convierte el "después" en una afirmación fuerte en vez de
una opinión. Si el refactor mueve un píxel, cambia el hash y el test lo nombra.

Los casos cubren las ramas que `_draw` puede tomar: app_name presente y ausente,
título visible y plegado (navegador), colapsado y expandido, cuerpo corto, de 2
líneas y con overflow, con y sin actions, franja de descarte con y sin hover, y
banner inferior.

Los rects publicados (`_expand_rect`, `_image_left_rect`, `_close_rect`,
`_action_rects`) se hashean aparte: son el contrato que leen los tests de
click/hover, así que un cambio de geometría se ve aunque los píxeles no cambien
(un rect puede moverse y el mismo texto seguir "cayendo" donde cayó antes).
"""

import hashlib

import wayland_popup as wp
from render_helpers import alloc_and_draw, surface_pixels

W = 360

CUERPO_CORTO = "Conexión «pvpn-killswitch» activada."
CUERPO_2LINEAS = "Conexión «pvpn-routed-killswitch» activada."
CUERPO_LARGO = ("Bienvenido Larp a Capuchino. Un pequeño espacio donde trataremos "
                "de temas variados en un circulo amistoso. Disfruten su estancia "
                "!! El Ultimo power fue Twenty")
ACCIONES = ["default", "Abrir sitio", "settings", "Ajustes", "mark", "Marcar"]

# (nombre, cuerpo, kwargs del widget, expanded, hover)
CASOS = [
    ("corto",              CUERPO_CORTO,  {}, False, False),
    ("corto-hover",        CUERPO_CORTO,  {}, False, True),
    ("2-lineas",           CUERPO_2LINEAS, {}, False, False),
    ("largo-colapsado",    CUERPO_LARGO,  {}, False, False),
    ("largo-expandido",    CUERPO_LARGO,  {}, True,  False),
    ("sin-app",            CUERPO_LARGO,  {"app_name": ""}, False, False),
    ("sin-app-corto",      CUERPO_CORTO,  {"app_name": ""}, False, False),
    ("titulo-oculto",      CUERPO_LARGO,  {"hide_title": True}, False, False),
    ("titulo-oculto-largo", CUERPO_LARGO, {"hide_title": True}, True, False),
    ("actions",            CUERPO_CORTO,  {"actions": ACCIONES}, False, False),
    ("actions-largo",      CUERPO_LARGO,  {"actions": ACCIONES}, False, False),
    ("actions-expandido",  CUERPO_LARGO,  {"actions": ACCIONES}, True,  False),
    ("franja-hover",       CUERPO_LARGO,  {"persistent": True}, False, True),
    ("franja-hover-corto", CUERPO_CORTO,  {"persistent": True}, False, True),
    ("franja-sin-hover",   CUERPO_LARGO,  {"persistent": True}, False, False),
    ("banner",             CUERPO_LARGO,  {"banner": True}, False, False),
]

# Hashes del render ACTUAL, generados con `_recalcular_goldens()` ANTES de tocar
# `_draw` (ver el docstring de esa función). Se commitean como fixture: si un
# caso entra o cambia en la lista, hay que regenerarlos explícitamente.
# Formato: "<sha256 de los píxeles, 32 hex>|<sha256 de los rects, 16 hex>".
GOLDEN = {
    "corto": "4bde4695b7254de8d2dd43327c3fdd9b|8c32b59bacc6320e",
    "corto-hover": "caea8b47e3b5ed92e0c1ad1bca42465c|8c32b59bacc6320e",
    "2-lineas": "757a7bd8fb07a3dddbda0a2a49de228c|8c32b59bacc6320e",
    "largo-colapsado": "127074288706af382acc0688ea1db56e|c886508c9d1760af",
    "largo-expandido": "3ead5216eecc9a124c99d5388c36f83c|7db324f12e034db6",
    "sin-app": "10991e3f61740a1eb668c123bc485047|883868078c7f85a0",
    "sin-app-corto": "aef69cec4acec76be3f1ead0e8a045fc|885001d523b11efa",
    "titulo-oculto": "2a52ebc8c36330c7e669cc3c7509ef34|688a75145344cac5",
    "titulo-oculto-largo": "094e73a94f4e0e5b3a556f86d4e9896a|0c174ae12082b1f6",
    "actions": "650ed75d76ac9f13d3cdb222f11d9b9a|bbf150d5791d6d0d",
    "actions-largo": "057a56c53cee8892755f20dbcdfb2b16|2a85c2601b973fac",
    "actions-expandido": "dc0da75656b56014d4354666e23ecb5a|020b06ba0e121748",
    "franja-hover": "30fda1e1516533cdd2a804874bbb737b|287518452fa7455d",
    "franja-hover-corto": "9dd70d332e7a6b5c57a6ce6eb43ce44b|407c9951a4a1f5a2",
    "franja-sin-hover": "127074288706af382acc0688ea1db56e|c886508c9d1760af",
    "banner": "6585663132676b895755bdeacbe7093f|c886508c9d1760af",
}


def _pixbuf(w_px, h_px, rgba):
    from gi.repository import GdkPixbuf
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, w_px, h_px)
    pix.fill(rgba)
    return pix


def _widget(cuerpo, kwargs):
    w = wp.NotificationWidget(
        app_name=kwargs.get("app_name", "xat-notifier"),
        app_icon="",
        titulo=kwargs.get("titulo", "Bienvenido Larp"),
        cuerpo=cuerpo,
        icon_path="",
        image_path="",
        accent=kwargs.get("accent", "#89b4fa"),
        hide_title=kwargs.get("hide_title", False),
        persistent=kwargs.get("persistent", False),
        actions=kwargs.get("actions"),
    )
    if kwargs.get("banner"):
        # `_draw` lee `self._image_pb` directo (la banda inferior del toast);
        # se asigna acá para no depender del camino de carga del daemon.
        w._image_pb = _pixbuf(64, 64, 0x2A2A3AFF)
    return w


def _hash_widget(cuerpo, kwargs, expanded, hover):
    w = _widget(cuerpo, kwargs)
    w._font_scale = 1.0          # la escala depende del ancho de pantalla del runner
    w._expanded = expanded
    h = w.desired_height()
    px = surface_pixels(alloc_and_draw(w, W, h, hover=hover))
    pix = hashlib.sha256()
    for row in px:
        for r, g, b, a in row:
            pix.update(bytes((r, g, b, a)))
    rects = "|".join(repr(x) for x in (
        w._expand_rect, w._image_left_rect, w._close_rect, w._action_rects))
    return "%s|%s" % (pix.hexdigest()[:32],
                      hashlib.sha256(rects.encode()).hexdigest()[:16])


def _recalcular_goldens():
    """Imprime los hashes del render ACTUAL. Solo para agregar o alterar un caso:
    se corre, se copia la salida en GOLDEN y se commitea como fixture."""
    for nombre, cuerpo, kwargs, expanded, hover in CASOS:
        print('    "%s": "%s",' % (nombre, _hash_widget(cuerpo, kwargs,
                                                        expanded, hover)))


def test_render_no_cambia_de_un_pixeles():
    """Cada configuración de toast renderiza exactamente los mismos píxeles y
    publica los mismos rects que antes del refactor de `_draw`."""
    assert GOLDEN, (
        "GOLDEN vacío: faltan los hashes de referencia. Corré "
        "`_recalcular_goldens()` y commiteá la salida."
    )
    cambios = []
    for nombre, cuerpo, kwargs, expanded, hover in CASOS:
        actual = _hash_widget(cuerpo, kwargs, expanded, hover)
        esperado = GOLDEN.get(nombre)
        if actual != esperado:
            cambios.append("%s:\n      actual   %s\n      esperado %s"
                           % (nombre, actual, esperado))
    assert not cambios, (
        "el render de `_draw` cambió respecto del golden — el refactor no debe "
        "mover un píxel ni un rect:\n  " + "\n  ".join(cambios)
    )