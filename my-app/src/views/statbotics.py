"""Statbotics predictions and The Blue Alliance schedule/team lookups."""

import json

import flet as ft
import httpx2 as httpx

from api import fetch_schedule, fetch_statbotics


RED = ft.Colors.RED_800


def alliance_card(label: str, teams: list, background: str, accent: str) -> ft.Control:
    """Compact alliance panel reused by predictions and schedules."""
    return ft.Container(
        expand=True,
        padding=12,
        bgcolor=background,
        border=ft.Border.all(1, accent),
        border_radius=10,
        content=ft.Column(
            controls=[ft.Text(label, color=accent, weight=ft.FontWeight.BOLD),
                     *(ft.Text(str(team).removeprefix("frc"), color=accent) for team in teams)],
        ),
    )


def match_card(match: dict, label: str) -> ft.Control:
    """Format a TBA match response into a readable red-vs-blue row."""
    alliances = match.get("alliances", {})
    red = alliances.get("red", {}).get("team_keys", [])
    blue = alliances.get("blue", {}).get("team_keys", [])
    return ft.Container(
        padding=10,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=10,
        content=ft.Column(
            controls=[
                ft.Text(label, weight=ft.FontWeight.BOLD),
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        alliance_card("RED", red, ft.Colors.RED_50, ft.Colors.RED_800),
                        alliance_card("BLUE", blue, ft.Colors.BLUE_50, ft.Colors.BLUE_800),
                    ],
                ),
            ]
        ),
    )


