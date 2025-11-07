import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
import time

# List of websites to scrape
URLS = ['https://buffer.com', 'https://mailchimp.com', 'https://hootsuite.com', 'https://www.activecampaign.com',
        'https://www.hubspot.com', 'https://www.asana.com', 'https://www.slack.com', 'https://www.shopify.com',
        'https://www.squarespace.com', 'https://www.figma.com', 'https://www.airtable.com']

# Browser headers for requests
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Patterns to skip (CTA buttons, login links, etc.)
SKIP_PATTERNS = [r'^get\s+(a\s+)?(demo|started|free)', r'^sign\s+(up|in)', r'^log\s*in', r'^try\s+', 
                 r'^contact\s+(us|sales)', r'^request\s+', r'^download\s+', r'^watch\s+', r'^view\s+all', 
                 r'^see\s+all', r'^learn\s+more$', r'^start\s+free', r'^pricing$', r'^support$', 
                 r'^buy\s+now', r'^free\s+trial', r'^book\s+a', r'^schedule\s+', r'^talk\s+to']

# Exact text to exclude
EXCLUDE_TEXT = ['english', 'select a language', 'log in', 'login', 'sign in', 'sign up', 'get a demo', 
                'get started free', 'get started', 'try for free', 'pricing', 'support', 'contact', 'careers', 'about us']

# Patterns that indicate user account menus (not public navigation)
USER_MENU_INDICATORS = [r'account', r'profile', r'user', r'settings', r'dashboard', r'my\s+', r'inbox', 
                        r'notification', r'logout', r'sign\s+out', r'preferences', r'billing', r'subscription', 
                        r'upgrade', r'admin', r'workspace']

# Keywords that indicate public navigation
PUBLIC_NAV_KEYWORDS = ['product', 'solution', 'resource', 'feature', 'why', 'company', 'pricing', 
                       'enterprise', 'for', 'use case', 'industry', 'platform']

def fetch_html(url):
    """Fetch HTML content from URL"""
    try:
        return requests.get(url, headers=HEADERS, timeout=15).text
    except:
        return None

def is_site(url, domain):
    """Check if URL belongs to a specific domain"""
    return domain in urlparse(url).netloc.lower()

def has_class_pattern(elem, pattern):
    """Check if element or its parent has a class matching the pattern"""
    return elem.find(class_=re.compile(pattern, re.I)) or \
           (parent := elem.find_parent(['div', 'nav', 'header'])) and \
           re.search(pattern, ' '.join(parent.get('class', [])), re.I)

def is_user_menu(text, elem):
    """Determine if this is a user account menu (not public navigation)"""
    return any(re.search(p, text.lower()) for p in USER_MENU_INDICATORS) or \
           has_class_pattern(elem, r'user|account|profile|avatar|settings|auth|login') or \
           elem.find('img', alt=re.compile(r'user|account|profile|avatar', re.I))

def is_public_nav_trigger(text, elem):
    """Check if element is likely a public navigation trigger"""
    return any(k in text.lower() for k in PUBLIC_NAV_KEYWORDS) or len(text.lower().split()) <= 3 or \
           has_class_pattern(elem, r'main.*nav|primary.*nav|global.*nav|top.*nav|site.*nav')

def get_main_navigation_containers(soup, base_url):
    """Find main navigation containers in the page"""
    containers = [(t, e) for t, e in [
        # Generic headers (excluding user menus)
        *[('header', h) for h in soup.find_all('header') if not re.search(r'user|account|auth|login|footer', ' '.join(h.get('class', [])), re.I)],
        # Navigation elements with specific classes
        *[('main-nav', n) for n in soup.find_all('nav', class_=re.compile(r'main|primary|global|top|site', re.I))],
        # Elements with navigation role
        *[('role-nav', n) for n in soup.find_all(attrs={'role': 'navigation'}) if not re.search(r'user|account|footer|sidebar', ' '.join(n.get('class', [])), re.I)],
        # Site-specific containers
        *([('asana', n) for n in soup.find_all('nav', class_=re.compile(r'Topbar', re.I))] if is_site(base_url, 'asana.com') else []),
        *([('squarespace', d) for d in soup.find_all('div', class_=re.compile(r'Header-nav', re.I))] if is_site(base_url, 'squarespace.com') else [])
    ]]
    return containers if containers else [('fallback', soup)]

def create_trigger(elem, text, panel_id, trigger_type):
    """Create a trigger object with metadata"""
    return {'element': elem, 'menu_name': text, 'panel_id': panel_id, 'type': trigger_type, 'trigger_element': elem}

