
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

# Comprehensive noise patterns
NOISE_KEYWORDS = [
    'log in', 'login', 'sign in', 'signin', 'sign up', 'signup', 'get started', 
    'start free', 'try free', 'free trial', 'book demo', 'request demo',
    'skip to', 'jump to', 'back to', 'return to',
    'view all', 'see all', 'show all', 'learn more', 'read more', 'explore all',
    'privacy policy', 'terms of service', 'cookie policy', 'gdpr', 'ccpa',
    'twitter', 'facebook', 'linkedin', 'instagram', 'youtube', 'github social',
    'mastodon', 'discord', 'slack',
    'english', 'español', 'français', 'deutsch', 'italiano', 'português',
    'language', 'currency', 'region',
    'search', 'menu', 'close', 'open', 'toggle'
]

ICON_PATTERNS = [
    r'an?\s+icon\s+of', r'chevron', r'arrow', r'caret', r'symbol',
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
    """Aggressive text cleaning"""
    if not text:
        return ""
    
    # Remove screen reader / icon text
    for pattern in ICON_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.I)
    
    # Remove unicode symbols
    text = re.sub(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove leading/trailing punctuation
    text = re.sub(r'^[^\w]+|[^\w]+$', '', text)
    
    return text

def is_noise(text, elem):
    """Detect if text/element should be filtered"""
    if not text or len(text) < 2 or len(text) > 300:
        return True
    
    text_lower = text.lower().strip()
    
    # Check noise keywords
    for keyword in NOISE_KEYWORDS:
        if keyword == text_lower or (len(keyword) > 5 and keyword in text_lower):
            return True
    
    # Check for screen reader classes
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bsr-only\b|\bvisually-hidden\b|\bhidden\b', classes):
        return True
    
    # Check parent chain (10 levels)
    for parent in list(elem.parents)[:10]:
        p_class = ' '.join(parent.get('class', [])).lower()
        p_id = parent.get('id', '').lower()
        p_tag = parent.name
        
        # Footer/cookie/search/mobile
        if p_tag == 'footer':
            return True
        if re.search(r'\bfooter\b|\bcookie\b|\bsearch\b|\bmobile\b|\bsidebar\b', p_class + ' ' + p_id):
            return True
    
    return False

def is_visible(elem):
    """Check if element is visible (basic check)"""
    style = elem.get('style', '').lower()
    if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', ''):
        return False
    
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bhidden\b|\binvisible\b', classes):
        return False
    
    return True

def find_primary_nav(soup):
    """Ultra-precise primary navigation detection"""
    candidates = []
    body = soup.find('body')
    if not body:
        return None
    
    # Get body height (proxy for position check)
    all_elems = body.find_all(True)
    body_depth = len(all_elems)
    
    for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
        # Skip if not visible
        if not is_visible(elem):
            continue
        
        # Skip footer/sidebar/mobile
        cls = ' '.join(elem.get('class', [])).lower()
        elem_id = elem.get('id', '').lower()
        
        if re.search(r'\bfooter\b|\bsidebar\b|\bmobile-menu\b|\boff-canvas\b', cls + ' ' + elem_id):
            continue
        
        if elem.find_parent('footer'):
            continue
        
        # Count visible links
        links = [a for a in elem.find_all('a', href=True) if is_visible(a)]
        if len(links) < 3:
            continue
        
        # Calculate position score
        position_in_dom = 0
        for i, parent in enumerate(elem.parents):
            if parent.name == 'body':
                position_in_dom = i
                break
        
        # Base score
        score = len(links) * 2
        
        # Semantic bonuses
        if elem.name == 'nav':
            score += 150
        if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls + ' ' + elem_id):
            score += 80
        if re.search(r'\bmain\b|\bprimary\b|\btop\b|\bglobal\b', cls + ' ' + elem_id):
            score += 120
        
        # Position bonus (closer to top = better)
        if position_in_dom <= 3:
            score += 100
        elif position_in_dom <= 5:
            score += 50
        else:
            score -= (position_in_dom - 5) * 15
        
        # Penalize if too nested
        if position_in_dom > 8:
            score -= 100
        
        # Bonus for ul > li structure
        if elem.find('ul'):
            score += 30
        
        candidates.append((score, elem, len(links)))
    
    if not candidates:
        return None
    
    # Return highest scoring
    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"   🎯 Found nav: {candidates[0][2]} links, score={candidates[0][0]}")
    return candidates[0][1]

