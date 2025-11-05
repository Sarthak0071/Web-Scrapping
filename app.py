import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
import time
from urls import URLS

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

SKIP_PATTERNS = [r'^get\s+(a\s+)?(demo|started|free)', r'^sign\s+(up|in)', r'^log\s*in', 
                 r'^try\s+', r'^contact\s+(us|sales)', r'^request\s+', r'^download\s+', 
                 r'^watch\s+', r'^view\s+all', r'^see\s+all', r'^learn\s+more$', 
                 r'^start\s+free', r'^pricing$', r'^support$']

EXCLUDE_TEXT = ['english', 'select a language', 'log in', 'login', 'sign in', 'sign up',
                'get a demo', 'get started free', 'get started', 'try for free']

def fetch_html(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=15).text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def is_site(url, domain):
    return domain in urlparse(url).netloc.lower()

def find_nav_triggers(soup, base_url):
    triggers = []
    
    # HubSpot specific
    if is_site(base_url, 'hubspot.com'):
        for t in soup.find_all('button', class_=re.compile(r'global-nav-tab.*-hasSubNav', re.I)):
            text = t.get_text(strip=True)
            if text and len(text) <= 50 and text.lower() not in EXCLUDE_TEXT:
                triggers.append({'element': t, 'menu_name': text, 'panel_id': None, 
                               'type': 'hubspot-trigger', 'trigger_element': t})
        if triggers:
            print(f"  HubSpot triggers: {[t['menu_name'] for t in triggers]}")
            return triggers
    
    # SproutSocial specific
    if is_site(base_url, 'sproutsocial.com'):
        header = soup.find('header') or soup.find('nav', class_=re.compile(r'main|primary|header', re.I))
        if header:
            for t in header.find_all(['button', 'a'], attrs={'aria-expanded': True}):
                text = t.get_text(strip=True)
                if text and 2 <= len(text) <= 50 and text.lower() not in EXCLUDE_TEXT:
                    triggers.append({'element': t, 'menu_name': text, 'panel_id': t.get('aria-controls'),
                                   'type': 'sprout-trigger', 'trigger_element': t})
            if triggers:
                print(f"  SproutSocial triggers: {[t['menu_name'] for t in triggers]}")
                return triggers
    
    # Find header
    header = (soup.find('header') or 
              soup.find('nav', class_=re.compile(r'main|primary|global|header|navigation', re.I)) or
              soup.find('div', attrs={'role': 'navigation'}) or
              soup.find('div', class_=re.compile(r'header|navigation|navbar|nav-bar|mainNav', re.I)) or
              soup.find('div', id=re.compile(r'header|nav|menu', re.I)) or soup)
    
    # Strategy 1: Buffer-style triggers
    for t in header.find_all('button', class_=re.compile(r'NavigationMenu_trigger', re.I)):
        text = t.get_text(strip=True)
        if text and len(text) <= 50:
            triggers.append({'element': t, 'menu_name': text, 'panel_id': None,
                           'type': 'buffer-trigger', 'trigger_element': t})
    
    # Strategy 2-6: Generic patterns
    if not triggers:
        patterns = [
            ('data-menu-id', lambda e: e.get('data-menu-id')),
            ('aria-controls', lambda e: e.get('aria-controls')),
            ('aria-expanded', lambda e: e.get('aria-controls') or e.get('data-target') or e.get('id')),
            ('nav-link', lambda e: e.get('aria-controls') or e.get('data-target') or e.get('data-menu') or e.get('id'))
        ]
        
        for ptype, get_panel_id in patterns:
            if triggers:
                break
            selector = {'data-menu-id': True} if ptype == 'data-menu-id' else \
                      {'aria-controls': True} if ptype == 'aria-controls' else \
                      {'aria-expanded': True} if ptype == 'aria-expanded' else \
                      {'class': re.compile(r'nav-link|nav-item|menu-item|dropdown-toggle|has-menu|has-submenu', re.I)}
            
            for elem in header.find_all(['button', 'a', 'div'], selector):
                text = elem.get_text(strip=True)
                if text and 2 <= len(text) <= 50:
                    triggers.append({'element': elem, 'menu_name': text, 'panel_id': get_panel_id(elem),
                                   'type': ptype, 'trigger_element': elem})
    
    return triggers