def find_nav_triggers(soup, base_url):
    """Find all navigation menu triggers (buttons/links that open dropdowns)"""
    triggers, seen = [], set()
    
    # Site-specific configurations
    site_configs = {
        'asana.com': ('button', r'NavigationMenu.*trigger', 'asana-nav'),
        'squarespace.com': ('button', r'Header-nav-folder-title', 'squarespace-folder'),
        'hubspot.com': ('button', r'global-nav-tab.*-hasSubNav', 'hubspot-button')
    }
    
    for _, container in get_main_navigation_containers(soup, base_url):
        # Try site-specific patterns first
        for domain, (tag, pattern, ttype) in site_configs.items():
            if is_site(base_url, domain):
                for elem in container.find_all(tag, class_=re.compile(pattern, re.I)):
                    text = elem.get_text(strip=True)
                    if text and 2 <= len(text) <= 50 and text.lower() not in seen and not is_user_menu(text, elem):
                        triggers.append(create_trigger(elem, text, elem.get('aria-controls'), ttype))
                        seen.add(text.lower())
        
        # Look for elements with ARIA attributes
        for attr in [{'aria-expanded': True}, {'aria-haspopup': True}] if len(triggers) < 3 else [{'aria-expanded': True}]:
            for elem in container.find_all(['button', 'a'], attrs=attr):
                text = elem.get_text(strip=True)
                if text and 2 <= len(text) <= 50 and text.lower() not in seen and not is_user_menu(text, elem) and is_public_nav_trigger(text, elem):
                    triggers.append(create_trigger(elem, text, elem.get('aria-controls') or elem.get('aria-owns'), 'aria-expanded'))
                    seen.add(text.lower())
        
        # Fallback to class-based patterns
        if len(triggers) < 3:
            for pattern in [r'dropdown.*toggle', r'menu.*trigger', r'nav.*trigger', r'has.*dropdown', r'has.*submenu', r'NavigationMenu.*trigger']:
                for elem in container.find_all(['button', 'a'], class_=re.compile(pattern, re.I)):
                    text = elem.get_text(strip=True)
                    if text and 2 <= len(text) <= 50 and text.lower() not in seen and not is_user_menu(text, elem) and is_public_nav_trigger(text, elem):
                        triggers.append(create_trigger(elem, text, elem.get('aria-controls'), 'class-pattern'))
                        seen.add(text.lower())
        
        # Stop after finding triggers in first valid container
        if triggers:
            break
    return triggers[:10]

def is_valid_panel(panel):
    """Check if panel has a reasonable number of links"""
    return panel and 2 <= len(panel.find_all('a', href=True)) <= 50

def is_user_panel(panel):
    """Determine if panel is a user menu (not public navigation)"""
    if not panel:
        return False
    text = panel.get_text(strip=True).lower()
    # Check if multiple user indicators are present
    if sum(1 for p in USER_MENU_INDICATORS if re.search(p, text)) >= 3:
        return True
    # Check if majority of links are user-related
    links = panel.find_all('a', href=True)
    return len(links) > 0 and sum(1 for l in links if any(re.search(p, l.get_text(strip=True).lower()) for p in USER_MENU_INDICATORS)) / len(links) > 0.5

def score_panel(panel):
    """Score panel based on characteristics to find the best match"""
    if not panel:
        return 0
    classes, links = ' '.join(panel.get('class', [])), panel.find_all('a', href=True)
    link_count = len(links)
    if not (2 <= link_count <= 50):
        return 0
    
    score = (4 if 5 <= link_count <= 40 else 2) + \
            (5 if re.search(r'mega.*menu|dropdown.*menu|submenu|nav.*panel|menu.*panel', classes, re.I) else 
             3 if re.search(r'menu|dropdown|nav|content|panel|flyout', classes, re.I) else 0) + \
            (3 if any(x in panel.get('style', '').replace(' ', '') for x in ['display:none', 'visibility:hidden']) or panel.get('aria-hidden') == 'true' else 0) + \
            (3 if panel.get('role') in ['menu', 'navigation', 'menubar'] else 0) + \
            (2 if panel.find_all(['h2', 'h3', 'h4', 'h5', 'h6'], limit=1) else 0) + \
            (3 if sum(1 for k in PUBLIC_NAV_KEYWORDS if k in panel.get_text(strip=True).lower()) >= 2 else 0)
    return score

