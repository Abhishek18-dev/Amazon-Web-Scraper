import csv
import re
import bs4
import requests
import time
import random
from datetime import datetime
import concurrent.futures
from tqdm import tqdm

USER_AGENTS = [
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36 Edg/117.0.2045.60",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0",
]

NO_THREADS = 5


def build_request_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Referer": "https://www.amazon.com/",
    }


#### GETTING HTML OF WEBSITE
def get_page_html(url):
    for attempt in range(1, 4):
        # Add small jitter to avoid bursty request pattern.
        time.sleep(random.uniform(1.0, 2.2))
        try:
            response = requests.get(url, headers=build_request_headers(), timeout=20)
            print(f" URL : {url} -> Status code: {response.status_code} (attempt {attempt})")

            lower_text = response.text.lower()
            blocked = (
                response.status_code in (429, 503)
                or "captcha" in lower_text
                or "to discuss automated access" in lower_text
            )

            if blocked:
                print(f"Bot protection detected for {url}; retrying...")
                continue

            if response.ok:
                return response.content
        except requests.RequestException as exc:
            print(f"Error fetching {url} (attempt {attempt}): {exc}")

    return None


#### GETTING PRODUCT PRICE ON WEBSITE OF SPECIFIC URLS
def get_product_price(soup):
    price_selectors = [
        "span.a-price.aok-align-center .a-offscreen",
        "span.a-price .a-offscreen",
        "span#priceblock_ourprice",
        "span#priceblock_dealprice",
        "span#priceblock_saleprice",
        "span#corePriceDisplay_desktop_feature_div .a-offscreen",
    ]

    for selector in price_selectors:
        price_node = soup.select_one(selector)
        if not price_node:
            continue

        price_text = price_node.get_text(" ", strip=True)
        match = re.search(r"(\d+[\d,]*\.?\d*)", price_text)
        if not match:
            continue

        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            continue

    return None


#### GETTING PRODUCT TITLE ON WEBSITE OF SPECIFIC URLS
def get_product_title(soup):
    title_selectors = [
        "#productTitle",
        "#title span",
        "h1.a-size-large span",
    ]

    for selector in title_selectors:
        node = soup.select_one(selector)
        if node:
            title = node.get_text(" ", strip=True)
            if title:
                return title

    return None


#### GETTING PRODUCT RATING ON WEBSITE OF SPECIFIC URLS
def get_product_rating(soup):
    rating_candidates = [
        soup.select_one("span[data-hook='rating-out-of-text']"),
        soup.select_one("i[data-hook='average-star-rating'] span.a-icon-alt"),
        soup.select_one("span#acrPopover span.a-size-base.a-color-base"),
        soup.select_one("span#acrPopover span.a-icon-alt"),
        soup.select_one("span.a-icon-alt"),
    ]

    for node in rating_candidates:
        if not node:
            continue
        rating_text = node.get_text(" ", strip=True)
        match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
        if not match:
            continue
        try:
            return float(match.group(1))
        except ValueError:
            continue

    return None


