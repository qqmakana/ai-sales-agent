"""
Free Lead Scraper - No API costs!
Scrapes DuckDuckGo, business directories, and websites for leads.
Uses multiple sources for reliability.
"""

import re
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse, quote_plus
import json

# Rotating user agents to avoid blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

def get_headers() -> Dict[str, str]:
    """Get randomized headers for requests."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }


def extract_emails_from_text(text: str) -> List[str]:
    """Extract email addresses from text using regex."""
    # Email regex pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    
    # Filter out common false positives
    filtered = []
    skip_patterns = ['example.com', 'test.com', 'domain.com', 'email.com', 'yoursite.com', 
                     'sentry.io', 'wixpress.com', 'w3.org', '.png', '.jpg', '.gif', '.css', '.js']
    
    for email in emails:
        email_lower = email.lower()
        if not any(skip in email_lower for skip in skip_patterns):
            if len(email) < 100:  # Reasonable length
                filtered.append(email.lower())
    
    return list(set(filtered))  # Remove duplicates


def scrape_website_for_emails(url: str, timeout: int = 10) -> List[str]:
    """Scrape a website for email addresses."""
    emails = set()
    
    try:
        # Ensure URL has protocol
        if not url.startswith('http'):
            url = 'https://' + url
        
        response = requests.get(url, headers=get_headers(), timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Extract from page content
        page_emails = extract_emails_from_text(response.text)
        emails.update(page_emails)
        
        # Parse HTML for contact page links
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Look for mailto links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].strip()
                if '@' in email:
                    emails.add(email.lower())
        
        # Try to find and scrape contact page
        contact_keywords = ['contact', 'about', 'get-in-touch', 'reach-us']
        for link in soup.find_all('a', href=True):
            href_lower = link['href'].lower()
            if any(kw in href_lower for kw in contact_keywords):
                try:
                    contact_url = urljoin(url, link['href'])
                    contact_response = requests.get(contact_url, headers=get_headers(), timeout=timeout)
                    contact_emails = extract_emails_from_text(contact_response.text)
                    emails.update(contact_emails)
                    
                    # Check mailto links on contact page
                    contact_soup = BeautifulSoup(contact_response.text, 'lxml')
                    for mailto in contact_soup.find_all('a', href=True):
                        if mailto['href'].startswith('mailto:'):
                            email = mailto['href'].replace('mailto:', '').split('?')[0].strip()
                            if '@' in email:
                                emails.add(email.lower())
                    break  # Found contact page, stop looking
                except:
                    continue
                    
    except Exception as e:
        print(f"[SCRAPER] Error scraping {url}: {str(e)}")
    
    return list(emails)


def scrape_duckduckgo(query: str, num_results: int = 15) -> List[Dict[str, str]]:
    """
    Scrape DuckDuckGo search results - more permissive than Google.
    Returns list of businesses with name, website, snippet.
    """
    businesses = []
    
    try:
        # DuckDuckGo HTML search
        encoded_query = quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find search results
        for result in soup.find_all('div', class_='result'):
            try:
                # Get title and link
                title_elem = result.find('a', class_='result__a')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text().strip()
                link = title_elem.get('href', '')
                
                # Get snippet
                snippet_elem = result.find('a', class_='result__snippet')
                snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                
                # Clean up the link (DuckDuckGo wraps links)
                if 'uddg=' in link:
                    # Extract actual URL from DuckDuckGo redirect
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                    if 'uddg' in parsed:
                        link = parsed['uddg'][0]
                
                if title and link and 'duckduckgo.com' not in link:
                    businesses.append({
                        'name': title,
                        'website': link,
                        'snippet': snippet
                    })
                    
                if len(businesses) >= num_results:
                    break
            except:
                continue
                
    except Exception as e:
        print(f"[SCRAPER] DuckDuckGo search error: {str(e)}")
    
    return businesses


def scrape_bing_search(query: str, num_results: int = 10) -> List[Dict[str, str]]:
    """
    Scrape Bing search as backup.
    """
    businesses = []
    
    try:
        encoded_query = quote_plus(query)
        search_url = f"https://www.bing.com/search?q={encoded_query}&count={num_results}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        for result in soup.find_all('li', class_='b_algo'):
            try:
                title_elem = result.find('h2')
                if not title_elem:
                    continue
                    
                link_elem = title_elem.find('a')
                title = link_elem.get_text().strip() if link_elem else None
                link = link_elem.get('href', '') if link_elem else None
                
                snippet_elem = result.find('p')
                snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                
                if title and link:
                    businesses.append({
                        'name': title,
                        'website': link,
                        'snippet': snippet
                    })
            except:
                continue
                
    except Exception as e:
        print(f"[SCRAPER] Bing search error: {str(e)}")
    
    return businesses


def scrape_yellow_pages_sa(niche: str, location: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Scrape Yellow Pages South Africa for business leads.
    """
    businesses = []
    
    try:
        # Format search URL
        niche_slug = niche.lower().replace(' ', '-').replace('&', 'and')
        location_slug = location.lower().replace(' ', '-')
        
        search_url = f"https://www.yellowpages.co.za/search?what={quote_plus(niche)}&where={quote_plus(location)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find business listings
            for listing in soup.find_all('div', class_='listing'):
                try:
                    name = listing.find('h2') or listing.find('a', class_='listing-name')
                    name = name.get_text().strip() if name else None
                    
                    phone = listing.find('a', class_='phone') or listing.find('span', class_='phone')
                    phone = phone.get_text().strip() if phone else ""
                    
                    website = listing.find('a', class_='website')
                    website = website['href'] if website else ""
                    
                    address = listing.find('span', class_='address') or listing.find('div', class_='address')
                    address = address.get_text().strip() if address else ""
                    
                    if name:
                        businesses.append({
                            'name': name,
                            'phone': phone,
                            'website': website,
                            'address': address,
                            'niche': niche
                        })
                        
                    if len(businesses) >= max_results:
                        break
                except:
                    continue
                    
    except Exception as e:
        print(f"[SCRAPER] Yellow Pages error: {str(e)}")
    
    return businesses


