"""Match scouting screen with live match lookup and Google Sheets submission."""

import flet as ft
import httpx2 as httpx
import socket

from api import append_to_google_sheet, fetch_match, fetch_scouted_teams_prioritized
from storage import load_pending_matches, save_pending_matches


async def check_internet_connectivity(timeout: float = 3.0) -> bool:
    """Check if the device has internet connectivity by attempting a DNS resolve.

    Returns True if connectivity is available, False if offline.
    Uses a quick DNS check to avoid long timeouts.
    """
    try:
        # Try resolving a well-known hostname with a short timeout
        socket.create_connection(("1.1.1.1", 53), timeout=timeout)
        return True
    except (OSError, socket.timeout):
        return False


AUTO_STARTING = ["Left", "Right", "Center"]
SHOOTER_TYPES = ["Single Dumper", "Multi-Wide Dumper", "Single Turret", "Dual Turret"]
HOPPER_SIZES = ["Small (<30)", "Medium (31-60)", "Large (>61)"]
RATINGS = ["Extremely Slow", "Below Average", "Average", "Above Average", "Super Fast"]
RED = ft.Colors.RED_800
INK = ft.Colors.GREY_900
MUTED = ft.Colors.GREY_700


def styled_field(label: str, **kwargs) -> ft.TextField:
    """Create a consistent, roomy text input for the scouting form."""
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
        cursor_color=RED,
        **kwargs,
    )


def styled_dropdown(label: str, options: list[ft.DropdownOption], **kwargs) -> ft.Dropdown:
    """Match dropdown borders and padding to the rounded text inputs."""
    return ft.Dropdown(
        label=label,
        options=options,
        filled=True,
        fill_color=ft.Colors.WHITE,
        text_size=16,
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
        **kwargs,
    )


def styled_switch(label: str, value: bool = False) -> ft.Switch:
    """Use a consistent red active state on all yes/no questions."""
    return ft.Switch(
        label=label,
        value=value,
        active_color=RED,
        active_track_color=ft.Colors.RED_200,
        inactive_track_color=ft.Colors.GREY_300,
    )


def switch_tile(control: ft.Switch) -> ft.Container:
    """Place a toggle on a soft grey tile so questions are easy to spot and tap."""
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=5),
        bgcolor=ft.Colors.GREY_100,
        border=ft.Border.all(1, ft.Colors.GREY_200),
        border_radius=12,
        content=control,
    )


def section(title: str, controls: list[ft.Control]) -> ft.Container:
    """Give each part of the long form a clear, welcoming card."""
    return ft.Container(
        padding=18,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=16,
        content=ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Text(title, size=21, weight=ft.FontWeight.BOLD, color=RED),
                *controls,
            ],
        ),
    )


def alliance_card(title: str, teams: list[str], bg: str, accent: str) -> ft.Control:
    """Show preset alliance members in their traditional red/blue colors."""
    return ft.Container(
        expand=True,
        padding=16,
        bgcolor=bg,
        border=ft.Border.all(2, accent),
        border_radius=14,
        content=ft.Column(
            spacing=5,
            controls=[
                ft.Text(title, color=accent, weight=ft.FontWeight.BOLD, size=15),
                *(ft.Text(team, color=accent, weight=ft.FontWeight.BOLD, size=20) for team in teams),
            ],
        ),
    )


