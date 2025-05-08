import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import argparse
import re
import sys

def get_movie_id(movie_url):
    """Extract IMDb movie ID from URL or return the ID if already provided."""
    if movie_url.startswith('tt'):
        return movie_url
    
    # Try to extract the ID using regex
    match = re.search(r'(tt\d+)', movie_url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid IMDb URL or ID. Please provide a valid IMDb movie URL or ID.")

def get_movie_title(movie_id):
    """Get the movie title for the given IMDb ID."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    url = f'https://www.imdb.com/title/{movie_id}/'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Try different selectors as IMDb may have multiple title formats
        title_elem = soup.select_one('h1[data-testid="hero__pageTitle"]') or soup.find('h1') or soup.select_one('.title_wrapper h1')
        if title_elem:
            # Clean up the title to remove year and other info
            title_text = title_elem.text.strip()
            # Remove year pattern (YYYY) if present
            title_text = re.sub(r'\(\d{4}\)', '', title_text).strip()
            return title_text
    
    return movie_id  # Return the ID if title can't be found

def scrape_reviews(movie_id_or_url, max_pages=5, delay_range=(3, 7)):
    """
    Scrape movie reviews from IMDb using the latest HTML structure.
    
    Args:
        movie_id_or_url: IMDb movie ID (tt12345) or URL
        max_pages: Maximum number of review pages to scrape
        delay_range: Range for random delay between requests (in seconds)
    
    Returns:
        List of review dictionaries and movie title
    """
    movie_id = get_movie_id(movie_id_or_url)
    reviews = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    print(f"Starting to scrape reviews for movie ID: {movie_id}")
    movie_title = get_movie_title(movie_id)
    print(f"Movie title: {movie_title}")
    
    # Use the direct reviews URL format
    base_url = f'https://www.imdb.com/title/{movie_id}/reviews'
    
    pages_scraped = 0
    pagination_key = None
    
    while pages_scraped < max_pages:
        # For first page or when we have a pagination key
        if pages_scraped == 0:
            url = base_url
        elif pagination_key:
            url = f"{base_url}/_ajax?paginationKey={pagination_key}"
        else:
            break
            
        pages_scraped += 1
        print(f"Scraping page {pages_scraped} from: {url}")
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page: {e}")
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find review containers based on the new IMDb structure
        # Based on the provided HTML, reviews are in article elements with class="user-review-item"
        review_containers = soup.find_all('article', class_='user-review-item')
        
        if not review_containers:
            print("No reviews found on this page. Trying alternative selectors...")
            # Try alternative selectors
            review_containers = soup.find_all('div', class_='ipc-list-card--border-speech')
            
            if not review_containers:
                print("No reviews found with alternative selectors either.")
                break
        
        print(f"Found {len(review_containers)} reviews on this page")
        
        for container in review_containers:
            try:
                review_data = {}
                
                # Get rating (if available)
                # Look for the rating span with class="ipc-rating-star"
                rating_element = container.find('span', class_='ipc-rating-star')
                if rating_element:
                    rating_value = rating_element.find('span', class_='ipc-rating-star--rating')
                    review_data['rating'] = rating_value.text.strip() if rating_value else "N/A"
                else:
                    review_data['rating'] = "N/A"
                
                # Get review title
                # Look for the h3 with class="ipc-title__text"
                title_element = container.find('h3', class_='ipc-title__text')
                if title_element:
                    # Remove the chevron icon from the title
                    title_text = re.sub(r'<svg.*?</svg>', '', str(title_element)).strip()
                    title_soup = BeautifulSoup(title_text, 'html.parser')
                    review_data['title'] = title_soup.text.strip()
                else:
                    review_data['title'] = "No Title"
                
                # Get reviewer name and date
                # Updated selector for author information
                author_section = container.find('div', {'data-testid': 'reviews-author'})
                if author_section:
                    author_link = author_section.find('a', {'data-testid': 'author-link'})
                    review_data['reviewer'] = author_link.text.strip() if author_link else "Anonymous"
                    
                    # Get date
                    date_element = author_section.find('li', class_='review-date')
                    review_data['date'] = date_element.text.strip() if date_element else "Unknown date"
                else:
                    review_data['reviewer'] = "Anonymous"
                    review_data['date'] = "Unknown date"
                
                # Get review text
                # This is challenging as it's not directly visible in the HTML snippet
                # We'll need to follow the permalink to get the full review text
                permalink = None
                permalink_link = None
                
                if author_section:
                    permalink_link = author_section.find('a', {'data-testid': 'permalink-link'})
                
                if permalink_link and 'href' in permalink_link.attrs:
                    permalink = permalink_link['href']
                    
                if permalink:
                    # Fetch the full review page
                    full_review_url = f"https://www.imdb.com{permalink}"
                    try:
                        # Add a short delay before fetching the full review
                        time.sleep(random.uniform(1, 2))
                        review_response = requests.get(full_review_url, headers=headers)
                        review_soup = BeautifulSoup(review_response.text, 'html.parser')
                        
                        # Look for the review text in various possible containers
                        review_text_elem = (
                            review_soup.find('div', class_='text show-more__control') or
                            review_soup.find('div', class_='content') or
                            review_soup.select_one('[class*="Content__ReviewContent"]')
                        )
                        
                        if review_text_elem:
                            review_data['text'] = review_text_elem.text.strip()
                        else:
                            print(f"Could not find review text for {full_review_url}")
                            review_data['text'] = "Review text not available"
                    except Exception as e:
                        print(f"Error fetching full review: {e}")
                        review_data['text'] = "Error fetching full review"
                else:
                    review_data['text'] = "No permalink available to fetch full review"
                    
                # If we got to this point, we have a complete review
                reviews.append(review_data)
                print(f"Scraped review by {review_data['reviewer']}: {review_data['title'][:30]}...")
                
            except Exception as e:
                print(f"Error parsing a review: {e}")
                continue
        
        # Check for next page - look for the pagination key
        pagination_key = None
        load_more = soup.find('div', class_='load-more-data')
        if load_more and 'data-key' in load_more.attrs:
            pagination_key = load_more['data-key']
        else:
            # Look for button with "Load More" text
            load_more_btn = soup.find('button', string=re.compile(r'Load\s+More'))
            if load_more_btn:
                parent = load_more_btn.parent
                if parent and 'data-key' in parent.attrs:
                    pagination_key = parent['data-key']
        
        if not pagination_key:
            print("No more pages available.")
            break
        
        # Be respectful with a random delay between requests
        if pages_scraped < max_pages:
            delay = random.uniform(delay_range[0], delay_range[1])
            print(f"Waiting {delay:.2f} seconds before next request...")
            time.sleep(delay)
    
    print(f"Scraped {len(reviews)} reviews in total.")
    return reviews, movie_title

def save_to_csv(reviews, movie_title, filename=None):
    """Save reviews to a CSV file."""
    if not filename:
        # Clean movie title for filename
        clean_title = re.sub(r'[^\w\s-]', '', movie_title).strip().replace(' ', '_')
        filename = f"{clean_title}_reviews.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['reviewer', 'title', 'rating', 'date', 'text']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for review in reviews:
            writer.writerow(review)
    
    print(f"Reviews saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Scrape movie reviews from IMDb')
    parser.add_argument('movie_id', help='IMDb movie ID (tt12345) or URL')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum number of pages to scrape')
    parser.add_argument('--output', help='Output CSV filename')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    try:
        print("IMDb Movie Review Scraper")
        print("-----------------------")
        reviews, movie_title = scrape_reviews(args.movie_id, max_pages=args.max_pages)
        if reviews:
            save_to_csv(reviews, movie_title, args.output)
            print(f"Successfully scraped {len(reviews)} reviews for '{movie_title}'")
        else:
            print("No reviews were found. The script may need to be updated to match IMDb's current structure.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        print("\nTroubleshooting tips:")
        print("1. Check your internet connection")
        print("2. Verify the IMDb ID is correct")
        print("3. IMDb may have changed their site structure - check for updates to this script")
        print("4. Run with --debug flag for more information")

if __name__ == "__main__":
    main()