import logging
import requests
from playwright.sync_api import sync_playwright

# setup logging
logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - %(levelname)s - %(message)s'
)

# function to fetch data
def fetch_migrant_data():

    url = "https://www.gov.uk/government/publications/migrants-detected-crossing-the-english-channel-in-small-boats"
    download_text = "Migrants detected crossing the English Channel in small boats – time series"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)

            href = page.locator(
                "a",
                has_text=download_text
            ).first.get_attribute("href")

            try:
              download_resp = requests.get(href)
              download_resp.raise_for_status()
              download_file_name = href.split("/")[-1]
              output_dir = f"incoming/{download_file_name}"
              with open(output_dir, 'wb') as fp:
                  fp.write(download_resp.content)
              logging.info(f"Downloaded -> {download_file_name}")
            except requests.exceptions.RequestException as e:
                logging.critical(f"An RequestException error occured: {e}")
                raise
    except Exception as e:
        logging.critical(f"An Exception occured: {e}")

if __name__ == "__main__":
    fetch_migrant_data()