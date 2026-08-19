---
name: wayland-hud-fullstack
description: End-to-end production architecture blueprint for interactive Wayland HUD cards on KDE Plasma 6 integrating Python 3.13, GTK3, LayerShell, Cairo, Pango, and Gdk.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [fullstack, wayland, kde-plasma-6, gtk3, gtk-layer-shell, cairo, pango]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [desktop-hud, wayland-overlay, production-blueprint, complete-stack]
    triggers:
      - "when creating full production-ready Wayland desktop HUD widgets"
      - "when assembling the complete GTK3 + LayerShell + Cairo + Pango stack"
---

# SKILL: Full-Stack Wayland Desktop HUD Integration Blueprint

## 1. When to Use / Triggers
Activate this skill when orchestrating or synthesizing all individual skills into a full desktop application:
- An enterprise-grade, floating, glassmorphism HUD notification/widget for KDE Plasma 6 Wayland.
- Real-time V-Sync animations via Cairo wipe shaders.
- Bundled Manrope typography with wrapping and truncation.
- Interactive close pill with responsive hover/click feedback.

## 2. Execution Blueprint
Run the bundled application `app.py` directly within your Python 3.13 virtual environment:
```bash
python app.py
```
