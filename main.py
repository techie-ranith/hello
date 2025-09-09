import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook
import os
import time

BASE_URL = "https://autostream.lk"

# --------------------------
# Scraper function for a single vehicle ad
# --------------------------
def scrape_vehicle(url):
    print(f"🔹 Scraping vehicle: {url}")  # Debug: starting a vehicle scrape
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    data = {"Ad URL": url}

    # --------------------------
    # Dealer details
    # --------------------------
    dealer_name = soup.select_one(".dealer-info h3")
    data["Dealer Name"] = dealer_name.get_text(strip=True) if dealer_name else ""
    print(f"    Dealer Name: {data['Dealer Name']}")  # Debug

    dealer_location = soup.select_one(".dealer-info .stm-dealer-location")
    data["Dealership Location"] = dealer_location.get_text(strip=True) if dealer_location else ""
    print(f"    Location: {data['Dealership Location']}")  # Debug

    sales_hours = soup.select_one(".dealer-info .dealer-working-hours")
    data["Sales Hours"] = sales_hours.get_text(strip=True) if sales_hours else ""
    print(f"    Sales Hours: {data['Sales Hours']}")  # Debug

    seller_email = soup.select_one(".dealer-info a[href^='mailto:']")
    data["Seller Email"] = seller_email.get_text(strip=True) if seller_email else ""
    print(f"    Seller Email: {data['Seller Email']}")  # Debug

    dealer_contact = soup.select_one(".dealer-info a[href^='tel:']")
    data["Dealer Contact Number"] = dealer_contact.get_text(strip=True) if dealer_contact else ""
    print(f"    Dealer Contact: {data['Dealer Contact Number']}")  # Debug

    # --------------------------
    # Vehicle details
    # --------------------------
    vehicle_name = soup.select_one("h1.listing-title")
    data["Vehicle Name"] = vehicle_name.get_text(strip=True) if vehicle_name else ""
    print(f"    Vehicle Name: {data['Vehicle Name']}")  # Debug

    vehicle_price = soup.select_one(".price .heading-font")
    data["Vehicle Price"] = vehicle_price.get_text(strip=True) if vehicle_price else ""
    print(f"    Price: {data['Vehicle Price']}")  # Debug

    contact_number = soup.select_one(".listing-phone-wrap a[href^='tel:']")
    data["Contact Number"] = contact_number.get_text(strip=True) if contact_number else ""
    print(f"    Contact Number: {data['Contact Number']}")  # Debug

    reg_no = soup.find("div", string=lambda s: s and "Registration" in s)
    data["Registration Number"] = reg_no.get_text(strip=True) if reg_no else ""
    print(f"    Registration No: {data['Registration Number']}")  # Debug

    # --------------------------
    # Main attributes (Body, Mileage, Fuel Type, Engine CC, etc.)
    # --------------------------
    for item in soup.select(".single-listing-attribute-boxes .item"):
        label = item.select_one(".label-text")
        value = item.select_one(".value-text")
        if label and value:
            data[label.get_text(strip=True)] = value.get_text(strip=True)
            print(f"    {label.get_text(strip=True)}: {value.get_text(strip=True)}")  # Debug

    # --------------------------
    # Additional data (Grade, District, Exterior/Interior Color, etc.)
    # --------------------------
    for li in soup.select(".stm-single-car-listing-data .data-list-item"):
        label = li.select_one(".item-label")
        value = li.select_one(".heading-font")
        if label and value:
            data[label.get_text(strip=True)] = value.get_text(strip=True)
            print(f"    {label.get_text(strip=True)}: {value.get_text(strip=True)}")  # Debug

    # --------------------------
    # Features grouped by category
    # --------------------------
    for group in soup.select(".stm-single-listing-car-features .grouped_checkbox-3"):
        category = group.select_one("h4")
        if not category:
            continue
        category_name = category.get_text(strip=True)
        features_list = [li.get_text(strip=True) for li in group.select("ul li span") if li.get_text(strip=True)]
        data[category_name] = ", ".join(features_list)
        print(f"    Features ({category_name}): {data[category_name]}")  # Debug

    # --------------------------
    # Seller Notes
    # --------------------------
    seller_notes = soup.select_one("section:has(h2:-soup-contains('Seller Notes'))")
    if seller_notes:
        data["Seller Notes"] = seller_notes.get_text(strip=True)
        print(f"    Seller Notes: {data['Seller Notes'][:60]}...")  # Debug first 60 chars

    return data

# --------------------------
# Collect all ads from a dealer
# --------------------------
def scrape_dealer(dealer_url):
    ads = []
    page = 1

    while True:
        url = f"{dealer_url}page/{page}/" if page > 1 else dealer_url
        print(f"🔎 Scraping dealer page: {url}")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        ad_links = []
        for listing in soup.select(".car-listing-row.row.row-3"):
            for a_tag in listing.find_all("a", href=True):
                if "/listings/" in a_tag["href"]:  # only vehicle ads
                    ad_links.append(a_tag["href"])

        ad_links = list(set(ad_links))  # remove duplicates

        print(f"    Found {len(ad_links)} ads on this page.")

        if not ad_links:
            print("⚠️ No ads found on this page.")
            break

        for ad_url in ad_links:
            if not ad_url.startswith("http"):
                ad_url = BASE_URL + ad_url
            try:
                ad_data = scrape_vehicle(ad_url)
                ads.append(ad_data)
                time.sleep(1)  # polite delay
            except Exception as e:
                print(f"❌ Failed to scrape {ad_url}: {e}")

        # Check if "next page" exists
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
        print("⚠️ No data to save.")
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
        print(f"📄 Excel file exists, appending data: {file_name}")
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        print(f"📄 Created new Excel file: {file_name}")

    for row in data_list:
        ws.append([row.get(h, "") for h in headers])

    wb.save(file_name)
    print(f"✅ Saved {len(data_list)} ads into {file_name}")

# --------------------------
# MAIN
# --------------------------
dealer_url = "https://autostream.lk/author/achalamansara9gmail-com/"
ads_data = scrape_dealer(dealer_url)
save_to_excel(ads_data)
