import requests
from bs4 import BeautifulSoup
import json, re, time
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import List, Optional

URLS = [
    'https://mailchimp.com',
    'https://www.aweber.com',
    'https://todoist.com',
    'https://evernote.com',
    'https://www.rescuetime.com',
    'https://ghost.org',
    'https://neocities.org',
    'https://www.shopify.com',
    'https://bigcartel.com',
    'https://www.trello.com',
    'https://www.teuxdeux.com',
    'https://typedream.com',
    'https://buffer.com/',
    'https://write.as',
    'https://gumroad.com/',
    'https://carrd.co/',
    'https://x.com',
    'https://manpages.debian.org',
    'https://stuffandnonsense.co.uk',
    'https://w3.org',
    'https://stallman.org',
    'https://text.npr.org',
    'https://suckless.org',
    'https://projecteuler.net',
    'https://www.gnu.org',
    'https://www.cs.princeton.edu/'
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Navigation Scraper Bot)'}
SKIP_TEXT = ['skip to', 'sr-only', 'visually-hidden', 'skip navigation']
ICON_CHARS = re.compile(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹]')
ICON_TEXT = re.compile(r'\ban icon of\b', re.I)
BLOG_PATTERNS = re.compile(r'\bpost\b|\barticle\b|\bblog-list\b|\barchive\b|\bfeed\b', re.I)

@dataclass
class NavNode:
    type: str
    title: str
    url: Optional[str] = None
    description: Optional[str] = None
    children: List['NavNode'] = field(default_factory=list)
    is_cta: bool = False
    
    def to_dict(self):
        d = {'type': self.type, 'title': self.title}
        if self.url: d['url'] = self.url
        if self.description: d['description'] = self.description
        if self.is_cta: d['is_cta'] = self.is_cta
        if self.children: d['children'] = [c.to_dict() for c in self.children]
        return d

def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"   Fetch error: {str(e)[:80]}")
        return None

def clean_text(text):
    if not text: return ""
    text = ICON_CHARS.sub('', text)
    text = ICON_TEXT.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'^[^\w]+|[^\w]+$', '', text)

def split_title_description(text):
    """Split concatenated title+description like 'SitesBuild your website'"""
    if not text or len(text) < 20: return text, None
    
    # Look for capital letter boundary
    match = re.search(r'([A-Z][a-z]+)([A-Z][a-z].{10,})', text)
    if match:
        return match.group(1), match.group(2)
    
    # Look for punctuation boundary
    match = re.search(r'^(.{3,30}?)([.!?]\s+.{10,})$', text)
    if match:
        return match.group(1), match.group(2).strip('. ')
    
    return text, None

def is_hidden(elem):
    style = elem.get('style', '').lower().replace(' ', '')
    if 'display:none' in style or 'visibility:hidden' in style: return True
    cls = ' '.join(elem.get('class', [])).lower()
    return bool(re.search(r'\bsr-only\b|\bvisually-hidden\b|\bhidden\b|\bd-none\b', cls))

def should_skip(text, elem):
    if not text or len(text) < 1: return True
    if is_hidden(elem): return True
    text_lower = text.lower()
    return any(skip in text_lower for skip in SKIP_TEXT)

def is_footer(elem):
    """Enhanced footer detection"""
    parents_list = list(elem.parents)
    for i, p in enumerate(parents_list):
        if i >= 12: break
        if p.name == 'footer': return True
        cls_id = ' '.join(p.get('class', [])).lower() + ' ' + p.get('id', '').lower()
        if re.search(r'\bfooter\b|\bsite-footer\b|\bpage-footer\b|\bbottom\b', cls_id): 
            return True
    return False

def is_content_area(elem):
    """Detect if element is inside main content (blog, articles, etc.)"""
    parents_list = list(elem.parents)
    for i, p in enumerate(parents_list):
        if i >= 10: break
        if p.name in ['main', 'article']: return True
        cls_id = ' '.join(p.get('class', [])).lower() + ' ' + p.get('id', '').lower()
        if BLOG_PATTERNS.search(cls_id): return True
    return False

