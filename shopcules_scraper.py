import requests
from bs4 import BeautifulSoup
import csv
import argparse
import time
import re
from datetime import datetime

class ShopCluesScraper:
    def __init__(self, url=None):
        self.url = url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.product_data = {}
        self.reviews = []
    
    def fetch_page(self, url):
        """Fetch the HTML content of a page"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page: {e}")
            return None
    
    def parse_product_info(self, html):
        """Extract product information from the page"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract product details
        try:
            product_name = soup.select_one('h1.product_name')
            product_name = product_name.text.strip() if product_name else "Name not found"
            
            price = soup.select_one('span.f_price')
            price = price.text.strip() if price else "Price not found"
            
            mrp = soup.select_one('span#sec_discounted_price_display')
            mrp = mrp.text.strip() if mrp else "MRP not found"
            
            discount = soup.select_one('span.prd_discount')
            discount = discount.text.strip() if discount else "Discount not found"
            
            seller_name = soup.select_one('a#seller_name')  
            seller_name = seller_name.text.strip() if seller_name else "Seller not found"
            
            rating_elem = soup.select_one('span.rating_num')
            rating = rating_elem.text.strip('()') if rating_elem else "Rating not found"
            
            # Extract product specifications
            specs = {}
            spec_table = soup.select('div.prd_detls_tb table tr')
            if spec_table:
                for row in spec_table:
                    columns = row.select('td')
                    if len(columns) >= 2:
                        key = columns[0].text.strip()
                        value = columns[1].text.strip()
                        specs[key] = value
            
            self.product_data = {
                'product_name': product_name,
                'price': price,
                'mrp': mrp,
                'discount': discount,
                'seller_name': seller_name,
                'rating': rating,
                'specifications': specs,
                'url': self.url
            }
            
            return True
            
        except Exception as e:
            print(f"Error parsing product info: {e}")
            return False
    
    def parse_reviews(self, html):
        """Extract reviews from the page"""
        soup = BeautifulSoup(html, 'html.parser')
        reviews_list = []
        
        # Find all review items
        review_items = soup.select('div.rnr_lists ul li')
        
        for item in review_items:
            try:
                # Extract review details
                rating_span = item.select_one('div.prd_ratings span')
                rating = rating_span.text.strip() if rating_span else "N/A"
                
                reviewer = item.select_one('div.r_by')
                reviewer_name = reviewer.text.strip() if reviewer else "Anonymous"
                
                date_elem = item.select_one('div.r_date')
                date_str = date_elem.text.strip() if date_elem else ""
                
                verified = item.select_one('div.use_type')
                verified_status = verified.text.strip() if verified else "N/A"
                
                review_text = item.select_one('div.review_desc p')
                review_content = review_text.text.strip() if review_text else "No content"
                
                # Clean up any extra data in reviewer name
                if '<!--' in reviewer_name:
                    reviewer_name = reviewer_name.split('<!--')[0].strip()
                
                # Clean up review content
                if '<!--' in review_content:
                    review_content = review_content.split('<!--')[0].strip()
                
                review_data = {
                    'reviewer_name': reviewer_name,
                    'rating': rating,
                    'date': date_str,
                    'verified_status': verified_status,
                    'review_content': review_content
                }
                
                reviews_list.append(review_data)
                
            except Exception as e:
                print(f"Error parsing a review: {e}")
                continue
        
        return reviews_list
    
    def fetch_all_reviews(self):
        """Fetch all reviews by navigating through pagination"""
        if not self.url:
            print("URL not provided")
            return []
        
        # Initialize with first page of reviews
        html = self.fetch_page(self.url)
        if not html:
            return []
        
        all_reviews = self.parse_reviews(html)
        
        # Check if there's pagination for reviews and handle accordingly
        # This is a starting point - you might need to adjust this logic
        # based on how ShopClues implements pagination
        soup = BeautifulSoup(html, 'html.parser')
        load_more = soup.select_one('div.load_more a#moreReview')
        
        page = 1
        # If "Load more reviews" button exists, we need to simulate AJAX calls
        if load_more:
            # Extract product ID from URL
            product_id_match = re.search(r'(\d+)\.html', self.url)
            if product_id_match:
                product_id = product_id_match.group(1)
                
                while True:
                    page += 1
                    # Construct the AJAX URL for next page of reviews
                    ajax_url = f"https://www.shopclues.com/ajaxCall/getReviews?product_id={product_id}&page={page}"
                    
                    try:
                        response = requests.get(ajax_url, headers=self.headers)
                        if response.status_code != 200:
                            break
                        
                        # Parse JSON response
                        data = response.json()
                        if not data.get('html') or data.get('html') == "":
                            break
                        
                        # Parse reviews from HTML in JSON
                        review_soup = BeautifulSoup(data['html'], 'html.parser')
                        page_reviews = self.parse_reviews(str(review_soup))
                        
                        if not page_reviews:
                            break
                        
                        all_reviews.extend(page_reviews)
                        print(f"Fetched {len(page_reviews)} reviews from page {page}")
                        
                        # Sleep to prevent rate limiting
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"Error fetching reviews page {page}: {e}")
                        break
        
        self.reviews = all_reviews
        return all_reviews
    
    def scrape_product(self, url=None):
        """Main method to scrape product details and reviews"""
        if url:
            self.url = url
        
        if not self.url:
            print("URL not provided")
            return False
        
        html = self.fetch_page(self.url)
        if not html:
            return False
        
        # Parse product information
        product_parsed = self.parse_product_info(html)
        if not product_parsed:
            print("Failed to parse product information")
            return False
        
        # Fetch all reviews
        self.fetch_all_reviews()
        
        print(f"Successfully scraped product with {len(self.reviews)} reviews")
        return True
    
    def save_to_csv(self, output_file):
        """Save product information and reviews to CSV files"""
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write product information section
                writer.writerow(['PRODUCT INFORMATION'])
                headers = ['product_name', 'price', 'mrp', 'discount', 'seller_name', 'rating', 'url']
                writer.writerow(headers)
                row = [self.product_data.get(header, '') for header in headers]
                writer.writerow(row)
                
                # Write specifications
                if self.product_data.get('specifications'):
                    writer.writerow([])  # Empty row for spacing
                    writer.writerow(['SPECIFICATIONS'])
                    for key, value in self.product_data['specifications'].items():
                        writer.writerow([key, value])
                
                # Write reviews section
                if self.reviews:
                    writer.writerow([])  # Empty row for spacing
                    writer.writerow(['PRODUCT REVIEWS'])
                    writer.writerow(['reviewer_name', 'rating', 'date', 'verified_status', 'review_content'])
                    
                    for review in self.reviews:
                        writer.writerow([
                            review.get('reviewer_name', ''),
                            review.get('rating', ''),
                            review.get('date', ''),
                            review.get('verified_status', ''),
                            review.get('review_content', '')
                        ])
            
            print(f"All data saved to {output_file}")
            
        except Exception as e:
            print(f"Error saving data: {e}")
    
    # Remove save_to_json method entirely

def main():
    print("\nShopClues Product Scraper")
    print("=" * 50)
    print("Example URL: https://www.shopclues.com/product-name-123456.html")
    url = input("\nEnter ShopClues product URL: ")
    
    # Extract product name from URL
    product_name = url.split('/')[-1].split('.')[0]
    print(f"\nProduct: {product_name}")
    
    print("\nStarting scraper...")
    scraper = ShopCluesScraper(url)
    if scraper.scrape_product():
        output_file = f"{product_name}.csv"
        scraper.save_to_csv(output_file)
        print("\nScraping completed successfully!")

if __name__ == '__main__':
    main()