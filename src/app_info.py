"""Identidad de la app — fuente ÚNICA del nombre.

Antes "Verdantis" estaba inline en 4 módulos y el tuple de GetServerInformation
repetía el nombre como vendor. Regla: name = el server, vendor = quien lo hace
(spec freedesktop). Cualquier display de nombre sale de APP_NAME; los
identificadores técnicos (layer namespace, prefijo de logs) de APP_ID.
VERSION vive en verdantis_daemon.py (la usa GetServerInformation)."""

APP_NAME = "Verdantis"   # nombre display: DBus server name, títulos de ventana
APP_ID = "verdantis"     # identificador técnico: layer-shell namespace, logs
VENDOR = "MoriNo23"      # vendor del server (spec: quien lo hace, no el nombre)

# Acento de identidad (fuente ÚNICA): lo heredan el daemon, el replay, el
# one-shot y los defaults de ambos backends. Antes el CLI decía #89b4fa y el
# producto real usaba #80cbc4 — un acento partido en dos.
DEFAULT_ACCENT = "#80cbc4"

# Urgency 2 (critical, spec 1.2): no expira y se diferencia en la pila con un
# rail de este color. Rojo suave de la misma paleta que el acento de identidad.
CRITICAL_ACCENT = "#ef9a9a"


def accent_for(urgency, requested=None):
    """El acento de un critical no lo puede sobrescribir la app que lo envía."""
    return CRITICAL_ACCENT if urgency == 2 else (requested or DEFAULT_ACCENT)
