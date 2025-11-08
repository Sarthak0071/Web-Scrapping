

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
import json, re, time
from urllib.parse import urljoin, urlparse
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
NOISE_KW = ['log in', 'login', 'sign in', 'signin', 'sign up', 'signup', 'get started', 'start free', 
    'try free', 'free trial', 'book demo', 'request demo', 'watch demo', 'skip to', 'jump to', 'back to', 
    'return to', 'go to', 'view all', 'see all', 'show all', 'learn more', 'read more', 'explore all',
    'privacy policy', 'terms of service', 'cookie policy', 'gdpr', 'ccpa', 'twitter', 'facebook', 
    'linkedin', 'instagram', 'youtube', 'github social', 'mastodon', 'discord', 'slack', 'tiktok', 
    'reddit', 'english', 'español', 'français', 'deutsch', 'italiano', 'português', 'language', 
    'currency', 'region', 'country']
ICON_PAT = [r'an?\s+icon\s+of', r'chevron', r'arrow\s+(right|left|up|down)', r'caret',
    r'^[▾▸►▼▲◄◀→←↑↓✓✕✗×]+$', r'right\s+pointing', r'left\s+pointing']

def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"   ❌ Fetch error: {str(e)[:100]}")
        return None

def clean_text(text):
    if not text: return ""
    for pat in ICON_PAT: text = re.sub(pat, '', text, flags=re.I)
    text = re.sub(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹]|\\bNew\\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'^[^\w]+|[^\w]+$', '', text)

def is_noise(text, elem):
    if not text or len(text) < 2 or len(text) > 300: return True
    text_lower = text.lower().strip()
    if text_lower in NOISE_KW or any(kw in text_lower for kw in NOISE_KW if len(kw) > 5): return True
    cls = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bsr-only\b|\bvisually-hidden\b|\bhidden\b', cls): return True
    for parent in list(elem.parents)[:10]:
        if parent.name == 'footer': return True
        p_cls = ' '.join(parent.get('class', [])).lower() + ' ' + parent.get('id', '').lower()
        if re.search(r'\bfooter\b|\bcookie\b|\bsearch\b|\bmobile(?:-menu)?\b|\bsidebar\b|\boff-canvas\b', p_cls): 
            return True
    return False

def is_visible(elem):
    style = elem.get('style', '').lower().replace(' ', '')
    if 'display:none' in style or 'visibility:hidden' in style: return False
    cls = ' '.join(elem.get('class', [])).lower()
    return not re.search(r'\bhidden\b|\binvisible\b|\bd-none\b', cls)

def count_top_level(nav):
    count = sum(len(ul.find_all('li', recursive=False)) for ul in nav.find_all('ul', recursive=False, limit=5))
    if count: return count
    for child in nav.children:
        if hasattr(child, 'name') and child.name in ['div', 'nav']:
            count = sum(len(ul.find_all('li', recursive=False)) for ul in child.find_all('ul', recursive=False, limit=5))
            if count: return count
    count = sum(1 for child in nav.children if hasattr(child, 'name') and child.name in ['a', 'button'] and is_visible(child))
    if count: return count
    return sum(1 for child in nav.find_all(['div', 'li'], recursive=False, limit=30) if child.find(['a', 'button'], recursive=False))

def find_primary_nav(soup):
    candidates = []
    for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
        if not is_visible(elem): continue
        cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
        if re.search(r'\bfooter\b|\bsidebar\b|\bmobile-menu\b|\boff-canvas\b|\bsearch\b', cls_id) or elem.find_parent('footer'): 
            continue
        top_cnt = count_top_level(elem)
        if not (3 <= top_cnt <= 25): continue
        
        score = 100
        if elem.name == 'nav': score += 200
        if elem.get('role') == 'navigation': score += 150
        if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls_id): score += 80
        if re.search(r'\bmain\b|\bprimary\b|\btop\b|\bglobal\b', cls_id): score += 120
        pos = next((i for i, p in enumerate(elem.parents) if p.name == 'body'), 0)
        score += 100 if pos <= 3 else (50 if pos <= 5 else -(pos-5)*20)
        if elem.find('ul'): score += 40
        if pos > 8: score -= 150
        
        candidates.append((score, elem, top_cnt, len(elem.find_all(['a', 'button']))))
    
    if not candidates: return None
    best = max(candidates, key=lambda x: x[0])
    print(f"   🎯 Nav found: {best[2]} top-level, {best[3]} total clickables, score={best[0]}")
    return best[1]

