import base64

import flet as ft

THEME_STORAGE_KEY = "different_tastes.theme.v1"
PALETTES = (
    ("#896600", "#FFF0AD", "#FFFBEA", "#FFFEF6", "#332B14", "#756A48", "#E8DCA6", "#FFE600"),
    ("#AB326B", "#FFDDEC", "#FFF5FA", "#FFFBFD", "#422133", "#806371", "#EED3DF", "#FF92C8"),
    ("#3158D7", "#DFE7FF", "#F3F6FF", "#FDFDFF", "#1C284A", "#657092", "#D2DCF4", "#1545FF"),
    ("#8150BA", "#EDE1FF", "#FFF8F2", "#FFFDFA", "#3D294B", "#7D6587", "#E6D8ED", "#B678F3"),
    ("#BC2C39", "#FFDFDF", "#FFF5F1", "#FFFCFA", "#48252A", "#89666A", "#EED4D4", "#F12636"),
)


def emoji_source(index):
    fill = PALETTES[index][7]
    definitions = ""
    if index == 3:
        definitions = '<defs><linearGradient id="r"><stop stop-color="#ff635e"/><stop offset=".25" stop-color="#ffe941"/><stop offset=".5" stop-color="#67eb67"/><stop offset=".75" stop-color="#52baff"/><stop offset="1" stop-color="#ca69ff"/></linearGradient></defs>'
        fill = "url(#r)"
    eyes = '<ellipse cx="22" cy="25" rx="3" ry="5"/><ellipse cx="42" cy="25" rx="3" ry="5"/>'
    mouth = '<path d="M17 38 Q32 54 47 38" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>'
    if index == 1:
        eyes = '<ellipse cx="21" cy="25" rx="7" ry="10"/><ellipse cx="43" cy="25" rx="7" ry="10"/><g fill="white"><ellipse cx="19" cy="21" rx="3" ry="4"/><ellipse cx="41" cy="21" rx="3" ry="4"/></g><g fill="#F95E9E"><ellipse cx="15" cy="39" rx="5" ry="3"/><ellipse cx="49" cy="39" rx="5" ry="3"/></g>'
        mouth = '<path d="M27 41 Q32 47 37 41" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>'
    if index == 4:
        eyes = '<path d="M17 20 L27 27 L19 29 Z M47 20 L37 27 L45 29 Z"/>'
        mouth = '<path d="M14 36 Q32 45 50 36 Q44 56 32 54 Q20 54 14 36Z"/><path d="M18 39 Q32 45 46 39 L43 44 Q32 49 21 44Z" fill="white"/>'
    ink = "#FFFFFF" if index == 2 else "#242122"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">{definitions}<circle cx="32" cy="32" r="30" fill="{fill}"/><g fill="{ink}" color="{ink}">{eyes}{mouth}</g></svg>'
    return base64.b64encode(svg.encode()).decode()


class ThemeSwitch(ft.Stack):
    def __init__(self, on_change):
        self.slider = ft.Slider(min=0, max=4, divisions=4, value=0, width=112, height=44,
            padding=16, active_color="transparent", inactive_color="transparent",
            thumb_color="transparent", overlay_color="transparent", on_change=on_change,
            tooltip="Тема оформления")
        self.track = ft.Container(left=0, right=0, top=7, height=30, border_radius=18,
                                  bgcolor=ft.Colors.PRIMARY_CONTAINER)
        dots = [ft.Container(left=12 + i * 20, top=18, width=8, height=8, border_radius=4,
                             bgcolor=p[7]) for i, p in enumerate(PALETTES)]
        dots[3].gradient = ft.LinearGradient(colors=["#FF7979", "#F7E750", "#62DCAF", "#9482F5"])
        self.thumb = ft.Container(content=ft.Image(src=emoji_source(0), width=28, height=28),
            left=0, top=6, width=32, height=32, padding=2, bgcolor="#FFFFFF", border_radius=18,
            animate_position=ft.Animation(140, ft.AnimationCurve.EASE_OUT))
        decoration = ft.TransparentPointer(content=ft.Stack(controls=[self.track, *dots, self.thumb], width=112, height=44))
        super().__init__(controls=[self.slider, decoration], width=112, height=44)

    def select(self, index):
        self.slider.value = index
        self.thumb.left = index * 20
        self.thumb.content.src = emoji_source(index)
        self.track.gradient = (ft.LinearGradient(colors=["#FFD5C9", "#FFF1AC", "#D3F7D8", "#E2D5FF"])
                               if index == 3 else None)
