import base64
from datetime import datetime
import json
import os
import re
import requests
from bs4 import BeautifulSoup

# ================= 1. Configuration =================
WP_DOMAIN = os.getenv("WP_DOMAIN", "https://test.vedicvibe.online")
PAGE_ID_HOME = os.getenv("WP_PAGE_ID", "20")
PAGE_ID_LUNCHTIME = "74"  # Dedicated child page for UK49s Lunchtime

WP_DOMAIN = os.getenv("WP_DOMAIN", "https://test.vedicvibe.online")
WP_PAGE_ENDPOINT_HOME = f"{WP_DOMAIN}/wp-json/wp/v2/pages/{PAGE_ID_HOME}"
WP_PAGE_ENDPOINT_LUNCHTIME = f"{WP_DOMAIN}/wp-json/wp/v2/pages/{PAGE_ID_LUNCHTIME}"

WP_USER = os.getenv("WP_USER", os.getenv("WP_USERNAME", "admin"))
APP_PASSWORD = os.getenv("APP_PASSWORD", os.getenv("WP_APP_PASSWORD", ""))

BASE_URL = "https://za.national-lottery.com"
SOURCE_URL = "https://za.national-lottery.com/results"
LUNCHTIME_HISTORY_URL = "https://za.national-lottery.com/uk-49s/results/lunchtime"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# 11 Core Lottery Config
CORE_GAMES = {
    "UK49s Lunchtime": {
        "aliases": ["uk49s lunchtime", "uk 49s lunchtime", "lunchtime"],
        "booster": True,
        "special_color": "#f59e0b",
        "time": "Daily • 12:45 PM UTC",
        "internal_link": "https://test.vedicvibe.online/uk49s-lunchtime-results-history/"
    },
    "UK49s Teatime": {"aliases": ["uk49s teatime", "uk 49s teatime", "teatime"], "booster": True, "special_color": "#f59e0b", "time": "Daily • 05:49 PM UTC"},
    "UK49s Brunchtime": {"aliases": ["uk49s brunchtime", "uk 49s brunchtime", "brunchtime"], "booster": True, "special_color": "#f59e0b", "time": "Daily • 10:49 AM UTC"},
    "UK49s Drivetime": {"aliases": ["uk49s drivetime", "uk 49s drivetime", "drivetime"], "booster": True, "special_color": "#f59e0b", "time": "Daily • 04:49 PM UTC"},
    "Daily Lotto": {"aliases": ["daily lotto"], "booster": False, "special_color": "", "time": "Daily • 09:00 PM SAST"},
    "Daily Lotto Plus": {"aliases": ["daily lotto plus"], "booster": False, "special_color": "", "time": "Daily • 09:00 PM SAST"},
    "PowerBall": {"aliases": ["powerball"], "booster": True, "special_color": "#dc2626", "time": "Tue, Fri • 09:00 PM SAST"},
    "PowerBall PLUS": {"aliases": ["powerball plus", "powerball xtra"], "booster": True, "special_color": "#dc2626", "time": "Tue, Fri • 09:00 PM SAST"},
    "Lotto": {"aliases": ["lotto"], "booster": True, "special_color": "#f59e0b", "time": "Wed, Sat • 08:57 PM SAST"},
    "Lotto Plus 1": {"aliases": ["lotto plus 1"], "booster": True, "special_color": "#f59e0b", "time": "Wed, Sat • 08:57 PM SAST"},
    "Lotto 5 Max": {"aliases": ["lotto 5 max", "lotto plus 2"], "booster": True, "special_color": "#f59e0b", "time": "Daily • 08:57 PM SAST"}
}