def find_panel_for_trigger(soup, trigger_info):
    trigger_type, elem, panel_id = trigger_info['type'], trigger_info['trigger_element'], trigger_info.get('panel_id')
    
    # HubSpot specific
    if trigger_type == 'hubspot-trigger':
        panel = elem.find_next_sibling('section', class_=re.compile(r'global-nav-tab-dropdown-section', re.I))
        if panel:
            return panel
        parent = elem.find_parent(['div', 'nav'])
        if parent:
            return parent.find_next_sibling('section', class_=re.compile(r'global-nav-tab-dropdown', re.I)) or \
                   parent.find('section', class_=re.compile(r'global-nav-tab-dropdown', re.I))
    
    # SproutSocial specific
    if trigger_type == 'sprout-trigger':
        if panel_id and (panel := soup.find(id=panel_id)):
            return panel
        return elem.find_next_sibling(['div', 'ul'], class_=re.compile(r'dropdown|menu|submenu', re.I))
    
    # Buffer specific
    if trigger_type == 'buffer-trigger':
        parent = elem.find_parent('div')
        if parent:
            return parent.find_next_sibling('div', class_=re.compile(r'NavigationMenu_content', re.I)) or \
                   parent.find('div', class_=re.compile(r'NavigationMenu_content', re.I))
    
    # Generic strategies
    if panel_id and (panel := soup.find(id=panel_id)):
        return panel
    if panel_id and (panel := soup.find(attrs={'aria-labelledby': panel_id})):
        return panel
    if panel_id and (panel := soup.find(attrs={'data-menu-panel': panel_id})):
        return panel
    
    parent = elem.find_parent(['li', 'div', 'nav'])
    if parent:
        if panel := parent.find_next_sibling(['div', 'ul', 'nav'], class_=re.compile(r'menu|dropdown|submenu|mega|panel|content|flyout', re.I)):
            return panel
        if panel := parent.find(['div', 'ul', 'nav'], class_=re.compile(r'dropdown-menu|submenu|mega-menu|menu-panel|nav-panel', re.I), recursive=False):
            return panel
    
    if panel := elem.find_next_sibling(['div', 'ul', 'nav', 'section']):
        if re.search(r'menu|dropdown|mega|panel|content', ' '.join(panel.get('class', [])), re.I):
            return panel
    
    # Search nearby
    if elem.parent:
        for nearby in elem.parent.find_all(['div', 'ul', 'nav', 'section'], attrs={'role': 'menu'}, limit=5):
            if is_mega_menu_panel(nearby):
                return nearby
        for hidden in elem.parent.find_all(['div', 'ul', 'nav', 'section'], attrs={'aria-hidden': 'true'}, limit=5):
            if is_mega_menu_panel(hidden):
                return hidden
    
    return None

def is_mega_menu_panel(panel):
    if not panel:
        return False
    
    links = panel.find_all('a', href=True)
    link_count = len(links)
    
    if link_count > 50 or link_count < 2:
        return False
    
    classes = ' '.join(panel.get('class', []))
    score = 0
    
    if re.search(r'menu|nav|dropdown|content|mega|panel|flyout|submenu', classes, re.I):
        score += 3
    
    style, aria_hidden = panel.get('style', ''), panel.get('aria-hidden')
    if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', '') or \
       aria_hidden == 'true' or panel.get('data-state') == 'closed':
        score += 2
    
    if panel.get('role') in ['menu', 'navigation', 'menubar', 'list']:
        score += 2
    
    score += 3 if 5 <= link_count <= 40 else 1 if link_count > 2 else 0
    
    return score >= 3

def should_skip_link(title):
    title_lower = title.lower().strip()
    return any(re.search(p, title_lower, re.I) for p in SKIP_PATTERNS)

