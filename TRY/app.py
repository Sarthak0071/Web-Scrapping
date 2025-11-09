import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse, urlunparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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
DOMAIN_ALIASES = {'sendinblue.com': ['brevo.com', 'sendinblue.com']}

def normalize_url(url: str, base_url: str) -> str:
    """Normalize URL for accurate deduplication"""
    full_url = urljoin(base_url, url.strip())
    parsed = urlparse(full_url)
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip('/') or '/',
        '', '', ''
    ))
    return normalized

def normalize_text(text: str) -> str:
    """Normalize text for comparison"""
    return ' '.join(text.strip().split())

def is_valid_nav_url(href: str) -> bool:
    """Check if URL is valid for navigation"""
    if not href:
        return False
    href = href.strip().lower()
    invalid = ['#', 'javascript:', 'mailto:', 'tel:']
    return not any(href.startswith(inv) for inv in invalid)

def is_internal_url(url: str, base_url: str) -> bool:
    """Check if URL is internal"""
    base_domain = urlparse(base_url).netloc.replace('www.', '')
    url_domain = urlparse(url).netloc.replace('www.', '')
    domains = DOMAIN_ALIASES.get(base_domain, [base_domain])
    return any(d in url_domain for d in domains)

def is_visible(elem) -> bool:
    """Check if element is visually visible"""
    style = elem.get('style', '').lower()
    if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', ''):
        return False
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bhidden\b|\binvisible\b|\bd-none\b|\bvisually-hidden\b', classes):
        return False
    return True

def is_mobile_only(elem) -> bool:
    """Check if element is mobile-only menu"""
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bmobile\b|\boff-canvas\b|\bhamburger\b', classes):
        return True
    for parent in list(elem.parents)[:5]:
        p_class = ' '.join(parent.get('class', [])).lower()
        if re.search(r'\bmobile\b|\boff-canvas\b|\bhamburger\b', p_class):
            return True
    return False

def is_in_forbidden_zone(elem) -> bool:
    """Check if element is in forbidden areas"""
    if elem.find_parent('footer'):
        return True
    for parent in elem.parents:
        classes = ' '.join(parent.get('class', [])).lower()
        if re.search(r'\bhero\b|\bbanner\b|\bjumbotron\b|\bpromo\b', classes):
            return True
    main_parent = elem.find_parent(['main', 'article'])
    if main_parent:
        depth = 0
        curr = elem
        while curr and curr != main_parent and depth < 10:
            curr = curr.parent
            depth += 1
        if depth > 5:
            return True
    return False

def get_nav_confidence(elem) -> int:
    """Score element's confidence as navigation container"""
    score = 0
    if elem.name == 'nav':
        score += 200
    elif elem.name == 'header':
        score += 100
    if elem.get('role') == 'navigation':
        score += 150
    cls = ' '.join(elem.get('class', [])).lower()
    elem_id = elem.get('id', '').lower()
    combined = cls + ' ' + elem_id
    if re.search(r'\bnavigation\b|\bnav\b|\bmenu\b', combined):
        score += 100
    if re.search(r'\bmain-nav\b|\bprimary-nav\b|\btop-nav\b|\bheader-nav\b', combined):
        score += 150
    if re.search(r'\bfooter\b|\bsidebar\b|\bsecondary\b', combined):
        score -= 200
    depth = len(list(elem.parents))
    if depth <= 3:
        score += 100
    elif depth <= 5:
        score += 50
    else:
        score -= (depth - 5) * 10
    if elem.find('ul'):
        score += 50
    return score

def count_navigable_items(container) -> int:
    """Count top-level navigable items"""
    count = 0
    for ul in container.find_all('ul', recursive=False, limit=10):
        count += len(ul.find_all('li', recursive=False))
    if count > 0:
        return count
    for child in container.children:
        if hasattr(child, 'name'):
            if child.name in ['a', 'button'] and is_visible(child):
                count += 1
            elif child.name in ['div', 'li']:
                if child.find(['a', 'button'], recursive=False):
                    count += 1
    return count

def find_navigation_container(soup) -> Optional[any]:
    """Find primary navigation container"""
    candidates = []
    for elem in soup.find_all(['nav', 'header', 'div'], limit=150):
        if not is_visible(elem):
            continue
        if is_in_forbidden_zone(elem):
            continue
        item_count = count_navigable_items(elem)
        if item_count < 3 or item_count > 30:
            continue
        confidence = get_nav_confidence(elem)
        candidates.append((confidence, item_count, elem))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], -abs(x[1] - 10)), reverse=True)
    winner = candidates[0]
    print(f"   🎯 Nav: {winner[2].name}, {winner[1]} items, confidence={winner[0]}")
    return winner[2]

