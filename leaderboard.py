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
# New Google Form field – total session duration in seconds (replace with actual ID)
ENTRY_DURATION = "entry.2117623304"

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

# --------------------------------------------------------------------
#  Per-wave personal-best helpers
# --------------------------------------------------------------------


def _wave_records() -> dict:
    """Return dict of wave -> {score, duration_ms}."""
    return _player_data().get("wave_records", {})


def _save_wave_records(records: dict):
    data = _player_data()
    data["wave_records"] = records
    _write_player_data(data)


def get_wave_best(wave: int):
    recs = _wave_records()
    return recs.get(str(wave))  # returns None or dict


def is_new_wave_best(wave: int, score: int, duration_ms: int) -> bool:
    """Return True if (wave,score,duration) beats stored best for that wave.

    Criteria: higher score wins; if equal score then shorter duration wins.
    """
    best = get_wave_best(wave)
    if best is None:
        return True
    if score > best.get("score", 0):
        return True
    if score == best.get("score", 0) and duration_ms < best.get("duration_ms", 10**9):
        return True
    return False


def update_wave_best(wave: int, score: int, duration_ms: int):
    recs = _wave_records()
    recs[str(wave)] = {"score": int(score), "duration_ms": int(duration_ms)}
    _save_wave_records(recs)

# --------------------------------------------------------------------
#  New session-level record helpers
# --------------------------------------------------------------------


def _best_session_data():
    """Return stored best-session dictionary or default."""
    d = _player_data()
    return {
        "wave": d.get("best_wave", 0),
        "duration_ms": d.get("best_duration_ms", None),
        "score": d.get("best_score", 0),
    }


def is_new_session(wave: int, duration_ms: int, score: int) -> bool:
    """Return True if (wave, duration, score) is better than stored best.

    Comparison order:
      1. Higher *wave* reached wins
      2. For equal wave, shorter *duration_ms* wins
      3. Tie-break by higher *score* wins
    """
    best = _best_session_data()
    if wave > best["wave"]:
        return True
    if wave == best["wave"]:
        if best["duration_ms"] is None or duration_ms < best["duration_ms"]:
            return True
        if duration_ms == best["duration_ms"] and score > best["score"]:
            return True
    return False


def update_best_session(wave: int, duration_ms: int, score: int):
    """Persist the given session as the new personal best."""
    data = _player_data()
    data["best_wave"] = int(wave)
    data["best_duration_ms"] = int(duration_ms)
    data["best_score"] = int(score)
    _write_player_data(data)

def update_high_score(score: int, wave: int):
    data = _player_data()
    data["high_score"] = int(score)
    data["high_wave"] = int(wave)
    _write_player_data(data)

# --------------------------------------------------------------------
#  Submission helpers (Google Form) – SESSION-LEVEL
# --------------------------------------------------------------------


def _format_duration(duration_ms: int) -> str:
    """Return duration in seconds with one-decimal precision as string."""
    return f"{duration_ms / 1000:.1f}"


def submit_session(score: int, wave: int, duration_ms: int) -> bool:
    """Submit session record via public Google Form (no auth)."""
    try:
        form_data = {
            ENTRY_PLAYER:    get_player_name(),
            ENTRY_SCORE:     str(score),
            ENTRY_WAVE:      str(wave),
            ENTRY_DURATION:  _format_duration(duration_ms),
            ENTRY_DATE:      datetime.datetime.utcnow().isoformat(),
        }
        data = urllib.parse.urlencode(form_data).encode()
        urllib.request.urlopen(FORM_URL, data=data, timeout=3)
        print("[Leaderboard] Submitted session via Google Form")
        return True
    except Exception as e:
        print("[Leaderboard] Session submit error:", e)
        return False


def handle_session_end(score: int, wave: int, duration_ms: int):
    """Public helper – call once when the player's run ends."""
    if is_new_session(wave, duration_ms, score):
        print("[Leaderboard] New best session:", (
            f"wave={wave}", f"duration_ms={duration_ms}", f"score={score}"))
        update_best_session(wave, duration_ms, score)

        # Submit asynchronously so main thread isn't blocked
        threading.Thread(target=submit_session,
                         args=(score, wave, duration_ms),
                         daemon=True).start()


def submit_wave_score(score: int, wave: int, duration_ms: int) -> bool:
    """Submit wave personal best via Google Form (no auth)."""
    print(f"[Leaderboard] Attempting to submit wave {wave}: score={score}, duration_ms={duration_ms}")
    try:
        form_data = {
            ENTRY_PLAYER:   get_player_name(),
            ENTRY_SCORE:    str(score),
            ENTRY_WAVE:     str(wave),
            ENTRY_DURATION: _format_duration(duration_ms),
            ENTRY_DATE:     datetime.datetime.utcnow().isoformat(),
        }
        print(f"[Leaderboard] Form data: {form_data}")
        data = urllib.parse.urlencode(form_data).encode()
        print(f"[Leaderboard] Encoded data: {data}")
        urllib.request.urlopen(FORM_URL, data=data, timeout=3)
        print(f"[Leaderboard] Submitted wave {wave} PB")
        return True
    except Exception as e:
        print("[Leaderboard] Wave submit error:", e)
        return False


def handle_end_of_wave(score: int, wave: int, duration_ms: int):
    """Update per-wave PB and submit if it's a new record."""
    print(f"[Leaderboard] handle_end_of_wave called: score={score}, wave={wave}, duration_ms={duration_ms}")
    if is_new_wave_best(wave, score, duration_ms):
        print(f"[Leaderboard] New wave {wave} best detected!")
        update_wave_best(wave, score, duration_ms)
        threading.Thread(target=submit_wave_score,
                         args=(score, wave, duration_ms),
                         daemon=True).start()
    else:
        print(f"[Leaderboard] Not a new best for wave {wave}")
        best = get_wave_best(wave)
        print(f"[Leaderboard] Current best: {best}")

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


def get_top_scores(_unused_wave: int = 0, limit: int = 10):
    """Return top leaderboard entries globally (single board).

    Sorting priority: highest *wave*, then shortest *duration*, then highest *score*.
    Returns list of dicts: name, wave, duration (sec), score, date.
    """
    rows = _download_csv()
    if not rows:
        return []

    header = [h.strip().lower() for h in rows[0]]
    # Required columns
    try:
        idx_player   = header.index("player")
        idx_score    = header.index("score")
        idx_wave     = header.index("wave")
        idx_duration = header.index("duration")  # seconds
    except ValueError:
        return []  # header mismatch

    idx_date = header.index("date") if "date" in header else None

    results = []
    for r in rows[1:]:
        if len(r) <= max(idx_player, idx_score, idx_wave, idx_duration):
            continue
        try:
            wave = int(r[idx_wave])
            score = int(r[idx_score])
            duration_sec = float(r[idx_duration])
        except ValueError:
            continue

        results.append({
            "name": r[idx_player] or "Anonymous",
            "wave": wave,
            "duration": duration_sec,
            "score": score,
            "date": r[idx_date] if idx_date is not None and idx_date < len(r) else "",
        })

    # Sorting: highest wave, then shortest duration, then highest score
    results.sort(key=lambda d: (-d["wave"], d["duration"], -d["score"]))
    return results[:limit] 