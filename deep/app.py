

# import requests
# from bs4 import BeautifulSoup
# import json
# import re
# from urllib.parse import urljoin, urlparse
# import time
# from collections import defaultdict

# URLS = [
#     'https://mailchimp.com', 'https://www.constantcontact.com', 'https://www.getresponse.com',
#     'https://www.aweber.com', 'https://sendinblue.com', 'https://www.campaignmonitor.com',
#     'https://www.airtable.com', 'https://www.dropbox.com', 'https://todoist.com',
#     'https://evernote.com', 'https://www.rescuetime.com', 'https://toggl.com',
#     'https://www.twilio.com', 'https://www.sendgrid.com', 'https://postmarkapp.com',
#     'https://www.mailgun.com', 'https://www.plausible.io', 'https://umami.is',
#     'https://www.wordpress.com', 'https://ghost.org', 'https://write.as', 'https://neocities.org',
#     'https://www.shopify.com', 'https://bigcartel.com', 'https://gumroad.com', 'https://payhip.com',
#     'https://www.trello.com', 'https://basecamp.com', 'https://www.teuxdeux.com',
#     'https://carrd.co', 'https://typedream.com', 'https://buffer.com/'
# ]

# HEADERS = {'User-Agent': 'Mozilla/5.0'}

# # Noise patterns to exclude
# NOISE_PATTERNS = [
#     r'log\s*in', r'sign\s*in', r'sign\s*up', r'get\s*started', r'start\s*free',
#     r'try\s*free', r'book\s*demo', r'free\s*trial', r'skip\s*to', r'back\s*to',
#     r'view\s*all', r'see\s*all', r'learn\s*more', r'read\s*more',
#     r'privacy', r'terms', r'cookie', r'gdpr', r'ccpa',
#     r'twitter', r'facebook', r'linkedin', r'instagram', r'youtube', r'mastodon',
#     r'english', r'español', r'français', r'deutsch', r'language',
#     r'^icon\s', r'arrow', r'symbol', r'^[▾▸►▼▲◄◀→←↑↓]+$'
# ]

# def fetch(url):
#     try:
#         return requests.get(url, headers=HEADERS, timeout=15).text
#     except Exception as e:
#         print(f"   ❌ Fetch error: {e}")
#         return None

# def clean_text(text):
#     """Clean and normalize text"""
#     if not text:
#         return ""
#     # Remove icon descriptions
#     text = re.sub(r'An?\s+(icon\s+)?of.*?(?:symbol|arrow)', '', text, flags=re.I)
#     # Remove unicode arrows
#     text = re.sub(r'[▾▸►▼▲◄◀→←↑↓]', '', text)
#     # Normalize whitespace
#     text = re.sub(r'\s+', ' ', text).strip()
#     return text

# def is_noise(text, elem):
#     """Check if text is noise/unwanted"""
#     if not text or len(text) < 2 or len(text) > 300:
#         return True
    
#     text_lower = text.lower().strip()
    
#     # Check noise patterns
#     for pattern in NOISE_PATTERNS:
#         if re.search(pattern, text_lower):
#             return True
    
#     # Check if in footer/cookie banner (check 8 levels up)
#     for parent in list(elem.parents)[:8]:
#         cls = ' '.join(parent.get('class', [])).lower()
#         tag = parent.name
#         if tag == 'footer' or 'footer' in cls or 'cookie' in cls:
#             return True
    
#     return False

# def find_primary_nav(soup):
#     """Find the primary navigation container using scoring system"""
#     candidates = []
    
#     # Find all potential nav containers
#     for elem in soup.find_all(['nav', 'header', 'div'], limit=50):
#         cls = ' '.join(elem.get('class', [])).lower()
#         elem_id = elem.get('id', '').lower()
        
#         # Skip footers and cookie banners
#         if 'footer' in cls or 'cookie' in cls or elem.find_parent('footer'):
#             continue
        
#         # Count links
#         links = elem.find_all('a', href=True)
#         if len(links) < 2:
#             continue
        
#         # Calculate score
#         score = len(links)
        
#         # Semantic bonuses
#         if elem.name == 'nav':
#             score += 100
#         if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls + ' ' + elem_id):
#             score += 50
#         if re.search(r'\bmain\b|\bprimary\b|\btop\b', cls + ' ' + elem_id):
#             score += 100
        
#         # Position bonus (top 30% of page)
#         position = 0
#         for i, p in enumerate(list(elem.parents)):
#             if p.name == 'body':
#                 position = i
#                 break
#         if position <= 3:
#             score += 50
        
#         # Penalize deep nesting
#         score -= max(0, position - 5) * 10
        
#         candidates.append((score, elem))
    
#     if not candidates:
#         return None
    
#     # Return highest scoring
#     candidates.sort(key=lambda x: x[0], reverse=True)
#     return candidates[0][1]

# def extract_link_data(link, base_url, seen_urls):
#     """Extract and validate link data"""
#     href = link.get('href', '').strip()
    
#     # Skip invalid hrefs
#     if not href or href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
#         return None
    
#     # Get title
#     title = clean_text(link.get_text(strip=True))
#     if not title or is_noise(title, link):
#         return None
    
#     # Construct full URL
#     full_url = urljoin(base_url, href)
    
#     # Skip if already seen
#     if full_url in seen_urls:
#         return None
    
