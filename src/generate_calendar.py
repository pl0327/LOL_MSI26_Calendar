#!/usr/bin/env python3
"""Generate MSI 2026 knockout calendar JSON database and ICS from lolesports.com."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

TOURNAMENT_ID = "115570934354631452"
KNOCKOUT_STAGE_ID = "115570934355090206"
KNOCKOUTS_URL = (
    "https://lolesports.com/en-US/tournament/"
    f"{TOURNAMENT_ID}/stage/{KNOCKOUT_STAGE_ID}"
)
SCHEDULE_URL = "https://lolesports.com/en-US/leagues/first_stand,msi,worlds"
LIVE_STREAM_URL = "https://www.youtube.com/@lolesports"

CALENDAR_TITLE = "MSI 2026 Knockouts"
MATCH_DURATION = timedelta(hours=3)
POST_MATCH_UPDATE_OFFSETS = (timedelta(hours=3), timedelta(hours=6))
EVENT_TIMEZONE = ZoneInfo("Asia/Seoul")

PHASE_BY_PREFIX = {
    "UR1": "UPPER 1",
    "UR2": "UPPER 2",
    "UR3": "UPPER 3",
    "LR1": "LOWER 1",
    "LR2": "LOWER 2",
    "LR3": "LOWER 3",
    "LR4": "LOWER 4",
}

PHASE_ROUND_LABEL = {
    "UPPER 1": "Upper Bracket - Round 1",
    "UPPER 2": "Upper Bracket - Round 2",
    "UPPER 3": "Upper Bracket - Round 3",
    "LOWER 1": "Lower Bracket - Round 1",
    "LOWER 2": "Lower Bracket - Round 2",
    "LOWER 3": "Lower Bracket - Round 3",
    "LOWER 4": "Lower Bracket - Round 4",
    "FINALS": "Finals",
}

TRACKED_MATCH_FIELDS = (
    "team1",
    "team2",
    "team1Name",
    "team2Name",
    "summary",
    "descriptionText",
    "status",
    "state",
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; MSI26-Calendar/1.0; +https://github.com)"
)


def fetch_knockouts_page() -> str:
    request = urllib.request.Request(
        KNOCKOUTS_URL,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def unescape_rsc_payload(payload: str) -> str:
    return payload.replace('\\"', '"').replace("\\\\", "\\")


def extract_next_chunks(html: str) -> list[str]:
    return re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)


def phase_from_description(description: str) -> str | None:
    description = description.strip()
    if description.startswith("Finals"):
        return "FINALS"
    for prefix, phase in PHASE_BY_PREFIX.items():
        if description.startswith(prefix):
            return phase
    return None


def normalize_team_code(code: str | None, slug: str | None = None) -> str:
    if not code or code.upper() == "TBD" or slug == "tbd":
        return "TBD"
    return code


def normalize_team_name(name: str | None, slug: str | None = None) -> str:
    if not name or name.upper() == "TBD" or slug == "tbd":
        return "TBD"
    return name


def parse_match_teams(teams_raw: str) -> tuple[str, str, str, str]:
    teams = re.findall(
        r'"slug":"([^"]*)","name":"([^"]*)","code":"([^"]*)"',
        teams_raw,
    )
    if not teams:
        teams = re.findall(r'"name":"([^"]*)","code":"([^"]*)"', teams_raw)
        teams = [("unknown", name, code) for name, code in teams]

    if len(teams) < 2:
        return "TBD", "TBD", "TBD", "TBD"

    team1_code = normalize_team_code(teams[0][2], teams[0][0])
    team2_code = normalize_team_code(teams[1][2], teams[1][0])
    team1_name = normalize_team_name(teams[0][1], teams[0][0])
    team2_name = normalize_team_name(teams[1][1], teams[1][0])
    return team1_code, team2_code, team1_name, team2_name


def parse_embedded_matches(html: str) -> list[dict]:
    match_pattern = re.compile(
        r'"structuralId":"([^"]+)","state":"([^"]+)"'
        r'(?:[^}]*?"type":"([^"]+)")?'
        r'[^}]*?"matchTeams":\[(.*?)\],'
        r'"destinations":\{.*?\},'
        r'"startTime":"([^"]+)"',
        re.DOTALL,
    )
    id_pattern = re.compile(
        r'\{"__typename":"Match","id":"(\d+)","description":"([^"]*)",'
        r'"structuralId":"([^"]+)","state":"([^"]+)"'
        r'(?:[^}]*?"type":"([^"]+)")?'
        r'[^}]*?"matchTeams":\[(.*?)\],'
        r'"destinations":\{.*?\},'
        r'"startTime":"([^"]+)"\}',
        re.DOTALL,
    )

    parsed: dict[str, dict] = {}
    for chunk in extract_next_chunks(html):
        text = unescape_rsc_payload(chunk)
        if "matchDataById" not in text and '"description":"UR' not in text:
            continue

        for match in id_pattern.finditer(text):
            (
                match_id,
                description,
                structural_id,
                state,
                _match_type,
                teams_raw,
                start_time,
            ) = match.groups()
            phase = phase_from_description(description)
            if phase is None:
                continue

            team1, team2, team1_name, team2_name = parse_match_teams(teams_raw)
            parsed[structural_id] = {
                "matchId": match_id,
                "description": description.strip(),
                "structuralId": structural_id,
                "phase": phase,
                "state": state,
                "team1": team1,
                "team2": team2,
                "team1Name": team1_name,
                "team2Name": team2_name,
                "startTime": start_time,
            }

        # Some payloads omit startTime on bracket cells; fill from matchDataById entries.
        for structural_id, state, _match_type, teams_raw, start_time in match_pattern.findall(
            text
        ):
            if structural_id in parsed:
                continue
            description_match = re.search(
                rf'"structuralId":"{re.escape(structural_id)}","state":"[^"]+"[^}}]*?'
                rf'"description":"([^"]*)"',
                text,
            )
            if description_match is None:
                continue
            description = description_match.group(1).strip()
            phase = phase_from_description(description)
            if phase is None:
                continue

            id_match = re.search(
                rf'"id":"(\d+)","description":"{re.escape(description)}",'
                rf'"structuralId":"{re.escape(structural_id)}"',
                text,
            )
            if id_match is None:
                continue

            team1, team2, team1_name, team2_name = parse_match_teams(teams_raw)
            parsed[structural_id] = {
                "matchId": id_match.group(1),
                "description": description,
                "structuralId": structural_id,
                "phase": phase,
                "state": state,
                "team1": team1,
                "team2": team2,
                "team1Name": team1_name,
                "team2Name": team2_name,
                "startTime": start_time,
            }

    matches = list(parsed.values())
    matches.sort(key=lambda match: match["startTime"])
    return matches


def fetch_matches() -> list[dict]:
    html = fetch_knockouts_page()
    return parse_embedded_matches(html)


def parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def to_local_datetime(value: str) -> datetime:
    return parse_utc_datetime(value).astimezone(EVENT_TIMEZONE).replace(tzinfo=None)


def build_match_url(_match_id: str) -> str:
    return LIVE_STREAM_URL


def ics_status(state: str) -> str:
    if state == "completed":
        return "CONFIRMED"
    if state == "inProgress":
        return "CONFIRMED"
    return "CONFIRMED"


def transform_match(raw: dict) -> dict:
    team1 = raw["team1"]
    team2 = raw["team2"]
    team1_name = raw["team1Name"]
    team2_name = raw["team2Name"]
    phase = raw["phase"]
    description = raw["description"]
    match_id = raw["matchId"]
    round_label = PHASE_ROUND_LABEL[phase]

    start_local = to_local_datetime(raw["startTime"])
    end_local = start_local + MATCH_DURATION
    match_url = build_match_url(match_id)
    summary = f"{phase} - {team1} vs {team2}"
    detail = (
        f"League of Legends MSI 2026 Knockouts\n"
        f"{round_label}\n"
        f"{team1_name} vs {team2_name}\n\n"
        f"Schedule: {SCHEDULE_URL}\n\n"
        f"Bracket: {KNOCKOUTS_URL}"
    )

    return {
        "matchId": match_id,
        "uid": f"msi26-knockout-{match_id}@msi-calendar",
        "phase": phase,
        "roundLabel": round_label,
        "description": description,
        "team1": team1,
        "team2": team2,
        "team1Name": team1_name,
        "team2Name": team2_name,
        "state": raw["state"],
        "startLocal": start_local.isoformat(),
        "endLocal": end_local.isoformat(),
        "timezone": str(EVENT_TIMEZONE),
        "matchUrl": match_url,
        "status": ics_status(raw["state"]),
        "summary": summary,
        "descriptionText": detail,
    }


def match_kickoff_utc(match: dict) -> datetime:
    start_local = datetime.fromisoformat(match["startLocal"])
    start = start_local.replace(tzinfo=EVENT_TIMEZONE)
    return start.astimezone(timezone.utc)


def is_post_match_update_window(matches: list[dict], now: datetime) -> bool:
    """True during the hour after start+3h or start+6h for any match."""
    for match in matches:
        kickoff = match_kickoff_utc(match)
        for offset in POST_MATCH_UPDATE_OFFSETS:
            update_time = kickoff + offset
            if update_time <= now < update_time + timedelta(hours=1):
                return True
    return False


def should_fetch_now(matches: list[dict], now: datetime) -> bool:
    return is_post_match_update_window(matches, now)


def matches_changed(old_matches: list[dict], new_matches: list[dict]) -> bool:
    old_by_id = {match["matchId"]: match for match in old_matches}
    for match in new_matches:
        previous = old_by_id.get(match["matchId"])
        if previous is None:
            return True
        for field in TRACKED_MATCH_FIELDS:
            if previous.get(field) != match.get(field):
                return True
    return False


def changed_match_ids(old_matches: list[dict], new_matches: list[dict]) -> list[str]:
    old_by_id = {match["matchId"]: match for match in old_matches}
    changed: list[str] = []
    for match in new_matches:
        previous = old_by_id.get(match["matchId"])
        if previous is None:
            changed.append(match["matchId"])
            continue
        for field in TRACKED_MATCH_FIELDS:
            if previous.get(field) != match.get(field):
                changed.append(match["matchId"])
                break
    return changed


def load_existing_matches(json_path: Path) -> list[dict] | None:
    if not json_path.exists():
        return None
    database = json.loads(json_path.read_text())
    return database.get("matches")


def format_ics_datetime(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S")


def escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_database(matches: list[dict]) -> dict:
    return {
        "calendarTitle": CALENDAR_TITLE,
        "lastUpdated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": KNOCKOUTS_URL,
        "scheduleUrl": SCHEDULE_URL,
        "liveStreamUrl": LIVE_STREAM_URL,
        "postMatchUpdateOffsetsHours": [
            int(offset.total_seconds() // 3600) for offset in POST_MATCH_UPDATE_OFFSETS
        ],
        "matchCount": len(matches),
        "matches": matches,
    }


def build_ics(matches: list[dict], generated_at: datetime) -> str:
    dtstamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    refresh_hours = 1
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MSI Calendar//LoL MSI 2026 Knockouts//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CALENDAR_TITLE}",
        f"REFRESH-INTERVAL;VALUE=DURATION:PT{refresh_hours}H",
        f"X-PUBLISHED-TTL:PT{refresh_hours}H",
    ]

    for match in matches:
        start = datetime.fromisoformat(match["startLocal"])
        end = datetime.fromisoformat(match["endLocal"])
        description = escape_ics_text(match["descriptionText"])
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{match['uid']}",
                f"DTSTAMP:{dtstamp}",
                (
                    f"DTSTART;TZID={match['timezone']}:"
                    f"{format_ics_datetime(start)}"
                ),
                f"DTEND;TZID={match['timezone']}:{format_ics_datetime(end)}",
                f"SUMMARY:{escape_ics_text(match['summary'])}",
                f"DESCRIPTION:{description}",
                f"URL:{match['matchUrl']}",
                f"STATUS:{match['status']}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\n".join(lines) + "\n"


def write_outputs(matches: list[dict], generated_at: datetime) -> tuple[Path, Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    database = build_database(matches)
    json_path = DATA_DIR / "matches.json"
    ics_path = ROOT / "msi_2026.ics"
    docs_ics_path = DOCS_DIR / "msi_2026.ics"

    ics_content = build_ics(matches, generated_at)
    json_path.write_text(json.dumps(database, indent=2, ensure_ascii=False) + "\n")
    ics_path.write_text(ics_content)
    docs_ics_path.write_text(ics_content)
    (DOCS_DIR / ".nojekyll").touch()

    return json_path, ics_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Only fetch during post-match update windows (start+3h and "
            "start+6h), and write when scraped data has changed."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Always scrape lolesports.com and rewrite outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = datetime.now(timezone.utc)
    json_path = DATA_DIR / "matches.json"
    existing_matches = load_existing_matches(json_path)

    if args.auto and not args.force:
        if existing_matches is None:
            print("No existing database found; performing initial fetch.")
        elif not should_fetch_now(existing_matches, generated_at):
            print(
                "Outside post-match update window "
                "(start+3h or start+6h); skipping update."
            )
            return

    raw_matches = fetch_matches()
    if not raw_matches:
        raise SystemExit(
            "No knockout matches found on lolesports.com. "
            "The page layout may have changed."
        )

    matches = [transform_match(raw) for raw in raw_matches]

    if args.auto and not args.force and existing_matches is not None:
        if not matches_changed(existing_matches, matches):
            print("Scraped data unchanged; no calendar update needed.")
            return
        changed = changed_match_ids(existing_matches, matches)
        print(f"Updating calendar for changed matches: {changed}")

    write_outputs(matches, generated_at)
    print(f"Wrote {len(matches)} matches to {json_path}")
    print(f"Wrote calendar to {ROOT / 'msi_2026.ics'}")
    print(f"Wrote calendar to {DOCS_DIR / 'msi_2026.ics'}")


if __name__ == "__main__":
    main()