def find_primary_nav(soup):
    candidates = []
    for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
        if is_hidden(elem): continue
        cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
        
        # Skip footers, sidebars, mobile menus, content areas
        if re.search(r'\bfooter\b|\bsidebar\b|\bmobile-menu\b|\boff-canvas\b', cls_id): 
            continue
        if elem.find_parent('footer') or is_content_area(elem):
            continue
        
        link_count = len(elem.find_all(['a', 'button']))
        
        # NEW: Reject if too many flat links (likely blog archive)
        if link_count > 50:
            nested_lists = elem.find_all('ul')
            if not nested_lists or len(nested_lists) < 3:
                continue  # Too many links without proper structure
        
        if not (3 <= link_count <= 100): continue
        
        score = 100
        if elem.name == 'nav': score += 200
        if elem.get('role') == 'navigation': score += 150
        if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls_id): score += 80
        if re.search(r'\bmain\b|\bprimary\b|\btop\b|\bglobal\b', cls_id): score += 120
        
        parents_list = list(elem.parents)
        depth = next((i for i, p in enumerate(parents_list) if p.name == 'body'), 0)
        score += 100 if depth <= 3 else (50 if depth <= 5 else -(depth-5)*20)
        if elem.find('ul'): score += 40
        
        candidates.append((score, elem, link_count))
    
    if not candidates: return None
    best = max(candidates, key=lambda x: x[0])
    print(f"   Nav found: {best[2]} links, score={best[0]}")
    return best[1]

def extract_description(link):
    """Extract description from nearby elements or split from title"""
    # Try sibling/child description elements
    for desc in link.find_all(['p', 'span', 'div'], class_=re.compile(r'\bdesc\b|\bsubtitle\b|\bcaption\b', re.I), limit=2):
        desc_text = clean_text(desc.get_text(strip=True))
        if desc_text and 5 < len(desc_text) < 300:
            return desc_text
    
    if next_elem := link.find_next_sibling(['p', 'span']):
        if not next_elem.find('a'):
            desc_text = clean_text(next_elem.get_text(strip=True))
            if desc_text and 5 < len(desc_text) < 300:
                return desc_text
    
    return None

def is_cta_link(link):
    cls = ' '.join(link.get('class', [])).lower()
    text = clean_text(link.get_text(strip=True)).lower()
    if re.search(r'\bbtn\b|\bbutton\b|\bcta\b|\bprimary\b', cls): return True
    cta_words = ['sign up', 'get started', 'try free', 'start free', 'book demo', 'contact us']
    return any(cta in text for cta in cta_words)

def is_external_link(url, base_domain):
    """Check if link points to external domain"""
    try:
        link_domain = urlparse(url).netloc.replace('www.', '')
        return link_domain and link_domain != base_domain
    except:
        return False

def find_controlled_panel(trigger, soup):
    if panel_id := trigger.get('aria-controls'):
        if panel := soup.find(id=panel_id):
            return panel
    for attr in ['data-target', 'data-bs-target', 'data-dropdown']:
        if target := trigger.get(attr):
            if panel := soup.find(id=target.lstrip('#')):
                return panel
    if parent_li := trigger.find_parent('li'):
        for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
            if child.find(['a', 'button']): return child
        if panel := parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I)):
            return panel
    if next_sib := trigger.find_next_sibling(['div', 'ul', 'section']):
        if re.search(r'dropdown|menu|panel|mega', ' '.join(next_sib.get('class', [])).lower()):
            return next_sib
    return None

def detect_columns(container):
    for pattern in [r'\bcol-|\bcolumn-|\bgrid', r'\bcol\b', r'\bmega-col\b']:
        cols = container.find_all(['div', 'section', 'li'], class_=re.compile(pattern, re.I), limit=50)
        if len(cols) >= 2: return cols
    return []