#     # Extract description if present
#     description = ""
#     for desc_elem in link.find_all(['p', 'span'], class_=re.compile(r'\bdesc\b|\bsubtitle\b|\bcaption\b', re.I), limit=2):
#         desc_text = clean_text(desc_elem.get_text(strip=True))
#         if desc_text and desc_text != title and len(desc_text) < 500:
#             description = desc_text
#             break
    
#     seen_urls.add(full_url)
    
#     return {
#         'title': title,
#         'description': description,
#         'url': full_url
#     }

# def find_dropdown_panel(trigger_elem, soup):
#     """Find the panel associated with a dropdown trigger"""
#     panel = None
    
#     # Method 1: aria-controls
#     if panel_id := trigger_elem.get('aria-controls'):
#         panel = soup.find(id=panel_id)
#         if panel:
#             return panel
    
#     # Method 2: data-target
#     if data_target := trigger_elem.get('data-target'):
#         panel = soup.find(id=data_target.lstrip('#'))
#         if panel:
#             return panel
    
#     # Method 3: Parent <li> contains submenu
#     parent_li = trigger_elem.find_parent('li')
#     if parent_li:
#         # Look for direct child ul/div with submenu classes
#         for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
#             if child.find('a', href=True):
#                 return child
        
#         # Look deeper for submenu
#         panel = parent_li.find(['ul', 'div', 'section'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
#         if panel and panel.find('a', href=True):
#             return panel
    
#     # Method 4: Next sibling
#     next_sib = trigger_elem.find_next_sibling(['div', 'ul', 'section'])
#     if next_sib and next_sib.find('a', href=True):
#         return next_sib
    
#     # Method 5: Parent's next sibling
#     parent = trigger_elem.parent
#     if parent:
#         next_sib = parent.find_next_sibling(['div', 'ul', 'section'])
#         if next_sib and next_sib.find('a', href=True):
#             return next_sib
    
#     return None

# def extract_sections_from_panel(panel, base_url, seen_urls):
#     """Extract hierarchical sections from dropdown panel"""
#     sections = []
#     processed_links = set()
    
#     # STRATEGY 1: Column-based mega menus
#     columns = panel.find_all(['div', 'section', 'li'], class_=re.compile(r'\bcol\b|\bcolumn\b|\bgrid-item\b', re.I), recursive=False)
#     if len(columns) >= 2:
#         for col in columns:
#             section_title = None
            
#             # Find section heading
#             for heading in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], limit=1):
#                 section_title = clean_text(heading.get_text(strip=True))
#                 if section_title and 2 <= len(section_title) <= 150:
#                     break
            
#             # Try heading classes if no h tag
#             if not section_title:
#                 for elem in col.find_all(class_=re.compile(r'\btitle\b|\bheading\b|\blabel\b', re.I), limit=1):
#                     if elem.name not in ['a', 'span']:
#                         section_title = clean_text(elem.get_text(strip=True))
#                         if section_title and 2 <= len(section_title) <= 150:
#                             break
            
#             # Extract links
#             items = []
#             for link in col.find_all('a', href=True, limit=50):
#                 link_id = id(link)
#                 if link_id in processed_links:
#                     continue
                
#                 # Skip if link text matches section title
#                 if section_title and clean_text(link.get_text(strip=True)) == section_title:
#                     continue
                
#                 if data := extract_link_data(link, base_url, seen_urls):
#                     items.append(data)
#                     processed_links.add(link_id)
            
#             if items:
#                 sections.append({
#                     'section_title': section_title,
#                     'items': items
#                 })
        
#         if sections:
#             return sections
    
#     # STRATEGY 2: Heading-based sections
#     headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
#     if len(headings) >= 1:
#         for i, heading in enumerate(headings):
#             section_title = clean_text(heading.get_text(strip=True))
#             if not section_title or len(section_title) < 2 or len(section_title) > 150:
#                 continue
            
#             # Find all links until next heading
#             next_heading = headings[i + 1] if i + 1 < len(headings) else None
#             items = []
            
#             # Navigate through siblings and descendants
#             current = heading.find_next()
#             iterations = 0
#             while current and iterations < 200:
#                 iterations += 1
                
#                 # Stop at next heading
#                 if next_heading and (current == next_heading or next_heading in list(current.parents)):
#                     break
                
#                 # Extract link
#                 if hasattr(current, 'name') and current.name == 'a' and current.get('href'):
#                     link_id = id(current)
#                     if link_id not in processed_links:
#                         # Skip if matches section title
#                         if clean_text(current.get_text(strip=True)) != section_title:
#                             if data := extract_link_data(current, base_url, seen_urls):
#                                 items.append(data)
#                                 processed_links.add(link_id)
                
#                 try:
#                     current = current.find_next()
#                 except:
#                     break
            
#             if items:
#                 sections.append({
#                     'section_title': section_title,
#                     'items': items
#                 })
        
#         if sections:
#             return sections
    
#     # STRATEGY 3: List-based sections
#     top_lists = [ul for ul in panel.find_all('ul') if not ul.find_parent('ul')]
#     if len(top_lists) >= 1:
#         for ul in top_lists:
#             # Check if list has a preceding heading
#             section_title = None
#             prev = ul.find_previous_sibling()
#             if prev and prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
#                 section_title = clean_text(prev.get_text(strip=True))
            
#             items = []
#             for link in ul.find_all('a', href=True, limit=50):
#                 link_id = id(link)
#                 if link_id not in processed_links:
#                     if data := extract_link_data(link, base_url, seen_urls):
#                         items.append(data)
#                         processed_links.add(link_id)
            
