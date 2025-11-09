import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
import time
from pathlib import Path

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

def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"   ❌ Fetch: {str(e)[:80]}")
        return None

def is_visible(elem):
    style = elem.get('style', '').lower()
    if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', ''):
        return False
    classes = ' '.join(elem.get('class', [])).lower()
    return not re.search(r'\bhidden\b|\binvisible\b|\bd-none\b', classes)

def is_hidden_menu(elem):
    classes = ' '.join(elem.get('class', [])).lower()
    if re.search(r'\bmobile\b|\boff-canvas\b', classes):
        return True
    for parent in list(elem.parents)[:5]:
        p_class = ' '.join(parent.get('class', [])).lower()
        if re.search(r'\bmobile\b|\bhidden\b|\boff-canvas\b', p_class):
            return True
    return False

def count_top_level(nav):
    count = 0
    for ul in nav.find_all('ul', recursive=False, limit=5):
        count += len(ul.find_all('li', recursive=False))
    if count > 0:
        return count
    for child in nav.children:
        if hasattr(child, 'name') and child.name in ['div', 'nav']:
            for ul in child.find_all('ul', recursive=False, limit=5):
                count += len(ul.find_all('li', recursive=False))
    if count > 0:
        return count
    for child in nav.children:
        if hasattr(child, 'name') and child.name in ['a', 'button'] and is_visible(child):
            count += 1
    return count or len(nav.find_all(['div', 'li'], recursive=False, limit=30))

def find_primary_nav(soup):
    candidates = []
    for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
        if not is_visible(elem):
            continue
        cls = ' '.join(elem.get('class', [])).lower()
        elem_id = elem.get('id', '').lower()
        if re.search(r'\bfooter\b|\bsidebar\b|\bsearch\b', cls + ' ' + elem_id) or elem.find_parent('footer'):
            continue
        top_level = count_top_level(elem)
        if not (3 <= top_level <= 25):
            continue
        score = 100
        if elem.name == 'nav':
            score += 200
        if elem.get('role') == 'navigation':
            score += 150
        if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls + ' ' + elem_id):
            score += 80
        if re.search(r'\bmain\b|\bprimary\b|\btop\b', cls + ' ' + elem_id):
            score += 120
        pos = next((i for i, p in enumerate(elem.parents) if p.name == 'body'), 10)
        score += 100 if pos <= 3 else (50 if pos <= 5 else -(pos - 5) * 20)
        if elem.find('ul'):
            score += 40
        if pos > 8:
            score -= 150
        candidates.append((score, elem, top_level))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"   🎯 Nav: {candidates[0][2]} items, score={candidates[0][0]}")
    return candidates[0][1]

def find_panel(trigger, soup):
    if pid := trigger.get('aria-controls'):
        if panel := soup.find(id=pid):
            if panel.find(['a', 'button']):
                return panel
    for attr in ['data-target', 'data-bs-target', 'data-dropdown']:
        if target := trigger.get(attr):
            if panel := soup.find(id=target.lstrip('#')):
                if panel.find(['a', 'button']):
                    return panel
    parent_li = trigger.find_parent('li')
    if parent_li:
        for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
            if child.find(['a', 'button']):
                return child
        for sub in parent_li.find_all(['ul', 'div', 'section'], limit=10):
            if sub == parent_li:
                continue
            depth = 0
            curr = sub
            while curr and curr != parent_li and depth <= 4:
                depth += 1
                curr = curr.parent
            if depth <= 4 and len(sub.find_all(['a', 'button'])) >= 2:
                return sub
    next_sib = trigger.find_next_sibling(['div', 'ul', 'section'])
    if next_sib and len(next_sib.find_all(['a', 'button'])) >= 2:
        return next_sib
    parent = trigger.parent
    if parent and parent.name in ['li', 'div', 'nav']:
        next_sib = parent.find_next_sibling(['div', 'ul', 'section'])
        if next_sib and len(next_sib.find_all(['a', 'button'])) >= 2:
            return next_sib
    return None