#### GETTIING PRODUCT ALL TECHNICAL DETAILS ON WEBSITE FROM SOUP OF SPECIFIC URL
def get_product_technical_details(soup):
    technical_details = {}

    def clean_text(text):
        return " ".join(text.replace("\u200e", "").replace("\u200f", "").replace("\xa0", " ").split())

    def add_detail(key, value):
        k = clean_text(key) if key else ""
        v = clean_text(value) if value else ""
        if k and v and k not in technical_details:
            technical_details[k] = v

    # 1️⃣ NEW: modern Amazon layout
    rows = soup.select("#productOverview_feature_div tr")
    for row in rows:
        cols = row.find_all(["td", "th"])
        if len(cols) >= 2:
            add_detail(cols[0].get_text(" ", strip=True), cols[1].get_text(" ", strip=True))

    # 2️⃣ bullet section (updated)
    bullets = soup.select("#detailBullets_feature_div li")
    for li in bullets:
        text = clean_text(li.get_text(" ", strip=True))
        if ":" in text:
            key, value = text.split(":", 1)
            add_detail(key, value)

    # 2b: detail bullets table-like rows
    for row in soup.select("#detailBullets_feature_div tr"):
        header = row.find("th")
        data_cells = row.find_all("td")
        if header and data_cells:
            add_detail(header.get_text(" ", strip=True), data_cells[-1].get_text(" ", strip=True))
        elif len(data_cells) >= 2:
            add_detail(data_cells[0].get_text(" ", strip=True), data_cells[1].get_text(" ", strip=True))

    # 2c: additional product detail tables often present on Amazon pages
    for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr"):
        header = row.find("th")
        data_cells = row.find_all("td")
        if header and data_cells:
            add_detail(header.get_text(" ", strip=True), data_cells[-1].get_text(" ", strip=True))
        elif len(data_cells) >= 2:
            add_detail(data_cells[0].get_text(" ", strip=True), data_cells[1].get_text(" ", strip=True))

    # 3️⃣ fallback: ALL tables
    tables = soup.select("table")
    for table in tables:
        for row in table.select("tr"):
            header = row.find("th")
            data_cells = row.find_all("td")
            if header and data_cells:
                add_detail(header.get_text(" ", strip=True), data_cells[-1].get_text(" ", strip=True))
            elif len(data_cells) >= 2:
                add_detail(data_cells[0].get_text(" ", strip=True), data_cells[1].get_text(" ", strip=True))

    return technical_details


#### MAIN EXTRACTING FUNCTION HANDLE ALL THE SCRAPING  STEPS
def extract_products_info(url, output):
    product_info = {}

    html_content = get_page_html(url)
    if not html_content:
        print(f"Failed to retrieve content from {url}")
        return product_info

    try:
        soup = bs4.BeautifulSoup(html_content, "lxml")
    except bs4.FeatureNotFound:
        soup = bs4.BeautifulSoup(html_content, "html.parser")

    product_info["Price"] = get_product_price(soup)
    product_info["Title"] = get_product_title(soup)
    product_info["Rating"] = get_product_rating(soup)
    product_info.update(get_product_technical_details(soup))

    # Ensure Telegram output never loses primary fields to None.
    product_info["Title"] = product_info.get("Title") or "N/A"
    product_info["Price"] = product_info.get("Price") if product_info.get("Price") is not None else "N/A"
    product_info["Rating"] = product_info.get("Rating") if product_info.get("Rating") is not None else "N/A"

    print(f"[DEBUG] Extracted product_info for {url}: {product_info}")
    output.append(product_info)


#### MAIN FUNCTION FROM WHERE EVERYTHING IS CALLED
if __name__ == "__main__":
    products_data_for_csv = []
    urls = []

    with open("urls.csv", newline="", encoding="utf-8") as csvfile:
        urls = list(csv.reader(csvfile, delimiter=","))

    with concurrent.futures.ThreadPoolExecutor(max_workers=NO_THREADS) as executer:
        for worker_number in tqdm(range(0, len(urls))):
            executer.submit(extract_products_info, urls[worker_number][0], products_data_for_csv)

    output_file_name = "output-{}.csv".format(datetime.today().strftime("%d-%m-%Y"))
    all_keys = set()
    for product in products_data_for_csv:
        all_keys.update(product.keys())

    priority_fields = ["Title", "Price", "Rating"]
    other_fields = [key for key in all_keys if key not in priority_fields]
    final_keys = priority_fields + other_fields

    with open(output_file_name, "w", newline="", encoding="utf-8") as outputfile:
        writer = csv.DictWriter(outputfile, fieldnames=final_keys)
        writer.writeheader()
        for product in products_data_for_csv:
            row = {k: product.get(k, "") for k in final_keys}
            writer.writerow(row)

    print("All products info extracted successfully.")
    print(f"All the products Data will be saved to {output_file_name}")