#             if items:
#                 sections.append({
#                     'section_title': section_title,
#                     'items': items
#                 })
        
#         if sections:
#             return sections
    
#     # STRATEGY 4: Flat extraction (fallback)
#     items = []
#     for link in panel.find_all('a', href=True, limit=100):
#         link_id = id(link)
#         if link_id not in processed_links:
#             if data := extract_link_data(link, base_url, seen_urls):
#                 items.append(data)
#                 processed_links.add(link_id)
    
#     if items:
#         return [{'section_title': None, 'items': items}]
    
#     return []

# def extract_navigation(nav, soup, base_url):
#     """Extract complete navigation hierarchy"""
#     menus = []
#     seen_urls = set()
#     seen_triggers = set()
    
#     # PHASE 1: Find all potential dropdown triggers
#     dropdown_triggers = []
    
#     # Type A: <li> with nested <ul>
#     for li in nav.find_all('li'):
#         # Get direct child link/button
#         trigger = li.find(['a', 'button'], recursive=False)
#         if not trigger:
#             continue
        
#         trigger_text = clean_text(trigger.get_text(strip=True))
#         if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 80:
#             continue
        
#         if is_noise(trigger_text, trigger):
#             continue
        
#         # Check for submenu
#         submenu = li.find(['ul', 'div', 'section'], recursive=False)
#         if not submenu:
#             submenu = li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
        
#         if submenu and len(submenu.find_all('a', href=True)) >= 1:
#             if trigger_text.lower() not in seen_triggers:
#                 dropdown_triggers.append((trigger_text, submenu))
#                 seen_triggers.add(trigger_text.lower())
    
#     # Type B: Elements with ARIA attributes
#     for elem in nav.find_all(['button', 'a', 'div']):
#         if not (elem.get('aria-expanded') or elem.get('aria-haspopup')):
#             continue
        
#         trigger_text = clean_text(elem.get_text(strip=True))
#         if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 80:
#             continue
        
#         if is_noise(trigger_text, elem):
#             continue
        
#         panel = find_dropdown_panel(elem, soup)
#         if panel and len(panel.find_all('a', href=True)) >= 1:
#             if trigger_text.lower() not in seen_triggers:
#                 dropdown_triggers.append((trigger_text, panel))
#                 seen_triggers.add(trigger_text.lower())
    
#     # PHASE 2: Extract dropdown menus
#     for trigger_text, panel in dropdown_triggers:
#         sections = extract_sections_from_panel(panel, base_url, seen_urls)
        
#         if sections:
#             total_items = sum(len(s['items']) for s in sections)
#             print(f"   ✅ {trigger_text}: {total_items} items, {len(sections)} sections")
#             menus.append({
#                 'menu_name': trigger_text,
#                 'sections': sections
#             })
    
#     # PHASE 3: Extract top-level links (not in dropdowns)
#     top_level_links = []
    
#     # Direct <a> children of nav
#     for link in nav.find_all('a', href=True, limit=300):
#         # Skip if already in a dropdown
#         link_id = id(link)
        
#         # Check if inside processed dropdown
#         is_in_dropdown = False
#         for _, panel in dropdown_triggers:
#             if link in panel.find_all('a'):
#                 is_in_dropdown = True
#                 break
        
#         if is_in_dropdown:
#             continue
        
#         # Skip if parent li has submenu
#         parent_li = link.find_parent('li')
#         if parent_li:
#             has_submenu = parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega', re.I))
#             if has_submenu:
#                 continue
        
#         if data := extract_link_data(link, base_url, seen_urls):
#             top_level_links.append(data)
    
#     # Add top-level links as separate menu
#     if top_level_links:
#         print(f"   ✅ Navigation: {len(top_level_links)} top-level items")
#         menus.append({
#             'menu_name': 'Navigation',
#             'sections': [{
#                 'section_title': None,
#                 'items': top_level_links
#             }]
#         })
    
#     return menus

# def validate_navigation(menus, base_url):
#     """Validate extracted navigation quality"""
#     if not menus:
#         return False, "No menus extracted"
    
#     # Count total items
#     total_items = sum(len(s['items']) for m in menus for s in m['sections'])
#     if total_items < 2:
#         return False, f"Too few items: {total_items}"
    
#     # Check internal link ratio
#     domain = urlparse(base_url).netloc.replace('www.', '')
#     internal_count = sum(
#         1 for m in menus 
#         for s in m['sections'] 
#         for i in s['items'] 
#         if domain in urlparse(i['url']).netloc
#     )
    
#     ratio = internal_count / total_items if total_items > 0 else 0
#     if ratio < 0.15:
#         return False, f"Low internal ratio: {ratio*100:.1f}%"
    
#     return True, f"{total_items} items, {ratio*100:.1f}% internal"

# def scrape(url):
#     """Main scraping function"""
#     print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    
#     html = fetch(url)
#     if not html:
#         return None
    
#     soup = BeautifulSoup(html, 'html.parser')
    
#     # Find primary navigation
#     nav = find_primary_nav(soup)
#     if not nav:
#         print("   ❌ No navigation found")
#         return None
    
#     # Extract navigation structure
#     menus = extract_navigation(nav, soup, url)
    
#     # Validate
#     is_valid, msg = validate_navigation(menus, url)
#     print(f"   📊 {msg}")
    
#     if not is_valid:
#         print("   ❌ REJECTED")
#         return None
    
