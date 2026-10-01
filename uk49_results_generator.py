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
    # Load old history - yehi source of truth hai ab
    hist_path = "history.json"
    history = {}
    if os.path.exists(hist_path):
        try:
            with open(hist_path,"r") as hf:
                history = json.load(hf)
        except:
            history = {}

    old_by_slug = {}
    if os.path.exists("results.json"):
        try:
            with open("results.json","r") as f:
                old = json.load(f)
                for item in old:
                    if "slug" in item:
                        old_by_slug[item["slug"]] = item
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
                if slug in old_by_slug:
                    print(f"  -> Aaj ka nahi mila, KAL KA DATA rakh raha hu for {slug}: {old_by_slug[slug]['numbers']} - {old_by_slug[slug].get('dateLong')}")
                    results.append(old_by_slug[slug])
                else:
                    print(f"  -> Failed {slug} and no old data")

    if len(results) == 0 and old_by_slug:
        print("All scrapes failed, keeping entire old results.json")
        results = list(old_by_slug.values())

    # --- HISTORY UPDATE (pehle) ---
    for r in results:
        slug = r["slug"]
        lst = history.get(slug, [])
        if lst and lst[0].get("dateLong")==r["dateLong"] and lst[0].get("numbers")==r["numbers"]:
            continue
        last_no = lst[0].get("drawNo", 2480) if lst else 2480
        # agar history khali hai to 2488 se start, taaki aaj 1 Oct ko 2488 ban sake jaisa tere screenshot me hai
        entry = {
            "drawNo": (last_no+1) if lst else (lst[0].get("drawNo", 2488) if lst else 2488),
            "numbers": r["numbers"],
            "bonus": r["bonus"],
            "dateLong": r["dateLong"],
            "date": r["date"]
        }
        if not lst:
            entry["drawNo"] = 2488
        else:
            entry["drawNo"] = last_no+1
        lst.insert(0, entry)
        # date ke hisaab se sort karo taaki 1 Oct upar rahe, 30 Sep niche
        # duplicate date hatane ke liye dict use karo
        seen = {}
        dedup = []
        for item in lst:
            key = item["dateLong"]+"|"+",".join(item["numbers"])
            if key not in seen:
                seen[key]=True
                dedup.append(item)
        # date sort - newest first (parse)
        def parse_date(d):
            try:
                return datetime.strptime(d["dateLong"], "%d %B %Y")
            except:
                return datetime.min
        dedup.sort(key=parse_date, reverse=True)
        history[slug] = dedup[:10]

    with open(hist_path,"w") as hf:
        json.dump(history, hf, indent=2)
    print(f"history.json written")

    # --- RESULTS.JSON ko HISTORY se banao taaki homepage aur detail page SYNC rahe ---
    final_results = []
    for slug in URLS.keys():
        lst = history.get(slug, [])
        if lst:
            latest = lst[0]
            final_results.append({
                "slug": slug,
                "name": slug.replace("uk49s-","UK49s ").title(),
                "numbers": latest["numbers"],
                "bonus": latest["bonus"],
                "dateLong": latest["dateLong"],
                "date": latest["date"],
                "history": lst  # homepage bhi chaahe to history dekh sake
            })
        else:
            # fallback
            for r in results:
                if r["slug"]==slug:
                    r["name"]=slug.replace("uk49s-","UK49s ").title()
                    r["history"]=[]
                    final_results.append(r)
    with open("results.json","w") as f:
        json.dump(final_results, f, indent=2)
    print(f"results.json written from history (SYNC) with {len(final_results)} draws")
    print(json.dumps(final_results, indent=2))

if __name__ == "__main__":
    main()