def find_dropdown_panel(trigger, soup, nav_container) -> Optional[any]:
    """Multi-strategy dropdown panel detection"""
    # Strategy 1: ARIA
    if aria_id := trigger.get('aria-controls'):
        panel = soup.find(id=aria_id)
        if panel and len(panel.find_all('a', href=True)) >= 1:
            return panel
    
    # Strategy 2: Data attributes
    for attr in ['data-target', 'data-bs-target', 'data-dropdown', 'data-menu']:
        if target := trigger.get(attr):
            target_id = target.lstrip('#')
            panel = soup.find(id=target_id)
            if panel and len(panel.find_all('a', href=True)) >= 1:
                return panel
    
    # Strategy 3: Immediate sibling
    next_elem = trigger.find_next_sibling(['div', 'ul', 'section', 'nav'])
    if next_elem and len(next_elem.find_all('a', href=True)) >= 2:
        classes = ' '.join(next_elem.get('class', [])).lower()
        if re.search(r'dropdown|submenu|mega-menu|panel|detail|tab', classes):
            return next_elem
    
    # Strategy 4: Within parent li
    parent_li = trigger.find_parent('li')
    if parent_li:
        for child in parent_li.find_all(['ul', 'div'], recursive=False, limit=3):
            if child != trigger and len(child.find_all('a', href=True)) >= 1:
                return child
        for submenu in parent_li.find_all(['ul', 'div'], limit=5):
            if submenu == parent_li:
                continue
            if submenu.find_parent('li') == parent_li:
                if len(submenu.find_all('a', href=True)) >= 1:
                    return submenu
    
    # Strategy 5: GLOBAL SEARCH - Look for separate nav/div elements (Trello pattern)
    # Get trigger text to match against potential panels
    trigger_text = normalize_text(trigger.get_text()).lower()
    trigger_words = set(trigger_text.split())
    
    # Search for nav/div elements OUTSIDE nav container that might be dropdown panels
    for potential_panel in soup.find_all(['nav', 'div'], limit=100):
        # Skip if it's the nav container itself or inside it
        if potential_panel == nav_container or nav_container in list(potential_panel.parents):
            continue
        
        # Must have links
        panel_links = potential_panel.find_all('a', href=True)
        if len(panel_links) < 2:
            continue
        
        # Check if classes suggest it's a dropdown/tab panel
        classes = ' '.join(potential_panel.get('class', [])).lower()
        if not re.search(r'dropdown|submenu|panel|detail|tab|menu', classes):
            continue
        
        # Check if panel content relates to trigger text
        panel_text = normalize_text(potential_panel.get_text()).lower()
        panel_words = set(panel_text.split())
        
        # If trigger words appear in panel, it's likely the dropdown
        if trigger_words & panel_words:
            return potential_panel
    
    return None

def extract_links(container, base_url: str, limit: int = 200) -> List[Dict]:
    """Extract links from container"""
    items = []
    seen_urls = set()
    for link in container.find_all('a', href=True, limit=limit):
        if is_in_forbidden_zone(link):
            continue
        href = link.get('href', '').strip()
        if not is_valid_nav_url(href):
            continue
        title = normalize_text(link.get_text())
        if not title or len(title) < 2 or len(title) > 200:
            continue
        url = normalize_url(href, base_url)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append({'title': title, 'url': url})
    return items

def extract_dropdown_structure(panel, base_url: str) -> List[Dict]:
    """Extract hierarchical structure from dropdown"""
    # Try column-based
    cols = panel.find_all(
        ['div', 'section', 'li'], 
        class_=re.compile(r'\bcol-|\bcolumn|\bgrid-item|\bcol\b', re.I),
        limit=50
    )
    if len(cols) >= 2:
        sections = []
        for col in cols:
            section_name = None
            for heading in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=3):
                if heading.find('a'):
                    continue
                text = normalize_text(heading.get_text())
                if 2 <= len(text) <= 100:
                    section_name = text
                    break
            items = extract_links(col, base_url)
            if items:
                sections.append({'section': section_name, 'items': items})
        if sections:
            return sections
    
    # Try heading-based
    headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], limit=20)
    if len(headings) >= 1:
        sections = []
        for i, heading in enumerate(headings):
            if heading.find('a'):
                continue
            section_name = normalize_text(heading.get_text())
            if not section_name or len(section_name) < 2 or len(section_name) > 100:
                continue
            next_heading = headings[i + 1] if i + 1 < len(headings) else None
            items = []
            current = heading.find_next()
            iterations = 0
            while current and iterations < 300:
                iterations += 1
                if next_heading and (current == next_heading or next_heading in list(current.parents)):
                    break
                if panel not in list(current.parents):
                    break
                if hasattr(current, 'name') and current.name == 'a' and current.get('href'):
                    href = current.get('href', '').strip()
                    if is_valid_nav_url(href):
                        title = normalize_text(current.get_text())
                        if title and title != section_name and len(title) >= 2:
                            url = normalize_url(href, base_url)
                            items.append({'title': title, 'url': url})
                try:
                    current = current.find_next()
                except:
                    break
            if items:
                sections.append({'section': section_name, 'items': items})
        if sections:
            return sections
    
    # Flat fallback
    items = extract_links(panel, base_url)
    if items:
        return [{'section': None, 'items': items}]
    return []