#     return {
#         'website': url,
#         'domain': urlparse(url).netloc,
#         'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
#         'menus': menus
#     }

# def main():
#     success = 0
    
#     for i, url in enumerate(URLS, 1):
#         print(f"\n{'#'*70}\n[{i}/{len(URLS)}]\n{'#'*70}")
        
#         try:
#             if data := scrape(url):
#                 filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
#                 with open(filename, 'w', encoding='utf-8') as f:
#                     json.dump(data, f, indent=2, ensure_ascii=False)
#                 print(f"   💾 Saved to {filename}")
#                 success += 1
#         except Exception as e:
#             print(f"   ❌ Error: {e}")
#             import traceback
#             traceback.print_exc()
        
#         time.sleep(2)
    
#     print(f"\n{'='*70}\n📊 SUCCESS: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}")

# if __name__ == "__main__":
#     main()





import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
import time
from collections import defaultdict

URLS = [
    'https://mailchimp.com', 'https://www.constantcontact.com', 'https://www.getresponse.com',
    'https://www.aweber.com', 'https://sendinblue.com', 'https://www.campaignmonitor.com',
    'https://www.airtable.com', 'https://www.dropbox.com', 'https://todoist.com',
    'https://evernote.com', 'https://www.rescuetime.com', 'https://toggl.com',
    'https://www.twilio.com', 'https://www.sendgrid.com', 'https://postmarkapp.com',
    'https://www.mailgun.com', 'https://www.plausible.io', 'https://umami.is',
    'https://www.wordpress.com', 'https://ghost.org', 'https://write.as', 'https://neocities.org',
    'https://www.shopify.com', 'https://bigcartel.com', 'https://gumroad.com', 'https://payhip.com',
    'https://www.trello.com', 'https://basecamp.com', 'https://www.teuxdeux.com',
    'https://carrd.co', 'https://typedream.com', 'https://buffer.com/'
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

NOISE_KEYWORDS = [
    'log in', 'login', 'sign in', 'signin', 'sign up', 'signup', 'get started', 
    'start free', 'try free', 'free trial', 'book demo', 'request demo', 'watch demo',
    'skip to', 'jump to', 'back to', 'return to', 'go to',
    'view all', 'see all', 'show all', 'learn more', 'read more', 'explore all',
    'privacy policy', 'terms of service', 'cookie policy', 'gdpr', 'ccpa',
    'twitter', 'facebook', 'linkedin', 'instagram', 'youtube', 'github social',
    'mastodon', 'discord', 'slack', 'tiktok', 'reddit',
    'english', 'español', 'français', 'deutsch', 'italiano', 'português',
    'language', 'currency', 'region', 'country'
]

ICON_PATTERNS = [
    r'an?\s+icon\s+of', r'chevron', r'arrow\s+(right|left|up|down)', r'caret',
    r'^[▾▸►▼▲◄◀→←↑↓✓✕✗×]+$', r'right\s+pointing', r'left\s+pointing'
]

def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"   ❌ Fetch error: {str(e)[:100]}")
        return None