def detect_sections_by_headings(container):
    sections = []
    headings = [h for h in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']) if not h.find('a')]
    for i, h in enumerate(headings):
        title = clean_text(h.get_text(strip=True))
        if not title or should_skip(title, h): continue
        
        next_h = headings[i+1] if i+1 < len(headings) else None
        links = []
        curr = h.find_next()
        iterations = 0
        
        while curr and iterations < 200:  # Reduced from 500
            iterations += 1
            if not curr: break
            if next_h:
                parents_list = list(curr.parents) if hasattr(curr, 'parents') else []
                if curr == next_h or next_h in parents_list:
                    break
            
            parents_list = list(curr.parents) if hasattr(curr, 'parents') else []
            if container not in parents_list:
                break
                
            if hasattr(curr, 'name') and curr.name in ['a', 'button'] and curr.get('href'):
                links.append(curr)
            try: 
                curr = curr.find_next()
            except: 
                break
        
        if links:
            sections.append((title, links))
    return sections

def flatten_single_children(nodes):
    """Remove redundant nesting where section has only 1 child"""
    flattened = []
    for node in nodes:
        if node.type == 'section' and len(node.children) == 1:
            # Promote single child up
            flattened.append(node.children[0])
        else:
            if node.children:
                node.children = flatten_single_children(node.children)
            flattened.append(node)
    return flattened

def build_tree_from_container(container, base_url, seen_urls, base_domain, depth=0, max_depth=3):
    """NEW: Added max_depth=3 limit and base_domain filtering"""
    if depth > max_depth: return []
    
    nodes = []
    processed = set()
    
    if columns := detect_columns(container):
        for col in columns:
            col_title = None
            for h in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=2):
                if not h.find('a'):
                    title = clean_text(h.get_text(strip=True))
                    if title and not should_skip(title, h):
                        col_title = title
                        break
            
            child_nodes = build_tree_from_container(col, base_url, seen_urls, base_domain, depth+1)
            if child_nodes:
                if col_title:
                    nodes.append(NavNode(type='section', title=col_title, children=child_nodes))
                else:
                    nodes.extend(child_nodes)
        
        if nodes: 
            return flatten_single_children(nodes)  # NEW
    
    if sections := detect_sections_by_headings(container):
        for sec_title, links in sections:
            child_nodes = []
            for link in links:
                if id(link) in processed: continue
                if node := create_link_node(link, base_url, seen_urls, base_domain):
                    child_nodes.append(node)
                    processed.add(id(link))
            
            if child_nodes:
                nodes.append(NavNode(type='section', title=sec_title, children=child_nodes))
        
        if nodes: 
            return flatten_single_children(nodes)  # NEW
    
    for ul in container.find_all('ul', recursive=False, limit=50):
        parent_ul = ul.find_parent('ul')
        depth_check = 0
        temp = ul
        while parent_ul and depth_check < 2:
            depth_check += 1
            temp = parent_ul
            parent_ul = temp.find_parent('ul')
        
        if depth_check >= 2:
            continue
            
        sec_title = None
        if prev := ul.find_previous_sibling(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            title = clean_text(prev.get_text(strip=True))
            if title and not should_skip(title, prev):
                sec_title = title
        
        child_nodes = []
        for link in ul.find_all(['a', 'button']):
            if id(link) in processed: continue
            if node := create_link_node(link, base_url, seen_urls, base_domain):
                child_nodes.append(node)
                processed.add(id(link))
        
        if child_nodes:
            if sec_title:
                nodes.append(NavNode(type='section', title=sec_title, children=child_nodes))
            else:
                nodes.extend(child_nodes)
    
    if nodes: 
        return flatten_single_children(nodes)  # NEW
    
    for link in container.find_all(['a', 'button'], limit=500):
        if id(link) in processed: continue
        if node := create_link_node(link, base_url, seen_urls, base_domain):
            nodes.append(node)
            processed.add(id(link))
    
    return nodes

def create_link_node(link, base_url, seen_urls, base_domain):
    """NEW: Added base_domain parameter for external link filtering"""
    href = link.get('href', '').strip()
    if not href or href.startswith('javascript:') or href == '#': return None
    
    raw_title = clean_text(link.get_text(strip=True))
    if not raw_title or should_skip(raw_title, link): return None
    if is_footer(link): return None
    
    full_url = urljoin(base_url, href)
    if full_url in seen_urls: return None
    
    # NEW: Filter external links (optional - can be disabled)
    # if is_external_link(full_url, base_domain):
    #     return None
    
    seen_urls.add(full_url)
    
    # NEW: Split concatenated title/description
    title, auto_desc = split_title_description(raw_title)
    description = extract_description(link) or auto_desc
    
    return NavNode(
        type='link',
        title=title,
        url=full_url,
        description=description,
        is_cta=is_cta_link(link)
    )

def extract_navigation_tree(nav, soup, base_url):
    tree = []
    seen_urls = set()
    dd_triggers = set()
    dd_links = set()
    base_domain = urlparse(base_url).netloc.replace('www.', '')
    
    print("   Phase 1: Detecting dropdowns...")
    dropdowns = []
    
    for li in nav.find_all('li', limit=200):
        trigger = next((c for c in li.find_all(['a', 'button'], recursive=False, limit=1)), None)
        if not trigger or is_hidden(trigger): continue
        
        title = clean_text(trigger.get_text(strip=True))
        if not title or should_skip(title, trigger): continue
        
        submenu = li.find(['ul', 'div', 'section'], recursive=False) or \
                  li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
        
        if submenu and len(submenu.find_all(['a', 'button'])) >= 1:
            dropdowns.append((title, trigger, submenu))
            dd_triggers.add(id(trigger))
    
    for elem in nav.find_all(['button', 'a', 'div'], limit=200):
        if is_hidden(elem): continue
        if not (elem.get('aria-expanded') or elem.get('aria-haspopup') or elem.get('data-toggle')): continue
        
        title = clean_text(elem.get_text(strip=True))
        if not title or should_skip(title, elem): continue
        
        if panel := find_controlled_panel(elem, soup):
            if len(panel.find_all(['a', 'button'])) >= 1:
                dropdowns.append((title, elem, panel))
                dd_triggers.add(id(elem))
    
    print(f"   Found {len(dropdowns)} dropdowns")
    print("   Phase 2: Building hierarchy...")
    
    for title, trigger, panel in dropdowns:
        for link in panel.find_all(['a', 'button']): dd_links.add(id(link))
        
        children = build_tree_from_container(panel, base_url, seen_urls, base_domain)
        if children:
            trigger_url = trigger.get('href') if trigger.get('href') and not trigger.get('href').startswith('#') else None
            dropdown_type = 'mega-menu' if len(detect_columns(panel)) >= 2 else 'dropdown'
            
            node = NavNode(type=dropdown_type, title=title, url=trigger_url, children=children)
            tree.append(node)
            print(f"      Added '{title}': {sum(count_links(c) for c in children)} links")
    
    print("   Phase 3: Top-level links...")
    top_level = []
    for link in nav.find_all(['a', 'button'], limit=1000):
        if is_hidden(link) or not link.get('href'): continue
        if id(link) in dd_triggers or id(link) in dd_links: continue
        if is_footer(link): continue  # NEW: Double-check footer
        
        if parent_li := link.find_parent('li'):
            if parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I)):
                continue
        
        if node := create_link_node(link, base_url, seen_urls, base_domain):
            top_level.append(node)
    
    if top_level:
        print(f"      Added {len(top_level)} top-level links")
        tree.extend(top_level)
    
    return flatten_single_children(tree)  # NEW