def find_dropdown_panel(trigger_elem, soup):
    """Find panel for dropdown trigger - 5 methods"""
    
    # Method 1: aria-controls
    if panel_id := trigger_elem.get('aria-controls'):
        if panel := soup.find(id=panel_id):
            if panel.find('a', href=True):
                return panel
    
    # Method 2: data-target / data-bs-target
    for attr in ['data-target', 'data-bs-target', 'data-dropdown']:
        if target := trigger_elem.get(attr):
            target = target.lstrip('#')
            if panel := soup.find(id=target):
                if panel.find('a', href=True):
                    return panel
    
    # Method 3: Parent <li> contains submenu
    parent_li = trigger_elem.find_parent('li')
    if parent_li:
        # Direct child ul/div
        for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
            if child.find('a', href=True):
                return child
        
        # Deeper search with dropdown classes
        panel = parent_li.find(['ul', 'div', 'section'], 
                               class_=re.compile(r'dropdown|submenu|mega|panel|flyout', re.I))
        if panel and panel.find('a', href=True):
            return panel
    
    # Method 4: Next sibling
    next_sib = trigger_elem.find_next_sibling(['div', 'ul', 'section'])
    if next_sib and next_sib.find('a', href=True):
        # Check if sibling has dropdown classes
        cls = ' '.join(next_sib.get('class', [])).lower()
        if re.search(r'dropdown|menu|panel|flyout', cls):
            return next_sib
    
    # Method 5: Parent's next sibling (for button + div structure)
    parent = trigger_elem.parent
    if parent and parent.name in ['li', 'div']:
        next_sib = parent.find_next_sibling(['div', 'ul', 'section'])
        if next_sib and next_sib.find('a', href=True):
            cls = ' '.join(next_sib.get('class', [])).lower()
            if re.search(r'dropdown|menu|panel', cls):
                return next_sib
    
    return None

def is_dropdown_trigger(elem, soup):
    """Determine if element is a dropdown trigger (not a regular link)"""
    
    # Has ARIA dropdown attributes
    if elem.get('aria-expanded') or elem.get('aria-haspopup'):
        return True
    
    # Has data attributes
    if elem.get('data-target') or elem.get('data-toggle') or elem.get('data-dropdown'):
        return True
    
    # Parent <li> has submenu
    parent_li = elem.find_parent('li')
    if parent_li:
        # Check for nested ul
        if parent_li.find('ul', recursive=False):
            return True
        # Check for dropdown div
        if parent_li.find(['div', 'section'], class_=re.compile(r'dropdown|submenu|mega', re.I)):
            return True
    
    # Has href="#" or javascript (common for dropdowns)
    href = elem.get('href', '').strip()
    if href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
        # Check if has panel
        if find_dropdown_panel(elem, soup):
            return True
    
    # Check if next sibling is dropdown panel
    next_sib = elem.find_next_sibling(['div', 'ul'])
    if next_sib:
        cls = ' '.join(next_sib.get('class', [])).lower()
        if re.search(r'dropdown|submenu|mega', cls) and next_sib.find('a', href=True):
            return True
    
    return False

def extract_link_data(link, base_url, seen_urls):
    """Extract validated link data"""
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
    
    # Construct URL
    full_url = urljoin(base_url, href)
    
    # Skip duplicates
    if full_url in seen_urls:
        return None
    
    # Extract description
    description = ""
    
    # Look for description in nearby elements
    for desc_elem in link.find_all(['p', 'span', 'div'], 
                                    class_=re.compile(r'\bdesc\b|\bsubtitle\b|\bcaption\b|\bsummary\b', re.I), 
                                    limit=3):
        desc_text = clean_text(desc_elem.get_text(strip=True))
        if desc_text and desc_text != title and len(desc_text) > 5 and len(desc_text) < 500:
            description = desc_text
            break
    
    # Check next sibling for description
    if not description:
        next_elem = link.find_next_sibling(['p', 'span', 'div'])
        if next_elem:
            desc_text = clean_text(next_elem.get_text(strip=True))
            if desc_text and desc_text != title and len(desc_text) > 5 and len(desc_text) < 500:
                # Make sure it's not another link
                if not next_elem.find('a'):
                    description = desc_text
    
    seen_urls.add(full_url)
    
    return {
        'title': title,
        'description': description,
        'url': full_url
    }

