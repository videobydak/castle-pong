import os, json, datetime, getpass, urllib.request, urllib.parse, threading

"""Lightweight leaderboard utilities.

This module stores each player's best score locally and, when configured,
submits new personal records to a public Google Sheet that acts as the
remote leaderboard.  The approach avoids running any dedicated backend
while still giving players a global high-score table.

Usage (from gameplay code):
    from leaderboard import handle_end_of_wave

    # inside End-of-Wave screen after total score is known
    handle_end_of_wave(total_score, wave)

Configuration:
1.  PLAYER NAME – by default this is read from player_data.json, the
    CASTLE_PONG_PLAYER environment variable, or the system username.
2.  API KEY – write your Sheets v4 API key into google_api_key.txt or set
    the GOOGLE_SHEETS_API_KEY environment variable.  If no key is
    available, remote submission is silently skipped and only the local
    high score is updated.
3.  SHEET_ID – hard-coded to the public sheet supplied by the project
    owner.  Change here if you switch leaderboards.
"""

SHEET_ID = "1WiH2xiUjg5XGaXCYbpfjWCBWwSlP1d5D0xnGKA0M9zA"
PLAYER_DATA_FILE = "player_data.json"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
APPEND_URL_TMPL = (
    "https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/Sheet1!A:D:append"
    "?valueInputOption=RAW&key={api_key}"
)

# ------------------------------------------------------------------------
#  Google Form configuration (public – no auth required)
# ------------------------------------------------------------------------

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScRlsOSmQB8WMUFejsj2AK8XLWIIMFsvqMLRiNa29-j5vYf1Q/formResponse"

# IDs captured from the pre-filled sample link the user provided
ENTRY_PLAYER = "entry.1025709388"
ENTRY_SCORE  = "entry.495305126"
ENTRY_WAVE   = "entry.1995773847"
ENTRY_DATE   = "entry.1605421804"

# ------------------------------------------------------------------------

def _load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def _save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("[Leaderboard] Failed to save", path, ":", e)

def _player_data():
    return _load_json(PLAYER_DATA_FILE, {})

def _write_player_data(d):
    _save_json(PLAYER_DATA_FILE, d)

def get_player_name() -> str:
    """Return the player name, falling back gracefully if not set."""
    data = _player_data()
    if "player_name" in data and data["player_name"]:
        return data["player_name"]
    name = (
        os.getenv("CASTLE_PONG_PLAYER")
        or getpass.getuser()
        or "Player"
    )
    data["player_name"] = name
    _write_player_data(data)
    return name

def set_player_name(name: str):
    """Set the player's name explicitly."""
    data = _player_data()
    data["player_name"] = name
    _write_player_data(data)

def is_new_high(score: int) -> bool:
    """True if *score* beats the stored personal best."""
    return score > _player_data().get("high_score", 0)

def update_high_score(score: int, wave: int):
    data = _player_data()
    data["high_score"] = int(score)
    data["high_wave"] = int(wave)
    _write_player_data(data)


def _read_api_key() -> str:
    """Return a Google Sheets API key from env or local file, if present."""
    key = os.getenv("GOOGLE_SHEETS_API_KEY")
    if key:
        return key.strip()
    if os.path.exists("google_api_key.txt"):
        with open("google_api_key.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def submit_score(score: int, wave: int) -> bool:
    """Submit via public Google Form (no auth, 3-second timeout)."""
    try:
        form_data = {
            ENTRY_PLAYER: get_player_name(),
            ENTRY_SCORE:  str(score),
            ENTRY_WAVE:   str(wave),
            ENTRY_DATE:   datetime.datetime.utcnow().isoformat(),
        }
        data = urllib.parse.urlencode(form_data).encode()
        urllib.request.urlopen(FORM_URL, data=data, timeout=3)
        print("[Leaderboard] Submitted via Google Form")
        return True
    except Exception as e:
        print("[Leaderboard] Form-submit error:", e)
        return False


def handle_end_of_wave(score: int, wave: int):
    """Update local high-score data and submit remotely if it is a record."""
    if is_new_high(score):
        print("[Leaderboard] New personal best:", score)
        update_high_score(score, wave)

        # run submission in a background thread so gameplay isn’t blocked
        threading.Thread(target=submit_score, args=(score, wave), daemon=True).start()

# --------------------- Public Fetch Helpers ---------------------------

_csv_cache: dict[str, tuple[int, list[list[str]]]] = {}


def _download_csv() -> list[list[str]]:
    """Download the entire sheet as CSV and return it parsed.

    Very lightweight (no auth) because the sheet is public.  Result is
    cached for 60 seconds to avoid spamming Google on repeated menu
    draws.
    """
    import time, csv, io

    now = int(time.time())
    if CSV_URL in _csv_cache and now - _csv_cache[CSV_URL][0] < 60:
        return _csv_cache[CSV_URL][1]

    try:
        with urllib.request.urlopen(CSV_URL, timeout=5) as resp:
            data = resp.read().decode("utf-8", errors="replace")
        rows = list(csv.reader(io.StringIO(data)))
        _csv_cache[CSV_URL] = (now, rows)
        return rows
    except Exception as e:
        print("[Leaderboard] CSV fetch error:", e)
        return []


def get_top_scores(wave: int, limit: int = 10):
    """Return a list of dicts with the top *limit* scores for *wave*.

    Each dict has keys: name, score, wave, date.
    """
    rows = _download_csv()
    if not rows:
        return []

    header = [h.strip().lower() for h in rows[0]]

    # Determine column indices dynamically (handles Timestamp column shift)
    try:
        idx_player = header.index("player")
        idx_score  = header.index("score")
        idx_wave   = header.index("wave")
    except ValueError:
        # Header row doesn’t match expected columns
        return []

    idx_date = header.index("date") if "date" in header else None

    results = []
    for r in rows[1:]:
        if len(r) <= max(idx_player, idx_score, idx_wave):
            continue
        try:
            w = int(r[idx_wave])
            s = int(r[idx_score])
        except ValueError:
            continue
        if w == wave:
            results.append({
                "name": r[idx_player] or "Anonymous",
                "score": s,
                "wave": w,
                "date": r[idx_date] if idx_date is not None and idx_date < len(r) else "",
            })
    results.sort(key=lambda d: d["score"], reverse=True)
    return results[:limit] 