def generate_business_search_queries(niche: str, location: str) -> List[str]:
    """Generate effective Google search queries for finding businesses."""
    
    niche_lower = niche.lower()
    
    # Base queries
    queries = [
        f"{niche} companies in {location}",
        f"{niche} services {location}",
        f"best {niche} {location}",
        f"{niche} near {location}",
    ]
    
    # Niche-specific queries
    if 'security' in niche_lower:
        queries.extend([
            f"armed response companies {location}",
            f"security guarding services {location}",
            f"CCTV installation companies {location}",
            f"security patrol services {location}",
        ])
    elif 'solar' in niche_lower or 'renewable' in niche_lower:
        queries.extend([
            f"solar panel installation {location}",
            f"solar energy companies {location}",
            f"solar installers {location}",
            f"renewable energy companies {location}",
        ])
    elif 'logistics' in niche_lower or 'fleet' in niche_lower:
        queries.extend([
            f"logistics companies {location}",
            f"fleet management {location}",
            f"courier services {location}",
            f"transport companies {location}",
        ])
    
    return queries


def scrape_leads_free(niche: str, location: str = "South Africa", max_leads: int = 20) -> List[Dict[str, Any]]:
    """
    Main function: Scrape leads for FREE using DuckDuckGo, Bing, and website scraping.
    Returns list of leads with name, email, website, phone, niche.
    FAST VERSION - skips slow email checks to avoid timeouts.
    """
    all_leads = []
    seen_domains = set()
    
    print(f"[SCRAPER] Starting FAST lead search for '{niche}' in '{location}'...")
    
    # Generate search queries - use only 2 for speed
    queries = generate_business_search_queries(niche, location)
    
    for query in queries[:2]:  # Only 2 queries for speed
        print(f"[SCRAPER] Searching: {query}")
        
        # Try Bing first (faster and more reliable)
        results = scrape_bing_search(query, num_results=15)
        
        # Fallback to DuckDuckGo
        if not results:
            print(f"[SCRAPER] Trying DuckDuckGo...")
            results = scrape_duckduckgo(query, num_results=15)
        
        for result in results:
            website = result.get('website', '')
            
            # Skip invalid URLs
            if not website:
                continue
            
            # Skip common non-business sites
            skip_domains = ['facebook.com', 'linkedin.com', 'twitter.com', 'youtube.com', 
                          'wikipedia.org', 'instagram.com', 'tiktok.com', 'pinterest.com',
                          'yelp.com', 'tripadvisor.com', 'amazon.com', 'ebay.com', 'bing.com']
            
            try:
                domain = urlparse(website).netloc.lower().replace('www.', '')
                if any(skip in domain for skip in skip_domains):
                    continue
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)
            except:
                continue
            
            # Extract domain for company name if needed
            name = result.get('name', '')
            if not name and website:
                parsed = urlparse(website)
                name = parsed.netloc.replace('www.', '').split('.')[0].title()
            
            # Clean up name
            name = name.replace(' - Home', '').replace(' | Home', '').replace(' - Google Search', '').strip()
            if len(name) > 80:
                name = name[:80]
            
            lead = {
                'name': name or 'Business',
                'website': website,
                'email': '',  # Skip slow email checking
                'phone': '',
                'niche': niche,
                'source': 'web_search'
            }
            
            all_leads.append(lead)
            
            if len(all_leads) >= max_leads:
                break
        
        if len(all_leads) >= max_leads:
            break
    
    print(f"[SCRAPER] Done! Found {len(all_leads)} leads")
    
    return all_leads[:max_leads]


# For testing
if __name__ == "__main__":
    leads = scrape_leads_free("Security Services", "Johannesburg", max_leads=10)
    for lead in leads:
        print(f"- {lead['name']}: {lead['email']} ({lead['website']})")