def count_links(node):
    if node.type == 'link': return 1
    return sum(count_links(c) for c in node.children)

def get_depth(node, current=1):
    if not node.children: return current
    return max(get_depth(c, current+1) for c in node.children)

def validate_tree(tree, base_url):
    if not tree: return False, "Empty tree"
    
    total = sum(count_links(node) for node in tree)
    if total < 2: return False, f"Too few links: {total}"
    
    # NEW: Reject if too many flat links (likely blog archive)
    if total > 40 and len(tree) > 30 and all(not n.children for n in tree):
        return False, f"Too many flat links ({total}), likely blog archive"
    
    domain = urlparse(base_url).netloc.replace('www.', '')
    
    def count_internal(node):
        count = 0
        if node.type == 'link' and node.url:
            if domain in urlparse(node.url).netloc: count = 1
        for child in node.children:
            count += count_internal(child)
        return count
    
    internal = sum(count_internal(node) for node in tree)
    ratio = internal / total if total > 0 else 0
    
    # NEW: Increased threshold from 15% to 30%
    if ratio < 0.30: return False, f"Low internal ratio: {ratio*100:.0f}%"
    
    return True, f"{total} links, {ratio*100:.0f}% internal, {len(tree)} top items"

def scrape(url):
    print(f"\n{'='*70}\n{url}\n{'='*70}")
    if not (html := fetch(url)): return None
    
    soup = BeautifulSoup(html, 'html.parser')
    if not (nav := find_primary_nav(soup)):
        print("   No primary nav found")
        return None
    
    tree = extract_navigation_tree(nav, soup, url)
    is_valid, msg = validate_tree(tree, url)
    print(f"   Result: {msg}")
    
    if not is_valid:
        print(f"   REJECTED: {msg}")
        return None
    
    print("   ACCEPTED")
    return {
        'website': url,
        'domain': urlparse(url).netloc,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'navigation': [node.to_dict() for node in tree],
        'metadata': {
            'total_links': sum(count_links(n) for n in tree),
            'top_level_items': len(tree),
            'max_depth': max((get_depth(n) for n in tree), default=1)
        }
    }

def main():
    print(f"\n{'#'*70}\n# UNIVERSAL NAVIGATION SCRAPER v4.0 FIXED\n# Processing {len(URLS)} websites\n{'#'*70}")
    
    success, results = 0, []
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
        try:
            if data := scrape(url):
                filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   Saved: {filename}")
                success += 1
                results.append((url, 'SUCCESS', filename))
            else:
                results.append((url, 'FAILED', 'Validation failed'))
        except Exception as e:
            print(f"   Exception: {str(e)[:150]}")
            import traceback
            traceback.print_exc()
            results.append((url, 'ERROR', str(e)[:80]))
        time.sleep(1.5)  # Reduced from 2s
    
    print(f"\n\n{'='*70}\n   FINAL: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}\n")
    
    for url, status, detail in results:
        symbol = "✓" if status == "SUCCESS" else "✗"
        print(f"[{symbol}] {urlparse(url).netloc.replace('www.', ''):30s} {detail}")
    
    print(f"\n{'='*70}\nSuccess: {success} | Failed: {len(URLS)-success}\n{'='*70}\n")

if __name__ == "__main__":
    main()





