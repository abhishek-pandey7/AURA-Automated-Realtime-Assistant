"""
aura/tools/calendar.py — Google Calendar integration for AURA.

First-time setup:
  1. Go to https://console.cloud.google.com/
  2. Create a new project → Enable "Google Calendar API"
  3. Credentials → Create OAuth 2.0 Client ID → Desktop app
  4. Download the JSON → save as credentials.json in the project root
  5. Run `aura run` and ask AURA to list events — it will open a browser for one-time auth.
     A token.json file will be saved so you never need to log in again.
"""

import os
import json
import datetime

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "token.json")

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "calendar_list_events",
            "description": "List upcoming events from Google Calendar. Returns the next N events with their title, date, and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of upcoming events to return (default 10)."
                    }
                },
                "required": []
            }
        }
    },
]


def _get_service():
    """Authenticate and return the Google Calendar API service object."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    token_path = os.path.abspath(TOKEN_FILE)
    creds_path = os.path.abspath(CREDENTIALS_FILE)

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    "[ AURA ] credentials.json not found!\n"
                    "  Please follow these steps:\n"
                    "  1. Go to https://console.cloud.google.com/\n"
                    "  2. Create a project → Enable 'Google Calendar API'\n"
                    "  3. Credentials → Create OAuth 2.0 Client ID → Desktop app\n"
                    "  4. Download JSON → save as 'credentials.json' in the project root.\n"
                    "  5. Run this command again — a browser window will open for one-time login."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def calendar_list_events(max_results: int = 10) -> str:
    try:
        service = _get_service()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return "[ AURA ] No upcoming events found in your Google Calendar."

        lines = [f"[ AURA ] Upcoming {len(events)} events:\n"]
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", "Unknown"))
            title = e.get("summary", "(No title)")
            desc = e.get("description", "")
            desc_snippet = f" — {desc[:60]}" if desc else ""
            lines.append(f"  • {start}  |  {title}{desc_snippet}")

        return "\n".join(lines)
    except Exception as ex:
        return f"[ AURA ] Calendar list failed: {ex}"


