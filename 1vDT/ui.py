import base64

import flet as ft
import media

INK = ft.Colors.ON_SURFACE
MUTED = ft.Colors.ON_SURFACE_VARIANT
ACCENT = ft.Colors.PRIMARY
SOFT = ft.Colors.PRIMARY_CONTAINER
PAPER = ft.Colors.SURFACE_CONTAINER_LOWEST
LINE = ft.Colors.OUTLINE_VARIANT
ERROR = ft.Colors.ERROR
CARD = ft.Colors.SURFACE


def configure_page(page, index=0):
    from themes import PALETTES
    accent, soft, paper, card, ink, muted, line, _ = PALETTES[index]
    page.title = "Different Tastes"
    page.padding = 0
    page.bgcolor = PAPER
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=accent,
        color_scheme=ft.ColorScheme(primary=accent, on_primary="#FFFFFF",
            primary_container=soft, on_primary_container=ink,
            secondary=accent, secondary_container=soft, on_secondary_container=ink,
            surface=card, surface_container_lowest=paper,
            surface_container_low=paper, surface_container=soft,
            surface_container_high=soft, surface_container_highest=soft,
            on_surface=ink, on_surface_variant=muted,
            outline=line, outline_variant=line, error="#A5362F"),
        text_theme=ft.TextTheme(
            body_medium=ft.TextStyle(size=18, color=INK),
            body_large=ft.TextStyle(size=18, color=INK),
            label_large=ft.TextStyle(size=18, weight=ft.FontWeight.W_600),
        ),
        button_theme=ft.ButtonTheme(style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: ACCENT, ft.ControlState.DISABLED: LINE},
            color={ft.ControlState.DEFAULT: "#FFFFFF", ft.ControlState.DISABLED: MUTED},
            text_style=ft.TextStyle(size=18, weight=ft.FontWeight.W_600),
            shape=ft.RoundedRectangleBorder(radius=16),
        )),
        navigation_bar_theme=ft.NavigationBarTheme(
            bgcolor=CARD, indicator_color=SOFT, height=80,
            label_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
        ),
    )


def text_field(label, **kwargs):
    return ft.TextField(label=label, text_size=18, border_radius=16,
                        content_padding=16, **kwargs)


def primary(label, on_click, **kwargs):
    return ft.Button(content=label, height=56, on_click=on_click, **kwargs)


def avatar(name, size=48, avatar_path=None):
    if avatar_path:
        try:
            data = media.read_avatar(avatar_path)
            return ft.Container(
                content=ft.Image(src=base64.b64encode(data).decode(), width=size, height=size, fit=ft.BoxFit.COVER),
                width=size, height=size, border_radius=size / 2, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        except (OSError, ValueError):
            pass
    return ft.Container(
        content=ft.Text((name.strip()[:1] or "?").upper(), size=22, weight=ft.FontWeight.BOLD, color=ACCENT),
        width=size, height=size, bgcolor=SOFT, border_radius=size / 2,
        alignment=ft.Alignment.CENTER,
    )


def surface(content, padding=20):
    return ft.Container(content=content, padding=padding, bgcolor=CARD,
                        border=ft.Border.all(1, LINE), border_radius=24)


def stack(controls, spacing=16, **kwargs):
    return ft.Column(controls=controls, spacing=spacing,
                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH, **kwargs)


def sync_text(event):
    ft.context.disable_auto_update()
    if isinstance(event.data, str):
        event.control.value = event.data