def find_dropdown_panel(trigger, soup):
    if panel_id := trigger.get('aria-controls'):
        if panel := soup.find(id=panel_id):
            if panel.find(['a', 'button']): return panel
    
    for attr in ['data-target', 'data-bs-target', 'data-dropdown', 'data-panel']:
        if target := trigger.get(attr):
            if panel := soup.find(id=target.lstrip('#')):
                if panel.find(['a', 'button']): return panel
    
    if parent_li := trigger.find_parent('li'):
        for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
            if child.find(['a', 'button']): return child
        if panel := parent_li.find(['ul', 'div', 'section'], class_=re.compile(r'dropdown|submenu|mega|panel|flyout', re.I)):
            if panel.find(['a', 'button']): return panel
    
    if next_sib := trigger.find_next_sibling(['div', 'ul', 'section']):
        if re.search(r'dropdown|menu|panel|flyout|mega', ' '.join(next_sib.get('class', [])).lower()):
            if next_sib.find(['a', 'button']): return next_sib
    
    if parent := trigger.parent:
        if parent.name in ['li', 'div', 'nav']:
            if next_sib := parent.find_next_sibling(['div', 'ul', 'section']):
                if re.search(r'dropdown|menu|panel', ' '.join(next_sib.get('class', [])).lower()):
                    if next_sib.find(['a', 'button']): return next_sib
    return None

def extract_link_data(link, base_url, seen_urls):
    href = link.get('href', '').strip()
    if not href or href.startswith('javascript:') or href == '#': return None
    
    title = clean_text(link.get_text(strip=True))
    if not title or is_noise(title, link) or len(title) < 2 or len(title) > 200: return None
    
    full_url = urljoin(base_url, href)
    if full_url in seen_urls: return None
    
    description = ""
    for desc in link.find_all(['p', 'span', 'div'], class_=re.compile(r'\bdesc\b|\bsubtitle\b|\bcaption\b|\bsummary\b', re.I), limit=3):
        desc_text = clean_text(desc.get_text(strip=True))
        if desc_text and desc_text != title and 5 < len(desc_text) < 500:
            description = desc_text
            break
    
    if not description:
        if next_elem := link.find_next_sibling(['p', 'span', 'div']):
            if not next_elem.find('a'):
                desc_text = clean_text(next_elem.get_text(strip=True))
                if desc_text and desc_text != title and 5 < len(desc_text) < 500:
                    description = desc_text
    
    seen_urls.add(full_url)
    return {'title': title, 'description': description, 'url': full_url}

