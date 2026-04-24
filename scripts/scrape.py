import os
import json
import base64
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone

PLAYERS = [
    {"name": "マチュ",          "tag": "KR2",  "url": "https://lol.ps/summoner/%E3%83%9E%E3%83%81%E3%83%A5%20_KR2?region=kr"},
    {"name": "Squirt1e",       "tag": "2004", "url": "https://lol.ps/summoner/Squirt1e%20_2004?region=kr"},
    {"name": "leave me alone", "tag": "2005", "url": "https://lol.ps/summoner/leave%20me%20alone%20_2005?region=kr"},
]

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

TIER_ORDER = {
    "Challenger": 9, "Grandmaster": 8, "Master": 7,
    "Diamond": 6, "Emerald": 5, "Platinum": 4,
    "Gold": 3, "Silver": 2, "Bronze": 1, "Iron": 0,
    "Unranked": -1, "Error": -2,
}

# Wait between players (seconds) - longer to avoid 429
PLAYER_WAIT = 60

# Gemini retry: wait 60s, 120s, 180s
RETRY_WAITS = [60, 120, 180]


def screenshot_page(url: str) -> bytes:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception:
            page.goto(url, timeout=45000)
            page.wait_for_timeout(8000)
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollBy(0, 400)")
        page.wait_for_timeout(1000)
        screenshot = page.screenshot(full_page=True)
        browser.close()
        return screenshot


def parse_with_gemini(image_bytes: bytes, player_name: str) -> dict:
    image_b64 = base64.b64encode(image_bytes).decode()

    prompt = (
        f"This is a screenshot of a League of Legends profile page for player '{player_name}' on lol.ps.\n"
        "Find the ranked solo/duo queue statistics on this page.\n"
        "Wins and losses may appear as: '47W 36L', '47Win 36Loss', or numbers next to W/L labels.\n"
        "Return ONLY a valid JSON object, no markdown, no explanation.\n"
        'Example: {"tier": "Master", "lp": 180, "wins": 47, "losses": 36}\n'
        "- tier: Iron/Bronze/Silver/Gold/Platinum/Emerald/Diamond/Master/Grandmaster/Challenger\n"
        "- lp: integer\n"
        "- wins: integer\n"
        "- losses: integer\n"
        'If not found: {"tier": "Unranked", "lp": 0, "wins": 0, "losses": 0}'
    )

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
            ]
        }]
    }

    data = json.dumps(body).encode("utf-8")

    for attempt, wait in enumerate(RETRY_WAITS):
        try:
            req = urllib.request.Request(
                GEMINI_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
            break  # success
        except urllib.error.HTTPError as e:
            code = e.code
            if code in (429, 503) and attempt < len(RETRY_WAITS) - 1:
                print(f"  HTTP {code}, waiting {wait}s before retry {attempt+2}/{len(RETRY_WAITS)}...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < len(RETRY_WAITS) - 1:
                print(f"  Error: {e}, waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                raise

    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)


def load_previous_data() -> dict:
    try:
        with open("docs/data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_history() -> list:
    try:
        with open("docs/history.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def main():
    previous = load_previous_data()
    prev_players = {p["name"]: p for p in previous.get("players", [])}

    players_data = []

    for idx, player in enumerate(PLAYERS):
        print(f"Processing {player['name']}...")

        # Wait between players (skip before first)
        if idx > 0:
            print(f"  Waiting {PLAYER_WAIT}s before next player...")
            time.sleep(PLAYER_WAIT)

        try:
            img = screenshot_page(player["url"])
            print(f"  Screenshot captured ({len(img)} bytes)")

            rank = parse_with_gemini(img, player["name"])
            print(f"  Parsed: {rank}")

            wins = rank.get("wins", 0)
            losses = rank.get("losses", 0)
            total = wins + losses
            winrate = round(wins / total * 100, 1) if total > 0 else 0.0

            prev = prev_players.get(player["name"])
            prev_wins = prev.get("wins", 0) if prev else 0
            prev_losses = prev.get("losses", 0) if prev else 0
            prev_lp_diff = prev.get("lp_diff", None) if prev else None

            # Only calculate new diff when games have been played (W or L changed)
            games_changed = (wins != prev_wins or losses != prev_losses)

            if (prev and prev.get("tier") == rank.get("tier")
                    and prev.get("tier") not in ("Error", "Unranked")
                    and games_changed):
                # Games played since last update - calculate fresh diff
                lp_diff = rank.get("lp", 0) - prev.get("lp", 0)
                print(f"  Games changed ({prev_wins}W/{prev_losses}L -> {wins}W/{losses}L), lp_diff={lp_diff}")
            elif not games_changed and prev_lp_diff is not None:
                # No games played - keep previous diff
                lp_diff = prev_lp_diff
                print(f"  No games played, keeping previous lp_diff={lp_diff}")
            else:
                lp_diff = None

            players_data.append({
                "name": player["name"],
                "tag": player["tag"],
                "url": player["url"],
                "tier": rank.get("tier", "Unranked"),
                "lp": rank.get("lp", 0),
                "lp_diff": lp_diff,
                "wins": wins,
                "losses": losses,
                "winrate": winrate,
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            # Fall back to previous data if available
            prev = prev_players.get(player["name"])
            if prev and prev.get("tier") not in ("Error",):
                print(f"  Using previous data for {player['name']}")
                players_data.append({
                    "name": player["name"],
                    "tag": player["tag"],
                    "url": player["url"],
                    "tier": prev.get("tier", "Unranked"),
                    "lp": prev.get("lp", 0),
                    "lp_diff": prev.get("lp_diff", None),
                    "wins": prev.get("wins", 0),
                    "losses": prev.get("losses", 0),
                    "winrate": prev.get("winrate", 0.0),
                    "stale": True,  # mark as carried-over data
                })
            else:
                players_data.append({
                    "name": player["name"],
                    "tag": player["tag"],
                    "url": player["url"],
                    "tier": "Error",
                    "lp": 0,
                    "lp_diff": None,
                    "wins": 0,
                    "losses": 0,
                    "winrate": 0.0,
                    "error": str(e),
                })

    players_data.sort(
        key=lambda p: (TIER_ORDER.get(p["tier"], -1), p["lp"]),
        reverse=True,
    )

    for i, p in enumerate(players_data):
        p["rank"] = i + 1

    now = datetime.now(timezone.utc).isoformat()
    output = {"updated_at": now, "players": players_data}

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\ndata.json written successfully.")

    valid = [p for p in players_data if p["tier"] != "Error"]
    # Only write history if at least one player has FRESH data (not carried-over stale data)
    fresh = [p for p in players_data if not p.get("stale") and p["tier"] != "Error"]
    if fresh:
        history = load_history()
        history.append({
            "updated_at": now,
            "players": [
                {
                    "name": p["name"],
                    "tier": p["tier"],
                    "lp": p["lp"],
                    "wins": p["wins"],
                    "losses": p["losses"],
                    "winrate": p["winrate"],
                    "rank": p["rank"],
                }
                for p in players_data
                if p["tier"] != "Error"
            ],
        })
        with open("docs/history.json", "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"history.json updated ({len(history)} entries).")
    else:
        print("No fresh data, skipping history entry.")

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