def extract_items(container, base_url):
    items = []
    for link in container.find_all('a', href=True, limit=300):
        if link.find_parent('footer'):
            continue
        href = link.get('href', '').strip()
        if not href or href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
            continue
        title = link.get_text(strip=True)
        if not title or len(title) < 2 or len(title) > 300:
            continue
        items.append({'title': title, 'url': urljoin(base_url, href)})
    return items

def extract_dropdown(panel, base_url):
    children = []
    cols = panel.find_all(['div', 'section', 'li'], class_=re.compile(r'\bcol-|\bcolumn-|\bgrid-item|\bcol\b', re.I), limit=50)
    if len(cols) >= 2:
        for col in cols:
            section_name = None
            for heading in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=2):
                if heading.find('a'):
                    continue
                text = heading.get_text(strip=True)
                if text and 2 <= len(text) <= 150:
                    section_name = text
                    break
            items = extract_items(col, base_url)
            if items:
                children.append({'section': section_name, 'items': items})
        if children:
            return children
    headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    if len(headings) >= 1:
        for i, heading in enumerate(headings):
            if heading.find('a'):
                continue
            section_name = heading.get_text(strip=True)
            if not section_name or len(section_name) < 2 or len(section_name) > 150:
                continue
            next_heading = headings[i + 1] if i + 1 < len(headings) else None
            items = []
            current = heading.find_next()
            iters = 0
            while current and iters < 500:
                iters += 1
                if next_heading and (current == next_heading or next_heading in list(current.parents)):
                    break
                if panel not in list(current.parents):
                    break
                if hasattr(current, 'name') and current.name == 'a' and current.get('href'):
                    href = current.get('href', '').strip()
                    if href and href not in ['#', 'javascript:void(0)', 'javascript:;']:
                        title = current.get_text(strip=True)
                        if title and title != section_name and len(title) >= 2:
                            items.append({'title': title, 'url': urljoin(base_url, href)})
                try:
                    current = current.find_next()
                except:
                    break
            if items:
                children.append({'section': section_name, 'items': items})
        if children:
            return children
    items = extract_items(panel, base_url)
    if items:
        return [{'section': None, 'items': items}]
    return []

def extract_navigation(nav, soup, base_url):
    menus = []
    seen_sigs = set()
    dropdown_triggers = set()
    dropdown_links = set()
    print("   🔍 Finding dropdowns...")
    dropdowns = []
    for li in nav.find_all('li', limit=200):
        if is_hidden_menu(li):
            continue
        trigger = None
        for child in li.find_all(['a', 'button'], recursive=False, limit=1):
            trigger = child
            break
        if not trigger or not is_visible(trigger):
            continue
        title = trigger.get_text(strip=True)
        if not title or len(title) < 2 or len(title) > 100:
            continue
        if title.lower() in ['back', 'close', 'menu', 'return']:
            continue
        submenu = li.find(['ul', 'div', 'section'], recursive=False)
        if not submenu:
            submenu = li.find(['ul', 'div'])
            if submenu and len(submenu.find_all(['a', 'button'])) < 2:
                submenu = None
        if submenu and len(submenu.find_all(['a', 'button'])) >= 1:
            dropdowns.append((title, submenu, trigger))
            dropdown_triggers.add(id(trigger))
    for elem in nav.find_all(['button', 'a', 'div'], limit=200):
        if not is_visible(elem) or is_hidden_menu(elem):
            continue
        if not (elem.get('aria-expanded') or elem.get('aria-haspopup') or elem.get('data-toggle') or elem.get('data-target')):
            continue
        title = elem.get_text(strip=True)
        if not title or len(title) < 2 or len(title) > 100:
            continue
        if title.lower() in ['back', 'close', 'menu', 'return']:
            continue
        panel = find_panel(elem, soup)
        if not panel and elem.name == 'button':
            print(f"      ⚠️  JS: '{title}'")
            dropdown_triggers.add(id(elem))
            continue
        if panel and len(panel.find_all(['a', 'button'])) >= 1:
            dropdowns.append((title, panel, elem))
            dropdown_triggers.add(id(elem))
    for wrapper in nav.find_all('div', limit=300):
        if not is_visible(wrapper) or is_hidden_menu(wrapper):
            continue
        children = [c for c in wrapper.children if hasattr(c, 'name') and c.name in ['a', 'button']]
        if len(children) != 1:
            continue
        trigger = children[0]
        title = trigger.get_text(strip=True)
        if not title or len(title) < 2 or len(title) > 100:
            continue
        if title.lower() in ['back', 'close', 'menu', 'return']:
            continue
        if id(trigger) in dropdown_triggers:
            continue
        sub = None
        for child in wrapper.find_all(['ul', 'div', 'section'], limit=10):
            if child == wrapper or child == trigger:
                continue
            if len(child.find_all(['a', 'button'])) >= 2:
                sub = child
                break
        if sub:
            dropdowns.append((title, sub, trigger))
            dropdown_triggers.add(id(trigger))
    print(f"   ✓ {len(dropdowns)} candidates")
    print("   🔍 Extracting with deduplication...")
    for name, panel, trigger in dropdowns:
        link_count = len(panel.find_all('a', href=True))
        sig = f"{name.lower()}:{link_count}"
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        for link in panel.find_all(['a', 'button']):
            dropdown_links.add(id(link))
        children = extract_dropdown(panel, base_url)
        if children:
            total = sum(len(s['items']) for s in children)
            print(f"      ✅ '{name}': {total} items, {len(children)} sections")
            menus.append({'menu_name': name, 'children': children})
    print("   🔍 Top-level...")
    top_items = []
    for link in nav.find_all('a', href=True, limit=1000):
        if not is_visible(link) or is_hidden_menu(link):
            continue
        if id(link) in dropdown_triggers or id(link) in dropdown_links:
            continue
        parent_li = link.find_parent('li')
        if parent_li and parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I)):
            continue
        if link.find_parent('footer'):
            continue
        href = link.get('href', '').strip()
        if not href or href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
            continue
        title = link.get_text(strip=True)
        if not title or len(title) < 2 or len(title) > 300:
            continue
        top_items.append({'title': title, 'url': urljoin(base_url, href)})
    if top_items:
        print(f"      ✅ Top-level: {len(top_items)} items")
        menus.append({'menu_name': 'Navigation', 'children': [{'section': None, 'items': top_items}]})
    return menus

