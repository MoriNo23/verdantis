from __future__ import annotations

import enum

from pywayland.protocol_core import (
    Argument,
    ArgumentType,
    Global,
    Interface,
    Proxy,
    Resource,
)

from .wl_output import WlOutput
from .wl_surface import WlSurface


class ZwlrLayerShellV1(Interface):
    """create surfaces that are layers of the desktop

    Clients can use this interface to assign the surface_layer role to
    wl_surfaces. Such surfaces are assigned to a "layer" of the output and
    rendered with a defined z-depth respective to each other. They may also be
    anchored to the edges and corners of a screen and specify input handling
    semantics. This interface should be suitable for the implementation of
    many desktop shell components, and a broad number of other applications
    that interact with the desktop.
    """

    name = "zwlr_layer_shell_v1"
    version = 5

    @classmethod
    def get_layer_surface(cls, surface: WlSurface, output: WlOutput | None, layer: int, namespace: str) -> ZwlrLayerSurfaceV1:
        """Create a layer surface
        Create a layer surface that is assigned to a layer of the output.
        """
        id = ZwlrLayerSurfaceV1(cls._ptr, surface, output, layer, namespace)
        cls._ptr.destroy = cls._ptr.destroy
        return id

    @classmethod
    def destroy(cls):
        """Destroy the layer shell
        """
        cls._ptr.destroy()


class ZwlrLayerSurfaceV1(Interface):
    """Layer surface

    A layer surface is a wl_surface that has been assigned to a layer.
    """

    name = "zwlr_layer_surface_v1"
    version = 5

    def set_size(self, width: int, height: int):
        """Set the size of the layer surface
        """
        self._ptr.set_size(width, height)

    def set_anchor(self, anchor: int):
        """Set the anchor of the layer surface
        """
        self._ptr.set_anchor(anchor)

    def set_exclusive_zone(self, zone: int):
        """Set the exclusive zone of the layer surface
        """
        self._ptr.set_exclusive_zone(zone)

    def set_margin(self, top: int, right: int, bottom: int, left: int):
        """Set the margin of the layer surface
        """
        self._ptr.set_margin(top, right, bottom, left)

    def set_keyboard_interactivity(self, keyboard_interactivity: int):
        """Set the keyboard interactivity of the layer surface
        """
        self._ptr.set_keyboard_interactivity(keyboard_interactivity)

    def get_popup(self, popup):
        """Get a popup for the layer surface
        """
        self._ptr.get_popup(popup)

    def ack_configure(self, serial: int):
        """Acknowledge a configure event
        """
        self._ptr.ack_configure(serial)

    def destroy(self):
        """Destroy the layer surface
        """
        self._ptr.destroy()

    def set_layer(self, layer: int):
        """Set the layer of the layer surface
        """
        self._ptr.set_layer(layer)

    def set_exclusive_edge(self, edge: int):
        """Set the exclusive edge of the layer surface
        """
        self._ptr.set_exclusive_edge(edge)


class Layer(int):
    """Layer enum"""
    BACKGROUND = 0
    BOTTOM = 1
    TOP = 2
    OVERLAY = 3


class Anchor(int):
    """Anchor enum"""
    TOP = 1
    BOTTOM = 2
    LEFT = 4
    RIGHT = 8
    TOP_LEFT = TOP | LEFT
    TOP_RIGHT = TOP | RIGHT
    BOTTOM_LEFT = BOTTOM | LEFT
    BOTTOM_RIGHT = BOTTOM | RIGHT


class KeyboardInteractivity(int):
    """Keyboard interactivity enum"""
    NONE = 0
    FOCUS = 1
    ALL = 2