# ================= 2. Scrapers =================
def fetch_homepage_draws():
    print(f"Scraping central results from {SOURCE_URL}...")
    draw_results = {}
    try:
        res = requests.get(SOURCE_URL, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return draw_results

        soup = BeautifulSoup(res.text, "html.parser")

        for h in soup.find_all(["h2", "h3", "h4"]):
            raw_title = h.get_text().strip().lower()
            if not raw_title:
                continue

            matched_key = None
            for key, conf in CORE_GAMES.items():
                for alias in conf["aliases"]:
                    if alias == raw_title:
                        matched_key = key
                        break
                if matched_key:
                    break

            if not matched_key:
                continue

            parent = h.find_parent("div")
            while parent and len(parent.select(".ball, .draw-ball, .result-ball, ul.numbers li, .balls span")) == 0:
                parent = parent.find_parent("div")
                if not parent or parent.name == "body":
                    break

            if not parent:
                continue

            ball_elements = parent.select(".ball, .draw-ball, .result-ball, ul.numbers li, .balls span")
            balls = []
            for b in ball_elements:
                val = b.get_text().strip()
                if val.isdigit():
                    num = int(val)
                    balls.append(num)

            # Prefer internal link if configured, else default external
            cfg = CORE_GAMES[matched_key]
            if "internal_link" in cfg:
                target_link = cfg["internal_link"]
            else:
                link_tag = parent.find("a", href=True)
                raw_href = link_tag["href"] if link_tag else ""
                target_link = raw_href if raw_href.startswith("http") else (BASE_URL + raw_href if raw_href else "#")

            date_match = re.search(
                r"(\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                parent.get_text(),
                re.IGNORECASE
            )
            draw_date = date_match.group(1).strip() if date_match else datetime.now().strftime("%d %b %Y")

            if balls:
                if cfg["booster"] and len(balls) >= 2:
                    main_balls = [f"{n:02d}" for n in balls[:-1]]
                    booster_ball = f"{balls[-1]:02d}"
                else:
                    main_balls = [f"{n:02d}" for n in balls]
                    booster_ball = None

                draw_results[matched_key] = {
                    "date": draw_date,
                    "main_balls": main_balls,
                    "booster": booster_ball,
                    "link": target_link,
                    "time": cfg["time"],
                    "special_color": cfg["special_color"]
                }

    except Exception as e:
        print(f"Homepage scraper error: {e}")

    return draw_results


def fetch_lunchtime_history():
    print(f"Scraping history from {LUNCHTIME_HISTORY_URL}...")
    history_items = []
    try:
        res = requests.get(LUNCHTIME_HISTORY_URL, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return history_items

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            return history_items

        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue

            # Extract date
            date_text = cols[0].get_text().strip()
            if "Draw Date" in date_text or not date_text:
                continue

            # Clean date string (e.g. Wednesday 16 September 2026)
            cleaned_date = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)", r"\1 ", date_text)

            # Extract ball numbers in this row
            balls_in_row = [b.get_text().strip() for b in cols[1].find_all(["li", "span"]) if b.get_text().strip().isdigit()]
            if not balls_in_row:
                # Fallback to text split
                balls_in_row = [part for part in cols[1].get_text().split() if part.isdigit()]

            if len(balls_in_row) >= 6:
                main_balls = [f"{int(x):02d}" for x in balls_in_row[:6]]
                booster = f"{int(balls_in_row[6]):02d}" if len(balls_in_row) >= 7 else None
                history_items.append({
                    "date": cleaned_date,
                    "main_balls": main_balls,
                    "booster": booster
                })

    except Exception as e:
        print(f"History scraper error: {e}")

    return history_items

# ================= 3. Visual Builders =================
def render_balls(balls, special_ball=None, special_color="#f59e0b", size="normal"):
    if not balls:
        return '<span style="color: #64748b; font-size: 13px; font-weight: 600;">Awaiting latest draw...</span>'

    dim = "clamp(34px, 8.2vw, 42px)" if size == "normal" else "30px"
    font = "clamp(13px, 3.8vw, 15px)" if size == "normal" else "12px"

    style = (
        f"width: {dim}; height: {dim}; "
        "border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; "
        f"font-weight: 700; font-size: {font}; color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.12); flex-shrink: 0;"
    )
    b_html = "".join([f'<span style="{style} background: linear-gradient(135deg, #2563eb, #1d4ed8); margin: 0 2px;">{b}</span>' for b in balls])
    if special_ball:
        b_html += f'<span style="{style} background: linear-gradient(135deg, {special_color}, #991b1b); margin: 0 2px;">{special_ball}</span>'
    return b_html

def ad_slot(label):
    return f"""
    <div style="margin: 20px 0; text-align: center; clear: both; width: 100%;">
        <span style="font-size: 10px; color: #94a3b8; letter-spacing: 1px; text-transform: uppercase; font-weight: 600; display: block; margin-bottom: 4px;">Advertisement</span>
        <div style="border: 1px dashed #cbd5e1; background: #ffffff; border-radius: 8px; padding: 16px 10px; min-height: 85px; display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 13px;">
            [AdSpace • {label}]
        </div>
    </div>
    """

def make_card(name, data, is_hero=False):
    today = datetime.now().strftime("%d %b %Y")
    d_date = data["date"] if data else today
    d_time = data["time"] if data else CORE_GAMES.get(name, {}).get("time", "Daily")
    spec_color = data.get("special_color", "#f59e0b") if data else CORE_GAMES.get(name, {}).get("special_color", "#f59e0b")
    balls_html = render_balls(data["main_balls"], data.get("booster"), spec_color) if data else render_balls([])
    link_url = data.get("link", "#") if data else "#"

    btn_html = f"""<a href="{link_url}" target="_blank" rel="noopener noreferrer" style="background: #2563eb; color: #ffffff; text-decoration: none; font-size: 11px; font-weight: 700; padding: 6px 12px; border-radius: 5px; text-transform: uppercase; letter-spacing: 0.3px; display: inline-block; white-space: nowrap;">History & Stats →</a>"""

    if is_hero:
        return f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px 16px; text-align: center; width: 100%; box-sizing: border-box; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04); margin-bottom: 18px;">
            <h2 style="color: #0f172a; font-size: 22px; letter-spacing: 0.5px; margin: 0 0 4px 0; text-transform: uppercase; font-weight: 800;">{name}</h2>
            <div style="color: #2563eb; font-size: 13px; font-weight: 700; margin-bottom: 4px;">Draw Date: {d_date}</div>
            <div style="color: #64748b; font-size: 12px; font-weight: 500; margin-bottom: 16px;">{d_time}</div>
            <div style="display: flex; justify-content: center; align-items: center; gap: clamp(4px, 1.4vw, 8px); margin-bottom: 18px; flex-wrap: nowrap; overflow-x: auto; padding: 4px 0;">
                {balls_html}
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f5f9; padding-top: 14px; gap: 8px;">
                <span style="border: 1px solid #10b981; background: #ecfdf5; color: #065f46; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 4px; text-transform: uppercase;">Official Result</span>
                {btn_html}
            </div>
        </div>
        """

    return f"""
    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 14px; text-align: center; flex: 1 1 calc(50% - 14px); min-width: 290px; box-sizing: border-box; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04); margin-bottom: 16px;">
        <h3 style="color: #0f172a; font-size: 18px; letter-spacing: 0.5px; margin: 0 0 4px 0; text-transform: uppercase; font-weight: 700;">{name}</h3>
        <div style="color: #2563eb; font-size: 13px; font-weight: 700; margin-bottom: 4px;">Draw Date: {d_date}</div>
        <div style="color: #64748b; font-size: 12px; font-weight: 500; margin-bottom: 16px;">{d_time}</div>
        <div style="display: flex; justify-content: center; align-items: center; gap: clamp(3px, 1.2vw, 8px); margin-bottom: 16px; flex-wrap: nowrap; overflow-x: auto; padding: 4px 0;">
            {balls_html}
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f5f9; padding-top: 12px; gap: 8px;">
            <span style="border: 1px solid #10b981; background: #ecfdf5; color: #065f46; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px; text-transform: uppercase;">Official Result</span>
            {btn_html}
        </div>
    </div>
    """

# ================= 4. WordPress Exporter =================
def update_wordpress_page(endpoint, html_content, auth_headers, page_name="Page"):
    payload = {"content": html_content}
    try:
        res = requests.post(endpoint, headers=auth_headers, json=payload, timeout=25)
        print(f"[{page_name}] WP Update Status: {res.status_code}")
    except Exception as e:
        print(f"[{page_name}] Error publishing: {e}")


def build_and_push_lunchtime_page(draw_data, history_data, auth_headers):
    hero_card = make_card("UK49s Lunchtime", draw_data.get("UK49s Lunchtime"), is_hero=True)

    # Build history rows (Limit to latest 15 draws)
    table_rows = ""
    for item in history_data[:15]:
        balls_row_html = render_balls(item["main_balls"], item.get("booster"), special_color="#f59e0b", size="small")
        table_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; background: #ffffff;">
            <td style="padding: 12px 14px; font-weight: 600; color: #1e293b; font-size: 13px; white-space: nowrap;">{item['date']}</td>
            <td style="padding: 10px 14px; text-align: right; display: flex; justify-content: flex-end; align-items: center;">{balls_row_html}</td>
        </tr>
        """

    page_html = f"""
<div style="background-color: #f1f5f9; padding: 18px 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 80vh; width: 100%; max-width: 900px; margin: 0 auto; box-sizing: border-box;">

    <!-- BACK TO HOME BUTTON -->
    <div style="margin-bottom: 14px;">
        <a href="https://test.vedicvibe.online/" style="color: #2563eb; text-decoration: none; font-size: 13px; font-weight: 600;">← Back to All Results</a>
    </div>

    <!-- LATEST DRAW HERO CARD -->
    {hero_card}

    <!-- MID AD -->
    {ad_slot("Lunchtime Content Banner")}

    <!-- HISTORY SECTION -->
    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04); margin-top: 18px;">
        <div style="margin-bottom: 16px;">
            <h3 style="color: #0f172a; font-size: 18px; margin: 0 0 4px 0; font-weight: 700; text-transform: uppercase;">UK49s Lunchtime Past Draw History</h3>
            <p style="color: #64748b; font-size: 12px; margin: 0;">Verified previous winning numbers & booster balls.</p>
        </div>

        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                        <th style="padding: 10px 14px; font-size: 12px; color: #475569; text-transform: uppercase; font-weight: 700;">Draw Date</th>
                        <th style="padding: 10px 14px; font-size: 12px; color: #475569; text-transform: uppercase; font-weight: 700; text-align: right;">Winning Numbers</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>

    <!-- BOTTOM AD -->
    {ad_slot("Lunchtime Bottom Banner")}

</div>
"""
    update_wordpress_page(WP_PAGE_ENDPOINT_LUNCHTIME, page_html, auth_headers, "Lunchtime Page 74")


