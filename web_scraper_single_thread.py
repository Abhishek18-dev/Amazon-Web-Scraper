import csv
import bs4
import requests
import time
import random
from datetime import datetime

USER_AGENTS = [
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36 Edg/117.0.2045.60",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0"
]

REQUEST_HEADER = {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}


#### GETTING HTML OF WEBSITE
def get_page_html(url):
    try:
        response = requests.get(url, headers=REQUEST_HEADER)
        print(f"Status code: {response.status_code}")
        if "captcha" in response.text.lower():
            print("CAPTCHA page detected.")
        elif "To discuss automated access" in response.text:
            print("Bot detection triggered.")
        return response.content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None
    # Simulate delay between requests
time.sleep(random.uniform(2, 5))  # sleep for 2 to 5 seconds


#### GETTING PRODUCT PRICE ON WEBSITE OF SPECIFIC URLS
def get_product_price(soup):
    main_price_span = soup.find("span", attrs ={
        "class": "a-price-whole"
    })
    if not main_price_span:
        return None
    #price_spans = main_price_span.findAll("span")
    for span in main_price_span:
        price = span.text.strip().replace(",","")
        #print(price)
        try:
            return float(price)
        except ValueError:
            print("Value obtain for price could not be parsed...")
            exit()
    return None


#### GETTING PRODUCT TITLE ON WEBSITE OF SPECIFIC URLS
def get_product_title(soup):
    product_title = soup.find("span", id = "productTitle")
    if product_title:
        return product_title.text.strip()
    return None


#### GETTING PRODUCT RATING ON WEBSITE OF SPECIFIC URLS
def get_product_rating(soup):
# first or direct method to find product rating from amazon
    product_rating = soup.find("span", class_="a-icon-alt")
   #rating = product_rating.text.strip().split(" ") if product_rating else None
   #print(rating)
    try:
        if product_rating:
            rating = product_rating.text.strip().split(" ")[0]
            return float(rating)
    except ValueError:
        print("Value obtain for rating could not be parsed...")
        return None
# second method to find product rating from amazon popover
    popover_product_rating = soup.find("span", id="acrPopover")    # for giving classs  write class_
    if popover_product_rating:
        product_rating = popover_product_rating.find("span")
        if product_rating:
            rating = product_rating.text.strip().split(" ")[0]
            return float(rating)
        return None


####GETTIING PRODUCT ALL TECHNICAL DETAILS ON WEBSITE FROM SOUP OF SPECIFIC URL
def get_product_technical_details(soup):
    technical_details = {}
    technical_details_section = soup.find("div",id = "prodDetails")
    if not technical_details_section:
        technical_details_section = soup.find("div", id="productDetails_techSpec_section_1")
    if not technical_details_section:
        technical_details_section = soup.find("div", id="productDetails_detailBullets_sections1")
    if not technical_details_section:
        return technical_details

    data_tables = technical_details_section.find_all("table", class_="prodDetTable")
    for table in data_tables:
        table_rows = table.find_all("tr")
        for row in table_rows:
            header = row.find("th")
            if header:
                key_header_text = header.text.strip()
                value = row.find("td")
                value_text = value.text.strip().replace("\u200e","")
                if key_header_text and value_text:
                    technical_details[key_header_text] = value_text
    return technical_details


#### MAIN EXTRACTING FUNCTION HANDLE ALL THE SCRAPING  STEPS
def extract_products_info(url):
    product_info={}
    print(f"Extracting products info from {url}")
    html_content = get_page_html(url)
    if not html_content:
        print(f"Failed to retrieve content from {url}")
        return product_info
    else:
        try:
            soup = bs4.BeautifulSoup(html_content, "html.parser")
        except bs4.FeatureNotFound:
            soup = bs4.BeautifulSoup(html_content, "html.parser")   
        product_info["Price"] = get_product_price(soup)
        product_info["Title"] = get_product_title(soup)
        product_info["Rating"] = get_product_rating(soup)
        product_info.update(get_product_technical_details(soup))
        return product_info
    

#### MAIN FUNCTION FROM WHERE EVERYTHING IS CALLED
if __name__ == "__main__":
    product_data_for_csv = []
    with open(r"C:\Users\ABHISHEK\PythonUdemyScraper\Web_Scraper\urls.csv", newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=",")
        for row in reader:
            url = row[0]
            product_info = extract_products_info(url)# may produce error
            #print(product_info)
            product_data_for_csv.append(product_info)
            print(f"Product info extracted from {url}")
            print("-" * 40)
            print("Waiting for 2 seconds before next request...")
            time.sleep(random.uniform(2, 5))  # sleep for 2 to 5 seconds
    output_file_name = "output-{}.csv".format(datetime.today().strftime("%d-%m-%Y"))
    with open(output_file_name,"w") as outputfile:
        writer = csv.writer(outputfile)
        writer.writerow(product_data_for_csv[0].keys())
        for product in product_data_for_csv:
            writer.writerow(product.values())
    print("All products info extracted successfully.")
    print(f"All the products Data will be saved to {output_file_name}")