def extract_item_data(link, base_url):
    href = link.get('href', '')
    if not href or href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
        return None
    
    # Extract title
    title = ""
    title_elem = link.find(class_=re.compile(r'title|heading|name|label|menuItem.*Title|item.*title', re.I))
    
    if title_elem:
        title = title_elem.get_text(strip=True)
    elif heading := link.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b']):
        title = heading.get_text(strip=True)
        title_elem = heading
    elif span := link.find('span', class_=re.compile(r'text|label|title', re.I)):
        title = span.get_text(strip=True)
        title_elem = span
    else:
        for text in link.stripped_strings:
            if 2 <= len(text) < 150:
                title = text.strip()
                break
    
    if not title:
        title = link.get('aria-label', '').strip()
    
    # Extract description
    desc = ""
    if desc_elem := link.find(class_=re.compile(r'desc|description|subtitle|summary|excerpt|menuItem.*Desc', re.I)):
        if desc_elem != title_elem:
            desc_text = desc_elem.get_text(strip=True)
            if desc_text and desc_text != title and not title.startswith(desc_text):
                desc = desc_text
    
    if not desc and (p_elem := link.find('p')) and p_elem != title_elem:
        desc_text = p_elem.get_text(strip=True)
        if desc_text != title:
            desc = desc_text
    
    if not desc and (small_elem := link.find(['small', 'span'], class_=re.compile(r'small|secondary|sub', re.I))) and small_elem != title_elem:
        desc_text = small_elem.get_text(strip=True)
        if desc_text != title:
            desc = desc_text
    
    title = re.sub(r'\s+', ' ', title).strip()
    desc = re.sub(r'\s+', ' ', desc).strip()[:300]
    
    if len(title) < 2 or len(title) > 200 or should_skip_link(title):
        return None
    
    url = urljoin(base_url, href)
    return None if url in [base_url, base_url + '/'] else {'title': title, 'description': desc, 'url': url}

def extract_hubspot_menu(panel, base_url):
    sections, seen_titles = [], set()
    
    card_groups = panel.find_all(['div', 'ul'], class_=re.compile(r'global-nav-card-group-list|global-nav-main-products-hub-cards|global-nav.*list', re.I)) or [panel]
    
    for group in card_groups:
        for card in group.find_all(['li', 'div'], class_=re.compile(r'global-nav-card|nav.*card', re.I)):
            title_elem = card.find(['h3', 'h4', 'h5'], class_=re.compile(r'global-nav-card-title|card.*title', re.I))
            desc_elem = card.find('p', class_=re.compile(r'global-nav-card-description|card.*description', re.I))
            link_elem = card.find('a', class_=re.compile(r'global-nav-card-cta-text-link|card.*link', re.I)) or card.find('a', href=True)
            
            if title_elem and link_elem:
                title = title_elem.get_text(strip=True)
                desc = desc_elem.get_text(strip=True) if desc_elem else ""
                href = link_elem.get('href', '')
                
                if href and href not in ['#', 'javascript:void(0)']:
                    url = urljoin(base_url, href)
                    if title.lower() not in seen_titles and title and len(title) >= 2 and not should_skip_link(title):
                        seen_titles.add(title.lower())
                        sections.append({'section_title': title, 'items': [{'title': title, 'description': desc, 'url': url}]})
    
    # Fallback to generic
    if not sections:
        for group in panel.find_all(['div', 'ul'], class_=re.compile(r'group|list|nav', re.I)):
            section_title = group.find(['h2', 'h3', 'h4', 'h5']).get_text(strip=True) if group.find(['h2', 'h3', 'h4', 'h5']) else None
            items = []
            for link in group.find_all('a', href=True, limit=15):
                if (item_data := extract_item_data(link, base_url)) and item_data['title'].lower() not in seen_titles:
                    items.append({'title': item_data['title'], 'description': item_data['description'], 'url': item_data['url']})
                    seen_titles.add(item_data['title'].lower())
            if items:
                sections.append({'section_title': section_title, 'items': items})
    
    return sections