def extract_sections_from_panel(panel, base_url, seen_urls):
    """Extract hierarchical sections - NO TRUNCATION"""
    sections = []
    processed_links = set()
    
    # STRATEGY 1: Grid/Column-based mega-menus
    columns = []
    
    # Try multiple column selectors
    for selector in [
        {'class_': re.compile(r'\bcol-|column-|grid-item', re.I)},
        {'class_': re.compile(r'\bcol\b', re.I)},
    ]:
        cols = panel.find_all(['div', 'section', 'li'], **selector, recursive=True)
        if len(cols) >= 2:
            columns = cols
            break
    
    if len(columns) >= 2:
        for col in columns:
            section_title = None
            
            # Find heading in column
            for heading in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=3):
                # Skip if heading contains link (it's not a title)
                if heading.find('a'):
                    continue
                
                title_text = clean_text(heading.get_text(strip=True))
                if title_text and 2 <= len(title_text) <= 150 and not is_noise(title_text, heading):
                    section_title = title_text
                    break
            
            # Try heading classes
            if not section_title:
                for elem in col.find_all(class_=re.compile(r'\btitle\b|\bheading\b|\blabel\b|\bhead\b', re.I), limit=3):
                    if elem.name == 'a':
                        continue
                    title_text = clean_text(elem.get_text(strip=True))
                    if title_text and 2 <= len(title_text) <= 150 and not is_noise(title_text, elem):
                        section_title = title_text
                        break
            
            # Extract ALL links in column
            items = []
            for link in col.find_all('a', href=True, limit=200):
                link_id = id(link)
                if link_id in processed_links:
                    continue
                
                # Skip if link text == section title
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
    
    # STRATEGY 2: Heading-based sections (NO ITERATION LIMIT)
    headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    if len(headings) >= 1:
        for i, heading in enumerate(headings):
            section_title = clean_text(heading.get_text(strip=True))
            
            # Skip if heading contains link
            if heading.find('a'):
                continue
            
            if not section_title or len(section_title) < 2 or len(section_title) > 150:
                continue
            
            if is_noise(section_title, heading):
                continue
            
            # Get next heading
            next_heading = headings[i + 1] if i + 1 < len(headings) else None
            
            items = []
            current = heading.find_next()
            
            # Process until next heading - NO LIMIT
            while current:
                # Stop at next heading
                if next_heading:
                    if current == next_heading:
                        break
                    if next_heading in list(current.parents):
                        break
                
                # Stop if we've left the panel
                if panel not in list(current.parents):
                    break
                
                # Extract link
                if hasattr(current, 'name') and current.name == 'a' and current.get('href'):
                    link_id = id(current)
                    if link_id not in processed_links:
                        link_text = clean_text(current.get_text(strip=True))
                        if link_text != section_title:
                            if data := extract_link_data(current, base_url, seen_urls):
                                items.append(data)
                                processed_links.add(link_id)
                
                # Get next element safely
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
    top_lists = [ul for ul in panel.find_all('ul', limit=50) if not ul.find_parent('ul')]
    
    if top_lists:
        for ul in top_lists:
            section_title = None
            
            # Check for preceding heading
            prev = ul.find_previous_sibling()
            if prev and prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                section_title = clean_text(prev.get_text(strip=True))
                if len(section_title) < 2 or len(section_title) > 150:
                    section_title = None
            
            items = []
            for link in ul.find_all('a', href=True, limit=200):
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
    
    # STRATEGY 4: Flat (fallback)
    items = []
    for link in panel.find_all('a', href=True, limit=500):
        link_id = id(link)
        if link_id not in processed_links:
            if data := extract_link_data(link, base_url, seen_urls):
                items.append(data)
                processed_links.add(link_id)
    
    if items:
        return [{'section_title': None, 'items': items}]
    
    return []

