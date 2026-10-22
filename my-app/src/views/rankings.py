"""Event rankings screen backed by The Blue Alliance."""

import httpx2 as httpx
import flet as ft

from api import fetch_rankings


async def _load(event_field: ft.TextField, status: ft.Text, results: ft.Column, page: ft.Page):
    """Fetch rankings and render each team as a compact standings card."""
    event = (event_field.value or "").strip()
    if not event:
        status.value = "Enter an event key first."
        status.color = ft.Colors.RED_800
        page.update()
        return
    status.value = "Loading event rankings…"
    status.color = ft.Colors.GREY_700
    page.update()
    try:
        ranking_rows = await fetch_rankings(event)
        results.controls = [
            ft.Container(
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                content=ft.Row(
                    wrap=True,
                    controls=[
                        ft.Text(f"#{row.get('rank', '—')}", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800),
                        ft.Text(f"Team {str(row.get('team_key', '')).removeprefix('frc')}", weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"W {row.get('record', {}).get('wins', 0)}  ·  "
                            f"L {row.get('record', {}).get('losses', 0)}  ·  "
                            f"T {row.get('record', {}).get('ties', 0)}"
                        ),
                        ft.Text(f"Played {row.get('matches_played', 0)}  ·  DQ {row.get('dq', 0)}"),
                    ],
                ),
            )
            for row in ranking_rows
        ]
        status.value = f"Loaded {len(ranking_rows)} teams for {event.upper()}."
        status.color = ft.Colors.GREEN_800
    except (ValueError, httpx.HTTPError) as error:
        results.controls.clear()
        status.value = f"Could not load rankings: {error}"
        status.color = ft.Colors.RED_800
    page.update()


def build_rankings_view(page: ft.Page) -> ft.Control:
    """Create the event input and dynamic ranking results."""
    event_field = ft.TextField(label="Event key", value="2026mibg", expand=True)
    status = ft.Text()
    results = ft.Column(spacing=8)
    load_button = ft.Button(content="Load Rankings")
    load_button.style = ft.ButtonStyle(bgcolor=ft.Colors.RED_800, color=ft.Colors.WHITE)

    async def load():
        await _load(event_field, status, results, page)

    load_button.on_click = load

    return ft.Column(
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Text("Event Rankings", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800),
            ft.Text("See the current qualification standings for an event."),
            ft.Row(controls=[event_field, load_button]),
            status,
            results,
        ],
    )
