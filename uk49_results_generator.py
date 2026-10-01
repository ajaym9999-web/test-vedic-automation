
import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/124"}

URLS = {
    "uk49s-lunchtime": "https://za.national-lottery.com/amp/uk-49s/results/lunchtime",
    "uk49s-teatime": "https://za.national-lottery.com/amp/uk-49s/results/teatime",
    "uk49s-brunchtime": "https://za.national-lottery.com/amp/uk-49s/results/brunchtime",
    "uk49s-drivetime": "https://za.national-lottery.com/amp/uk-49s/results/drivetime",
}

def scrape_one(slug, url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        text = r.text
        date_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+\d{1,2}\s+\w+\s+\d{4}', text, re.I)
        date_long = date_match.group(0).replace(',', '').strip() if date_match else datetime.now().strftime("%d %B %Y")
        try:
            parts = date_long.split()
            if parts[0].lower() in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']:
                date_long = ' '.join(parts[1:])
        except:
            pass

        soup = BeautifulSoup(text, "html.parser")
        numbers = []
        for li in soup.find_all(string=re.compile(r'^\s*\d{1,2}\s*$')):
            t = li.strip()
            if t.isdigit() and 1 <= int(t) <= 49:
                numbers.append(int(t))

        if len(numbers) < 6:
            numbers = [int(n) for n in re.findall(r'-\s*(\d{1,2})\s*(?:\n|<)', text) if 1 <= int(n) <= 49]

        if len(numbers) >= 7:
            main = numbers[:6]
            bonus = numbers[6]
        elif len(numbers) == 6:
            main = numbers[:6]
            bonus = numbers[-1]
        else:
            print(f"{slug}: Not enough numbers found at {url} -> {numbers}")
            return None

        main_sorted = sorted(main)
        return {
            "slug": slug,
            "numbers": [f"{n:02d}" for n in main_sorted[:6]],
            "bonus": f"{bonus:02d}",
            "dateLong": date_long,
            "date": date_long,
            "source": url
        }
    except Exception as e:
        print(f"Error {slug}: {e}")
        return None

def main():
    # Load old results.json if exists - to keep kal ka data
    old_by_slug = {}
    if os.path.exists("results.json"):
        try:
            with open("results.json","r") as f:
                old = json.load(f)
                for item in old:
                    if "slug" in item:
                        old_by_slug[item["slug"]] = item
            print(f"Loaded old results.json with {len(old_by_slug)} draws - will use as fallback for kal ka data")
        except Exception as e:
            print(f"Could not load old results.json: {e}")

    results = []
    for slug, url in URLS.items():
        print(f"Scraping {slug} from {url}")
        res = scrape_one(slug, url)
        if res:
            print(f"  OK LIVE: {res['numbers']} + {res['bonus']} - {res['dateLong']}")
            results.append(res)
        else:
            alt_url = url.replace('/amp/', '/')
            print(f"  Trying fallback {alt_url}")
            res2 = scrape_one(slug, alt_url)
            if res2:
                print(f"  OK FALLBACK: {res2['numbers']} - {res2['dateLong']}")
                results.append(res2)
            else:
                # KAL KA DATA LOGIC: agar aaj ka nahi mila to kal wala purana hi rakho, khali mat dikhao
                if slug in old_by_slug:
                    print(f"  -> Aaj ka nahi mila, KAL KA DATA rakh raha hu for {slug}: {old_by_slug[slug]['numbers']} - {old_by_slug[slug].get('dateLong')}")
                    results.append(old_by_slug[slug])
                else:
                    print(f"  -> Failed {slug} and no old data found, skipping")

    # Final safety: if still empty, keep all old data
    if len(results) == 0 and old_by_slug:
        print("All scrapes failed, keeping entire old results.json to avoid empty page")
        results = list(old_by_slug.values())

    with open("results.json","w") as f:
        json.dump(results, f, indent=2)
    print(f"\nresults.json written with {len(results)} draws")

    # --- 10 DAYS HISTORY LOGIC ---
    hist_path = "history.json"
    history = {}
    if os.path.exists(hist_path):
        try:
            with open(hist_path,"r") as hf:
                history = json.load(hf)
        except:
            history = {}
    for r in results:
        slug = r["slug"]
        lst = history.get(slug, [])
        # agar same date + same numbers already hai to duplicate mat karo
        if lst and lst[0].get("dateLong")==r["dateLong"] and lst[0].get("numbers")==r["numbers"]:
            continue
        # draw number: last se +1, nahi to 2499 se start
        last_no = lst[0].get("drawNo", 2499) if lst else 2499
        entry = {
            "drawNo": last_no+1 if lst else 2500,
            "numbers": r["numbers"],
            "bonus": r["bonus"],
            "dateLong": r["dateLong"],
            "date": r["date"]
        }
        # fix: pehli baar me drawNo sahi rakho
        if not lst:
            # purane screenshot me #2499 tha, isliye 2500 se start
            entry["drawNo"] = 2500
        lst.insert(0, entry)
        history[slug] = lst[:10]  # sirf last 10 rakho
    with open(hist_path,"w") as hf:
        json.dump(history, hf, indent=2)
    print(f"history.json written with 10-days history per draw")
    print(json.dumps(history, indent=2))

if __name__ == "__main__":
    main()