def clean_text(text):
    """Ultra-aggressive text cleaning"""
    if not text:
        return ""
    
    # Remove icon/screen reader text
    for pattern in ICON_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.I)
    
    # Remove unicode symbols
    text = re.sub(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹]', '', text)
    
    # Remove "New" badges
    text = re.sub(r'\bNew\b', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove leading/trailing punctuation
    text = re.sub(r'^[^\w]+|[^\w]+$', '', text)
    
    return text

def is_noise(text, elem):
    """Detect noise/unwanted content"""
    if not text or len(text) < 2 or len(text) > 300:
        return True
    
    text_lower = text.lower().strip()
    
    # Exact match noise keywords
    if text_lower in NOISE_KEYWORDS:
        return True
    
    # Partial match for longer keywords
    for keyword in NOISE_KEYWORDS:
        if len(keyword) > 5 and keyword in text_lower:
            return True
    
    # Check element classes
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bsr-only\b|\bvisually-hidden\b|\bhidden\b', classes):
        return True
    
    # Check parent chain (10 levels)
    for parent in list(elem.parents)[:10]:
        p_class = ' '.join(parent.get('class', [])).lower()
        p_id = parent.get('id', '').lower()
        p_tag = parent.name
        
        if p_tag == 'footer':
            return True
        
        if re.search(r'\bfooter\b|\bcookie\b|\bsearch\b|\bmobile(?:-menu)?\b|\bsidebar\b|\boff-canvas\b', p_class + ' ' + p_id):
            return True
    
    return False

def is_visible(elem):
    """Check element visibility"""
    style = elem.get('style', '').lower()
    if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', ''):
        return False
    
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bhidden\b|\binvisible\b|\bd-none\b', classes):
        return False
    
    return True

def count_top_level_items(nav):
    """Count direct navigation items (not all descendant links)"""
    count = 0
    
    # Strategy 1: <ul><li> structure
    for ul in nav.find_all('ul', recursive=False, limit=5):
        count += len(ul.find_all('li', recursive=False))
    
    if count > 0:
        return count
    
    # Strategy 2: Nested <ul> (look one level deeper)
    for child in nav.children:
        if hasattr(child, 'name') and child.name in ['div', 'nav']:
            for ul in child.find_all('ul', recursive=False, limit=5):
                count += len(ul.find_all('li', recursive=False))
    
    if count > 0:
        return count
    
    # Strategy 3: Direct <a>/<button> children
    for child in nav.children:
        if hasattr(child, 'name') and child.name in ['a', 'button']:
            if is_visible(child):
                count += 1
    
    if count > 0:
        return count
    
    # Strategy 4: Wrapper divs with clickables
    for child in nav.find_all(['div', 'li'], recursive=False, limit=30):
        if child.find(['a', 'button'], recursive=False):
            count += 1
    
    return count

def find_primary_nav(soup):
    """PHASE 0: Ultra-precise container detection"""
    candidates = []
    
    for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
        # Must be visible
        if not is_visible(elem):
            continue
        
        # Get classes and ID
        cls = ' '.join(elem.get('class', [])).lower()
        elem_id = elem.get('id', '').lower()
        
        # REJECT: footer, sidebar, mobile, search
        if re.search(r'\bfooter\b|\bsidebar\b|\bmobile-menu\b|\boff-canvas\b|\bsearch\b', cls + ' ' + elem_id):
            continue
        
        if elem.find_parent('footer'):
            continue
        
        # Count TOP-LEVEL items (critical!)
        top_level_count = count_top_level_items(elem)
        
        # REJECT: Too few or too many
        if not (3 <= top_level_count <= 25):
            continue
        
        # Count all clickables (for context)
        all_clickables = len(elem.find_all(['a', 'button']))
        
        # Base score from top-level count
        score = 100
        
        # BONUS: Semantic tags
        if elem.name == 'nav':
            score += 200
        if elem.get('role') == 'navigation':
            score += 150
        
        # BONUS: Semantic classes/IDs
        if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls + ' ' + elem_id):
            score += 80
        if re.search(r'\bmain\b|\bprimary\b|\btop\b|\bglobal\b', cls + ' ' + elem_id):
            score += 120
        
        # BONUS: Position (prefer elements early in DOM)
        position_in_dom = 0
        for i, parent in enumerate(elem.parents):
            if parent.name == 'body':
                position_in_dom = i
                break
        
        if position_in_dom <= 3:
            score += 100
        elif position_in_dom <= 5:
            score += 50
        else:
            score -= (position_in_dom - 5) * 20
        
        # BONUS: Has <ul> structure
        if elem.find('ul'):
            score += 40
        
        # PENALTY: Too deeply nested
        if position_in_dom > 8:
            score -= 150
        
        candidates.append((score, elem, top_level_count, all_clickables))
    
    if not candidates:
        return None
    
    # Sort by score
    candidates.sort(key=lambda x: x[0], reverse=True)
    
    best = candidates[0]
    print(f"   🎯 Nav found: {best[2]} top-level, {best[3]} total clickables, score={best[0]}")
    
    return best[1]

def find_dropdown_panel(trigger_elem, soup):
    """Find panel for dropdown trigger - 5 methods"""
    
    # Method 1: aria-controls
    if panel_id := trigger_elem.get('aria-controls'):
        panel = soup.find(id=panel_id)
        if panel and panel.find(['a', 'button']):
            return panel
    
    # Method 2: data-target variants
    for attr in ['data-target', 'data-bs-target', 'data-dropdown', 'data-panel']:
        if target := trigger_elem.get(attr):
            target = target.lstrip('#')
            panel = soup.find(id=target)
            if panel and panel.find(['a', 'button']):
                return panel
    
    # Method 3: Parent <li> contains submenu
    parent_li = trigger_elem.find_parent('li')
    if parent_li:
        # Direct child ul/div
        for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
            if child.find(['a', 'button']):
                return child
        
        # Deeper search with dropdown classes
        panel = parent_li.find(['ul', 'div', 'section'], 
                               class_=re.compile(r'dropdown|submenu|mega|panel|flyout', re.I))
        if panel and panel.find(['a', 'button']):
            return panel
    
    # Method 4: Next sibling with dropdown class
    next_sib = trigger_elem.find_next_sibling(['div', 'ul', 'section'])
    if next_sib:
        cls = ' '.join(next_sib.get('class', [])).lower()
        if re.search(r'dropdown|menu|panel|flyout|mega', cls):
            if next_sib.find(['a', 'button']):
                return next_sib
    
    # Method 5: Parent's next sibling
    parent = trigger_elem.parent
    if parent and parent.name in ['li', 'div', 'nav']:
        next_sib = parent.find_next_sibling(['div', 'ul', 'section'])
        if next_sib:
            cls = ' '.join(next_sib.get('class', [])).lower()
            if re.search(r'dropdown|menu|panel', cls):
                if next_sib.find(['a', 'button']):
                    return next_sib
    
    return None