def extract_navigation_hierarchy(nav, soup, base_url: str) -> List[Dict]:
    """Extract navigation with multi-pass detection"""
    navigation = []
    processed_triggers = set()
    processed_urls = set()
    
    print("   🔍 Phase 1: List-based dropdowns...")
    dropdowns = []
    
    # FIX 1: Relaxed <li> detection - allow deeper search
    for li in nav.find_all('li', limit=200):
        if not is_visible(li) or is_mobile_only(li):
            continue
        
        # Search deeper, but verify it belongs to this li
        trigger = li.find(['a', 'button'])
        if not trigger or not is_visible(trigger):
            continue
        
        # Check trigger actually belongs to this li's subtree
        if trigger.find_parent('li') != li:
            continue
        
        trigger_text = normalize_text(trigger.get_text())
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 80:
            continue
        if trigger_text.lower() in ['menu', 'back', 'close', 'return', '☰']:
            continue
        
        # Look for submenu
        submenu = li.find(['ul', 'div'], recursive=False)
        if not submenu:
            submenu = li.find(['ul', 'div'])
        
        if submenu and len(submenu.find_all('a', href=True)) >= 1:
            dropdowns.append((trigger_text, submenu, trigger))
            processed_triggers.add(id(trigger))
    
    print(f"   ✓ List-based: {len(dropdowns)} found")
    
    # FIX 2: ARIA detection - but continue even without ARIA
    print("   🔍 Phase 2: ARIA-based dropdowns...")
    aria_count = 0
    for trigger in nav.find_all(['button', 'a', 'div'], limit=200):
        if not is_visible(trigger) or is_mobile_only(trigger):
            continue
        if id(trigger) in processed_triggers:
            continue
        
        has_indicator = (
            trigger.get('aria-expanded') or 
            trigger.get('aria-haspopup') or 
            trigger.get('data-toggle') or 
            trigger.get('data-target')
        )
        
        if not has_indicator:
            continue
        
        trigger_text = normalize_text(trigger.get_text())
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 80:
            continue
        if trigger_text.lower() in ['menu', 'back', 'close', 'return', '☰']:
            continue
        
        panel = find_dropdown_panel(trigger, soup, nav)
        if panel and len(panel.find_all('a', href=True)) >= 1:
            dropdowns.append((trigger_text, panel, trigger))
            processed_triggers.add(id(trigger))
            aria_count += 1
    
    print(f"   ✓ ARIA-based: {aria_count} found")
    
    # FIX 3: Structural pattern detection (NEW)
    print("   🔍 Phase 3: Structural patterns...")
    structural_count = 0
    for item in nav.find_all(['li', 'div'], limit=300):
        if not is_visible(item) or is_mobile_only(item):
            continue
        
        # Get direct element children
        element_children = [c for c in item.children if hasattr(c, 'name') and c.name]
        
        if len(element_children) >= 2:
            potential_trigger = element_children[0]
            potential_panel = element_children[1]
            
            # Check if first child could be trigger
            if potential_trigger.name not in ['a', 'button', 'div']:
                continue
            
            # Check if second child could be panel
            if potential_panel.name not in ['div', 'ul', 'section']:
                continue
            
            # Check if panel has links
            if len(potential_panel.find_all('a', href=True)) < 2:
                continue
            
            # Try to find trigger text
            trigger_elem = potential_trigger if potential_trigger.name in ['a', 'button'] else potential_trigger.find(['a', 'button'])
            if not trigger_elem:
                continue
            
            if id(trigger_elem) in processed_triggers:
                continue
            
            trigger_text = normalize_text(trigger_elem.get_text())
            if trigger_text and len(trigger_text) >= 2 and len(trigger_text) <= 80:
                if trigger_text.lower() not in ['menu', 'back', 'close', 'return', '☰']:
                    dropdowns.append((trigger_text, potential_panel, trigger_elem))
                    processed_triggers.add(id(trigger_elem))
                    structural_count += 1
    
    print(f"   ✓ Structural: {structural_count} found")
    
    # FIX 4: Sibling pattern detection (NEW)
    print("   🔍 Phase 4: Sibling patterns...")
    sibling_count = 0
    
    # Also check for detached dropdown panels (Trello pattern)
    print("   🔍 Phase 4b: Detached dropdown panels...")
    detached_count = 0
    
    # Find all potential triggers in nav
    for trigger in nav.find_all(['a', 'button'], limit=100):
        if not is_visible(trigger) or is_mobile_only(trigger):
            continue
        if id(trigger) in processed_triggers:
            continue
        
        trigger_text = normalize_text(trigger.get_text())
        if not trigger_text or len(trigger_text) < 2 or len(trigger_text) > 80:
            continue
        if trigger_text.lower() in ['menu', 'back', 'close', 'return', '☰', 'pricing', 'log in', 'sign up', 'get started']:
            continue
        
        # Try standard sibling check first
        next_elem = trigger.find_next_sibling()
        if next_elem and next_elem.name in ['div', 'ul']:
            if len(next_elem.find_all('a', href=True)) >= 2:
                classes = ' '.join(next_elem.get('class', [])).lower()
                if re.search(r'dropdown|submenu|mega|panel|menu', classes):
                    dropdowns.append((trigger_text, next_elem, trigger))
                    processed_triggers.add(id(trigger))
                    sibling_count += 1
                    continue
        
        # Try global detached panel search (Trello pattern)
        trigger_words = set(trigger_text.lower().split())
        
        for potential_panel in soup.find_all(['nav', 'div'], limit=100):
            # Skip if inside nav container
            if potential_panel == nav or nav in list(potential_panel.parents):
                continue
            
            # Must have links
            if len(potential_panel.find_all('a', href=True)) < 2:
                continue
            
            # Check classes
            classes = ' '.join(potential_panel.get('class', [])).lower()
            if not re.search(r'dropdown|submenu|panel|detail|tab|menu', classes):
                continue
            
            # Check if panel relates to trigger
            panel_text = normalize_text(potential_panel.get_text()).lower()
            
            # Simple word overlap check
            panel_first_100 = ' '.join(panel_text.split()[:20])
            if any(word in panel_first_100 for word in trigger_words if len(word) > 3):
                dropdowns.append((trigger_text, potential_panel, trigger))
                processed_triggers.add(id(trigger))
                detached_count += 1
                break
    
    print(f"   ✓ Sibling: {sibling_count} found")
    print(f"   ✓ Detached: {detached_count} found")
    print(f"   📊 Total candidates: {len(dropdowns)}")
    
    # Extract dropdown structures
    print("   🔍 Phase 5: Extracting structures...")
    for menu_name, panel, trigger in dropdowns:
        sections = extract_dropdown_structure(panel, base_url)
        if not sections:
            continue
        
        # Dedupe within menu
        deduped_sections = []
        menu_has_new = False
        for section in sections:
            unique_items = []
            for item in section['items']:
                if item['url'] not in processed_urls:
                    unique_items.append(item)
                    processed_urls.add(item['url'])
                    menu_has_new = True
            if unique_items:
                deduped_sections.append({'section': section['section'], 'items': unique_items})
        
        if deduped_sections and menu_has_new:
            total = sum(len(s['items']) for s in deduped_sections)
            print(f"      ✅ '{menu_name}': {total} items, {len(deduped_sections)} sections")
            navigation.append({
                'type': 'dropdown',
                'name': menu_name,
                'sections': deduped_sections
            })
        else:
            print(f"      ⏭️  SKIP '{menu_name}': duplicates")
    
    # FIX 5: Smarter top-level extraction
    print("   🔍 Phase 6: Top-level links...")
    
    if not dropdowns:
        # No dropdowns detected - try full extraction
        print("   ⚠️  No dropdowns found - attempting full extraction")
        all_links = extract_links(nav, base_url, limit=500)
        
        if all_links:
            # Dedupe against processed URLs
            unique_links = []
            for link in all_links:
                if link['url'] not in processed_urls:
                    unique_links.append(link)
                    processed_urls.add(link['url'])
            
            if unique_links:
                print(f"      ℹ️  Flat extraction: {len(unique_links)} links")
                navigation.extend([{
                    'type': 'link',
                    'name': link['title'],
                    'url': link['url']
                } for link in unique_links])
    else:
        # Normal top-level extraction
        nav_lists = nav.find_all('ul', recursive=False, limit=10)
        if not nav_lists:
            for child in nav.children:
                if hasattr(child, 'name') and child.name in ['div', 'nav']:
                    nav_lists.extend(child.find_all('ul', recursive=False, limit=10))
        if not nav_lists:
            nav_lists = [nav]
        
        top_links = []
        for nav_list in nav_lists:
            for link in nav_list.find_all('a', href=True, limit=300):
                if not is_visible(link) or is_mobile_only(link):
                    continue
                if id(link) in processed_triggers:
                    continue
                
                parent_li = link.find_parent('li')
                if parent_li and parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega', re.I)):
                    continue
                
                if is_in_forbidden_zone(link):
                    continue
                
                href = link.get('href', '').strip()
                if not is_valid_nav_url(href):
                    continue
                
                url = normalize_url(href, base_url)
                if url in processed_urls:
                    continue
                
                title = normalize_text(link.get_text())
                if not title or len(title) < 2 or len(title) > 200:
                    continue
                
                processed_urls.add(url)
                top_links.append({'type': 'link', 'name': title, 'url': url})
        
        if top_links:
            print(f"      ✅ Top-level: {len(top_links)} links")
            navigation.extend(top_links)
    
    return navigation