def extract_navigation(nav, soup, base_url):
    """Extract complete navigation with proper hierarchy"""
    menus = []
    seen_urls = set()
    seen_trigger_texts = set()
    dropdown_trigger_elements = set()
    dropdown_link_ids = set()
    
    # PHASE 1: Identify ALL dropdown triggers
    dropdown_data = []
    
    print("   🔍 Phase 1: Finding dropdown triggers...")
    
    # Type A: <li> with nested submenu
    for li in nav.find_all('li', limit=100):
        # Get direct child link/button
        trigger = None
        for child in li.find_all(['a', 'button'], recursive=False, limit=1):
            trigger = child
            break
        
        if not trigger:
            continue
        
        if not is_visible(trigger):
            continue
        
        trigger_text = clean_text(trigger.get_text(strip=True))
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 100:
            continue
        
        if is_noise(trigger_text, trigger):
            continue
        
        # Check if has submenu
        submenu = li.find(['ul', 'div', 'section'], recursive=False)
        if not submenu:
            submenu = li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
        
        if submenu and len(submenu.find_all('a', href=True)) >= 1:
            if trigger_text.lower() not in seen_trigger_texts:
                dropdown_data.append((trigger_text, submenu, trigger))
                seen_trigger_texts.add(trigger_text.lower())
                dropdown_trigger_elements.add(id(trigger))
    
    # Type B: Elements with ARIA/data attributes
    for elem in nav.find_all(['button', 'a', 'div'], limit=100):
        if not is_visible(elem):
            continue
        
        # Must have dropdown indicators
        if not (elem.get('aria-expanded') or elem.get('aria-haspopup') or 
                elem.get('data-toggle') or elem.get('data-target')):
            continue
        
        trigger_text = clean_text(elem.get_text(strip=True))
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 100:
            continue
        
        if is_noise(trigger_text, elem):
            continue
        
        # Find panel
        panel = find_dropdown_panel(elem, soup)
        if panel and len(panel.find_all('a', href=True)) >= 1:
            if trigger_text.lower() not in seen_trigger_texts:
                dropdown_data.append((trigger_text, panel, elem))
                seen_trigger_texts.add(trigger_text.lower())
                dropdown_trigger_elements.add(id(elem))
    
    print(f"   ✓ Found {len(dropdown_data)} dropdown triggers")
    
    # PHASE 2: Extract dropdown menus with sections
    print("   🔍 Phase 2: Extracting dropdown contents...")
    
    for trigger_text, panel, trigger_elem in dropdown_data:
        # Mark all links in this dropdown
        for link in panel.find_all('a', href=True):
            dropdown_link_ids.add(id(link))
        
        sections = extract_sections_from_panel(panel, base_url, seen_urls)
        
        if sections:
            total_items = sum(len(s['items']) for s in sections)
            print(f"      ✅ '{trigger_text}': {total_items} items, {len(sections)} sections")
            menus.append({
                'menu_name': trigger_text,
                'sections': sections
            })
    
    # PHASE 3: Extract top-level flat links
    print("   🔍 Phase 3: Extracting top-level links...")
    
    top_level_items = []
    
    for link in nav.find_all('a', href=True, limit=500):
        if not is_visible(link):
            continue
        
        link_id = id(link)
        
        # Skip if it's a dropdown trigger
        if link_id in dropdown_trigger_elements:
            continue
        
        # Skip if it's inside a dropdown
        if link_id in dropdown_link_ids:
            continue
        
        # Skip if parent <li> has a submenu (nested case)
        parent_li = link.find_parent('li')
        if parent_li:
            has_submenu = parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I))
            if has_submenu:
                continue
        
        # Extract link
        if data := extract_link_data(link, base_url, seen_urls):
            top_level_items.append(data)
    
    # Add top-level links as menu
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
        return False, "No menus"
    
    total_items = sum(len(s['items']) for m in menus for s in m['sections'])
    
    if total_items < 3:
        return False, f"Too few items: {total_items}"
    
    # Check internal link ratio
    domain = urlparse(base_url).netloc.replace('www.', '')
    internal = sum(
        1 for m in menus 
        for s in m['sections'] 
        for i in s['items'] 
        if domain in urlparse(i['url']).netloc
    )
    
    ratio = internal / total_items if total_items > 0 else 0
    
    if ratio < 0.25:
        return False, f"Low internal ratio: {ratio*100:.0f}%"
    
    # Check for excessive duplicates
    url_counts = defaultdict(int)
    for m in menus:
        for s in m['sections']:
            for item in s['items']:
                url_counts[item['url']] += 1
    
    duplicates = sum(1 for count in url_counts.values() if count > 2)
    if duplicates > total_items * 0.2:
        return False, f"Too many duplicates: {duplicates}"
    
    return True, f"{total_items} items, {ratio*100:.0f}% internal, {len(menus)} menus"

def scrape(url):
    """Main scraping orchestrator"""
    print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    
    html = fetch(url)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find primary nav
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
    print(f"# UNIVERSAL HTML NAVIGATION SCRAPER")
    print(f"# Processing {len(URLS)} websites")
    print(f"{'#'*70}")
    
    success = 0
    results = []
    
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}] {url}\n{'#'*70}")
        
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
        print(f"{symbol} {urlparse(url).netloc:30s} {status:10s} {detail}")
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
            print(f"   • {urlparse(url).netloc}: {detail}")

if __name__ == "__main__":
    main()