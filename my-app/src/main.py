"""Application entry point, shared Team 1506 banner, and screen navigation."""

import logging

import flet as ft

from views.pit_scouting import build_pit_scouting_view
from views.rankings import build_rankings_view
from views.scouting import build_scouting_view
from views.statbotics import build_statbotics_view

LOG_LEVEL = logging.INFO
logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("app").setLevel(LOG_LEVEL)


SCREEN_NAMES = ["Match Scouting", "Pit Scouting", "Current Rankings", "Statbotics"]



def main(page: ft.Page):
    """Set the shared theme and mount the scouting, rankings, and Statbotics screens."""
    page.title = "Metal Muscle Scouting"
    page.padding = 16
    page.spacing = 12
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.bgcolor = ft.Colors.GREY_100
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.RED_800,
            on_primary=ft.Colors.WHITE,
            primary_container=ft.Colors.RED_100,
            on_primary_container=ft.Colors.GREY_900,
            secondary=ft.Colors.GREY_800,
            on_secondary=ft.Colors.WHITE,
            secondary_container=ft.Colors.GREY_200,
            on_secondary_container=ft.Colors.GREY_900,
            tertiary=ft.Colors.RED_900,
            on_tertiary=ft.Colors.WHITE,
            surface=ft.Colors.WHITE,
            on_surface=ft.Colors.GREY_900,
            outline=ft.Colors.GREY_600,
            outline_variant=ft.Colors.GREY_300,
        )
    )

    # Build each screen once so navigating away does not discard form state.
    screens = [
        build_scouting_view(page),
        build_pit_scouting_view(page),
        build_rankings_view(page),
        build_statbotics_view(page),
    ]
    for screen in screens[1:]:
        screen.visible = False

    # Recreate the selected page's title buttons with the active screen highlighted.
    nav_row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, wrap=True)

    def select_screen(index: int):
        for screen_index, screen in enumerate(screens):
            screen.visible = screen_index == index
        for button_index, button in enumerate(nav_row.controls):
            button.style = ft.ButtonStyle(
                color=ft.Colors.RED_800 if button_index == index else ft.Colors.GREY_700
            )
        page.update()

    for index, name in enumerate(SCREEN_NAMES):
        nav_row.controls.append(
            ft.TextButton(
                content=name,
                on_click=lambda e, i=index: select_screen(i),
                style=ft.ButtonStyle(color=ft.Colors.RED_800 if index == 0 else ft.Colors.GREY_700),
            )
        )

    # The header repeats across screens and uses the logo asset supplied by the user.
    header = ft.Container(
        padding=14,
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.all(2, ft.Colors.RED_800),
        border_radius=14,
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Image(
                    src="1506-logo.jpg",
                    width=86,
                    height=86,
                    fit=ft.BoxFit.CONTAIN,
                    semantics_label="FRC Team 1506 Metal Muscle logo",
                ),
                ft.Column(
                    expand=True,
                    controls=[
                        ft.Text("FRC TEAM 1506", color=ft.Colors.RED_300, weight=ft.FontWeight.BOLD),
                        ft.Text("Metal Muscle Scouting", color=ft.Colors.WHITE, size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("Match scouting, event data, and team insights.", color=ft.Colors.GREY_300),
                    ],
                ),
            ],
        ),
    )
    page.add(header, nav_row, *screens)


ft.run(main)
