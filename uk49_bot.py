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
        r = requests.get(url, headers=HEADERS, timeout=25)
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
            print(f"{slug}: Not enough numbers at {url} -> {numbers}")
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

def parse_date(dstr):
    # Try multiple formats
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y"):
        try:
            return datetime.strptime(dstr.strip(), fmt)
        except:
            continue
    try:
        # remove extra spaces, leading zero safe
        return datetime.strptime(dstr.strip(), "%d %B %Y")
    except:
        return datetime.min


def normalize_date_key(dstr):
    # parse then reformat to DD Month YYYY to make 2 Oct and 02 Oct same
    dt = parse_date(dstr)
    if dt == datetime.min:
        return dstr.strip().lower()
    return dt.strftime("%d %B %Y")

def main():
    hist_path = "history.json"
    history = {}
    if os.path.exists(hist_path):
        try:
            with open(hist_path,"r") as f:
                history = json.load(f)
        except:
            history = {}

    # CLEAN: key by NORMALIZED date to avoid duplicate dates like 02 Oct vs 2 Oct
    for slug in list(history.keys()):
        lst = history.get(slug, [])
        by_date = {}
        for item in lst:
            raw = item.get('dateLong','').strip()
            if not raw:
                continue
            norm_key = normalize_date_key(raw)
            # keep entry with higher drawNo if duplicate normalized date
            if norm_key not in by_date:
                by_date[norm_key] = item
            else:
                if item.get('drawNo', item.get('no',0)) > by_date[norm_key].get('drawNo', by_date[norm_key].get('no',0)):
                    by_date[norm_key] = item
        cleaned = list(by_date.values())
        cleaned.sort(key=lambda x: parse_date(x.get('dateLong','')), reverse=True)
        history[slug] = cleaned[:10]

    old_by_slug = {}
    if os.path.exists("results.json"):
        try:
            with open("results.json","r") as f:
                old = json.load(f)
                for item in old:
                    if "slug" in item:
                        old_by_slug[item["slug"]] = item
        except:
            pass

    results = []
    for slug, url in URLS.items():
        print(f"Scraping {slug} from {url}")
        res = scrape_one(slug, url)
        if not res:
            alt_url = url.replace('/amp/', '/')
            print(f"  Fallback {alt_url}")
            res = scrape_one(slug, alt_url)
        if res:
            print(f"  LIVE OK {slug}: {res['numbers']} + {res['bonus']} - {res['dateLong']}")
            results.append(res)
        else:
            if slug in old_by_slug:
                print(f"  -> Keep old for {slug}: {old_by_slug[slug]['numbers']} - {old_by_slug[slug].get('dateLong')}")
                results.append(old_by_slug[slug])

    # UPDATE HISTORY - REPLACE BY NORMALIZED DATE
    for r in results:
        slug = r["slug"]
        lst = history.get(slug, [])
        by_date = {}
        for it in lst:
            by_date[normalize_date_key(it.get('dateLong',''))] = it
        
        norm_new = normalize_date_key(r['dateLong'])
        # keep old drawNo if same date exists else new max+1
        existing = by_date.get(norm_new)
        if existing:
            draw_no = existing.get('drawNo', existing.get('no', 2500))
        else:
            draw_no = max([it.get('drawNo', it.get('no',2500)) for it in lst], default=2506)+1
        
        by_date[norm_new] = {
            "drawNo": draw_no,
            "no": draw_no,
            "numbers": r["numbers"],
            "bonus": r["bonus"],
            "dateLong": r["dateLong"].strip(),
            "date": r["date"].strip()
        }
        merged = list(by_date.values())
        merged.sort(key=lambda x: parse_date(x.get('dateLong','')), reverse=True)
        history[slug] = merged[:10]

    # Final cleanup - ensure sorted newest first and no duplicate normalized dates
    for slug in list(history.keys()):
        lst = history[slug]
        seen = {}
        for it in sorted(lst, key=lambda x: parse_date(x.get('dateLong','')), reverse=True):
            k = normalize_date_key(it.get('dateLong',''))
            if k not in seen:
                seen[k] = it
        history[slug] = list(seen.values())[:10]

    with open(hist_path,"w") as f:
        json.dump(history, f, indent=2)
    print(f"history.json written cleaned - sorted by date DESC, duplicates removed by normalized date")

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
                "history": lst
            })
    with open("results.json","w") as f:
        json.dump(final_results, f, indent=2)
    print(f"results.json SYNC written from history - {len(final_results)} draws, dates sorted newest first")
    print(json.dumps(final_results, indent=2))

if __name__ == "__main__":
    main()
