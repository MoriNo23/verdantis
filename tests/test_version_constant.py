"""Verify VERSION constant integration in GetServerInformation.

Runs headless (offscreen) — does NOT touch the live DBus daemon.
Exercises the real NotificationDaemon._handle_method_call with a mock
invocation so we confirm GetServerInformation returns (name, vendor,
VERSION, spec_version) and that VERSION is single-source-of-truth.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
# sys.path propio: este archivo debe poder correr aislado (antes solo pasaba
# como parte de la suite completa porque OTRO test insertaba src/ antes).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import re
import wayland_popup  # noqa: F401  (fija Gdk 3.0 antes de que gi cargue 4.0)
import verdantis_daemon as v
from verdantis_daemon import NotificationDaemon, VERSION


SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class _MockInvocation:
    """Captures return_value() instead of calling into the real bus."""
    def __init__(self):
        self.result = None

    def return_value(self, variant):
        self.result = variant


def test_version_constant_wellformed():
    assert isinstance(VERSION, str)
    assert SEMVER.match(VERSION), f"VERSION '{VERSION}' is not semver MAJOR.MINOR.PATCH"


def test_get_server_information_uses_version():
    d = NotificationDaemon()
    inv = _MockInvocation()
    d._handle_method_call(
        conn=None, sender=":1.1", obj_path="/org/freedesktop/Notifications",
        iface_name="org.freedesktop.Notifications",
        method_name="GetServerInformation", params=None, invocation=inv,
    )
    assert inv.result is not None, "GetServerInformation returned nothing"
    # Variant signature for GetServerInformation is (ssss)
    (name, vendor, version, spec_version) = inv.result.unpack()
    assert name == "Verdantis"
    assert vendor == "MoriNo23", (
        "vendor debe identificar al autor, no repetir el nombre del server "
        "(spec freedesktop: name=server, vendor=quien lo hace)"
    )
    assert version == VERSION, "GetServerInformation version must equal the VERSION constant"
    assert spec_version == "1.2"
    assert SEMVER.match(version)


def test_version_is_single_source():
    # The DBus method must reference the module-level VERSION, not an inline literal.
    src = open("src/verdantis_daemon.py", encoding="utf-8").read()
    assert 'VERSION, "1.2"' in src, "GetServerInformation must interpolate VERSION"
    # No stray inline version literal left in the GetServerInformation tuple.
    assert '"0.1.0"' not in src, "stale inline version literal must be gone"


def test_app_name_is_single_source():
    """El nombre "Verdantis" NO puede estar inline en GetServerInformation ni
    repetido en otros módulos: vive en app_info.APP_NAME y se importa."""
    src = open("src/verdantis_daemon.py", encoding="utf-8").read()
    assert 'APP_NAME, VENDOR' in src, (
        "GetServerInformation debe interpolar APP_NAME/VENDOR de app_info, "
        "no literales inline"
    )
    popup_src = open("src/wayland_popup.py", encoding="utf-8").read()
    assert 'set_title(APP_NAME)' in popup_src, (
        "window.set_title debe usar APP_NAME de app_info (single source)"
    )