def is_dropdown_trigger(elem, soup):
    """PHASE 2: Detect dropdown triggers (including hybrid link+trigger)"""
    
    # RULE 1: Has ARIA attributes
    if elem.get('aria-expanded') or elem.get('aria-haspopup'):
        return True
    
    # RULE 2: Has data attributes
    if elem.get('data-toggle') or elem.get('data-target') or elem.get('data-dropdown'):
        return True
    
    # RULE 3: Is a button (assume trigger unless proven otherwise)
    if elem.name == 'button':
        # Check if has panel
        panel = find_dropdown_panel(elem, soup)
        if panel:
            return True
        # If no panel, might be JS-rendered (we'll handle separately)
    
    # RULE 4: Parent <li> has submenu (CRITICAL FOR HYBRID TRIGGERS)
    parent_li = elem.find_parent('li')
    if parent_li:
        # Check for nested <ul>
        submenu = parent_li.find('ul', recursive=False)
        if submenu and submenu.find(['a', 'button']):
            return True
        
        # Check for dropdown div
        submenu = parent_li.find(['div', 'section'], 
                                 class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
        if submenu and submenu.find(['a', 'button']):
            return True
    
    # RULE 5: Next sibling is dropdown panel
    next_sib = elem.find_next_sibling(['div', 'ul', 'section'])
    if next_sib:
        cls = ' '.join(next_sib.get('class', [])).lower()
        if re.search(r'dropdown|submenu|mega|panel', cls):
            if next_sib.find(['a', 'button']):
                return True
    
    # RULE 6: Has href="#" or javascript (old-style triggers)
    href = elem.get('href', '').strip()
    if href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
        panel = find_dropdown_panel(elem, soup)
        if panel:
            return True
    
    return False

def extract_link_data(link, base_url, seen_urls):
    """Extract link with validation"""
    href = link.get('href', '').strip()
    
    # Skip invalid hrefs
    if not href or href.startswith('javascript:') or href == '#':
        return None
    
    # Get title
    title = clean_text(link.get_text(strip=True))
    if not title or is_noise(title, link):
        return None
    
    if len(title) < 2 or len(title) > 200:
        return None
    
    # Build full URL
    full_url = urljoin(base_url, href)
    
    # Skip duplicates
    if full_url in seen_urls:
        return None
    
    # Extract description
    description = ""
    
    # Look in children
    for desc_elem in link.find_all(['p', 'span', 'div'], 
                                    class_=re.compile(r'\bdesc\b|\bsubtitle\b|\bcaption\b|\bsummary\b', re.I), 
                                    limit=3):
        desc_text = clean_text(desc_elem.get_text(strip=True))
        if desc_text and desc_text != title and 5 < len(desc_text) < 500:
            description = desc_text
            break
    
    # Check next sibling
    if not description:
        next_elem = link.find_next_sibling(['p', 'span', 'div'])
        if next_elem and not next_elem.find('a'):
            desc_text = clean_text(next_elem.get_text(strip=True))
            if desc_text and desc_text != title and 5 < len(desc_text) < 500:
                description = desc_text
    
    seen_urls.add(full_url)
    
    return {
        'title': title,
        'description': description,
        'url': full_url
    }

def extract_sections_from_panel(panel, base_url, seen_urls, panel_bounds=None):
    """PHASE 5: Extract sections with boundary detection"""
    sections = []
    processed_links = set()
    
    # Get panel boundaries
    if panel_bounds is None:
        panel_start_line = getattr(panel, 'sourceline', 0)
        panel_html = str(panel)
        panel_end_line = panel_start_line + panel_html.count('\n') + 50  # Buffer
    else:
        panel_start_line, panel_end_line = panel_bounds
    
    def is_within_panel(elem):
        """Check if element is within panel boundaries"""
        elem_line = getattr(elem, 'sourceline', panel_start_line)
        return panel_start_line <= elem_line <= panel_end_line
    
    # STRATEGY 1: Column-based mega-menus
    columns = []
    
    for pattern in [
        r'\bcol-|\bcolumn-|\bgrid-item',
        r'\bcol\b',
        r'\bmenu-col\b|\bmega-col\b'
    ]:
        cols = panel.find_all(['div', 'section', 'li'], 
                              class_=re.compile(pattern, re.I), 
                              limit=50)
        if len(cols) >= 2:
            columns = cols
            break
    
    if len(columns) >= 2:
        for col in columns:
            if not is_within_panel(col):
                continue
            
            section_title = None
            
            # Find heading
            for heading in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=3):
                if heading.find('a'):
                    continue
                
                title_text = clean_text(heading.get_text(strip=True))
                if title_text and 2 <= len(title_text) <= 150 and not is_noise(title_text, heading):
                    section_title = title_text
                    break
            
            # Try heading classes
            if not section_title:
                for elem in col.find_all(class_=re.compile(r'\btitle\b|\bheading\b|\blabel\b', re.I), limit=3):
                    if elem.name == 'a':
                        continue
                    title_text = clean_text(elem.get_text(strip=True))
                    if title_text and 2 <= len(title_text) <= 150 and not is_noise(title_text, elem):
                        section_title = title_text
                        break
            
            # Extract links
            items = []
            for link in col.find_all(['a', 'button'], limit=300):
                if not link.get('href') and link.name == 'button':
                    continue
                
                if not is_within_panel(link):
                    continue
                
                link_id = id(link)
                if link_id in processed_links:
                    continue
                
                if section_title and clean_text(link.get_text(strip=True)) == section_title:
                    continue
                
                if data := extract_link_data(link, base_url, seen_urls):
                    items.append(data)
                    processed_links.add(link_id)
            
            if items:
                sections.append({
                    'section_title': section_title,
                    'items': items
                })
        
        if sections:
            return sections
    
    # STRATEGY 2: Heading-based sections
    headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    if len(headings) >= 1:
        for i, heading in enumerate(headings):
            if not is_within_panel(heading):
                continue
            
            if heading.find('a'):
                continue
            
            section_title = clean_text(heading.get_text(strip=True))
            if not section_title or len(section_title) < 2 or len(section_title) > 150:
                continue
            
            if is_noise(section_title, heading):
                continue
            
            next_heading = headings[i + 1] if i + 1 < len(headings) else None
            
            items = []
            current = heading.find_next()
            iterations = 0
            
            while current and iterations < 1000:
                iterations += 1
                
                # Stop at boundaries
                if not is_within_panel(current):
                    break
                
                if next_heading and (current == next_heading or next_heading in list(current.parents)):
                    break
                
                if panel not in list(current.parents):
                    break
                
                # Extract link
                if hasattr(current, 'name') and current.name in ['a', 'button'] and current.get('href'):
                    link_id = id(current)
                    if link_id not in processed_links:
                        link_text = clean_text(current.get_text(strip=True))
                        if link_text != section_title:
                            if data := extract_link_data(current, base_url, seen_urls):
                                items.append(data)
                                processed_links.add(link_id)
                
                try:
                    current = current.find_next()
                except:
                    break
            
            if items:
                sections.append({
                    'section_title': section_title,
                    'items': items
                })
        
        if sections:
            return sections
    
    # STRATEGY 3: List-based
    top_lists = [ul for ul in panel.find_all('ul', limit=100) if not ul.find_parent('ul')]
    
    if top_lists:
        for ul in top_lists:
            if not is_within_panel(ul):
                continue
            
            section_title = None
            
            # Check preceding heading
            prev = ul.find_previous_sibling()
            if prev and prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                section_title = clean_text(prev.get_text(strip=True))
                if len(section_title) < 2 or len(section_title) > 150:
                    section_title = None
            
            items = []
            for link in ul.find_all(['a', 'button'], limit=300):
                if not link.get('href'):
                    continue
                
                if not is_within_panel(link):
                    continue
                
                link_id = id(link)
                if link_id not in processed_links:
                    if data := extract_link_data(link, base_url, seen_urls):
                        items.append(data)
                        processed_links.add(link_id)
            
            if items:
                sections.append({
                    'section_title': section_title,
                    'items': items
                })
        
        if sections:
            return sections
    
    # STRATEGY 4: Flat fallback
    items = []
    for link in panel.find_all(['a', 'button'], limit=1000):
        if not link.get('href'):
            continue
        
        if not is_within_panel(link):
            continue
        
        link_id = id(link)
        if link_id not in processed_links:
            if data := extract_link_data(link, base_url, seen_urls):
                items.append(data)
                processed_links.add(link_id)
    
    if items:
        return [{'section_title': None, 'items': items}]
    
    return []