def build_scouting_view(page: ft.Page) -> ft.Control:
    """Build match scouting with persistent offline upload support."""
    # Build the page-level service explicitly; its API resolves through the
    # page context when the upload handlers run.
    preferences = ft.SharedPreferences()
    page._services.register_service(preferences)
    state = {
        "teams_found": False,
        # "predictions_ok": False,
        # "red_prediction": None,
        # "blue_prediction": None,
        "syncing_queue": False,
    }
    # Match identification and alliance selection.
    event_key = styled_field("Event key", value="2026mibg", hint_text="Example: 2026mibg")
    scouter_name = styled_field("Scouter name", hint_text="Your name")
    match_number = styled_field(
        "Qualification match number", value="1", keyboard_type=ft.KeyboardType.NUMBER
    )
    match_status = ft.Text(visible=False, color=RED)
    find_button = ft.Button(content="Find Teams")
    alliance_row = ft.Row(visible=False, spacing=12)
    team_picker = styled_dropdown(
        label="Select the team you are scouting",
        options=[],
        visible=False,
        height=64,
    )
    # Keep the team picker aligned with the left edge of the scouting form.
    team_picker_row = ft.Column(visible=False, controls=[team_picker])

    # Priority teams: teams in this match that haven't been scouted yet.
    priority_text = ft.Text(visible=False, size=16, weight=ft.FontWeight.BOLD, color=RED)
    priority_row = ft.Column(visible=False, controls=[priority_text])

    # Offline mode: manual team entry field (shown when offline)
    offline_team_row = ft.Column(
        visible=False,
        controls=[
            ft.Text("Offline Mode: Enter the team number you are scouting", color=ft.Colors.ORANGE_800, size=16, weight=ft.FontWeight.BOLD),
            styled_field("Team number", hint_text="e.g. 1506"),
            ft.Text("Enter the single team you are scouting.", color=MUTED, size=12),
        ]
    )

    # Match predictions are paused for now; keep this block for later.
    # predictions_toggle = styled_switch("Enter optional score predictions")
    # prediction_notice = ft.Text(
    #     "Predictions are just for fun. Enter both scores to unlock scouting when this is on.",
    #     color=MUTED,
    # )
    # red_prediction = styled_field("Red predicted score", value="0", keyboard_type=ft.KeyboardType.NUMBER)
    # blue_prediction = styled_field("Blue predicted score", value="0", keyboard_type=ft.KeyboardType.NUMBER)
    # prediction_status = ft.Text()
    # submit_prediction_button = ft.Button(content="Save Predictions")
    # prediction_box = ft.Column(
    #     visible=False,
    #     controls=[
    #         ft.Row(
    #             controls=[
    #                 ft.Column(expand=1, controls=[red_prediction]),
    #                 ft.Column(expand=1, controls=[blue_prediction]),
    #             ]
    #         ),
    #         submit_prediction_button,
    #         prediction_status,
    #     ],
    # )

    # Autonomous observations.
    auto_start = styled_dropdown(
        label="Auto start position",
        options=[ft.DropdownOption(text=location) for location in AUTO_STARTING],
        height=64,
    )
    center_scored = styled_switch("Scored fuel from center?")
    center_intaked = styled_switch("Collected extra fuel in auto?")
    center_controls = ft.Column(
        visible=False, controls=[switch_tile(center_scored), switch_tile(center_intaked)]
    )
    neutral_passes = styled_field(
        "Passes through the neutral zone", value="0", keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
    )
    subtract_pass_button = ft.IconButton(
        icon=ft.Icons.REMOVE, icon_color=RED, tooltip="Subtract one"
    )
    add_pass_button = ft.IconButton(
        icon=ft.Icons.ADD, icon_color=RED, tooltip="Add one"
    )
    neutral_passes_stepper = ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(expand=True, controls=[neutral_passes]),
            ft.Column(
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[add_pass_button, subtract_pass_button],
            ),
        ],
    )
    auto_climb = styled_switch("Climbed during auto?")

    # Tele-op shooting and intake performance.
    scored_fuel = styled_switch("Did the robot score fuel?", value=True)
    shooter_type = styled_dropdown(
        label="Shooter type", options=[ft.DropdownOption(text=x) for x in SHOOTER_TYPES]
    )
    hopper_size = styled_dropdown(
        label="Hopper capacity", options=[ft.DropdownOption(text=x) for x in HOPPER_SIZES], value=HOPPER_SIZES[1]
    )
    accuracy_value = ft.Text("80%", color=RED, weight=ft.FontWeight.BOLD)
    accuracy_header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Robot accuracy", weight=ft.FontWeight.W_600),
            accuracy_value,
        ],
    )
    accuracy = ft.Slider(
        min=0, max=100, value=80, divisions=20,
        active_color=RED, thumb_color=RED,
    )
    cycle_time = styled_dropdown(
        label="Robot cycle time", options=[ft.DropdownOption(text=x) for x in RATINGS], value="Average"
    )
    throughput = styled_dropdown(
        label="Shooting speed", options=[ft.DropdownOption(text=x) for x in RATINGS], value="Average"
    )
    scoring_controls = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[shooter_type, hopper_size, accuracy_header, accuracy, cycle_time, throughput],
    )
    intake_floor = ft.Checkbox(label="Floor", active_color=RED, value=True)
    intake_outpost = ft.Checkbox(label="Outpost / human player", active_color=RED)
    intake_rating = styled_dropdown(
        label="Floor intake rating",
        options=[
            ft.DropdownOption(text=x)
            for x in ["There's an intake?", "Jammed several times", "Average", "Above Average", "Awesome!"]
        ],
        value="Average",
        visible=False,
    )
    inactive_choices = [
        ft.Checkbox(label=choice, active_color=RED)
        for choice in ["Nothing", "Defense", "Clear opposing fuel", "Pass / collect fuel"]
    ]
    intake_group = ft.Column(
        spacing=4,
        controls=[
            ft.Text("How does the robot collect fuel?", weight=ft.FontWeight.W_600),
            intake_floor,
            intake_outpost,
            intake_rating,
        ],
    )
    inactive_group = ft.Column(
        spacing=4,
        controls=[
            ft.Text("What do they do while the hub is inactive?", weight=ft.FontWeight.W_600),
            *inactive_choices,
        ],
    )

    # Movement, defense and endgame observations.
    shoot_on_move = styled_switch("Shoot while moving?")
    trench = styled_switch("Drove under the trench?", value=True)
    bump = styled_switch("Drove over the bump?", value=True)
    travel_path = styled_dropdown(
        label="Preferred travel path",
        options=[ft.DropdownOption(text=x) for x in ["Trench", "Bump", "Can't tell"]],
    )
    travel_warning = ft.Text("Select a travel path when both routes were possible.", color=MUTED, visible=False)
    played_defense = styled_switch("Did they play defense?")
    defense_rating_value = ft.Text("It's okay", color=RED, weight=ft.FontWeight.BOLD)
    defense_rating_header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Defense effectiveness", weight=ft.FontWeight.W_600),
            defense_rating_value,
        ],
    )
    defense_rating = ft.Slider(
        label="Defense effectiveness",
        min=1, max=4, value=2, divisions=3,
        active_color=RED, thumb_color=RED,
        visible=False,
    )
    had_defense = styled_switch("Did another robot play defense against them?")
    defense_against_rating_value = ft.Text("A little", color=RED, weight=ft.FontWeight.BOLD)
    defense_against_header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("How much did defense affect them?", weight=ft.FontWeight.W_600),
            defense_against_rating_value,
        ],
    )
    defense_against_rating = ft.Slider(
        label="How much did defense affect them?",
        min=1, max=4, value=2, divisions=3,
        active_color=RED, thumb_color=RED,
        visible=False,
    )
    defense_team = styled_field("Team that played defense")
    defense_against_controls = ft.Column(
        visible=False, controls=[defense_against_rating, defense_team]
    )
    endgame_climb = styled_switch("Climbed in endgame?")
    climb_level_value = ft.Text("1", color=RED, weight=ft.FontWeight.BOLD)
    climb_level_header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Climb level", weight=ft.FontWeight.W_600),
            climb_level_value,
        ],
    )
    climb_level = ft.Slider(
        label="Climb level", min=1, max=3, value=1, divisions=2,
        active_color=RED, thumb_color=RED, visible=False,
    )
    broke = styled_switch("Did the robot break?")
    break_details = styled_field("What happened, and how did it affect them?", multiline=True, min_lines=2, visible=False)
    extra_notes = styled_field("Anything else to note about this match?", multiline=True, min_lines=3)

    # Upload feedback.
    upload_status = ft.Text(
        visible=False,
        size=18,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_800,
    )
    upload_button = ft.Button(content="Save Match Scouting")
    pending_upload_button = ft.OutlinedButton(content="Upload saved matches")
    pending_upload_status = ft.Text(
        "Offline matches are kept on this device until they can be uploaded.", color=MUTED
    )
    # Score-accuracy view, paused with match predictions.
    # real_red = styled_field("Actual red score", value="0", keyboard_type=ft.KeyboardType.NUMBER)
    # real_blue = styled_field("Actual blue score", value="0", keyboard_type=ft.KeyboardType.NUMBER)
    # red_prediction_detail = ft.Text("Predicted score: —", color=MUTED)
    # blue_prediction_detail = ft.Text("Predicted score: —", color=MUTED)
    # red_accuracy_value = ft.Text("—", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800)
    # blue_accuracy_value = ft.Text("—", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800)
    # average_accuracy_value = ft.Text("—", size=28, weight=ft.FontWeight.BOLD, color=INK)
    # result_hint = ft.Text("Enter both actual scores to calculate accuracy.", color=MUTED)

    # def accuracy_card(
    #     title: str, prediction: ft.Text, value: ft.Text, color: str, background: str
    # ) -> ft.Container:
    #     return ft.Container(
    #         expand=True,
    #         padding=14,
    #         bgcolor=background,
    #         border=ft.Border.all(1, color),
    #         border_radius=12,
    #         content=ft.Column(
    #             horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    #             controls=[
    #                 ft.Text(title, color=color, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
    #                 prediction,
    #                 value,
    #             ],
    #         ),
    #     )

    # result_box = ft.Column(
    #     spacing=12,
    #     visible=False,
    #     controls=[
    #         ft.Text("Prediction results", size=18, weight=ft.FontWeight.BOLD),
    #         ft.Row(
    #             spacing=10,
    #             controls=[
    #                 ft.Column(expand=1, controls=[real_red]),
    #                 ft.Column(expand=1, controls=[real_blue]),
    #             ],
    #         ),
    #         ft.Row(
    #             spacing=10,
    #             vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    #             controls=[
    #                 accuracy_card(
    #                     "Red prediction accuracy", red_prediction_detail,
    #                     red_accuracy_value, ft.Colors.RED_800, ft.Colors.RED_50,
    #                 ),
    #                 accuracy_card(
    #                     "Blue prediction accuracy", blue_prediction_detail,
    #                     blue_accuracy_value, ft.Colors.BLUE_800, ft.Colors.BLUE_50,
    #                 ),
    #             ],
    #         ),
    #         ft.Container(
    #             padding=12,
    #             bgcolor=ft.Colors.GREY_100,
    #             border_radius=12,
    #             content=ft.Column(
    #                 horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    #                 controls=[
    #                     ft.Text("Average accuracy", color=MUTED),
    #                     average_accuracy_value,
    #                     result_hint,
    #                 ],
    #             ),
    #         ),
    #     ],
    # )

    # Wrap each functional group in a card to make the long form easier to scan.
    auto_card = section(
        "Autonomous",
        [auto_start, center_controls, neutral_passes_stepper, switch_tile(auto_climb)],
    )
    tele_card = section(
        "Tele-op",
        [
            switch_tile(scored_fuel),
            scoring_controls,
            intake_group,
            inactive_group,
            switch_tile(shoot_on_move), switch_tile(trench), switch_tile(bump),
            travel_path, travel_warning,
            switch_tile(played_defense), defense_rating_header, defense_rating,
            switch_tile(had_defense), defense_against_header, defense_against_controls,
        ],
    )
    endgame_card = section(
        "Endgame & match notes",
        [switch_tile(endgame_climb), climb_level_header, climb_level, switch_tile(broke), break_details, extra_notes],
    )
    scouting_form = ft.Column(
        visible=False,
        spacing=14,
        controls=[auto_card, tele_card, endgame_card, upload_status, upload_button],
    )

    # Page content: straightforward flow from match details to team scouting form.
    find_button.style = ft.ButtonStyle(bgcolor=RED, color=ft.Colors.WHITE)
    # submit_prediction_button.style = ft.ButtonStyle(bgcolor=RED, color=ft.Colors.WHITE)
    upload_button.style = ft.ButtonStyle(bgcolor=RED, color=ft.Colors.WHITE)
    content = ft.Column(
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Container(
                padding=14,
                bgcolor=ft.Colors.GREY_200,
                border_radius=14,
                content=ft.Text(
                    "Every observation is an estimate—use your best judgment. Unselected fields without a preset save as N/A.",
                    color=INK,
                ),
            ),
            section(
                "Match details",
                [event_key, scouter_name, match_number],
                # [event_key, scouter_name, match_number, switch_tile(predictions_toggle), prediction_notice],
            ),
            section(
                "Saved match uploads",
                [
                    ft.Text("Match records that cannot upload are saved on this device."),
                    pending_upload_button,
                    pending_upload_status,
                ],
            ),
            find_button,
            match_status,
            alliance_row,
            # prediction_box,
            priority_row,
            team_picker_row,
            offline_team_row,
            # result_box,
            scouting_form,
        ],
    )

    # Small helpers keep the interaction logic readable and reusable.
    def number(value) -> int:
        try:
            return int(value or 0)
        except (ValueError, TypeError):
            return 0

    def answer(value):
        """Preserve preset and entered values; use N/A only when no value exists."""
        return "N/A" if value is None or value == "" else value

    def set_neutral_passes(delta: int):
        """Adjust the auto pass count while respecting its 0–3 range."""
        neutral_passes.value = str(max(0, min(3, number(neutral_passes.value) + delta)))
        page.update()

    def decrement_passes():
        set_neutral_passes(-1)

    def increment_passes():
        set_neutral_passes(1)

    def refresh_form():
        # In offline mode with manual team entry, allow proceeding to the scouting
        # form even though the team picker isn't used. Online mode still requires
        # the user to select a team from the TBA results first.
        team_ready = bool(team_picker.value) or offline_team_row.visible
        scouting_form.visible = team_ready
        # scouting_form.visible = team_ready and state["predictions_ok"]
        # result_box.visible = bool(
        #     state["teams_found"]
        #     and predictions_toggle.value
        #     and state["red_prediction"] is not None
        #     and state["blue_prediction"] is not None
        # )
        page.update()

    # def refresh_offline_form():
    #     """Update form visibility based on which team input method is active."""
    #     # If we're in offline mode with manual team entry, show scouting form
    #     # In offline mode, the manual team fields are visible and team_picker is hidden
    #     # In online mode, the team picker is visible
    #     if not state["teams_found"] and predictions_toggle.value:
    #         # Offline mode with manual entry - ensure scouting form is visible
    #         scouting_form.visible = True
    #     else:
    #         # Normal mode or online mode - normal visibility logic applies
    #         refresh_form()
    #     page.update()

    # def update_prediction_result():
    #     actual_red, actual_blue = number(real_red.value), number(real_blue.value)
    #     predictions_ready = (
    #         state["red_prediction"] is not None
    #         and state["blue_prediction"] is not None
    #     )
    #     if actual_red and actual_blue and predictions_ready:
    #         red_pct = max(0, round(100 - abs(actual_red - state["red_prediction"]) / actual_red * 100))
    #         blue_pct = max(0, round(100 - abs(actual_blue - state["blue_prediction"]) / actual_blue * 100))
    #         red_accuracy_value.value = f"{red_pct}%"
    #         blue_accuracy_value.value = f"{blue_pct}%"
    #         average_accuracy_value.value = f"{(red_pct + blue_pct) / 2:.1f}%"
    #         result_hint.value = "Higher average accuracy is better."
    #     else:
    #         red_accuracy_value.value = "—"
    #         blue_accuracy_value.value = "—"
    #         average_accuracy_value.value = "—"
    #         result_hint.value = "Enter both actual scores to calculate accuracy."
    #     page.update()

    def set_pending_status(message: str, count: int | None = None):
        """Keep the queued-row count and its upload feedback visible."""
        if count is not None:
            pending_upload_button.content = (
                f"Upload saved matches ({count})" if count else "Upload saved matches"
            )
        pending_upload_status.value = message
        pending_upload_status.visible = True
        page.update()

    async def sync_pending_queue() -> int:
        """Upload queued rows in order, removing each only after Sheets confirms it."""
        if state["syncing_queue"]:
            raise RuntimeError("A saved-match upload is already in progress.")
        state["syncing_queue"] = True
        try:
            rows = await load_pending_matches(preferences)
            uploaded = 0
            while rows:
                await append_to_google_sheet(rows[0])
                rows.pop(0)
                await save_pending_matches(preferences, rows)
                uploaded += 1
            return uploaded
        finally:
            state["syncing_queue"] = False

    async def retry_saved_matches():
        """Let a scout manually upload every row saved during an outage."""
        pending_upload_button.disabled = True
        pending_upload_status.value = "Checking saved matches…"
        page.update()
        try:
            uploaded = await sync_pending_queue()
            remaining = await load_pending_matches(preferences)
            if uploaded:
                message = f"Uploaded {uploaded} saved match{'es' if uploaded != 1 else ''}."
            else:
                message = "There are no saved matches waiting to upload."
            set_pending_status(message, len(remaining))
        except Exception as error:
            try:
                remaining_count = len(await load_pending_matches(preferences))
                message = (
                    f"Upload failed; {remaining_count} match(es) remain saved on this device. "
                    f"Try again when connected. {error}"
                )
            except Exception as storage_error:
                remaining_count = None
                message = f"Could not access the local saved-match queue: {storage_error}"
            set_pending_status(message, remaining_count)
        finally:
            pending_upload_button.disabled = False
            page.update()

    async def try_auto_upload_pending():
        """Retry older offline rows when a successful match lookup suggests connectivity."""
        try:
            pending = await load_pending_matches(preferences)
            if not pending:
                set_pending_status("No offline matches are waiting to upload.", 0)
                return
            uploaded = await sync_pending_queue()
            remaining = await load_pending_matches(preferences)
            if remaining:
                message = f"{len(remaining)} match(es) remain saved locally; retry when online."
            else:
                message = f"Automatically uploaded {uploaded} saved match(es)."
            set_pending_status(message, len(remaining))
        except Exception as error:
            try:
                count = len(await load_pending_matches(preferences))
            except Exception:
                count = None
            set_pending_status(
                f"Saved matches are still queued for upload. {error}", count
            )

    # Fetch the selected qualification match and populate its alliance cards.
    async def find_teams():
        key, qual = (event_key.value or "").strip(), number(match_number.value)
        if not key or qual < 1:
            match_status.value = "Enter an event key and a match number of at least 1."
            match_status.color = RED
            match_status.visible = True
            page.update()
            return

        # Check if we have internet connectivity
        has_internet = await check_internet_connectivity()

        find_button.disabled = True
        # result_box.visible = False
        match_status.value = "Loading alliance teams…"
        match_status.color = MUTED
        match_status.visible = True
        page.update()
        try:
            if has_internet:
                # Online mode: fetch from The Blue Alliance API
                teams = await fetch_match(key, qual)
                red_teams, blue_teams = teams["red"], teams["blue"]
                all_teams = red_teams + blue_teams
                if not all_teams:
                    raise ValueError("No teams were listed for this match.")
                state["teams_found"] = True
                # state["predictions_ok"] = not predictions_toggle.value
                # state["red_prediction"] = state["blue_prediction"] = None
                # real_red.value = real_blue.value = "0"
                # red_accuracy_value.value = blue_accuracy_value.value = "—"
                # average_accuracy_value.value = "—"
                # red_prediction_detail.value = blue_prediction_detail.value = "Predicted score: —"
                team_picker.value = None
                # Get scouted teams prioritized by least data to most
                try:
                    scouted_teams = await fetch_scouted_teams_prioritized()
                except Exception as error:
                    scouted_teams = []
                    match_status.value = f"Warning: Could not fetch scouting list ({error})"
                    match_status.color = ft.Colors.ORANGE_800
                # Scouted teams list is already ordered least data → most data.
                # Order all_teams by that priority: teams with less data appear first.
                scouted_set = set(scouted_teams)
                unscouted_teams = [team for team in all_teams if team not in scouted_set]
                scouted_in_match = [team for team in scouted_teams if team in all_teams]
                priority_teams = unscouted_teams + scouted_in_match
                team_picker.options = [ft.DropdownOption(text=team) for team in priority_teams]
                alliance_row.controls = [
                    alliance_card("RED ALLIANCE", red_teams, ft.Colors.RED_50, ft.Colors.RED_800),
                    alliance_card("BLUE ALLIANCE", blue_teams, ft.Colors.BLUE_50, ft.Colors.BLUE_800),
                ]
                alliance_row.visible = True
                team_picker.visible = True
                team_picker_row.visible = True
                # Show priority teams (sorted: unscouted first, then scouted teams by least data)
                priority_text.value = f"Priority Teams (least data first): {', '.join(priority_teams)}"
                priority_text.visible = True
                priority_row.visible = True
                offline_team_row.visible = False
                # prediction_box.visible = predictions_toggle.value
                scouting_form.visible = False
                match_status.value = f"Teams loaded · {key.upper()} · Qual {qual}"
                match_status.color = ft.Colors.GREEN_800
                await try_auto_upload_pending()
            else:
                # Offline mode: allow manual team number entry
                state["teams_found"] = False
                # state["predictions_ok"] = not predictions_toggle.value
                # Clear any previous team data
                team_picker.value = None
                team_picker.options = []
                alliance_row.visible = False
                priority_row.visible = False
                team_picker.visible = False
                team_picker_row.visible = False
                # prediction_box.visible = False
                # Show the manual team entry fields instead
                offline_team_row.visible = True
                scouting_form.visible = True
                match_status.value = "Offline mode — enter your team numbers manually below."
                match_status.color = ft.Colors.ORANGE_800
                match_status.visible = True
                page.update()
                await try_auto_upload_pending()
        except ValueError as error:
            state["teams_found"] = False
            match_status.value = str(error)
            match_status.color = RED
        except httpx.HTTPError as error:
            state["teams_found"] = False
            # If we were online but the request failed, show error;
            # if offline, this won't happen since we check first
            match_status.value = f"TBA request failed: {error}"
            match_status.color = RED
        finally:
            find_button.disabled = False
            match_status.visible = True
            page.update()

    # A saved prediction is required only when the optional prediction switch is on.
    # def save_predictions():
    #     red, blue = number(red_prediction.value), number(blue_prediction.value)
    #     if red > 0 and blue > 0:
    #         state["red_prediction"], state["blue_prediction"] = red, blue
    #         red_prediction_detail.value = f"Predicted score: {red}"
    #         blue_prediction_detail.value = f"Predicted score: {blue}"
    #         state["predictions_ok"] = True
    #         prediction_status.value = "Predictions saved. Enter the final scores below when available."
    #         prediction_status.color = ft.Colors.GREEN_800
    #     else:
    #         state["red_prediction"] = state["blue_prediction"] = None
    #         red_prediction_detail.value = blue_prediction_detail.value = "Predicted score: —"
    #         state["predictions_ok"] = False
    #         prediction_status.value = "Both predicted scores must be at least 1."
    #         prediction_status.color = RED
    #     update_prediction_result()
    #     refresh_form()

    # Return a list of selected labels for checkboxes in the scouting record.
    def selected_checks(controls):
        return ", ".join(control.label for control in controls if control.value) or "N/A"

    # Save the observation row to the configured Google Sheet.
    async def save_match():
        if state["syncing_queue"]:
            upload_status.value = "Wait for the saved-match upload to finish, then try again."
            upload_status.color = MUTED
            upload_status.visible = True
            page.update()
            return
        # In offline mode, the team is entered in a single field instead of two.
        if offline_team_row.visible:
            selected_team = offline_team_row.controls[1].value.strip()
            if not selected_team:
                upload_status.value = "Enter at least one team number before saving."
                upload_status.color = RED
                upload_status.visible = True
                page.update()
                return
        elif not team_picker.value:
            upload_status.value = "Select a team before saving."
            upload_status.color = RED
            upload_status.visible = True
            page.update()
            return
        else:
            selected_team = team_picker.value
        row = {
            "scouter": scouter_name.value.strip() or "N/A",
            "team": selected_team,
            "match": number(match_number.value),
            "auto_start": answer(auto_start.value),
            "auto_center_intaked": answer(center_intaked.value)
            if auto_start.value == "Center" else "N/A",
            "auto_center_scored": answer(center_scored.value)
            if auto_start.value == "Center" else "N/A",
            "neutral_passes": answer(
                max(0, min(3, number(neutral_passes.value)))
                if (neutral_passes.value or "").strip() else None,
            ) if auto_start.value != "Center" else "N/A",
            "auto_climb": answer(auto_climb.value),
            "scored_fuel": answer(scored_fuel.value),
            "shooter": answer(shooter_type.value)
            if scored_fuel.value else "N/A",
            "hopper": answer(hopper_size.value)
            if scored_fuel.value else "N/A",
            "accuracy": answer(round(accuracy.value))
            if scored_fuel.value else "N/A",
            "throughput": answer(throughput.value)
            if scored_fuel.value else "N/A",
            "cycle_time": answer(cycle_time.value)
            if scored_fuel.value else "N/A",
            "intake": selected_checks([intake_floor, intake_outpost]),
            "intake_rating": answer(intake_rating.value)
            if intake_floor.value else "N/A",
            "inactive_actions": selected_checks(inactive_choices),
            "shoot_on_move": answer(shoot_on_move.value),
            "trench": answer(trench.value),
            "bump": answer(bump.value),
            "travel_path": answer(travel_path.value)
            if trench.value and bump.value else "N/A",
            "played_defense": answer(played_defense.value),
            "defense_rating": answer(int(defense_rating.value))
            if played_defense.value else "N/A",
            "had_defense": answer(had_defense.value),
            "defense_against_rating": answer(int(defense_against_rating.value))
            if had_defense.value else "N/A",
            "defense_team": defense_team.value.strip() or "N/A"
            if had_defense.value else "N/A",
            "endgame_climb": answer(endgame_climb.value),
            "climb_level": answer(int(climb_level.value))
            if endgame_climb.value else "N/A",
            "broke": answer(broke.value),
            "break_details": break_details.value.strip() or "N/A"
            if broke.value else "N/A",
            "notes": extra_notes.value.strip() or "N/A",
        }
        values = list(row.values())
        upload_button.disabled = True
        pending_upload_button.disabled = True
        upload_status.value = "Sending match data to Google Sheets…"
        upload_status.color = MUTED
        upload_status.visible = True
        page.update()
        try:
            # Send any older offline records first, preserving their original order.
            await sync_pending_queue()
            await append_to_google_sheet(values)
            pending_count = len(await load_pending_matches(preferences))
            upload_status.value = "Match scouting saved to Google Sheets."
            upload_status.color = ft.Colors.GREEN_800
            set_pending_status(
                "No offline matches are waiting to upload." if not pending_count
                else f"{pending_count} match(es) are still queued.",
                pending_count,
            )
        except Exception as upload_error:
            # Keep the just-finished observation for an explicit later retry.
            try:
                queued_rows = await load_pending_matches(preferences)
                queued_rows.append(values)
                await save_pending_matches(preferences, queued_rows)
                pending_count = len(queued_rows)
                upload_status.value = (
                    f"Google Sheets upload failed. This match is saved on this device; "
                    f"{pending_count} match(es) are waiting. {upload_error}"
                )
                upload_status.color = ft.Colors.AMBER_900
                set_pending_status(
                    f"{pending_count} match(es) saved locally. Upload them when connected.",
                    pending_count,
                )
            except Exception as storage_error:
                upload_status.value = (
                    "Upload failed, and this device could not save the match locally. "
                    f"Keep this screen open and do not discard the form. {storage_error}"
                )
                upload_status.color = RED
        finally:
            upload_button.disabled = False
            pending_upload_button.disabled = False
            upload_status.visible = True
            page.update()

    # Show only the inputs relevant to the selected observations.
    def update_conditional_fields():
        center_controls.visible = auto_start.value == "Center"
        neutral_passes_stepper.visible = auto_start.value != "Center"
        scoring_controls.visible = scored_fuel.value
        intake_rating.visible = intake_floor.value
        travel_path.visible = trench.value and bump.value
        travel_warning.visible = not (trench.value and bump.value)
        defense_rating.visible = played_defense.value
        defense_rating_header.visible = played_defense.value
        defense_against_controls.visible = had_defense.value
        defense_against_header.visible = had_defense.value
        defense_against_rating.visible = had_defense.value
        climb_level.visible = endgame_climb.value
        climb_level_header.visible = endgame_climb.value
        break_details.visible = broke.value
        page.update()

    # Turning predictions off immediately makes team selection available again.
    # def toggle_predictions(_):
    #     prediction_box.visible = state["teams_found"] and predictions_toggle.value
    #     state["red_prediction"] = state["blue_prediction"] = None
    #     red_prediction_detail.value = blue_prediction_detail.value = "Predicted score: —"
    #     red_accuracy_value.value = blue_accuracy_value.value = "—"
    #     average_accuracy_value.value = "—"
    #     if predictions_toggle.value:
    #         state["predictions_ok"] = False
    #     else:
    #         state["predictions_ok"] = True
    #     refresh_form()
    #     refresh_offline_form()
    #     page.update()

    # Connect conditional controls and keep the accuracy readout live.
    def update_accuracy(_e):
        accuracy_value.value = f"{round(_e.control.value)}%"
        page.update()

    def update_defense_rating(_e):
        rating = round(_e.control.value)
        labels = ["Hurt more than helped", "It's okay", "Great!", "Amazing!"]
        defense_rating_value.value = labels[rating - 1]
        page.update()

    def update_defense_against_rating(_e):
        rating = round(_e.control.value)
        labels = ["Wait, what defense?", "A little", "Significantly", "Cost them the match"]
        defense_against_rating_value.value = labels[rating - 1]
        page.update()

    def update_climb_level(_e):
        climb_level_value.value = str(round(_e.control.value))
        page.update()

    find_button.on_click = find_teams
    # submit_prediction_button.on_click = save_predictions
    upload_button.on_click = save_match
    pending_upload_button.on_click = retry_saved_matches
    subtract_pass_button.on_click = decrement_passes
    add_pass_button.on_click = increment_passes
    # predictions_toggle.on_change = toggle_predictions
    team_picker.on_select = lambda _: refresh_form()
    auto_start.on_select = update_conditional_fields
    accuracy.on_change = update_accuracy
    defense_rating.on_change = update_defense_rating
    defense_against_rating.on_change = update_defense_against_rating
    climb_level.on_change = update_climb_level
    for control in (
        scored_fuel, intake_floor, trench, bump, played_defense,
        had_defense, endgame_climb, broke,
    ):
        control.on_change = update_conditional_fields

    # real_red.on_change = lambda _: update_prediction_result()
    # real_blue.on_change = lambda _: update_prediction_result()

    # Set initial visibility of conditional fields based on default values.
    update_conditional_fields()

    return ft.ResponsiveRow(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Container(
                col={"xs": 12, "sm": 12, "md": 10, "lg": 8, "xl": 7, "xxl": 7},
                content=content,
            )
        ],
    )
