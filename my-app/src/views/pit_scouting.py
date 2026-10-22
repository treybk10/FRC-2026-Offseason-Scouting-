"""Pit scouting form for recording a robot's design at the same event."""

import flet as ft
import httpx2 as httpx

from api import append_to_google_sheet


PIT_RANGE = "'Pit Scouting'!A1"
PIT_HEADERS = [
    "Team Number",
    "Robot Name",
    "Shooter Type",
    "Climber",
    "Drivetrain",
    "Auto Start Locations",
    "Fun Features",
    "Additional Notes",
]
RED = ft.Colors.RED_800


def field(label: str, **kwargs) -> ft.TextField:
    """Create a rounded, lightly filled input consistent with match scouting."""
    return ft.TextField(
        label=label,
        filled=True,
        fill_color=ft.Colors.WHITE,
        focused_bgcolor=ft.Colors.WHITE,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                side=ft.BorderSide(color=ft.Colors.GREY_400),
                border_radius=ft.BorderRadius.all(12),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                side=ft.BorderSide(color=RED, width=2),
                border_radius=ft.BorderRadius.all(12),
            ),
        },
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        **kwargs,
    )


def build_pit_scouting_view(page: ft.Page) -> ft.Control:
    """Build the pit form and save each robot record to its own sheet tab."""
    team_number = field("Team number", hint_text="For example: 1506", keyboard_type=ft.KeyboardType.NUMBER)
    robot_name = field("Robot name (optional)", hint_text="If they have one")
    shooter_type = ft.Dropdown(
        label="Shooter type",
        options=[
            ft.DropdownOption(text=name)
            for name in [
                "Single Dumper",
                "Multi-Wide Dumper",
                "Single Turret",
                "Dual Turret",
                "Other",
                "N/A",
            ]
        ],
        value="N/A",
        filled=True,
        fill_color=ft.Colors.WHITE,
        height=64,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                side=ft.BorderSide(color=ft.Colors.GREY_400),
                border_radius=ft.BorderRadius.all(12),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                side=ft.BorderSide(color=RED, width=2),
                border_radius=ft.BorderRadius.all(12),
            ),
        },
    )
    climber = ft.Dropdown(
        label="Climber",
        options=[
            ft.DropdownOption(text=choice)
            for choice in ["No climber", "Single-stage", "Multi-stage", "Other", "N/A"]
        ],
        value="N/A",
        filled=True,
        fill_color=ft.Colors.WHITE,
        height=64,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                side=ft.BorderSide(color=ft.Colors.GREY_400),
                border_radius=ft.BorderRadius.all(12),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                side=ft.BorderSide(color=RED, width=2),
                border_radius=ft.BorderRadius.all(12),
            ),
        },
    )
    drivetrain = ft.Dropdown(
        label="Drivetrain",
        options=[
            ft.DropdownOption(text=choice)
            for choice in ["Swerve", "Tank / differential", "Mecanum", "Other", "N/A"]
        ],
        value="N/A",
        filled=True,
        fill_color=ft.Colors.WHITE,
        height=64,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                side=ft.BorderSide(color=ft.Colors.GREY_400),
                border_radius=ft.BorderRadius.all(12),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                side=ft.BorderSide(color=RED, width=2),
                border_radius=ft.BorderRadius.all(12),
            ),
        },
    )
    auto_locations = [
        ft.Checkbox(label=location, active_color=RED)
        for location in ["Left", "Center", "Right"]
    ]
    fun_features = field(
        "Fun features",
        hint_text="What makes this robot memorable?",
        multiline=True,
        min_lines=2,
        max_lines=4,
    )
    additional_notes = field(
        "Additional pit notes (optional)",
        multiline=True,
        min_lines=2,
        max_lines=4,
    )
    save_button = ft.Button(content="Save Pit Scouting")
    save_button.style = ft.ButtonStyle(bgcolor=RED, color=ft.Colors.WHITE)
    status = ft.Text(visible=False)

    form = ft.Container(
        padding=18,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=16,
        content=ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Text("Robot details", size=21, weight=ft.FontWeight.BOLD, color=RED),
                team_number,
                robot_name,
                shooter_type,
                climber,
                drivetrain,
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    bgcolor=ft.Colors.GREY_100,
                    border=ft.Border.all(1, ft.Colors.GREY_200),
                    border_radius=12,
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text("Auto start locations", weight=ft.FontWeight.W_600),
                            ft.Text("Select every position the robot can start from.", color=ft.Colors.GREY_700),
                            *auto_locations,
                        ],
                    ),
                ),
                fun_features,
                additional_notes,
                save_button,
                status,
            ],
        ),
    )

    async def save_pit_scouting():
        """Validate the team number and append the robot profile to Google Sheets."""
        number = (team_number.value or "").strip()
        if not number.isdigit():
            status.value = "Enter a valid numeric team number before saving."
            status.color = ft.Colors.RED_800
            status.visible = True
            page.update()
            return

        locations = [box.label for box in auto_locations if box.value]
        row = [
            number,
            robot_name.value.strip() or "N/A",
            shooter_type.value or "N/A",
            climber.value or "N/A",
            drivetrain.value or "N/A",
            ", ".join(locations) or "N/A",
            fun_features.value.strip() or "N/A",
            additional_notes.value.strip() or "N/A",
        ]
        save_button.disabled = True
        status.value = "Saving pit scouting…"
        status.color = ft.Colors.GREY_700
        status.visible = True
        page.update()
        try:
            await append_to_google_sheet(row, range_name=PIT_RANGE, headers=PIT_HEADERS)
            status.value = f"Pit scouting saved for team {number}."
            status.color = ft.Colors.GREEN_800
        except (ValueError, httpx.HTTPError, ImportError) as error:
            status.value = f"Could not save pit scouting: {error}"
            status.color = ft.Colors.RED_800
        finally:
            save_button.disabled = False
            status.visible = True
            page.update()

    save_button.on_click = save_pit_scouting

    return ft.ResponsiveRow(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Container(
                col={"xs": 12, "sm": 12, "md": 10, "lg": 8, "xl": 7, "xxl": 7},
                content=ft.Column(
                    spacing=14,
                    controls=[
                        ft.Container(
                            padding=14,
                            bgcolor=ft.Colors.GREY_200,
                            border_radius=14,
                            content=ft.Text(
                                "Capture the robot's setup and the details you notice in the pits. "
                                "Unanswered fields are saved as N/A.",
                                color=ft.Colors.GREY_900,
                            ),
                        ),
                        form,
                        ft.Container(height=28),
                    ],
                ),
            )
        ],
    )
