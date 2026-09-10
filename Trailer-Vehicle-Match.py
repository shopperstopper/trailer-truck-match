import re
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE_URL = "https://www.apachecamping.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

def clean_int(val_str):
    if not val_str:
        return None
    cleaned = re.sub(r"[^\d]", "", str(val_str))
    return int(cleaned) if cleaned else None

def extract_vdp_specs(vdp_url):
    specs = {
        "DryWeight": None,
        "GVWR": None,
        "HitchWeight": None,
        "CargoCapacity": None,
        "Length": None,
        "Location": "Unassigned",
        "Image": "",
        "Status": "On Lot"
    }
    try:
        resp = requests.get(vdp_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return specs
            
        soup = BeautifulSoup(resp.content, "html.parser")
        text = soup.get_text(" ", strip=True)
        text_lower = text.lower()

        # 1. Location Detection
        if "portland" in text_lower or "clackamas" in text_lower:
            specs["Location"] = "Portland / Clackamas"
        elif "everett" in text_lower:
            specs["Location"] = "Everett"
        elif "tacoma" in text_lower:
            specs["Location"] = "Tacoma"
        elif "kitsap" in text_lower or "poulsbo" in text_lower:
            specs["Location"] = "Kitsap / Poulsbo"

        # 2. Status Detection (Incoming vs On Lot)
        if "incoming" in text_lower or "inbound" in text_lower or "on order" in text_lower:
            specs["Status"] = "Inbound / Incoming"
        else:
            specs["Status"] = "On Lot"

        # 3. Image URL
        img_tag = soup.select_one(".unit-photo img, .gallery-slide img, meta[property='og:image']")
        if img_tag:
            specs["Image"] = img_tag.get("content") or img_tag.get("src") or ""

        # 4. Hitch / Tongue Weight
        hitch_match = re.search(r"Hitch\s*Weight\s*([\d,]+)\s*lbs?", text, re.IGNORECASE)
        if hitch_match:
            specs["HitchWeight"] = clean_int(hitch_match.group(1))

        # 5. Dry Weight / Unloaded Weight
        dry_match = re.search(r"(?:Dry|Unloaded)\s*Weight\s*([\d,]+)\s*lbs?", text, re.IGNORECASE)
        if dry_match:
            specs["DryWeight"] = clean_int(dry_match.group(1))

        # 6. Cargo Capacity
        cargo_match = re.search(r"Cargo\s*Capacity\s*([\d,]+)\s*lbs?", text, re.IGNORECASE)
        if cargo_match:
            specs["CargoCapacity"] = clean_int(cargo_match.group(1))

        # 7. GVWR
        gvwr_match = re.search(r"GVWR\s*([\d,]+)\s*lbs?", text, re.IGNORECASE)
        if gvwr_match:
            specs["GVWR"] = clean_int(gvwr_match.group(1))
        elif specs["DryWeight"] and specs["CargoCapacity"]:
            specs["GVWR"] = specs["DryWeight"] + specs["CargoCapacity"]

        # 8. Length
        len_match = re.search(r"Length\s*(\d+)\s*ft(?:\s*(\d+)\s*in)?", text, re.IGNORECASE)
        if len_match:
            feet = float(len_match.group(1))
            inches = float(len_match.group(2)) if len_match.group(2) else 0.0
            specs["Length"] = round(feet + (inches / 12.0), 1)
        else:
            len_alt = re.search(r"Length\s*(\d+)'?\s*(\d+)?\"?", text, re.IGNORECASE)
            if len_alt and len_alt.group(1):
                feet = float(len_alt.group(1))
                inches = float(len_alt.group(2)) if len_alt.group(2) else 0.0
                specs["Length"] = round(feet + (inches / 12.0), 1)

    except Exception as e:
        print(f"    Error reading {vdp_url}: {e}")
        
    return specs

def scrape_apache_catalog():
    all_units = []
    seen_urls = set()
    page = 1

    print("--- Scraping Apache Inventory with Locations & Specs ---")

    while True:
        catalog_url = f"{BASE_URL}/rv-search?page={page}"
        print(f"\n[Fetching Page {page}]")
        
        try:
            resp = requests.get(catalog_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"End of pages reached (Status: {resp.status_code}).")
                break
        except Exception as e:
            print(f"Network error on page {page}: {e}")
            break

        soup = BeautifulSoup(resp.content, "html.parser")
        raw_links = soup.select("a[href*='/product/'], a[href*='/rv/']")
        if not raw_links:
            print("No links found on this page. Ending.")
            break

        units_found_on_page = 0
        for a in raw_links:
            href = a.get("href", "")
            title = a.get_text(strip=True)

            if not href or any(junk in title.lower() for junk in [
                "send to", "floorplan", "details", "photo", "view", "print", "brochure", "save", "quote"
            ]):
                continue

            full_vdp_url = href if href.startswith("http") else BASE_URL + href
            if full_vdp_url in seen_urls:
                continue
            
            seen_urls.add(full_vdp_url)
            units_found_on_page += 1

            specs = extract_vdp_specs(full_vdp_url)
            time.sleep(0.35)

            dry = specs["DryWeight"] if specs["DryWeight"] else 5200
            gvwr = specs["GVWR"] if specs["GVWR"] else (dry + 1800)
            hitch = specs["HitchWeight"] if specs["HitchWeight"] else int(round(gvwr * 0.12))
            length = specs["Length"] if specs["Length"] else 26.0

            print(f"  -> [{specs['Location']}] {title[:28]} | L: {length}' | Dry: {dry} | Hitch: {hitch}")

            all_units.append({
                "Model": title,
                "Length": length,
                "DryWeight": dry,
                "GVWR": gvwr,
                "HitchWeight": hitch,
                "Location": specs["Location"],
                "Status": specs["Status"],
                "Image": specs["Image"],
                "URL": full_vdp_url
            })

        if units_found_on_page == 0 or page >= 25:
            break

        page += 1

    df = pd.DataFrame(all_units)
    df.to_csv("apache_full_inventory.csv", index=False)
    print(f"\nSuccessfully saved {len(df)} units with lot locations to 'apache_full_inventory.csv'.")

if __name__ == "__main__":
    scrape_apache_catalog()
