"""Identidad de la app — fuente ÚNICA del nombre.

Antes "Verdantis" estaba inline en 4 módulos y el tuple de GetServerInformation
repetía el nombre como vendor. Regla: name = el server, vendor = quien lo hace
(spec freedesktop). Cualquier display de nombre sale de APP_NAME; los
identificadores técnicos (layer namespace, prefijo de logs) de APP_ID.
VERSION vive en verdantis_daemon.py (la usa GetServerInformation)."""

APP_NAME = "Verdantis"   # nombre display: DBus server name, títulos de ventana
APP_ID = "verdantis"     # identificador técnico: layer-shell namespace, logs
VENDOR = "MoriNo23"      # vendor del server (spec: quien lo hace, no el nombre)
