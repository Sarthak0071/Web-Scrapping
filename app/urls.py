# urls.py - URL Configuration for Menu Scraper

# ONLY HTML-LOADED WEBSITES (NO JavaScript-rendered sites)
# These sites have server-side rendered menus that work without JS
URLS = [
    # SaaS & Marketing Tools (HTML-based menus)
    'https://buffer.com',
    'https://mailchimp.com', 
    'https://hootsuite.com',
    'https://www.activecampaign.com',
    'https://www.hubspot.com',
    
    # Productivity Tools (HTML menus)
    'https://www.airtable.com',
    'https://www.notion.so',
    'https://www.dropbox.com',
    'https://www.zoom.us',
    
    # Developer Tools (HTML menus)
    'https://www.stripe.com',
    'https://www.twilio.com',
    'https://www.sendgrid.com',
    'https://www.cloudflare.com',
    
    # CMS & Website Builders (HTML menus)
    'https://www.wordpress.com',
    
    # More HTML-loaded sites to add:
    'https://www.shopify.com',
    'https://www.atlassian.com',
    'https://www.monday.com',
    'https://www.trello.com',
    
    # Add more HTML-based sites here (avoid Canva, Figma, Wix - they use heavy JS)
]

# Configuration settings
CONFIG = {
    # Performance settings
    'max_workers': 10,  # Reduced for stability (was 15)
    'timeout': 25,  # Increased timeout (was 20)
    'retry_attempts': 3,
    'retry_delay': 2,
    'rate_limit_delay': 1.5,  # Increased to avoid blocks
    
    # Scraping settings
    'max_links_per_menu': 60,
    'max_menus_per_site': 15,
    'min_links_per_panel': 2,
    'max_title_length': 200,
    'max_desc_length': 300,
    
    # Output settings
    'output_dir': 'scraped_menus',
    'log_file': 'scraper.log',
    'resume_mode': True,
    'save_failures': True,
}

# Site-specific overrides
SITE_OVERRIDES = {
    'hubspot.com': {
        'trigger_pattern': r'global-nav-tab',
        'panel_pattern': r'global-nav-tab-dropdown',
    },
}

# User agents (helps avoid blocks)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]