
import requests
from bs4 import BeautifulSoup
import json
import re
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
        # AMP page is simple markdown-like text when fetched via textise
        # Use regex to find date and numbers
        text = r.text
        
        # Method 1: Look for pattern like "Tuesday, 29 September 2026" followed by "- 7 - 17"
        # The open view showed lines like "Tuesday, 29 September 2026\n\n- 7\n\n- 17"
        date_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+\d{1,2}\s+\w+\s+\d{4}', text, re.I)
        date_long = date_match.group(0).replace(',', '').strip() if date_match else datetime.now().strftime("%d %B %Y")
        # Clean date to "29 September 2026" format
        try:
            # Remove day name
            parts = date_long.split()
            # If first part is day name, drop it
            if parts[0].lower() in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']:
                date_long = ' '.join(parts[1:])
        except:
            pass

        # Extract numbers: find all "- <digit>" after date
        # In AMP html they are list items
        soup = BeautifulSoup(text, "html.parser")
        # Get visible text lines
        numbers = []
        for li in soup.find_all(string=re.compile(r'^\s*\d{1,2}\s*$')):
            t = li.strip()
            if t.isdigit() and 1 <= int(t) <= 49:
                numbers.append(int(t))

        # Fallback: regex for "- 7" pattern in raw text
        if len(numbers) < 6:
            numbers = [int(n) for n in re.findall(r'-\s*(\d{1,2})\s*(?:\n|<)', text) if 1 <= int(n) <= 49]

        # Also try to find in table if numbers list failed
        if len(numbers) < 6:
            # Historical table first row has concatenated numbers like "891518203516"
            # That format is ambiguous, skip
            pass

        if len(numbers) >= 7:
            main = numbers[:6]
            bonus = numbers[6]
        elif len(numbers) == 6:
            main = numbers[:6]
            bonus = numbers[-1]
        else:
            print(f"{slug}: Not enough numbers found at {url} -> {numbers}")
            return None

        # Sort main ascending as site shows
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
    results = []
    for slug, url in URLS.items():
        print(f"Scraping {slug} from {url}")
        res = scrape_one(slug, url)
        if res:
            print(f"  OK: {res['numbers']} + {res['bonus']} - {res['dateLong']}")
            results.append(res)
        else:
            # Try non-amp page as fallback
            alt_url = url.replace('/amp/', '/')
            print(f"  Trying fallback {alt_url}")
            res2 = scrape_one(slug, alt_url)
            if res2:
                results.append(res2)
            else:
                print(f"  Failed {slug}, will use placeholder")

    # If any missing, don't use 00 placeholder - keep only found to avoid old data look
    # But ensure at least lunchtime/teatime
    with open("results.json","w") as f:
        json.dump(results, f, indent=2)
    print(f"\nresults.json written with {len(results)} draws")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