def extract_navigation(nav, soup, base_url):
    """Extract complete navigation structure"""
    menus = []
    seen_urls = set()
    seen_trigger_texts = set()
    dropdown_trigger_elements = set()
    dropdown_link_ids = set()
    js_rendered_triggers = []
    
    print("   🔍 Phase 1: Identifying dropdown triggers...")
    
    dropdown_data = []
    
    # Type A: <li> with nested submenu
    for li in nav.find_all('li', limit=200):
        trigger = None
        for child in li.find_all(['a', 'button'], recursive=False, limit=1):
            trigger = child
            break
        
        if not trigger or not is_visible(trigger):
            continue
        
        trigger_text = clean_text(trigger.get_text(strip=True))
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 100:
            continue
        
        if is_noise(trigger_text, trigger):
            continue
        
        # Check for submenu
        submenu = li.find(['ul', 'div', 'section'], recursive=False)
        if not submenu:
            submenu = li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
        
        if submenu and len(submenu.find_all(['a', 'button'])) >= 1:
            if trigger_text.lower() not in seen_trigger_texts:
                dropdown_data.append((trigger_text, submenu, trigger))
                seen_trigger_texts.add(trigger_text.lower())
                dropdown_trigger_elements.add(id(trigger))
    
    # Type B: ARIA/data attribute triggers
    for elem in nav.find_all(['button', 'a', 'div'], limit=200):
        if not is_visible(elem):
            continue
        
        if not (elem.get('aria-expanded') or elem.get('aria-haspopup') or 
                elem.get('data-toggle') or elem.get('data-target')):
            continue
        
        trigger_text = clean_text(elem.get_text(strip=True))
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 100:
            continue
        
        if is_noise(trigger_text, elem):
            continue
        
        panel = find_dropdown_panel(elem, soup)
        
        # PHASE 4: Detect JS-rendered dropdowns
        if not panel and elem.name == 'button':
            print(f"      ⚠️  JS-rendered dropdown (skipped): '{trigger_text}'")
            js_rendered_triggers.append(trigger_text)
            dropdown_trigger_elements.add(id(elem))
            continue
        
        if panel and len(panel.find_all(['a', 'button'])) >= 1:
            if trigger_text.lower() not in seen_trigger_texts:
                dropdown_data.append((trigger_text, panel, elem))
                seen_trigger_texts.add(trigger_text.lower())
                dropdown_trigger_elements.add(id(elem))
    
    print(f"   ✓ Found {len(dropdown_data)} dropdowns, {len(js_rendered_triggers)} JS-rendered")
    
    # PHASE 2: Extract dropdown contents
    print("   🔍 Phase 2: Extracting dropdown contents...")
    
    for trigger_text, panel, trigger_elem in dropdown_data:
        # Mark all links in dropdown
        for link in panel.find_all(['a', 'button']):
            dropdown_link_ids.add(id(link))
        
        sections = extract_sections_from_panel(panel, base_url, seen_urls)
        
        if sections:
            total = sum(len(s['items']) for s in sections)
            print(f"      ✅ '{trigger_text}': {total} items, {len(sections)} sections")
            menus.append({
                'menu_name': trigger_text,
                'sections': sections
            })
    
    # PHASE 3: Extract top-level links
    print("   🔍 Phase 3: Extracting top-level links...")
    
    top_level_items = []
    
    for link in nav.find_all(['a', 'button'], limit=1000):
        if not is_visible(link):
            continue
        
        # Must have href for links
        if link.name == 'a' and not link.get('href'):
            continue
        
        link_id = id(link)
        
        # Skip dropdown triggers
        if link_id in dropdown_trigger_elements:
            continue
        
        # Skip items inside dropdowns
        if link_id in dropdown_link_ids:
            continue
        
        # Skip if parent <li> has submenu
        parent_li = link.find_parent('li')
        if parent_li:
            has_submenu = parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I))
            if has_submenu:
                continue
        
        # Extract
        if link.name == 'a':
            if data := extract_link_data(link, base_url, seen_urls):
                top_level_items.append(data)
    
    if top_level_items:
        print(f"      ✅ Top-level: {len(top_level_items)} items")
        menus.append({
            'menu_name': 'Navigation',
            'sections': [{
                'section_title': None,
                'items': top_level_items
            }]
        })
    
    return menus

