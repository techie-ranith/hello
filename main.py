import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook
import os
import time

BASE_URL = "https://autostream.lk"

# --------------------------
# Normalize scraped labels to match Excel headers
# --------------------------
def normalize_label(label):
    mapping = {
        "Fuel type": "Fuel Type",
        "Engine CC / kW": "Engine CC / kw",
        "Year of Manufacture": "Year of Manufacture",
        "Transmission": "Transmission",
        "Body": "Body",
        "Mileage": "Mileage",
        "Grade": "Grade",
        "Exterior Color": "Exterior Color",
        "Interior Color": "Interior Color",
        "No. of Owners": "No. of Owners",
        "Blue-T Grade": "Blue-T Grade",
        "District": "District",
        "City": "City",
        "Year of Reg.": "Year of Reg.",
    }
    return mapping.get(label.strip(), label.strip())  # fallback to original


# --------------------------
# Scraper function for a single vehicle ad
# --------------------------
def scrape_vehicle(url, dealer_info):
    print(f"🔹 Scraping vehicle: {url}")  
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # start with dealer info (copied into every vehicle row)
    data = {**dealer_info, "Ad URL": url}

    # --------------------------
    # Vehicle details
    # --------------------------
    vehicle_name = soup.select_one("h1.listing-title")
    data["Vehicle Name"] = vehicle_name.get_text(strip=True) if vehicle_name else ""

    vehicle_price = soup.select_one(".price .heading-font")
    data["Vehicle Price"] = vehicle_price.get_text(strip=True) if vehicle_price else ""

    contact_number = soup.select_one(".listing-phone-wrap a[href^='tel:']")
    data["Contact Number"] = contact_number.get_text(strip=True) if contact_number else ""

    reg_no = soup.find("div", string=lambda s: s and "Registration" in s)
    data["Registration Number"] = reg_no.get_text(strip=True) if reg_no else ""

    # --------------------------
    # Main attributes (Body, Mileage, Fuel Type, Engine CC, etc.)
    # --------------------------
    for item in soup.select(".single-listing-attribute-boxes .item"):
        label = item.select_one(".label-text")
        value = item.select_one(".value-text")

        if label:
            label_text = normalize_label(label.get_text(strip=True))
            value_text = value.get_text(strip=True) if value else ""

            # Save even if value is empty
            data[label_text] = value_text
            print(f"    {label_text}: {value_text}")  # Debug

    # --------------------------
    # Additional attributes (like Grade, Color, etc.)
    # --------------------------
    for li in soup.select(".stm-single-car-listing-data .data-list-item"):
        label = li.select_one(".item-label")
        value = li.select_one(".heading-font")
        if label and value:
            label_text = normalize_label(label.get_text(strip=True))
            data[label_text] = value.get_text(strip=True)
            print(f"    {label_text}: {data[label_text]}")  # Debug

    # --------------------------
    # Features (grouped checkboxes)
    # --------------------------
    for group in soup.select(".stm-single-listing-car-features .grouped_checkbox-3"):
        category = group.select_one("h4")
        if not category:
            continue
        category_name = normalize_label(category.get_text(strip=True))
        features_list = [li.get_text(strip=True) for li in group.select("ul li span") if li.get_text(strip=True)]
        data[category_name] = ", ".join(features_list)
        print(f"    {category_name}: {data[category_name]}")  # Debug

    # --------------------------
    # Seller Notes
    # --------------------------
    seller_notes = soup.select_one("section:has(h2:-soup-contains('Seller Notes'))")
    if seller_notes:
        data["Seller Notes"] = seller_notes.get_text(strip=True)
        print(f"    Seller Notes: {data['Seller Notes']}")  # Debug

    return data


# --------------------------
# Collect all ads from a dealer (scrapes dealer info once)
# --------------------------
def scrape_dealer(dealer_url):
    ads = []

    # scrape dealer info only once
    print(f"🔎 Scraping dealer info: {dealer_url}")
    response = requests.get(dealer_url)
    soup = BeautifulSoup(response.text, "html.parser")

    dealer_info = {}
    dealer_name = soup.select_one(".dealer-info h3")
    dealer_info["Dealer Name"] = dealer_name.get_text(strip=True) if dealer_name else ""

    dealer_location = soup.select_one(".dealer-info .stm-dealer-location")
    dealer_info["Dealership Location"] = dealer_location.get_text(strip=True) if dealer_location else ""

    sales_hours = soup.select_one(".dealer-info .dealer-working-hours")
    dealer_info["Sales Hours"] = sales_hours.get_text(strip=True) if sales_hours else ""

    seller_email = soup.select_one(".dealer-info a[href^='mailto:']")
    dealer_info["Seller Email"] = seller_email.get_text(strip=True) if seller_email else ""

    dealer_contact = soup.select_one(".dealer-info a[href^='tel:']")
    dealer_info["Dealer Contact Number"] = dealer_contact.get_text(strip=True) if dealer_contact else ""

    print(f"✅ Dealer: {dealer_info}")

    # now go through vehicle pages
    page = 1
    while True:
        url = f"{dealer_url}page/{page}/" if page > 1 else dealer_url
        print(f"🔎 Scraping dealer page: {url}")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        ad_links = []
        for listing in soup.select(".car-listing-row.row.row-3"):
            for a_tag in listing.find_all("a", href=True):
                if "/listings/" in a_tag["href"]:
                    ad_links.append(a_tag["href"])

        ad_links = list(set(ad_links))  # remove duplicates

        if not ad_links:
            break

        print(f"    Found {len(ad_links)} ads on page {page}")

        for ad_url in ad_links:
            if not ad_url.startswith("http"):
                ad_url = BASE_URL + ad_url
            try:
                ad_data = scrape_vehicle(ad_url, dealer_info)
                ads.append(ad_data)
                time.sleep(1)  # polite delay
            except Exception as e:
                print(f"❌ Failed to scrape {ad_url}: {e}")

        # check next page
        next_btn = soup.select_one(".heading-font.next")
        if not next_btn:
            break
        page += 1

    print(f"✅ Total ads scraped: {len(ads)}")
    return ads


# --------------------------
# Save data to Excel
# --------------------------
def save_to_excel(data_list, file_name="vehicle_data.xlsx"):
    if not data_list:
        return

    headers = [
        "Dealer Name", "Dealership Location", "Sales Hours", "Seller Email", "Dealer Contact Number",
        "Vehicle Name", "Vehicle Price", "Contact Number", "Registration Number",
        "Body", "Mileage", "Fuel Type", "Engine CC / kw", "Year of Manufacture", "Transmission",
        "Grade", "Exterior Color", "Interior Color", "No. of Owners", "Blue-T Grade",
        "District", "City", "Year of Reg.", "Convenience", "Infotainment", "Safety & Security",
        "Interior & Seats", "Windows & Lighting", "Other Features", "Seller Notes", "Ad URL"
    ]

    if os.path.exists(file_name):
        wb = load_workbook(file_name)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(headers)

    for row in data_list:
        ws.append([row.get(h, "") for h in headers])

    wb.save(file_name)


# --------------------------
# MAIN
# --------------------------
dealer_url = "https://autostream.lk/author/achalamansara9gmail-com/"
ads_data = scrape_dealer(dealer_url)
save_to_excel(ads_data)