def extract_sections(panel, base_url, seen_urls):
    sections, processed = [], set()
    panel_start = getattr(panel, 'sourceline', 0)
    panel_end = panel_start + str(panel).count('\n') + 50
    is_in = lambda e: panel_start <= getattr(e, 'sourceline', panel_start) <= panel_end
    
    # Column-based
    columns = []
    for pat in [r'\bcol-|\bcolumn-|\bgrid-item', r'\bcol\b', r'\bmenu-col\b|\bmega-col\b']:
        cols = panel.find_all(['div', 'section', 'li'], class_=re.compile(pat, re.I), limit=50)
        if len(cols) >= 2: columns = cols; break
    
    if len(columns) >= 2:
        for col in columns:
            if not is_in(col): continue
            sec_title = None
            for h in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=3):
                if not h.find('a'):
                    title_text = clean_text(h.get_text(strip=True))
                    if title_text and 2 <= len(title_text) <= 150 and not is_noise(title_text, h):
                        sec_title = title_text; break
            
            items = []
            for link in col.find_all(['a', 'button'], limit=300):
                if link.name == 'button' and not link.get('href'): continue
                if not is_in(link) or id(link) in processed: continue
                if sec_title and clean_text(link.get_text(strip=True)) == sec_title: continue
                if data := extract_link_data(link, base_url, seen_urls):
                    items.append(data)
                    processed.add(id(link))
            
            if items: sections.append({'section_title': sec_title, 'items': items})
        if sections: return sections
    
    # Heading-based
    headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    if headings:
        for i, h in enumerate(headings):
            if not is_in(h) or h.find('a'): continue
            sec_title = clean_text(h.get_text(strip=True))
            if not sec_title or len(sec_title) < 2 or len(sec_title) > 150 or is_noise(sec_title, h): continue
            
            next_h = headings[i+1] if i+1 < len(headings) else None
            items, curr, iters = [], h.find_next(), 0
            
            while curr and iters < 1000:
                iters += 1
                if not is_in(curr) or (next_h and (curr == next_h or next_h in list(curr.parents))) or panel not in list(curr.parents): 
                    break
                if hasattr(curr, 'name') and curr.name in ['a', 'button'] and curr.get('href'):
                    if id(curr) not in processed:
                        if clean_text(curr.get_text(strip=True)) != sec_title:
                            if data := extract_link_data(curr, base_url, seen_urls):
                                items.append(data)
                                processed.add(id(curr))
                try: curr = curr.find_next()
                except: break
            
            if items: sections.append({'section_title': sec_title, 'items': items})
        if sections: return sections
    
    # List-based
    for ul in [u for u in panel.find_all('ul', limit=100) if not u.find_parent('ul')]:
        if not is_in(ul): continue
        sec_title = None
        if prev := ul.find_previous_sibling():
            if prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                sec_title = clean_text(prev.get_text(strip=True))
                if len(sec_title) < 2 or len(sec_title) > 150: sec_title = None
        
        items = []
        for link in ul.find_all(['a', 'button'], limit=300):
            if link.get('href') and is_in(link) and id(link) not in processed:
                if data := extract_link_data(link, base_url, seen_urls):
                    items.append(data)
                    processed.add(id(link))
        
        if items: sections.append({'section_title': sec_title, 'items': items})
    if sections: return sections
    
    # Flat
    items = []
    for link in panel.find_all(['a', 'button'], limit=1000):
        if link.get('href') and is_in(link) and id(link) not in processed:
            if data := extract_link_data(link, base_url, seen_urls):
                items.append(data)
                processed.add(id(link))
    return [{'section_title': None, 'items': items}] if items else []

def extract_navigation(nav, soup, base_url):
    menus, seen_urls, seen_trig, dd_triggers, dd_links, js_rend = [], set(), set(), set(), set(), []
    print("   🔍 Phase 1: Identifying dropdown triggers...")
    dd_data = []
    
    # Type A: <li> with submenu
    for li in nav.find_all('li', limit=200):
        trig = next((c for c in li.find_all(['a', 'button'], recursive=False, limit=1)), None)
        if not trig or not is_visible(trig): continue
        trig_txt = clean_text(trig.get_text(strip=True))
        if not trig_txt or len(trig_txt) < 2 or len(trig_txt) > 100 or is_noise(trig_txt, trig): continue
        
        submenu = li.find(['ul', 'div', 'section'], recursive=False) or li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
        if submenu and len(submenu.find_all(['a', 'button'])) >= 1:
            if trig_txt.lower() not in seen_trig:
                dd_data.append((trig_txt, submenu, trig))
                seen_trig.add(trig_txt.lower())
                dd_triggers.add(id(trig))
    
    # Type B: ARIA/data
    for elem in nav.find_all(['button', 'a', 'div'], limit=200):
        if not is_visible(elem) or not (elem.get('aria-expanded') or elem.get('aria-haspopup') or elem.get('data-toggle') or elem.get('data-target')): 
            continue
        trig_txt = clean_text(elem.get_text(strip=True))
        if not trig_txt or len(trig_txt) < 2 or len(trig_txt) > 100 or is_noise(trig_txt, elem): continue
        
        panel = find_dropdown_panel(elem, soup)
        if not panel and elem.name == 'button':
            print(f"      ⚠️  JS-rendered dropdown (skipped): '{trig_txt}'")
            js_rend.append(trig_txt)
            dd_triggers.add(id(elem))
            continue
        
        if panel and len(panel.find_all(['a', 'button'])) >= 1:
            if trig_txt.lower() not in seen_trig:
                dd_data.append((trig_txt, panel, elem))
                seen_trig.add(trig_txt.lower())
                dd_triggers.add(id(elem))
    
    print(f"   ✓ Found {len(dd_data)} dropdowns, {len(js_rend)} JS-rendered")
    print("   🔍 Phase 2: Extracting dropdown contents...")
    
    for trig_txt, panel, _ in dd_data:
        for link in panel.find_all(['a', 'button']): dd_links.add(id(link))
        sections = extract_sections(panel, base_url, seen_urls)
        if sections:
            total = sum(len(s['items']) for s in sections)
            print(f"      ✅ '{trig_txt}': {total} items, {len(sections)} sections")
            menus.append({'menu_name': trig_txt, 'sections': sections})
    
    print("   🔍 Phase 3: Extracting top-level links...")
    top_items = []
    for link in nav.find_all(['a', 'button'], limit=1000):
        if not is_visible(link) or (link.name == 'a' and not link.get('href')): continue
        link_id = id(link)
        if link_id in dd_triggers or link_id in dd_links: continue
        if parent_li := link.find_parent('li'):
            if parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I)): continue
        if link.name == 'a':
            if data := extract_link_data(link, base_url, seen_urls): top_items.append(data)
    
    if top_items:
        print(f"      ✅ Top-level: {len(top_items)} items")
        menus.append({'menu_name': 'Navigation', 'sections': [{'section_title': None, 'items': top_items}]})
    
    return menus