def find_panel_for_trigger(soup, trigger_info):
    """Find the dropdown panel associated with a trigger"""
    elem, panel_id, ttype = trigger_info['trigger_element'], trigger_info.get('panel_id'), trigger_info['type']
    
    # Site-specific panel finding
    if ttype == 'asana-nav' and panel_id and (panel := soup.find(id=panel_id)):
        return panel
    if ttype == 'squarespace-folder' and (parent := elem.find_parent('div', class_=re.compile(r'Header-nav-folder', re.I))) and \
       (panel := parent.find('div', class_=re.compile(r'Header-nav-folder-content', re.I))):
        return panel
    if ttype == 'hubspot-button':
        if panel := elem.find_next_sibling('section', class_=re.compile(r'global-nav-tab-dropdown', re.I)):
            return panel
        if (parent := elem.find_parent(['div', 'nav'])) and (panel := parent.find_next_sibling('section', class_=re.compile(r'dropdown', re.I))):
            return panel
    
    # Try finding panel by ID
    if panel_id:
        for finder in [lambda: soup.find(id=panel_id), lambda: soup.find(attrs={'aria-labelledby': panel_id})]:
            if (panel := finder()) and is_valid_panel(panel):
                return panel
    
    # Check siblings for dropdown panels
    for sibling in [elem.find_next_sibling(), elem.find_previous_sibling()]:
        if sibling and sibling.name in ['div', 'ul', 'nav', 'section'] and \
           re.search(r'dropdown|mega|menu|submenu|panel|content|flyout', ' '.join(sibling.get('class', [])), re.I) and \
           is_valid_panel(sibling) and not is_user_panel(sibling):
            return sibling
    
    # Check parent's children
    if (parent := elem.find_parent(['li', 'div', 'nav'])):
        for child in parent.find_all(['div', 'ul', 'nav', 'section'], recursive=False):
            if child != elem and is_valid_panel(child) and not is_user_panel(child):
                return child
    
    # Score and rank potential panels
    candidates = [(score_panel(c), c) for c in (elem.find_parent(['header', 'nav']) or soup).find_all(['div', 'ul', 'nav', 'section'], limit=30)
                  if c != elem and elem not in c.parents and not is_user_panel(c) and score_panel(c) > 3]
    return max(candidates, key=lambda x: x[0])[1] if candidates else None

def should_skip_link(title):
    """Check if link should be skipped based on patterns"""
    return any(re.search(p, title.lower().strip(), re.I) for p in SKIP_PATTERNS) or title.lower().strip() in EXCLUDE_TEXT

def extract_item_data(link, base_url):
    """Extract title, description, and URL from a link"""
    href = link.get('href', '')
    if not href or href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
        return None
    
    # Find title using various strategies
    title, title_elem = "", None
    for finder in [
        lambda: link.find(class_=re.compile(r'title|heading|name|label|menuItem.*Title|item.*title|link.*title', re.I)),
        lambda: link.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b']),
        lambda: link.find('span', class_=re.compile(r'text|label|title|name', re.I)),
        lambda: next((t.strip() for t in link.stripped_strings if 2 <= len(t) < 150), None),
        lambda: link.get('aria-label', '').strip()
    ]:
        if elem := finder():
            title, title_elem = (elem.get_text(strip=True), elem) if hasattr(elem, 'get_text') else (elem, None)
            if title:
                break
    
    # Find description
    desc = ""
    for finder in [
        lambda: link.find(class_=re.compile(r'desc|description|subtitle|summary|excerpt|menuItem.*Desc|item.*desc', re.I)),
        lambda: link.find('p')
    ]:
        if (elem := finder()) and elem != title_elem and (text := elem.get_text(strip=True)) != title:
            desc = text
            break
    
    # Clean and validate
    title, desc = re.sub(r'\s+', ' ', title).strip(), re.sub(r'\s+', ' ', desc).strip()[:300]
    if not (2 <= len(title) <= 200) or should_skip_link(title):
        return None
    
    url = urljoin(base_url, href)
    return None if url in [base_url, base_url + '/'] else {'title': title, 'description': desc, 'url': url}

