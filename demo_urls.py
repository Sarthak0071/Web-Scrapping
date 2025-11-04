"""
Demo URLs for testing the menu scraper

KNOWN API-FAILED SITES (included for debugging):
- zomato.com failed
- producthunt.com failed
- buffer.com failed
- mailchimp.com failed
"""
DEMO_URLS = [
    # International well-known websites
    'https://www.amazon.com',
    'https://www.apple.com',
    'https://www.microsoft.com',
    'https://www.bbc.com',
    'https://www.wikipedia.org',
   
    # International e-commerce (less known but established)
    'https://www.shopify.com',
    'https://www.wayfair.com',
    'https://www.overstock.com',
    'https://www.newegg.com',
   
   
    # === API-FAILED SITES (added for debugging) ===
    'https://www.zomato.com',     
    'https://www.producthunt.com',
    'https://buffer.com',          
    'https://mailchimp.com',       
   
    # Nepali e-commerce
    'https://www.daraz.com.np',
    'https://www.sastodeal.com',
    'https://www.gyapu.com',
   
    # Nepali IT/Tech websites
    'https://www.ictframe.com',
    'https://www.techpana.com',
    'https://www.nagariknews.nagariknetwork.com',
   
    # Nepali general websites
    'https://kathmandupost.com',
    'https://ekantipur.com',
    'https://myrepublica.nagariknetwork.com',
]