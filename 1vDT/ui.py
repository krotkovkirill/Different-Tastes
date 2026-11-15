import flet as ft

INK = "#242922"
MUTED = "#65705F"
ACCENT = "#345B42"
SOFT = "#EAF0E5"
PAPER = "#F8F8F2"
LINE = "#E2E6DB"
ERROR = "#A5362F"


def configure_page(page):
    page.title = "Different Tastes"
    page.padding = 0
    page.bgcolor = PAPER
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=ACCENT,
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
            bgcolor="#FFFFFF", indicator_color=SOFT, height=80,
            label_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
        ),
    )


def text_field(label, **kwargs):
    return ft.TextField(label=label, text_size=18, border_radius=16,
                        content_padding=16, **kwargs)


def primary(label, on_click, **kwargs):
    return ft.Button(content=label, height=56, on_click=on_click, **kwargs)


def avatar(name, size=48):
    return ft.Container(
        content=ft.Text((name.strip()[:1] or "?").upper(), size=22, weight=ft.FontWeight.BOLD, color=ACCENT),
        width=size, height=size, bgcolor=SOFT, border_radius=size / 2,
        alignment=ft.Alignment.CENTER,
    )


def surface(content, padding=20):
    return ft.Container(content=content, padding=padding, bgcolor="#FFFFFF",
                        border=ft.Border.all(1, LINE), border_radius=24)


def stack(controls, spacing=16, **kwargs):
    return ft.Column(controls=controls, spacing=spacing,
                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH, **kwargs)


def sync_text(event):
    ft.context.disable_auto_update()
    if isinstance(event.data, str):
        event.control.value = event.data
