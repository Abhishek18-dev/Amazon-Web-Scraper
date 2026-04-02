import csv
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

NO_THREADS = 5;


#### GETTING HTML OF WEBSITE
def get_page_html(url):
    try:
        response = requests.get(url, headers=REQUEST_HEADER)
        print(f" URL : {url} -> Status code: {response.status_code}")
        if "captcha" in response.text.lower():
            print("CAPTCHA page detected for url {url}.")
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
def extract_products_info(url,output):
    product_info={}
    #print(f"Extracting products info from {url}")

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
        output.append(product_info)
    

#### MAIN FUNCTION FROM WHERE EVERYTHING IS CALLED
if __name__ == "__main__":
    products_data_for_csv = []
    urls =[]
    with open(r"C:\Users\ABHISHEK\PythonUdemyScraper\Web_Scraper\urls.csv", newline="") as csvfile:
        urls = list(csv.reader(csvfile, delimiter=","))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=NO_THREADS) as executer:
        for worker_number in tqdm(range(0,len(urls))):
            executer.submit(extract_products_info,urls[worker_number][0],products_data_for_csv) #### im here 7::50
        
    # code to make an output csv file    
    output_file_name = "output-{}.csv".format(datetime.today().strftime("%d-%m-%Y"))
    all_keys = set()
    for product in products_data_for_csv:
        all_keys.update(product.keys())

    priority_fields = ["Title", "Price", "Rating"]
    other_fields = [key for key in all_keys if key not in priority_fields]
    final_keys = priority_fields + other_fields  # maintain order
    
    all_keys = list(all_keys)
    
    # write CSV with explicit newline handling and UTF-8 encoding
    with open(output_file_name, "w", newline="", encoding="utf-8") as outputfile:
        writer = csv.DictWriter(outputfile, fieldnames=all_keys)
        writer.writeheader()
        for product in products_data_for_csv:
            # Ensure we write a mapping that contains all header keys (fill missing with empty string)
            row = {k: product.get(k, "") for k in all_keys}
            writer.writerow(row)
    print("All products info extracted successfully.")
    print(f"All the products Data will be saved to {output_file_name}")