def build_and_push_homepage(draw_data, auth_headers):
    hero_html = make_card("UK49s Lunchtime", draw_data.get("UK49s Lunchtime"), is_hero=True)

    priority_keys = ["UK49s Teatime", "UK49s Brunchtime", "UK49s Drivetime", "Daily Lotto"]
    priority_cards = "".join([make_card(k, draw_data.get(k)) for k in priority_keys])

    secondary_keys = ["Daily Lotto Plus", "PowerBall", "PowerBall PLUS", "Lotto", "Lotto Plus 1", "Lotto 5 Max"]
    secondary_cards = "".join([make_card(k, draw_data.get(k)) for k in secondary_keys])

    homepage_html = f"""
<div style="background-color: #f1f5f9; padding: 18px 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 80vh; width: 100%; max-width: 1060px; margin: 0 auto; box-sizing: border-box;">

    <!-- TOP AD -->
    {ad_slot("Top Leaderboard (Responsive)")}

    <!-- HERO SECTION -->
    {hero_html}

    <!-- ROW 2 & 3: UK49s & SA DAILY LOTTO -->
    <div style="display: flex; flex-wrap: wrap; gap: 14px; justify-content: space-between;">
        {priority_cards}
    </div>

    <!-- IN-FEED AD -->
    {ad_slot("In-Feed Mid Banner")}

    <!-- SECTION TITLE: NATIONAL LOTTERIES -->
    <div style="margin: 24px 0 14px 0; text-align: center;">
        <h2 style="color: #0f172a; font-size: 20px; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px; margin: 0;">South African National Lotteries</h2>
        <p style="color: #64748b; font-size: 13px; margin: 4px 0 0 0;">Official Winning Numbers & Breakdown History</p>
    </div>

    <!-- EXPANSION LOTTERIES (POWERBALL & LOTTO PLUS) -->
    <div style="display: flex; flex-wrap: wrap; gap: 14px; justify-content: space-between;">
        {secondary_cards}
    </div>

    <!-- BOTTOM AD -->
    {ad_slot("Bottom Sticky Banner")}

</div>
"""
    update_wordpress_page(WP_PAGE_ENDPOINT_HOME, homepage_html, auth_headers, "Homepage 20")

# ================= Execution =================
if __name__ == "__main__":
    if not APP_PASSWORD:
        raise ValueError("APP_PASSWORD is missing!")

    token = base64.b64encode(f"{WP_USER}:{APP_PASSWORD}".encode()).decode("utf-8")
    auth_headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    # 1. Fetch live draws
    results = fetch_homepage_draws()
    print(f"Live draws parsed: {len(results)}")

    # 2. Fetch history for Lunchtime
    lunchtime_history = fetch_lunchtime_history()
    print(f"Lunchtime history records parsed: {len(lunchtime_history)}")

    # 3. Update Homepage (Page 20)
    build_and_push_homepage(results, auth_headers)

    # 4. Update Child Page (Page 74)
    build_and_push_lunchtime_page(results, lunchtime_history, auth_headers)
