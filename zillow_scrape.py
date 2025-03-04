import time
import random
import pandas as pd
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class ZillowFSBOScraper:
    def __init__(self, headless=True):
        """Initialize the scraper with browser options."""
        self.options = Options()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
        
        self.driver = None
        self.listings = []
        
    def start_browser(self):
        """Start the Chrome browser."""
        self.driver = webdriver.Chrome(options=self.options)
        # Set a reasonable window size
        self.driver.set_window_size(1366, 768)
        
    def close_browser(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            
    def random_delay(self, min_seconds=2, max_seconds=5):
        """Add random delay between actions to mimic human behavior."""
        time.sleep(random.uniform(min_seconds, max_seconds))
            
    def search_fsbo_listings(self, location, max_pages=3):
        """Search for FSBO listings in the specified location."""
        try:
            if not self.driver:
                self.start_browser()
                
            # Format the Zillow FSBO search URL
            base_url = f"https://www.zillow.com/homes/for_sale/{location.replace(' ', '-')}"
            fsbo_url = f"{base_url}/0_fs/"
            
            print(f"Searching FSBO listings in {location}...")
            self.driver.get(fsbo_url)
            self.random_delay(3, 6)
            
            # Check for and handle any initial popups
            self.handle_popups()
            
            # Iterate through the specified number of pages
            for page in range(1, max_pages + 1):
                print(f"Scraping page {page}...")
                
                # Wait for listings to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.photo-cards"))
                    )
                except TimeoutException:
                    print("Timeout waiting for listings to load")
                    
                # Parse the current page
                self.parse_listings_page()
                
                # Try to navigate to the next page if not on the last page
                if page < max_pages:
                    if not self.go_to_next_page():
                        print("No more pages available")
                        break
                        
            return self.listings
            
        except Exception as e:
            print(f"An error occurred during search: {str(e)}")
            return self.listings
        finally:
            # Make sure to close the browser
            self.close_browser()
            
    def handle_popups(self):
        """Handle common Zillow popups."""
        try:
            # Check for and close various possible popups
            # This varies based on Zillow's current website design
            popup_selectors = [
                "button[aria-label='Close']", 
                ".modal-dialog .close", 
                "#sgpd-closeButton",
                "button.popup-close"
            ]
            
            for selector in popup_selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in close_buttons:
                        if button.is_displayed():
                            button.click()
                            self.random_delay(1, 2)
                except:
                    continue
        except:
            pass
            
    def go_to_next_page(self):
        """Attempt to navigate to the next page of results."""
        try:
            # Find and click the next page button
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a[title='Next page']")
            if next_button.is_enabled():
                next_button.click()
                self.random_delay(3, 6)
                return True
            return False
        except NoSuchElementException:
            # Try alternative selectors if the first one fails
            try:
                next_buttons = self.driver.find_elements(By.CSS_SELECTOR, "li.PaginationNumberItem-c11n-8-84-3__sc-bnmlxt-0 a")
                # Find the active button and click the next one
                for i, button in enumerate(next_buttons):
                    if 'active' in button.get_attribute('class'):
                        if i + 1 < len(next_buttons):
                            next_buttons[i + 1].click()
                            self.random_delay(3, 6)
                            return True
                return False
            except:
                return False
                
    def parse_listings_page(self):
        """Parse the current page of listings."""
        try:
            # Get the page source and create a BeautifulSoup object
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Look for listing cards - this selector may need adjustment based on Zillow's current layout
            listing_cards = soup.select("ul.photo-cards > li")
            if not listing_cards:
                listing_cards = soup.select("div[data-test='property-card']")
                
            for card in listing_cards:
                listing = {}
                
                # Check if it's an FSBO listing
                fsbo_badge = card.select_one(".StyledZillowLogo-c11n-8-84-3__sc-1ly7na1-0")
                for_sale_by_owner_text = card.find(string=re.compile("For Sale by Owner", re.IGNORECASE))
                
                if fsbo_badge or for_sale_by_owner_text:
                    # Extract address
                    address_elem = card.select_one("address")
                    if address_elem:
                        listing['address'] = address_elem.text.strip()
                    
                    # Extract price
                    price_elem = card.select_one("[data-test='property-card-price']")
                    if price_elem:
                        listing['price'] = price_elem.text.strip()
                    
                    # Extract bed/bath/sqft info
                    details_elem = card.select_one("[data-test='property-card-details']")
                    if details_elem:
                        details_text = details_elem.text.strip()
                        
                        # Parse beds
                        beds_match = re.search(r"(\d+)\s*bd", details_text)
                        if beds_match:
                            listing['beds'] = beds_match.group(1)
                            
                        # Parse baths
                        baths_match = re.search(r"(\d+(?:\.\d+)?)\s*ba", details_text)
                        if baths_match:
                            listing['baths'] = baths_match.group(1)
                            
                        # Parse square footage
                        sqft_match = re.search(r"([\d,]+)\s*sqft", details_text)
                        if sqft_match:
                            listing['sqft'] = sqft_match.group(1).replace(',', '')
                    
                    # Extract listing URL
                    link_elem = card.select_one("a[href^='/homedetails']")
                    if link_elem:
                        href = link_elem['href']
                        if href.startswith('/'):
                            listing['url'] = f"https://www.zillow.com{href}"
                        else:
                            listing['url'] = href
                    
                    # Add the FSBO listing to our collection
                    if listing:
                        listing['source'] = 'Zillow FSBO'
                        print(f"Found FSBO listing: {listing.get('address', 'No address')} - {listing.get('price', 'No price')}")
                        self.listings.append(listing)
                        
        except Exception as e:
            print(f"Error parsing listings page: {str(e)}")
            
    def save_to_csv(self, filename='zillow_fsbo_listings.csv'):
        """Save the collected listings to a CSV file."""
        if self.listings:
            df = pd.DataFrame(self.listings)
            df.to_csv(filename, index=False)
            print(f"Saved {len(self.listings)} FSBO listings to {filename}")
        else:
            print("No listings to save")
            
def main():
    # Example usage
    locations = [
        "New York, NY",
        "Los Angeles, CA",
        "Chicago, IL"
    ]
    
    scraper = ZillowFSBOScraper(headless=False)  # Set to True for headless mode
    
    all_listings = []
    for location in locations:
        listings = scraper.search_fsbo_listings(location, max_pages=2)
        all_listings.extend(listings)
        # Add delay between locations to avoid rate limiting
        time.sleep(random.uniform(10, 20))
    
    if all_listings:
        df = pd.DataFrame(all_listings)
        df.to_csv('zillow_fsbo_listings.csv', index=False)
        print(f"Saved total of {len(all_listings)} FSBO listings to zillow_fsbo_listings.csv")
    else:
        print("No FSBO listings found")

if __name__ == "__main__":
    main()