def extract_hierarchical_menu(panel, base_url):
    if is_site(base_url, 'hubspot.com'):
        if hubspot_sections := extract_hubspot_menu(panel, base_url):
            return hubspot_sections
    
    sections = []
    all_links = panel.find_all('a', href=True)
    
    if len(all_links) > 50:
        return []
    
    # Strategy 1: Section containers
    section_containers = [c for c in panel.find_all(['div', 'ul', 'nav', 'section', 'li'], 
                          class_=re.compile(r'column|col-|grid-|section|group|category|channel|menu-group|nav-group', re.I))
                          if len(c.find_all('a', href=True)) >= 2]
    
    if section_containers:
        processed_links = set()
        for container in section_containers:
            section_title = None
            if heading := container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                section_title = heading.get_text(strip=True)
            elif title_elem := container.find(class_=re.compile(r'title|heading|category|section.*title|group.*title|channel.*title', re.I)):
                section_title = title_elem.get_text(strip=True)
            elif strong := container.find(['strong', 'b'], recursive=False):
                section_title = strong.get_text(strip=True)
            
            section_items = []
            for link in container.find_all('a', href=True):
                if id(link) not in processed_links and (item_data := extract_item_data(link, base_url)):
                    section_items.append({'title': item_data['title'], 'description': item_data['description'], 'url': item_data['url']})
                    processed_links.add(id(link))
            
            if section_items:
                sections.append({'section_title': section_title if section_title and len(section_title) < 100 else None, 'items': section_items})
    
    # Strategy 2: Group by headings
    if not sections:
        for heading in panel.find_all(['h2', 'h3', 'h4', 'h5', 'h6']):
            section_title = heading.get_text(strip=True)
            if not section_title or len(section_title) > 100:
                continue
            
            next_heading = heading.find_next(['h2', 'h3', 'h4', 'h5', 'h6'])
            container = heading.find_next(['ul', 'div', 'nav'])
            
            if container:
                links = []
                for link in container.find_all('a', href=True):
                    if next_heading and (link == next_heading or next_heading in link.parents):
                        break
                    links.append(link)
                
                section_items = [{'title': item_data['title'], 'description': item_data['description'], 'url': item_data['url']}
                               for link in links if (item_data := extract_item_data(link, base_url))]
                
                if section_items:
                    sections.append({'section_title': section_title, 'items': section_items})
    
    # Strategy 3: Flat
    if not sections:
        flat_items = [{'title': item_data['title'], 'description': item_data['description'], 'url': item_data['url']}
                     for link in all_links if (item_data := extract_item_data(link, base_url))]
        if flat_items:
            sections.append({'section_title': None, 'items': flat_items})
    
    # Deduplicate URLs
    seen_urls = set()
    for section in sections:
        unique_items = [item for item in section['items'] if item['url'] not in seen_urls and not seen_urls.add(item['url'])]
        section['items'] = unique_items
    
    return [s for s in sections if s['items']]

def scrape_website(url):
    print(f"\nScraping {url}...")
    
    if not (html := fetch_html(url)):
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    triggers = find_nav_triggers(soup, url)
    
    if not triggers:
        print(f"  No navigation triggers found")
        return None
    
    print(f"  Found {len(triggers)} navigation triggers")
    
    menu_data = {
        'website': url,
        'domain': urlparse(url).netloc,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'menus': []
    }
    
    global_seen_urls, seen_menu_names = set(), set()
    
    for trigger in triggers:
        menu_name = trigger['menu_name']
        
        if menu_name.lower() in seen_menu_names:
            print(f"  Skipping duplicate menu: {menu_name}")
            continue
        
        print(f"\n  Processing menu: {menu_name}")
        
        if not (panel := find_panel_for_trigger(soup, trigger)):
            print(f"    No panel found")
            continue
        
        if not is_mega_menu_panel(panel):
            print(f"    Invalid panel ({len(panel.find_all('a', href=True))} links)")
            continue
        
        sections = extract_hierarchical_menu(panel, url)
        
        # Deduplicate across menus
        for section in sections:
            section['items'] = [item for item in section['items'] 
                              if item['url'] not in global_seen_urls and not global_seen_urls.add(item['url'])]
        
        sections = [s for s in sections if s['items']]
        
        if sections and (total_items := sum(len(s['items']) for s in sections)) > 0:
            menu_data['menus'].append({'menu_name': menu_name, 'sections': sections})
            seen_menu_names.add(menu_name.lower())
            print(f"    SUCCESS: {len(sections)} sections, {total_items} items")
        else:
            print(f"    No items extracted")
    
    total_links = sum(len(section['items']) for menu in menu_data['menus'] for section in menu['sections'])
    print(f"\n  FINAL: {len(menu_data['menus'])} menus, {total_links} total links")
    
    return menu_data if menu_data['menus'] else None

def main():
    print("Starting Universal SaaS Navigation Menu Scraper")
    print(f"Scraping {len(URLS)} websites...\n")
    
    for url in URLS:
        if data := scrape_website(url):
            domain = urlparse(url).netloc.replace('www.', '')
            with open(f"{domain}.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Saved {domain}.json")
        time.sleep(2)
    
    print("\nDone!")

if __name__ == "__main__":
    main()