def extract_hierarchical_menu(panel, base_url):
    """Extract menu items organized by sections"""
    # Special handling 
    if is_site(base_url, 'hubspot.com'):
        sections, seen = [], set()
        for group in panel.find_all(['div', 'ul'], class_=re.compile(r'global-nav-card-group', re.I)):
            group_title = (t.get_text(strip=True) if (t := group.find_previous(['h2', 'h3'], class_=re.compile(r'title', re.I))) else None)
            items = []
            for card in group.find_all(['li', 'div'], class_=re.compile(r'global-nav-card', re.I)):
                if (te := card.find(['h3', 'h4'], class_=re.compile(r'title', re.I))) and (le := card.find('a', href=True)):
                    title, desc, href = te.get_text(strip=True), ((de.get_text(strip=True) if (de := card.find('p', class_=re.compile(r'description', re.I))) else "")), le.get('href', '')
                    if href not in ['#', 'javascript:void(0)'] and title.lower() not in seen and not should_skip_link(title):
                        seen.add(title.lower())
                        items.append({'title': title, 'description': desc, 'url': urljoin(base_url, href)})
            if items:
                sections.append({'section_title': group_title, 'items': items})
        if sections:
            return sections
    
    # Validate panel has links
    links = panel.find_all('a', href=True)
    if not (2 <= len(links) <= 50):
        return []
    
    sections, processed = [], set()
    
    # Strategy 1: Find containers with column/section classes
    containers = [c for c in panel.find_all(['div', 'ul', 'nav', 'section', 'li'], 
                  class_=re.compile(r'column|col-|grid-|section|group|category|channel|menu-group|nav-group|menu-column', re.I))
                  if len(c.find_all('a', href=True)) >= 2]
    
    if containers:
        for container in containers:
            # Find section title
            title = (h.get_text(strip=True) if (h := container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])) else
                    (t.get_text(strip=True) if (t := container.find(class_=re.compile(r'title|heading|category|section.*title', re.I))) else None))
            # Extract links
            items = [d for l in container.find_all('a', href=True) if id(l) not in processed and (d := extract_item_data(l, base_url)) and not processed.add(id(l))]
            if items:
                sections.append({'section_title': title if title and len(title) < 100 else None, 'items': items})
    
    # Strategy 2: Group by headings
    if not sections:
        for heading in panel.find_all(['h2', 'h3', 'h4', 'h5', 'h6']):
            if (title := heading.get_text(strip=True)) and len(title) <= 100:
                next_h, container = heading.find_next(['h2', 'h3', 'h4', 'h5', 'h6']), heading.find_next(['ul', 'div', 'nav'])
                if container:
                    # Get links until next heading
                    items = [d for l in [link for link in container.find_all('a', href=True) if not (next_h and (link == next_h or next_h in link.parents))]
                            if (d := extract_item_data(l, base_url))]
                    if items:
                        sections.append({'section_title': title, 'items': items})
    
    # Strategy 3: Find top-level lists
    if not sections:
        for ul in [u for u in panel.find_all('ul', recursive=True) if not u.find_parent('ul')]:
            if 2 <= (lc := len(ul.find_all('a', href=True, recursive=True))) <= 20:
                if items := [d for l in ul.find_all('a', href=True, recursive=True) if (d := extract_item_data(l, base_url))]:
                    sections.append({'section_title': None, 'items': items})
    
    # Strategy 4: Flat list of all links
    if not sections:
        if items := [d for l in links if (d := extract_item_data(l, base_url))]:
            sections.append({'section_title': None, 'items': items})
    
    # Remove duplicate URLs
    seen = set()
    for section in sections:
        section['items'] = [i for i in section['items'] if i['url'] not in seen and not seen.add(i['url'])]
    
    return [s for s in sections if s['items']]

def scrape_website(url):
    """Main function to scrape a website's navigation menu"""
    # Fetch HTML and find triggers
    if not (html := fetch_html(url)) or not (triggers := find_nav_triggers(BeautifulSoup(html, 'html.parser'), url)):
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    menu_data = {'website': url, 'domain': urlparse(url).netloc, 'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'menus': []}
    global_seen, seen_names = set(), set()
    
    # Process each trigger
    for trigger in triggers:
        if (name := trigger['menu_name']).lower() in seen_names:
            continue
        # Find and validate panel
        if not (panel := find_panel_for_trigger(soup, trigger)) or not is_valid_panel(panel):
            continue
        # Extract menu structure
        if sections := extract_hierarchical_menu(panel, url):
            # Remove globally seen URLs
            for s in sections:
                s['items'] = [i for i in s['items'] if i['url'] not in global_seen and not global_seen.add(i['url'])]
            if sections := [s for s in sections if s['items']]:
                menu_data['menus'].append({'menu_name': name, 'sections': sections})
                seen_names.add(name.lower())
    
    return menu_data if menu_data['menus'] else None

def main():
    """Run scraper for all URLs"""
    for url in URLS:
        if data := scrape_website(url):
            with open(f"{urlparse(url).netloc.replace('www.', '')}.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        time.sleep(2)

if __name__ == "__main__":
    main()