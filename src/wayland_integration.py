#!/usr/bin/env python3
"""
Wayland integration for NotifyApp using wlr_layer_shell protocol.

This module provides Wayland-specific positioning for notifications using
the wlr_layer_shell_unstable_v1 protocol, which allows anchoring surfaces
to screen edges and corners.
"""

import os
import sys
import struct

from pywayland.client.display import Display
from pywayland.protocol.wayland.wl_display import WlDisplay
from pywayland.protocol.wayland.wl_registry import WlRegistry
from pywayland.protocol.wayland.wl_compositor import WlCompositor
from pywayland.protocol.wayland.wl_shm import WlShm
from pywayland.protocol.wayland.wl_output import WlOutput

from protocols.wayland.zwlr_layer_shell_v1 import (
    ZwlrLayerShellV1,
    ZwlrLayerSurfaceV1,
    Layer,
    Anchor,
    KeyboardInteractivity,
)


class WaylandLayerShell:
    """Manages Wayland layer shell integration for notifications."""

    def __init__(self):
        self.display = None
        self.registry = None
        self.layer_shell = None
        self.compositor = None
        self.shm = None
        self.output = None
        self._globals = {}

    def connect(self):
        """Connect to the Wayland display."""
        try:
            self.display = Display()
            self.display.connect()
            self.registry = self.display.get_registry()
            self.registry.dispatcher['global'] = self._handle_global
            self.registry.dispatcher['global_remove'] = self._handle_global_remove
            self.display.roundtrip()
            return True
        except Exception as e:
            print(f"Wayland connection failed: {e}", file=sys.stderr)
            return False

    def _handle_global(self, registry, name, interface, version):
        """Handle global interface announcements."""
        self._globals[interface] = name
        if interface == 'zwlr_layer_shell_v1':
            self.layer_shell = self.registry.bind(name, ZwlrLayerShellV1, min(version, 5))
        elif interface == 'wl_compositor':
            self.compositor = self.registry.bind(name, WlCompositor, min(version, 4))
        elif interface == 'wl_shm':
            self.shm = self.registry.bind(name, WlShm, min(version, 1))
        elif interface == 'wl_output':
            if self.output is None:
                self.output = self.registry.bind(name, WlOutput, min(version, 4))

    def _handle_global_remove(self, registry, name):
        """Handle global interface removal."""
        pass

    def create_layer_surface(self, surface, layer=Layer.OVERLAY, anchor=Anchor.TOP_RIGHT,
                             width=320, height=200, margin=16, namespace="notify-app"):
        """Create a layer surface for a notification.

        Args:
            surface: WlSurface to use
            layer: Layer to place the surface in (Layer.OVERLAY, Layer.TOP, etc.)
            anchor: Corner to anchor to (Anchor.TOP_RIGHT, Anchor.BOTTOM_LEFT, etc.)
            width: Surface width in pixels
            height: Surface height in pixels
            margin: Margin from the edge in pixels
            namespace: Application namespace string

        Returns:
            ZwlrLayerSurfaceV1 object or None if layer shell is not available
        """
        if not self.layer_shell:
            return None

        layer_surface = self.layer_shell.get_layer_surface(
            surface, self.output, layer, namespace
        )

        layer_surface.set_size(width, height)
        layer_surface.set_anchor(anchor)
        layer_surface.set_margin(0, margin, 0, 0)
        layer_surface.set_exclusive_zone(-1)
        layer_surface.set_keyboard_interactivity(KeyboardInteractivity.NONE)

        return layer_surface

    def is_available(self):
        """Check if Wayland layer shell is available."""
        return self.layer_shell is not None

    def disconnect(self):
        """Disconnect from the Wayland display."""
        if self.display:
            self.display.disconnect()
            self.display = None


def is_wayland_session():
    """Check if running in a Wayland session."""
    return os.environ.get('WAYLAND_DISPLAY') is not None or \
           os.environ.get('XDG_SESSION_TYPE') == 'wayland'


def get_anchor_for_corner(corner):
    """Convert corner string to Anchor enum.

    Args:
        corner: One of 'top-right', 'top-left', 'bottom-right', 'bottom-left'

    Returns:
        Anchor enum value
    """
    anchors = {
        'top-right': Anchor.TOP_RIGHT,
        'top-left': Anchor.TOP_LEFT,
        'bottom-right': Anchor.BOTTOM_RIGHT,
        'bottom-left': Anchor.BOTTOM_LEFT,
    }
    return anchors.get(corner, Anchor.TOP_RIGHT)
