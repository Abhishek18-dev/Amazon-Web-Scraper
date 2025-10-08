#🕸️ Amazon Product Web Scraper

## 📌 About
A simple Python project that scrapes product details (title, price, rating, and technical specs) from Amazon product pages using BeautifulSoup and Requests.

Both versions were created by **Abhishek** for **educational and ethical purposes only**.  
⚠️ Please do not misuse this script. It is strictly meant for learning, personal productivity, and ethical use.


##🚀 Features

Extracts Title, Price, Rating, and Technical Details

Reads URLs from a urls.csv file

Saves all data to an output CSV automatically (output-DD-MM-YYYY.csv)

Two versions: Single-threaded & Multi-threaded

Uses random User-Agent headers to reduce risk of blocking

##⚙️ Usage

1.Add Amazon product URLs (one per line) in urls.csv.

2.Install dependencies:

pip install -r requirements.txt


3.Run the scraper:

python web_scraper.py


or (for single-threaded version):

python web_scraper_single_thread.py

4.The output CSV (output-DD-MM-YYYY.csv) will be generated automatically in the project folder.

##⚠️ Ethical Use

Only scrape for personal use or learning purposes.

Avoid overloading Amazon servers (use delays if needed).

Respect Amazon’s Terms of Service.

For improvements or contributions, feel free to connect or fork the project.

##🧩 Tech Used

Python • BeautifulSoup4 • Requests • TQDM • LXML

📜 License

MIT License – You are free to use, modify, and share this project, even for commercial purposes, but the original license and copyright notice must be included.

Think of it as: “Do what you want, just give credit to the original creator.”

##🧩 requirements.txt
beautifulsoup4
requests
tqdm
lxml