
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE_URL = "https://za.national-lottery.com"
SOURCE_URL = "https://za.national-lottery.com/results"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# Map titles to slugs used in homepage
SLUG_MAP = {
    "uk49s lunchtime": "uk49s-lunchtime",
    "uk 49s lunchtime": "uk49s-lunchtime",
    "lunchtime": "uk49s-lunchtime",
    "uk49s teatime": "uk49s-teatime",
    "uk 49s teatime": "uk49s-teatime",
    "teatime": "uk49s-teatime",
    "uk49s brunchtime": "uk49s-brunchtime",
    "brunchtime": "uk49s-brunchtime",
    "uk49s drivetime": "uk49s-drivetime",
    "drivetime": "uk49s-drivetime",
}

def fetch_results():
    print(f"Scraping {SOURCE_URL}...")
    results = []
    try:
        res = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")

        # Find all draw sections
        for h in soup.find_all(["h2","h3","h4"]):
            title = h.get_text().strip().lower()
            if title not in SLUG_MAP:
                continue
            slug = SLUG_MAP[title]
            
            # Find parent containing balls
            parent = h.find_parent("div")
            tries = 0
            while parent and len(parent.select(".ball, .draw-ball, ul.numbers li, .balls span")) == 0 and tries < 5:
                parent = parent.find_parent("div")
                tries+=1
            if not parent:
                continue
            
            ball_els = parent.select(".ball, .draw-ball, ul.numbers li, .balls span")
            balls = []
            for b in ball_els:
                txt = b.get_text().strip()
                if txt.isdigit():
                    balls.append(int(txt))
            
            if len(balls) < 6:
                continue

            # Date extraction
            text = parent.get_text()
            date_match = re.search(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})", text, re.I)
            date_str = date_match.group(1) if date_match else datetime.now().strftime("%d %B %Y")
            try:
                # Convert to long format 29 September 2026
                dt = datetime.strptime(date_str, "%d %b %Y")
                date_long = dt.strftime("%d %B %Y")
            except:
                try:
                    dt = datetime.strptime(date_str, "%d %B %Y")
                    date_long = dt.strftime("%d %B %Y")
                except:
                    date_long = date_str

            # Format: first 6 main, last booster
            main = balls[:6]
            bonus = balls[6] if len(balls) >=7 else balls[-1]
            if len(balls) == 6:
                # if only 6, no booster separate, use last as booster? but keep logic
                main = balls[:6]
                bonus = None
            
            # For this homepage we need numbers as 2-digit strings
            numbers = [f"{n:02d}" for n in main[:6]]
            booster = f"{bonus:02d}" if bonus else (f"{balls[-1]:02d}" if len(balls)>6 else "00")
            if len(balls) == 6:
                booster = f"{balls[-1]:02d}"  # fallback, but will duplicate; better keep as last
                numbers = [f"{n:02d}" for n in balls[:5]]
                # Actually for 6 balls only, first 5 main + 1 booster? No, keep 6 as main and booster separate logic:
                numbers = [f"{n:02d}" for n in balls[:6]]
                booster = numbers[-1]
                numbers = numbers[:6]

            # Ensure booster is not in main if 7 balls
            if len(balls) >=7:
                numbers = [f"{n:02d}" for n in balls[:6]]
                booster = f"{balls[6]:02d}"

            results.append({
                "slug": slug,
                "numbers": numbers,
                "bonus": booster,
                "dateLong": date_long,
                "date": date_long
            })
            print(f"Found {slug}: {numbers} + {booster} - {date_long}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()

    # Deduplicate by slug, keep first
    seen = {}
    for r in results:
        if r["slug"] not in seen:
            seen[r["slug"]] = r
    final = list(seen.values())
    
    # If some slugs missing, add dummy to avoid 404 blank
    for slug in ["uk49s-lunchtime","uk49s-teatime","uk49s-brunchtime","uk49s-drivetime"]:
        if slug not in seen:
            final.append({
                "slug": slug,
                "numbers": ["00","00","00","00","00","00"],
                "bonus": "00",
                "dateLong": datetime.now().strftime("%d %B %Y")
            })

    return final

if __name__ == "__main__":
    data = fetch_results()
    with open("results.json","w") as f:
        json.dump(data, f, indent=2)
    print(f"results.json written with {len(data)} items")