def validate_navigation(navigation: List[Dict], base_url: str) -> Tuple[bool, str]:
    """Validate navigation quality"""
    if not navigation:
        return False, "Empty navigation"
    
    total_items = 0
    all_urls = []
    for item in navigation:
        if item['type'] == 'dropdown':
            for section in item['sections']:
                for link in section['items']:
                    all_urls.append(link['url'])
                    total_items += 1
        else:
            all_urls.append(item['url'])
            total_items += 1
    
    if total_items < 1:
        return False, "No items"
    
    internal_count = sum(1 for url in all_urls if is_internal_url(url, base_url))
    internal_ratio = internal_count / len(all_urls) if all_urls else 0
    
    if internal_ratio < 0.15:
        return False, f"Low internal: {internal_ratio*100:.0f}%"
    
    dropdowns = sum(1 for item in navigation if item['type'] == 'dropdown')
    links = sum(1 for item in navigation if item['type'] == 'link')
    
    return True, f"{total_items} items, {dropdowns} dropdowns, {links} links, {internal_ratio*100:.0f}% internal"

def scrape_website(url: str) -> Optional[Dict]:
    """Main scraping function"""
    print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"   ❌ Fetch failed: {str(e)[:80]}")
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    nav = find_navigation_container(soup)
    if not nav:
        print("   ❌ No navigation container")
        return None
    
    navigation = extract_navigation_hierarchy(nav, soup, url)
    valid, msg = validate_navigation(navigation, url)
    print(f"   📊 {msg}")
    
    if not valid:
        print(f"   ❌ REJECTED: {msg}")
        Path('failed').mkdir(exist_ok=True)
        domain = urlparse(url).netloc.replace('www.', '')
        with open(f'failed/{domain}.json', 'w', encoding='utf-8') as f:
            json.dump({'url': url, 'reason': msg, 'navigation': navigation}, f, indent=2, ensure_ascii=False)
        return None
    
    print("   ✅ ACCEPTED")
    return {
        'website': url,
        'domain': urlparse(url).netloc,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'navigation': navigation
    }

def main():
    print(f"\n{'#'*70}")
    print(f"# NAVIGATION SCRAPER v7.1 - FIXED")
    print(f"# Multi-Pass Detection • 5 Strategies")
    print(f"# {len(URLS)} websites")
    print(f"{'#'*70}")
    
    success = 0
    results = []
    
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
        
        try:
            data = scrape_website(url)
            if data:
                filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   💾 {filename}")
                success += 1
                results.append((url, 'SUCCESS', filename))
            else:
                results.append((url, 'FAILED', 'See failed/'))
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)[:150]}")
            results.append((url, 'ERROR', str(e)[:80]))
        
        time.sleep(2)
    
    print(f"\n\n{'='*70}")
    print(f"FINAL: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)")
    print(f"{'='*70}\n")
    
    for url, status, detail in results:
        symbol = "✅" if status == "SUCCESS" else "❌"
        domain = urlparse(url).netloc.replace('www.', '')
        print(f"{symbol} {domain:30s} {detail}")

if __name__ == "__main__":
    main()