def build_statbotics_view(page: ft.Page) -> ft.Control:
    """Build three simple panels: match prediction, schedules, and team metrics."""
    # Match prediction fields (commented out for now)
    # event_key = ft.TextField(label="Event key", value="2026mimid1", expand=True)
    # match_number = ft.TextField(label="Match number", value="1", keyboard_type=ft.KeyboardType.NUMBER)
    # match_type = ft.Dropdown(
    #     label="Match type",
    #     value="Qualification",
    #     options=[ft.DropdownOption(text=name) for name in ["Qualification", "Semifinal", "Final"]],
    # )
    # match_status = ft.Text()
    # prediction_results = ft.Column(spacing=10)
    # raw_toggle = ft.TextButton(content="Show raw match response")
    # raw_data = ft.Text(selectable=True, visible=False, size=12)
    # video_link = ft.TextButton(content="Open match video", visible=False)

    # Event key (needed for schedules)
    event_key = ft.TextField(label="Event key", value="2026mimid1", expand=True)

    schedule_team = ft.TextField(label="Team number", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    schedule_status = ft.Text()
    schedule_results = ft.Column(spacing=10)
    # Team information fields (commented out for now)
    # team_number = ft.TextField(label="Team number", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    # team_status = ft.Text()
    # team_results = ft.Column(spacing=8)

    # async def load_prediction():
    #     event = (event_key.value or "").strip()
    #     try:
    #         number = int(match_number.value or "0")
    #     except ValueError:
    #         number = 0
    #     if not event or number < 1:
    #         match_status.value = "Enter an event key and match number of at least 1."
    #         match_status.color = RED
    #         page.update()
    #         return
    #     if match_type.value == "Final":
    #         key = f"{event}_f1m{number}"
    #     elif match_type.value == "Semifinal":
    #         key = f"{event}_sf{number}m1"
    #     else:
    #         key = f"{event}_qm{number}"
    #     match_status.value = f"Loading Statbotics prediction for {key}…"
    #     match_status.color = ft.Colors.GREY_700
    #     page.update()
    #     try:
    #         data = await fetch_statbotics(f"match/{key}")
    #         winner = str(data.get("predicted_winner") or "Unknown").upper()
    #         red_probability = float(data.get("red_win_prob", 0.5))
    #         probability = red_probability if winner == "RED" else 1 - red_probability if winner == "BLUE" else 0.5
    #         prediction_results.controls = [
    #             ft.Row(
    #                 controls=[
    #                     ft.Container(
    #                         expand=True, padding=14, bgcolor=ft.Colors.GREY_100,
    #                         border_radius=10,
    #                         content=ft.Column(controls=[
    #                             ft.Text("Predicted winner", color=ft.Colors.GREY_700),
    #                             ft.Text(winner, size=22, weight=ft.FontWeight.BOLD, color=RED),
    #                         ]),
    #                     ),
    #                     ft.Container(
    #                         expand=True, padding=14, bgcolor=ft.Colors.GREY_100,
    #                         border_radius=10,
    #                         content=ft.Column(controls=[
    #                             ft.Text("Win probability", color=ft.Colors.GREY_700),
    #                             ft.Text(f"{probability * 100:.1f}%", size=22, weight=ft.FontWeight.BOLD),
    #                         ]),
    #                     ),
    #                 ]
    #             ),
    #             alliance_card("RED ALLIANCE", [data.get(f"red_{i}") for i in range(1, 4)], ft.Colors.RED_50, ft.Colors.RED_800),
    #             alliance_card("BLUE ALLIANCE", [data.get(f"blue_{i}") for i in range(1, 4)], ft.Colors.BLUE_50, ft.Colors.BLUE_800),
    #         ]
    #         raw_data.value = json.dumps(data, indent=2)
    #         raw_toggle.visible = True
    #         video = data.get("video")
    #         video_link.visible = bool(video)
    #         if video:
    #             video_link.url = f"https://www.youtube.com/watch?v={video}"
    #         match_status.value = "Prediction loaded."
    #         match_status.color = ft.Colors.GREEN_800
    #     except (ValueError, httpx.HTTPError) as error:
    #         prediction_results.controls.clear()
    #         match_status.value = f"Could not load prediction: {error}"
    #         match_status.color = RED
    #     page.update()

    async def load_schedule(team_search: bool):
        event = (event_key.value or "").strip()
        team = (schedule_team.value or "").strip()
        if not event:
            schedule_status.value = "Enter an event key first."
            schedule_status.color = RED
            page.update()
            return
        if team_search and not team.isdigit():
            schedule_status.value = "Enter a numeric team number."
            schedule_status.color = RED
            page.update()
            return
        endpoint = (
            f"https://www.thebluealliance.com/api/v3/team/frc{team}/event/{event}/matches"
            if team_search else f"https://www.thebluealliance.com/api/v3/event/{event}/matches"
        )
        schedule_status.value = "Loading schedule…"
        schedule_status.color = ft.Colors.GREY_700
        page.update()
        try:
            matches = await fetch_schedule(endpoint)
            matches.sort(key=lambda item: (item.get("time") or 0, item.get("match_number", 0)))
            schedule_results.controls = [
                match_card(match, _match_label(match))
                for match in matches
                if match.get("comp_level") in ("qm", "sf", "f")
            ]
            schedule_status.value = f"Loaded {len(schedule_results.controls)} matches."
            schedule_status.color = ft.Colors.GREEN_800
        except (ValueError, httpx.HTTPError) as error:
            schedule_results.controls.clear()
            schedule_status.value = f"Could not load schedule: {error}"
            schedule_status.color = RED
        page.update()

    async def load_team_schedule():
        await load_schedule(True)

    async def load_event_schedule():
        await load_schedule(False)

    schedule_button = ft.Button(content="Find Team Matches", on_click=load_team_schedule)
    event_schedule_button = ft.Button(content="Load Event Schedule", on_click=load_event_schedule)
    for button in [schedule_button, event_schedule_button]:
        button.style = ft.ButtonStyle(bgcolor=RED, color=ft.Colors.WHITE)

    return ft.Column(
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Text("Statbotics & Schedules", size=24, weight=ft.FontWeight.BOLD, color=RED),
            ft.Text(
                "Explore event schedules, and team performance. "
                "If Statbotics is temporarily unavailable, the status below will show the request error."
            ),
            # Match predictions section (commented out for now)
            # ft.Container(
            #     padding=16, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, ft.Colors.GREY_300),
            #     border_radius=12,
            #     content=ft.Column(spacing=10, controls=[
            #         ft.Text("Match prediction", size=18, weight=ft.FontWeight.BOLD),
            #         event_key,
            #         ft.Row(controls=[match_type, match_number]),
            #         prediction_button, match_status, prediction_results, video_link, raw_toggle, raw_data,
            #     ]),
            # ),
            ft.Container(
                padding=16, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=12,
                content=ft.Column(spacing=10, controls=[
                    ft.Text("Match schedules", size=18, weight=ft.FontWeight.BOLD),
                    schedule_team,
                    ft.Row(controls=[schedule_button, event_schedule_button]),
                    schedule_status, schedule_results,
                ]),
            ),
            # Team information panel (commented out for now)
            # ft.Container(
            #     padding=16, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, ft.Colors.GREY_300),
            #     border_radius=12,
            #     content=ft.Column(spacing=10, controls=[
            #         ft.Text("Team information", size=18, weight=ft.FontWeight.BOLD),
            #         ft.Row(controls=[team_number, team_button]),
            #         team_status, team_results,
            #     ]),
            # ),
        ],
    )


def _match_label(match: dict) -> str:
    """Use familiar labels for qualification, semifinal and final matches."""
    level = match.get("comp_level")
    if level == "qm":
        return f"Qualification {match.get('match_number')}"
    if level == "sf":
        return f"Semifinal {match.get('set_number')} · Match {match.get('match_number')}"
    return f"Final {match.get('match_number')}"
