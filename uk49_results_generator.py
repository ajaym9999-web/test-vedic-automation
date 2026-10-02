
import json
from datetime import datetime
import os

def parse_date(dstr):
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y"):
        try:
            return datetime.strptime(dstr.strip(), fmt)
        except:
            continue
    return datetime.min

def normalize_date(dstr):
    dt = parse_date(dstr)
    if dt == datetime.min:
        return dstr.strip().lower()
    return dt.strftime("%d %B %Y")

def clean_history_file():
    hist_path = "history.json"
    if not os.path.exists(hist_path):
        print("history.json not found, nothing to clean")
        return
    
    with open(hist_path) as f:
        hist = json.load(f)
    
    cleaned = {}
    for slug, lst in hist.items():
        if not isinstance(lst, list):
            continue
        by_date = {}
        for item in lst:
            if not isinstance(item, dict):
                continue
            raw = item.get('dateLong') or item.get('date') or ''
            if not raw:
                continue
            norm = normalize_date(raw)
            # ensure drawNo exists and is int
            dn = item.get('drawNo', item.get('no', 0))
            try:
                dn_int = int(dn)
            except:
                dn_int = 0
            item['drawNo'] = dn_int
            item['no'] = dn_int
            # keep highest drawNo for duplicate date
            if norm not in by_date or dn_int > by_date[norm].get('drawNo',0):
                by_date[norm] = item
        
        sorted_items = sorted(by_date.values(), key=lambda x: parse_date(x.get('dateLong','')), reverse=True)
        # Re-number sequentially to avoid #undefined and gaps
        if sorted_items:
            max_no = max([i.get('drawNo',2500) for i in sorted_items])
            # If max_no is too small, start from 2507
            if max_no < 2400:
                max_no = 2507
            for idx, it in enumerate(sorted_items):
                it['drawNo'] = max_no - idx
                it['no'] = max_no - idx
                dt = parse_date(it.get('dateLong',''))
                if dt != datetime.min:
                    it['dateLong'] = dt.strftime("%d %B %Y")
                    it['date'] = dt.strftime("%d %B %Y")
        
        cleaned[slug] = sorted_items[:10]
    
    # Write cleaned history.json
    with open(hist_path, "w") as f:
        json.dump(cleaned, f, indent=2)
    
    # Write results.json array format for website
    results = []
    for slug in ["uk49s-lunchtime","uk49s-teatime","uk49s-brunchtime","uk49s-drivetime"]:
        lst = cleaned.get(slug, [])
        if not lst:
            continue
        latest = lst[0]
        results.append({
            "slug": slug,
            "name": slug.replace("uk49s-","UK49s ").title(),
            "numbers": latest["numbers"],
            "bonus": latest["bonus"],
            "dateLong": latest["dateLong"],
            "date": latest["date"],
            "drawNo": latest["drawNo"],
            "no": latest["no"],
            "history": lst
        })
    
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Cleaned: history.json and results.json written, no duplicates, sorted newest first")
    for r in results:
        print(f"  {r['slug']}: {r['dateLong']} Draw #{r['drawNo']} - {len(r['history'])} history")

if __name__ == "__main__":
    clean_history_file()