def validate_navigation(menus, base_url):
    """Strict validation"""
    if not menus:
        return False, "No menus extracted"
    
    total_items = sum(len(s['items']) for m in menus for s in m['sections'])
    
    if total_items < 3:
        return False, f"Too few items: {total_items}"
    
    # Internal link ratio
    domain = urlparse(base_url).netloc.replace('www.', '')
    internal = sum(
        1 for m in menus 
        for s in m['sections'] 
        for i in s['items'] 
        if domain in urlparse(i['url']).netloc
    )
    
    ratio = internal / total_items if total_items > 0 else 0
    
    if ratio < 0.20:
        return False, f"Low internal ratio: {ratio*100:.0f}%"
    
    # Duplicate check
    url_counts = defaultdict(int)
    for m in menus:
        for s in m['sections']:
            for item in s['items']:
                url_counts[item['url']] += 1
    
    duplicates = sum(1 for count in url_counts.values() if count > 2)
    if duplicates > total_items * 0.3:
        return False, f"Too many duplicates: {duplicates}/{total_items}"
    
    return True, f"{total_items} items, {ratio*100:.0f}% internal, {len(menus)} menus"

def scrape(url):
    """Main scraping orchestrator"""
    print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    
    html = fetch(url)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # PHASE 0: Find primary nav
    nav = find_primary_nav(soup)
    if not nav:
        print("   ❌ No primary navigation found")
        return None
    
    # Extract navigation
    menus = extract_navigation(nav, soup, url)
    
    # Validate
    is_valid, msg = validate_navigation(menus, url)
    print(f"   📊 Result: {msg}")
    
    if not is_valid:
        print(f"   ❌ REJECTED: {msg}")
        return None
    
    print("   ✅ ACCEPTED")
    
    return {
        'website': url,
        'domain': urlparse(url).netloc,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'menus': menus
    }

def main():
    print(f"\n{'#'*70}")
    print(f"# UNIVERSAL HTML NAVIGATION SCRAPER v2.0")
    print(f"# Master Plan Implementation")
    print(f"# Processing {len(URLS)} websites")
    print(f"{'#'*70}")
    
    success = 0
    results = []
    
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
        
        try:
            if data := scrape(url):
                # Handle duplicate menu names
                menu_names = {}
                for menu in data['menus']:
                    name = menu['menu_name']
                    if name in menu_names:
                        menu_names[name] += 1
                        menu['menu_name'] = f"{name} ({menu_names[name]})"
                    else:
                        menu_names[name] = 1
                
                filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   💾 Saved: {filename}")
                success += 1
                results.append((url, 'SUCCESS', filename))
            else:
                results.append((url, 'FAILED', 'Validation failed'))
        
        except Exception as e:
            print(f"   ❌ Exception: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            results.append((url, 'ERROR', str(e)[:100]))
        
        # Rate limiting
        time.sleep(2)
    
    # Final summary
    print(f"\n\n{'='*70}")
    print(f"{'='*70}")
    print(f"   FINAL RESULTS: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)")
    print(f"{'='*70}")
    print(f"{'='*70}\n")
    
    print("📋 DETAILED RESULTS:")
    print(f"{'='*70}")
    for url, status, detail in results:
        symbol = "✅" if status == "SUCCESS" else "❌"
        domain = urlparse(url).netloc.replace('www.', '')
        print(f"{symbol} {domain:30s} {status:10s} {detail}")
    print(f"{'='*70}\n")
    
    # Success breakdown
    if success > 0:
        print(f"✅ Successfully scraped {success} websites:")
        for url, status, detail in results:
            if status == "SUCCESS":
                print(f"   • {detail}")
        print()
    
    # Failure breakdown
    failures = [r for r in results if r[1] != "SUCCESS"]
    if failures:
        print(f"❌ Failed to scrape {len(failures)} websites:")
        for url, status, detail in failures:
            domain = urlparse(url).netloc.replace('www.', '')
            print(f"   • {domain}: {detail}")
        print()
    
    # Statistics
    print(f"📊 STATISTICS:")
    print(f"   Success Rate: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)")
    print(f"   Failures: {len(failures)}")
    print(f"   Errors: {sum(1 for r in results if r[1] == 'ERROR')}")
    print()

if __name__ == "__main__":
    main()