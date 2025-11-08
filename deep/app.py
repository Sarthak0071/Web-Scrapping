



import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
import time

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
    'https://carrd.co', 'https://typedream.com','https://buffer.com/'
]

HEADERS = {'User-Agent': 'Mozilla/5.0'}
AUTH = ['log in', 'login', 'sign in', 'sign up', 'get started', 'start free', 'try free', 'book demo', 'free trial']

def fetch(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=15).text
    except:
        return None

def clean(text):
    text = re.sub(r'An?\s+(icon\s+)?of.*?symbol', '', text, flags=re.I)
    text = re.sub(r'[▾▸►▼▲◄◀→←↑↓]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def is_bad(text, elem):
    t = text.lower().strip()
    if any(kw in t for kw in AUTH) or not (2 <= len(text) <= 300):
        return True
    if text in ['English', 'Español', 'Français', 'Deutsch']:
        return True
    for p in list(elem.parents)[:8]:
        cls = ' '.join(p.get('class', [])).lower()
        if re.search(r'\bfooter\b|\bcookie\b', cls) or p.name == 'footer':
            return True
    return False

def find_nav(soup):
    best, max_score = None, 0
    for elem in soup.find_all(['nav', 'header'], limit=30):
        cls = ' '.join(elem.get('class', [])).lower()
        if re.search(r'\bfooter\b|\bcookie\b', cls) or elem.find_parent('footer'):
            continue
        links = elem.find_all('a', href=True)
        if len(links) < 2:
            continue
        score = len(links)
        if re.search(r'\bmain\b|\bprimary\b|\bheader\b', cls):
            score += 200
        if elem.name == 'nav':
            score += 50
        if score > max_score:
            max_score, best = score, elem
    return best

def find_dropdowns_and_links(nav, soup):
    """Find dropdowns and top-level links - RECURSIVE search"""
    dropdowns, top_links_data, seen = [], [], set()
    
    # Find ALL <li> elements (recursive) that could be dropdowns or top-level
    for li in nav.find_all('li'):
        # Get direct child link
        link = li.find('a', recursive=False) or li.find('button', recursive=False)
        if not link:
            continue
        
        text = clean(link.get_text(strip=True))
        if not (2 <= len(text) <= 80) or text.lower() in seen or is_bad(text, link):
            continue
        
        # Check if has submenu (dropdown)
        submenu = li.find('ul', recursive=False) or li.find(['div', 'section'], recursive=False, class_=re.compile(r'dropdown|submenu|mega', re.I))
        
        if submenu and len(submenu.find_all('a', href=True)) >= 1:
            # It's a dropdown
            dropdowns.append({'trigger': text, 'panel': submenu})
            seen.add(text.lower())
        elif link.get('href'):
            # It's a top-level link
            top_links_data.append(link)
            seen.add(text.lower())
    
    # ARIA-based dropdowns (buttons/divs with aria-expanded)
    for elem in nav.find_all(['button', 'a', 'div']):
        if not (elem.get('aria-expanded') or elem.get('aria-haspopup')):
            continue
        
        text = clean(elem.get_text(strip=True))
        if not (2 <= len(text) <= 80) or text.lower() in seen or is_bad(text, elem):
            continue
        
        # Find panel
        panel = None
        if pid := elem.get('aria-controls'):
            panel = soup.find(id=pid)
        
        if not panel:
            parent = elem.find_parent(['li', 'div', 'nav'])
            if parent:
                panel = parent.find(['div', 'ul', 'section'], class_=re.compile(r'dropdown|menu|panel', re.I))
        
        if not panel:
            panel = elem.find_next_sibling(['div', 'ul'])
        
        if panel and len(panel.find_all('a', href=True)) >= 1:
            dropdowns.append({'trigger': text, 'panel': panel})
            seen.add(text.lower())
    
    # Direct <a> children of nav (flat navigation)
    for link in nav.find_all('a', href=True, limit=200):
        text = clean(link.get_text(strip=True))
        if 2 <= len(text) <= 80 and text.lower() not in seen and not is_bad(text, link):
            # Check if it's NOT inside a dropdown
            parent_li = link.find_parent('li')
            if parent_li:
                has_submenu = parent_li.find('ul', recursive=False)
                if has_submenu:
                    continue  # Skip, it's part of dropdown
            top_links_data.append(link)
            seen.add(text.lower())
    
    return dropdowns, top_links_data

def extract_link(link, base_url):
    href = link.get('href', '').strip()
    if not href or href in ['#', 'javascript:void(0)', 'javascript:;']:
        return None
    title = clean(link.get_text(strip=True))
    if is_bad(title, link):
        return None
    if re.search(r'^(learn more|view all|see all|back to)$', title.lower()):
        return None
    desc = ""
    for elem in link.find_all(['p', 'span'], class_=re.compile(r'\bdesc\b|\bsubtitle\b', re.I), limit=1):
        desc_text = clean(elem.get_text(strip=True))
        if desc_text != title and len(desc_text) < 400:
            desc = desc_text
            break
    url = urljoin(base_url, href)
    return {'title': title, 'description': desc, 'url': url} if url != base_url else None

def extract_sections(panel, base_url):
    """Extract sections with hierarchy"""
    sections, processed = [], set()
    
    # Strategy 1: Columns
    cols = panel.find_all(['div', 'section', 'li'], class_=re.compile(r'\bcol\b|\bcolumn\b|\bgrid', re.I))
    if len(cols) >= 2:
        for col in cols:
            title = None
            for h in col.find_all(['h2', 'h3', 'h4', 'h5', 'h6'], limit=1):
                title = clean(h.get_text(strip=True))
                if 2 <= len(title) <= 150:
                    break
            if not title:
                for t in col.find_all(class_=re.compile(r'\btitle\b|\bheading\b', re.I), limit=1):
                    if t.name not in ['a']:
                        title = clean(t.get_text(strip=True))
                        if 2 <= len(title) <= 150:
                            break
            items = []
            for link in col.find_all('a', href=True):
                if id(link) not in processed:
                    if title and clean(link.get_text(strip=True)) == title:
                        continue
                    if data := extract_link(link, base_url):
                        items.append(data)
                        processed.add(id(link))
            if items:
                sections.append({'section_title': title, 'items': items})
        if sections:
            return sections
    
    # Strategy 2: Headings
    headings = panel.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
    if headings:
        for i, h in enumerate(headings):
            title = clean(h.get_text(strip=True))
            if not (2 <= len(title) <= 150):
                continue
            next_h = headings[i+1] if i+1 < len(headings) else None
            items, current = [], h.find_next()
            count = 0
            while current and count < 100:
                count += 1
                if next_h and (current == next_h or (hasattr(current, 'parents') and next_h in current.parents)):
                    break
                if hasattr(current, 'name') and current.name == 'a' and current.get('href') and id(current) not in processed:
                    if data := extract_link(current, base_url):
                        items.append(data)
                        processed.add(id(current))
                try:
                    current = current.find_next()
                except:
                    break
            if items:
                sections.append({'section_title': title, 'items': items})
        if sections:
            return sections
    
    # Strategy 3: Lists
    lists = [ul for ul in panel.find_all('ul') if not ul.find_parent('ul')]
    if lists:
        for ul in lists:
            items = []
            for link in ul.find_all('a', href=True):
                if id(link) not in processed:
                    if data := extract_link(link, base_url):
                        items.append(data)
                        processed.add(id(link))
            if items:
                sections.append({'section_title': None, 'items': items})
        if sections:
            return sections
    
    # Strategy 4: Flat
    items = []
    for link in panel.find_all('a', href=True, limit=100):
        if id(link) not in processed:
            if data := extract_link(link, base_url):
                items.append(data)
                processed.add(id(link))
    return [{'section_title': None, 'items': items}] if items else []

def scrape(url):
    print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
    html = fetch(url)
    if not html:
        print("❌ Fetch failed")
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    nav = find_nav(soup)
    if not nav:
        print("❌ No nav")
        return None
    
    dropdowns, top_links = find_dropdowns_and_links(nav, soup)
    print(f"🔍 {len(dropdowns)} dropdowns, {len(top_links)} top-level links")
    
    menus, global_urls = [], set()
    
    # Process dropdowns
    for dd in dropdowns:
        sections = extract_sections(dd['panel'], url)
        for sec in sections:
            sec['items'] = [i for i in sec['items'] if i['url'] not in global_urls and not global_urls.add(i['url'])]
        sections = [s for s in sections if s['items']]
        if sections:
            total = sum(len(s['items']) for s in sections)
            print(f"   ✅ {dd['trigger']}: {total} items")
            menus.append({'menu_name': dd['trigger'], 'sections': sections})
    
    # Process top-level links
    if top_links:
        items = []
        for link in top_links:
            if data := extract_link(link, url):
                if data['url'] not in global_urls:
                    items.append(data)
                    global_urls.add(data['url'])
        if items:
            print(f"   ✅ Top-level: {len(items)} items")
            menus.append({'menu_name': 'Navigation', 'sections': [{'section_title': None, 'items': items}]})
    
    # Fallback
    if not menus:
        print("   🔄 Fallback")
        items = []
        for link in nav.find_all('a', href=True, limit=150):
            if data := extract_link(link, url):
                if data['url'] not in global_urls:
                    items.append(data)
                    global_urls.add(data['url'])
        if items:
            print(f"   ✅ Flat: {len(items)} items")
            menus.append({'menu_name': 'Navigation', 'sections': [{'section_title': None, 'items': items}]})
    
    if not menus:
        print("❌ No content")
        return None
    
    total = sum(len(s['items']) for m in menus for s in m['sections'])
    base = urlparse(url).netloc.replace('www.', '')
    internal = sum(1 for m in menus for s in m['sections'] for i in s['items'] if base in urlparse(i['url']).netloc)
    ratio = internal / total if total > 0 else 0
    
    print(f"✅ {total} items, {ratio*100:.0f}% internal, {len(menus)} menus")
    
    if total < 2 or ratio < 0.15:
        print("❌ REJECTED")
        return None
    
    return {
        'website': url,
        'domain': urlparse(url).netloc,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'menus': menus
    }

def main():
    success = 0
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n[{i}/{len(URLS)}]\n{'#'*70}")
        try:
            if data := scrape(url):
                filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"💾 {filename}")
                success += 1
        except Exception as e:
            print(f"❌ {e}")
            import traceback
            traceback.print_exc()
        time.sleep(2)
    print(f"\n{'='*70}\n📊 {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}")

if __name__ == "__main__":
    main()