def get_domains(url):
    domain = urlparse(url).netloc.replace('www.', '')
    return DOMAIN_ALIASES.get(domain, [domain])

def validate(menus, base_url):
    if not menus:
        return False, "No menus"
    total = sum(len(s['items']) for m in menus for s in m['children'])
    if total < 1:
        return False, f"Empty: {total}"
    domains = get_domains(base_url)
    internal = sum(1 for m in menus for s in m['children'] for i in s['items'] if any(d in urlparse(i['url']).netloc for d in domains))
    ratio = internal / total if total > 0 else 0
    if ratio < 0.10:
        return False, f"Low internal: {ratio*100:.0f}%"
    return True, f"{total} items, {ratio*100:.0f}% internal, {len(menus)} menus"

def scrape(url):
    print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    html = fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    nav = find_primary_nav(soup)
    if not nav:
        print("   ❌ No nav")
        return None
    menus = extract_navigation(nav, soup, url)
    valid, msg = validate(menus, url)
    print(f"   📊 {msg}")
    if not valid:
        print(f"   ❌ REJECTED")
        Path('failed').mkdir(exist_ok=True)
        domain = urlparse(url).netloc.replace('www.', '')
        with open(f'failed/{domain}.json', 'w', encoding='utf-8') as f:
            json.dump({'url': url, 'reason': msg, 'menus': menus}, f, indent=2, ensure_ascii=False)
        return None
    print("   ✅ ACCEPTED")
    return {'website': url, 'domain': urlparse(url).netloc, 'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'menus': menus}

def main():
    print(f"\n{'#'*70}")
    print(f"# UNIVERSAL SCRAPER v6.0 FINAL")
    print(f"# Deduplication + Hierarchy + {len(URLS)} sites")
    print(f"{'#'*70}")
    success = 0
    results = []
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
        try:
            if data := scrape(url):
                filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   💾 {filename}")
                success += 1
                results.append((url, 'SUCCESS', filename))
            else:
                results.append((url, 'FAILED', 'Validation failed'))
        except Exception as e:
            print(f"   ❌ {str(e)[:150]}")
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