"""Async network functions for The Blue Alliance, Statbotics, and Google Sheets."""

import time
from urllib.parse import quote

import httpx2 as httpx

try:
    from api_keys import (
        GOOGLE_SERVICE_ACCOUNT_INFO,
        GOOGLE_SHEETS_RANGE,
        GOOGLE_SHEETS_SPREADSHEET_ID,
        TBA_API_KEY,
    )
except ImportError:
    # api_keys.py is intentionally excluded from version control (it holds secrets
    # like the TBA API key and Google service account credentials). The GitHub
    # Pages build won't have it, so provide placeholders so the app still loads.
    # Features that need real keys raise a clear error when they're actually used.
    GOOGLE_SERVICE_ACCOUNT_INFO = {}
    GOOGLE_SHEETS_RANGE = None
    GOOGLE_SHEETS_SPREADSHEET_ID = None
    TBA_API_KEY = None

TBA_URL = "https://www.thebluealliance.com/api/v3"
STATBOTICS_URL = "https://api.statbotics.io/v3"


def _check_key(value: str, placeholder: str, label: str) -> None:
    """Fail with a helpful message before sending a request with a placeholder."""
    if not value or value == placeholder:
        raise ValueError(f"Add your {label} in src/api_keys.py first.")


def _tba_headers() -> dict:
    _check_key(TBA_API_KEY, "ADD_TBA_API_KEY_HERE", "TBA API key")
    return {"X-TBA-Auth-Key": TBA_API_KEY}


async def fetch_match(event_key: str, match_number: int) -> dict:
    """Load a qualification match's red and blue alliance teams."""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{TBA_URL}/match/{event_key}_qm{match_number}", headers=_tba_headers()
        )
        response.raise_for_status()
        data = response.json()
    if not data:
        raise ValueError("No match data was returned. Check the event and match numbers.")
    alliances = data.get("alliances", {})
    return {
        color: [team.removeprefix("frc") for team in alliances.get(color, {}).get("team_keys", [])]
        for color in ("red", "blue")
    }


async def fetch_rankings(event_key: str) -> list[dict]:
    """Get the event ranking rows from The Blue Alliance."""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{TBA_URL}/event/{event_key}/rankings", headers=_tba_headers())
        response.raise_for_status()
    rankings = response.json().get("rankings", [])
    if not isinstance(rankings, list):
        raise ValueError("TBA returned an unexpected rankings format.")
    return rankings


async def fetch_schedule(url: str) -> list[dict]:
    """Fetch match schedule data from a caller-provided TBA endpoint."""
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(url, headers=_tba_headers())
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, list):
        raise ValueError("TBA did not return a match list.")
    return data


async def fetch_statbotics(path: str) -> dict:
    """Read one Statbotics v3 resource."""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{STATBOTICS_URL}/{path.lstrip('/')}")
        response.raise_for_status()
        return response.json()


def _raise_google_error(response) -> None:
    """Include Google's response explanation when a Sheets request is rejected."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = response.text[:1000]
        raise ValueError(
            f"Google API returned HTTP {response.status_code}: {detail}"
        ) from error


def _google_service_account() -> tuple[str, str]:
    """Create and sign the short-lived assertion used to authorize Sheets access."""
    info = GOOGLE_SERVICE_ACCOUNT_INFO
    required = ["project_id", "private_key_id", "private_key", "client_email", "client_id"]
    if any(not info.get(key) or str(info[key]).startswith("ADD_") for key in required):
        raise ValueError("Fill in GOOGLE_SERVICE_ACCOUNT_INFO in src/api_keys.py first.")

    # google-auth signs the assertion locally; httpx2 performs the async token request.
    from google.auth.crypt import RSASigner
    from google.auth.jwt import encode

    now = int(time.time())
    signer = RSASigner.from_string(info["private_key"], info["private_key_id"])
    assertion = encode(
        signer,
        {
            "iss": info["client_email"],
            "scope": "https://www.googleapis.com/auth/spreadsheets",
            "aud": info.get("token_uri", "https://oauth2.googleapis.com/token"),
            "iat": now,
            "exp": now + 3600,
        },
    )
    return info.get("token_uri", "https://oauth2.googleapis.com/token"), assertion.decode("utf-8")


async def append_to_google_sheet(
    values: list,
    range_name: str | None = None,
    headers: list[str] | None = None,
) -> None:
    """Append a row, optionally creating a worksheet and its header row first."""
    if not GOOGLE_SHEETS_SPREADSHEET_ID or GOOGLE_SHEETS_SPREADSHEET_ID == "ADD_SPREADSHEET_ID":
        raise ValueError("Add GOOGLE_SHEETS_SPREADSHEET_ID in src/api_keys.py first.")

    token_url, assertion = _google_service_account()
    spreadsheet_url = f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEETS_SPREADSHEET_ID}"
    async with httpx.AsyncClient(timeout=25) as client:
        token_response = await client.post(
            token_url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        _raise_google_error(token_response)
        auth_headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

        target_range = range_name or GOOGLE_SHEETS_RANGE
        if headers and range_name:
            # Pit data uses its own tab so it does not mix with match-row columns.
            tab_name = range_name.split("!", 1)[0].strip("'")
            metadata = await client.get(
                spreadsheet_url,
                params={"fields": "sheets(properties(title))"},
                headers=auth_headers,
            )
            _raise_google_error(metadata)
            sheet_names = [
                sheet.get("properties", {}).get("title")
                for sheet in metadata.json().get("sheets", [])
            ]
            if tab_name not in sheet_names:
                created = await client.post(
                    f"{spreadsheet_url}:batchUpdate",
                    headers=auth_headers,
                    json={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
                )
                _raise_google_error(created)

            header_range = f"'{tab_name}'!1:1"
            header_url = f"{spreadsheet_url}/values/{quote(header_range, safe='')}"
            existing_headers = await client.get(header_url, headers=auth_headers)
            _raise_google_error(existing_headers)
            if not existing_headers.json().get("values"):
                first_cell_range = f"'{tab_name}'!A1"
                write_headers = await client.put(
                    f"{spreadsheet_url}/values/{quote(first_cell_range, safe='')}",
                    params={"valueInputOption": "USER_ENTERED"},
                    headers=auth_headers,
                    json={"values": [headers]},
                )
                _raise_google_error(write_headers)

        append_url = (
            f"{spreadsheet_url}/values/{quote(target_range, safe='')}:append"
        )
        response = await client.post(
            append_url,
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            headers=auth_headers,
            json={"values": [values]},
        )
        _raise_google_error(response)