def validate(menus, base_url):
    if not menus: return False, "No menus extracted"
    total = sum(len(s['items']) for m in menus for s in m['sections'])
    if total < 3: return False, f"Too few items: {total}"
    
    domain = urlparse(base_url).netloc.replace('www.', '')
    internal = sum(1 for m in menus for s in m['sections'] for i in s['items'] if domain in urlparse(i['url']).netloc)
    ratio = internal / total if total > 0 else 0
    if ratio < 0.20: return False, f"Low internal ratio: {ratio*100:.0f}%"
    
    url_counts = defaultdict(int)
    for m in menus:
        for s in m['sections']:
            for item in s['items']: url_counts[item['url']] += 1
    
    dups = sum(1 for count in url_counts.values() if count > 2)
    if dups > total * 0.3: return False, f"Too many duplicates: {dups}/{total}"
    
    return True, f"{total} items, {ratio*100:.0f}% internal, {len(menus)} menus"

def scrape(url):
    print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    if not (html := fetch(url)): return None
    
    soup = BeautifulSoup(html, 'html.parser')
    if not (nav := find_primary_nav(soup)):
        print("   ❌ No primary navigation found")
        return None
    
    menus = extract_navigation(nav, soup, url)
    is_valid, msg = validate(menus, url)
    print(f"   📊 Result: {msg}")
    
    if not is_valid:
        print(f"   ❌ REJECTED: {msg}")
        return None
    
    print("   ✅ ACCEPTED")
    return {
        'website': url, 'domain': urlparse(url).netloc,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'menus': menus
    }

def main():
    print(f"\n{'#'*70}\n# UNIVERSAL HTML NAVIGATION SCRAPER v2.0\n# Master Plan Implementation\n# Processing {len(URLS)} websites\n{'#'*70}")
    
    success, results = 0, []
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
        try:
            if data := scrape(url):
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
        time.sleep(2)
    
    print(f"\n\n{'='*70}\n{'='*70}\n   FINAL RESULTS: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}\n{'='*70}\n")
    print(f"📋 DETAILED RESULTS:\n{'='*70}")
    for url, status, detail in results:
        symbol = "✅" if status == "SUCCESS" else "❌"
        print(f"{symbol} {urlparse(url).netloc.replace('www.', ''):30s} {status:10s} {detail}")
    print(f"{'='*70}\n")
    
    if success > 0:
        print(f"✅ Successfully scraped {success} websites:")
        for url, status, detail in results:
            if status == "SUCCESS": print(f"   • {detail}")
        print()
    
    if failures := [r for r in results if r[1] != "SUCCESS"]:
        print(f"❌ Failed to scrape {len(failures)} websites:")
        for url, status, detail in failures:
            print(f"   • {urlparse(url).netloc.replace('www.', '')}: {detail}")
        print()
    
    print(f"📊 STATISTICS:\n   Success Rate: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n   Failures: {len(failures)}\n   Errors: {sum(1 for r in results if r[1] == 'ERROR')}\n")

if __name__ == "__main__":
    main()