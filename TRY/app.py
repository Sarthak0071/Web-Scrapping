import requests
from bs4 import BeautifulSoup, Tag
import json, re, time
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import List, Optional, Set

URLS = [
    # Your Original List (kept for testing)
    'https://mailchimp.com', 'https://www.aweber.com', 'https://todoist.com', 
    'https://evernote.com', 'https://www.rescuetime.com', 'https://www.sendgrid.com', 
    'https://postmarkapp.com', 'https://www.wordpress.com', 'https://ghost.org', 
    'https://neocities.org', 'https://www.shopify.com', 'https://bigcartel.com', 
    'https://www.trello.com', 'https://www.teuxdeux.com', 'https://typedream.com', 
    'https://buffer.com/', 'https://write.as', 'https://gumroad.com/', 'https://carrd.co/', 
    'https://www.berkshirehathaway.com', 'https://x.com', 'https://manpages.debian.org', 
    'https://stuffandnonsense.co.uk', 'https://example.com', 'https://motherfuckingwebsite.com', 
    'https://bettermotherfuckingwebsite.com', 'https://plaintextlist.com', 'https://w3.org', 
    'https://stallman.org', 'https://paulgraham.com', 'https://news.ycombinator.com', 
    'https://lite.cnn.com', 'https://text.npr.org', 'https://tilde.town', 
    'https://suckless.org', 'https://catb.org/~esr/', 'https://n-gate.com', 
    'https://info.cern.ch', 'https://projecteuler.net', 'https://lukesmith.xyz', 
    'https://tonsky.me', 'https://www.gnu.org', 'https://www.cs.princeton.edu/'
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
# FIX (gnu.org): Added 'skip\b' to filter out "Skip" links
SKIP_TEXT_RE = re.compile(r'skip to|sr-only|visually-hidden|skip\b', re.I)
ICON_CHARS = re.compile(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹\+]+')
CTA_RE = re.compile(r'\b(btn|button|cta|primary|sign up|get started|try free|start free|book demo|contact us)\b', re.I)

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
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"   Fetch error: {str(e)[:80]}")
        return None

def clean_text(text):
    if not text: return ""
    text = ICON_CHARS.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_hidden(elem):
    style = elem.get('style', '').lower().replace(' ', '')
    if 'display:none' in style or 'visibility:hidden' in style: return True
    cls = ' '.join(elem.get('class', [])).lower()
    return bool(re.search(r'\b(sr-only|visually-hidden|hidden|d-none|invisible)\b', cls))

def should_skip(text, elem):
    if not text or len(text) < 2: return True
    if is_hidden(elem): return True
    return bool(SKIP_TEXT_RE.search(text))

def is_footer_elem(elem):
    if elem.name == 'footer': return True
    cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
    if re.search(r'\bfooter\b', cls_id): return True
    return False

def find_primary_nav(soup, is_fallback=False):
    candidates = []
    search_tags = ['nav', 'header', 'div', 'aside']
    if is_fallback:
        search_tags = ['footer'] # Smart Footer Suppression

    for elem in soup.find_all(search_tags, limit=100):
        if is_hidden(elem): continue
        
        is_foot = is_footer_elem(elem) or elem.find_parent('footer')
        
        if not is_fallback and is_foot: # Main search: skip footers
            continue
        if is_fallback and not is_foot: # Footer search: *only* get footers
            continue

        cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
        
        # FIX (trello.com, tonsky.me): Penalize content/feature/product blocks
        # Added 'product' to the penalty list
        if elem.name in ['main', 'article'] or re.search(r'\b(content|post|entry|main-content|feature|blog|product)\b', cls_id):
            score = -1000
        else:
            score = 100

        # FIX (x.com): Remove 'sidebar' from penalty
        if re.search(r'\b(mobile-menu|off-canvas)\b', cls_id):
            continue
        
        link_count = len(elem.find_all(['a', 'button'], href=True))
        
        # FIX (x.com, tilde.town, tonsky.me, lite.cnn.com):
        # 1. Lowered min links to 2 (for x.com)
        # 2. Capped max links at 75 (to kill content feeds)
        if not (2 <= link_count < 75): continue
        
        # FIX (trello.com): Heavily boost explicit nav elements
        if elem.name == 'nav': score += 300
        if elem.get('role') == 'navigation': score += 250
        if elem.name == 'header': score += 100
        
        # FIX (trello.com): Add boost for data-testid
        if elem.get('data-testid'):
            if re.search(r'nav|menu|header', elem.get('data-testid')): 
                score += 400
        
        if re.search(r'\b(nav|menu|header)\b', cls_id): score += 120
        if re.search(r'\b(main|primary|top|global)\b', cls_id): score += 150
        # FIX (x.com): Reward sidebars
        if re.search(r'\b(sidebar|aside)\b', cls_id) or elem.name == 'aside': score += 70
        
        parents_list = list(elem.parents)
        depth = next((i for i, p in enumerate(parents_list) if p.name == 'body'), 10)
        
        # FIX (tonsky.me): Boost shallow elements (headers)
        if depth <= 3: score += 150
        elif depth <= 5: score += 50
        else: score -= (depth-5)*30 # Penalize deep
            
        if elem.find('ul'): score += 40
        if is_fallback: score += 500 # Boost footer in fallback mode
        
        candidates.append((score, elem, link_count))
    
    if not candidates: return None
    best = max(candidates, key=lambda x: x[0])
    
    if best[0] < 100: # Don't return low-score junk
        print(f"   Nav found: REJECTED low score {best[0]}")
        return None
        
    print(f"   Nav found: {best[2]} links, score={best[0]} (Fallback: {is_fallback})")
    return best[1]

def extract_description(link):
    for desc in link.find_all(['p', 'span', 'div'], class_=re.compile(r'\b(desc|subtitle|caption)\b', re.I), limit=2):
        desc_text = clean_text(desc.get_text(strip=True))
        if desc_text and 5 < len(desc_text) < 300:
            return desc_text
            
    # Check for text in parent 'a' tag that isn't the link title
    if link.parent and link.parent.name == 'a':
        parent_text = clean_text(link.parent.get_text(strip=True))
        link_text = clean_text(link.get_text(strip=True))
        if parent_text != link_text and 5 < len(parent_text) < 300:
             # Find the part that is *not* the link text
            desc_text = parent_text.replace(link_text, '').strip()
            if len(desc_text) > 5:
                return desc_text
    
    # Check for next sibling
    if next_elem := (link.find_next_sibling(['p', 'span']) or \
                     (link.parent and link.parent.find_next_sibling(['p', 'span']))):
        if not next_elem.find('a'):
            desc_text = clean_text(next_elem.get_text(strip=True))
            if desc_text and 5 < len(desc_text) < 300:
                return desc_text
    return None

def is_cta_link(link):
    cls = ' '.join(link.get('class', [])).lower()
    text = clean_text(link.get_text(strip=True))
    return bool(CTA_RE.search(cls) or CTA_RE.search(text))

def find_controlled_panel(trigger, soup):
    # Check aria-controls
    if panel_id := trigger.get('aria-controls'):
        if panel := soup.find(id=panel_id):
            return panel
            
    # Check data-attributes (Bootstrap, Alpine, etc.)
    for attr in ['data-target', 'data-bs-target', 'data-dropdown', 'data-collapse', 'href']:
        if target := trigger.get(attr):
            if target.startswith('#') and len(target) > 1:
                if panel := soup.find(id=target.lstrip('#')):
                    return panel
                    
    # BONUS: Check Alpine.js x-data refs
    if trigger.get('x-data'):
        return trigger # The trigger itself contains the dropdown
        
    # Check parent <li> for a 'ul' or 'div'
    if parent_li := trigger.find_parent('li'):
        for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
            if child.find(['a', 'button']): return child
        if panel := parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I)):
            return panel
            
    # Check next sibling
    if next_sib := trigger.find_next_sibling(['div', 'ul', 'section']):
        if re.search(r'dropdown|menu|panel|mega', ' '.join(next_sib.get('class', [])).lower()):
            return next_sib
    return None

def detect_columns(container):
    # Try class-based
    for pattern in [r'\bcol-|\bcolumn-|\bgrid', r'\bcol\b', r'\bmega-col\b']:
        cols = container.find_all(['div', 'section', 'li'], class_=re.compile(pattern, re.I), limit=50)
        if len(cols) >= 2: return cols
        
    # FIX (buffer.com, shopify.com): Add structural column detection
    # Find direct children that act as columns
    direct_children = container.find_all(['div', 'section', 'li'], recursive=False, limit=20)
    structural_cols = []
    for child in direct_children:
        # A structural col must contain links
        if len(child.find_all('a', limit=2)) >= 1:
            structural_cols.append(child)
    
    if len(structural_cols) >= 2:
        return structural_cols
    return []

def detect_sections_by_headings(container, processed_links: Set[Tag]):
    sections = []
    # Find headings that are not links themselves
    headings = [h for h in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong']) if not h.find('a')]
    
    for h in headings:
        title = clean_text(h.get_text(strip=True))
        if not title or should_skip(title, h): continue
        
        # Find the *closest* ancestor 'container' for this heading
        parent = h
        search_parent = h.parent
        iterations = 0
        
        # Go up until we find a reasonable 'section' wrapper
        while search_parent and search_parent != container and iterations < 5:
            if search_parent.name in ['li', 'div', 'section'] and len(search_parent.find_all('a')) > 0:
                parent = search_parent
                break
            search_parent = search_parent.parent
            iterations += 1
        
        # If no good parent found, use the direct parent
        if parent == h:
            parent = h.parent
            
        links = []
        for link in parent.find_all(['a', 'button']):
            if link not in processed_links and link.get('href'):
                links.append(link)
        
        if links:
            sections.append((title, links))
    return sections

# FIX (sendgrid.com, mailchimp.com, w3.org): Capped max_depth at 4
def build_tree_from_container(container, base_url, seen_urls, soup, depth=0, max_depth=4):
    if depth > max_depth: return []
    
    nodes = []
    processed_links = set() # Links processed *at this level*
    
    # --- STRATEGY 1: Columns (for buffer.com, shopify.com) ---
    if columns := detect_columns(container):
        for col in columns:
            col_title = None
            for h in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=2):
                if not h.find('a'):
                    title = clean_text(h.get_text(strip=True))
                    if title and not should_skip(title, h):
                        col_title = title
                        break
            
            # *** RECURSIVE CALL ***
            child_nodes = build_tree_from_container(col, base_url, seen_urls, soup, depth+1) 
            
            # Mark all links found in children as processed
            for link in col.find_all(['a', 'button']): processed_links.add(link)

            if child_nodes:
                if col_title:
                    nodes.append(NavNode(type='section', title=col_title, children=child_nodes))
                else:
                    nodes.extend(child_nodes)

    # --- STRATEGY 2: Headed Sections (for buffer.com) ---
    # This now runs *in addition* to columns, catching links columns missed
    if sections := detect_sections_by_headings(container, processed_links):
        for sec_title, links in sections:
            child_nodes = []
            for link in links:
                if link in processed_links: continue
                
                # Check for sub-dropdowns
                if panel := find_controlled_panel(link, soup):
                    sub_children = build_tree_from_container(panel, base_url, seen_urls, soup, depth+1)
                    if sub_children:
                        link_url = link.get('href') if link.get('href') and not link.get('href').startswith('#') else None
                        node = NavNode(type='dropdown', title=clean_text(link.get_text(strip=True)), url=link_url, children=sub_children)
                        child_nodes.append(node)
                        for sub_link in panel.find_all(['a', 'button']): processed_links.add(sub_link)
                else:
                    # Create a simple link
                    if node := create_link_node(link, base_url, seen_urls):
                        child_nodes.append(node)
                
                processed_links.add(link)
            
            if child_nodes:
                nodes.append(NavNode(type='section', title=sec_title, children=child_nodes))
    
    # --- STRATEGY 3: Plain Lists (for simple dropdowns) ---
    for ul in container.find_all('ul', recursive=False, limit=50):
        for item in ul.find_all('li', recursive=False, limit=50):
            link = item.find(['a', 'button'], recursive=False)
            if not link or link in processed_links or not link.get('href'):
                # Try finding link one level deeper
                if not link:
                    link_container = item.find(['div', 'span'], recursive=False)
                    if link_container:
                        link = link_container.find(['a', 'button'], recursive=False)
                
                if not link or link in processed_links or not link.get('href'):
                    continue

            title = clean_text(link.get_text(strip=True))
            if not title or should_skip(title, link): continue
            
            # Check for sub-dropdown
            panel = find_controlled_panel(link, soup)
            # Also check if the 'li' itself has a sub-menu
            if not panel:
                panel = item.find(['ul', 'div'], recursive=False)
                if panel and not panel.find('a'): # Ensure it's a real panel
                    panel = None

            if panel:
                sub_children = build_tree_from_container(panel, base_url, seen_urls, soup, depth+1)
                if sub_children:
                    link_url = link.get('href') if not link.get('href').startswith('#') else None
                    node = NavNode(type='dropdown', title=title, url=link_url, children=sub_children)
                    nodes.append(node)
                    for sub_link in panel.find_all(['a', 'button']): processed_links.add(sub_link)
            else:
                # Simple link
                if node := create_link_node(link, base_url, seen_urls):
                    nodes.append(node)
            
            processed_links.add(link)

    # --- STRATEGY 4: Loose Links (catch-all) ---
    for link in container.find_all(['a', 'button'], limit=200):
        if link in processed_links or not link.get('href'): continue
        if node := create_link_node(link, base_url, seen_urls):
            nodes.append(node)
        processed_links.add(link)
    
    return nodes

def create_link_node(link, base_url, seen_urls):
    href = link.get('href', '').strip()
    if not href or href.startswith('javascript:') or href == '#': return None
    
    title = clean_text(link.get_text(strip=True))
    if not title or should_skip(title, link): return None
    
    full_url = urljoin(base_url, href)
    if full_url in seen_urls: return None # Prevent duplicate URLs
    seen_urls.add(full_url)
    
    return NavNode(
        type='link',
        title=title,
        url=full_url,
        description=extract_description(link),
        is_cta=is_cta_link(link)
    )

def extract_navigation_tree(nav, soup, base_url):
    tree = []
    seen_urls = set()
    dd_triggers = set()
    dd_links = set()
    
    print("   Phase 1: Detecting dropdowns...")
    dropdowns = []
    processed_panel_ids = set() # <-- FIX: Added this set
    
    # Find all potential triggers at the top level of the nav
    for elem in nav.find_all(['a', 'button', 'div'], limit=200):
        if is_hidden(elem) or id(elem) in dd_triggers: continue
        
        # FIX (aweber.com): Skip mobile-only triggers
        cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
        if re.search(r'\b(mobile|burger|hamburger|menu-toggle)\b', cls_id): 
            continue
        
        # Check for explicit dropdown triggers
        is_trigger = elem.get('aria-expanded') or elem.get('aria-haspopup') or \
                     elem.get('data-toggle') or elem.get('data-bs-toggle') or \
                     elem.get('x-data')
                     
        title = clean_text(elem.get_text(strip=True))
        if not title and elem.get('aria-label'):
            title = clean_text(elem.get('aria-label'))
        
        # FIX (mailchimp.com): Skip template placeholders
        if not title or '%' in title or re.search(r'\{\{.*\}\}', title):
            continue
            
        if should_skip(title, elem):
            # Maybe the title is in a child span?
            if not title:
                span = elem.find('span')
                if span:
                    title = clean_text(span.get_text(strip=True))
            if not title or should_skip(title, elem):
                continue

        if panel := find_controlled_panel(elem, soup):
            
            if id(panel) in processed_panel_ids: continue # <-- FIX: Skip if panel already found
            
            if len(panel.find_all(['a', 'button'])) >= 1:
                dropdowns.append((title, elem, panel))
                dd_triggers.add(id(elem))
                processed_panel_ids.add(id(panel)) # <-- FIX: Mark panel as processed
                
                for link in panel.find_all(['a', 'button']): dd_links.add(id(link))
                
    print(f"   Found {len(dropdowns)} explicit dropdowns")
    print("   Phase 2: Building hierarchy...")
    
    for title, trigger, panel in dropdowns:
        # FIX (shopify.com): Pass 'soup' to build_tree
        children = build_tree_from_container(panel, base_url, seen_urls, soup)
        if children:
            trigger_url = trigger.get('href') if trigger.get('href') and not trigger.get('href').startswith('#') else None
            dropdown_type = 'mega-menu' if len(detect_columns(panel)) >= 2 else 'dropdown'
            
            node = NavNode(type=dropdown_type, title=title, url=trigger_url, children=children)
            tree.append(node)
            print(f"     Added '{title}': {sum(count_links(c) for c in children)} links")
    
    print("   Phase 3: Top-level links...")
    top_level = []
    # Find top-level 'li > a' links
    for link in nav.find_all(['a', 'button'], limit=1000):
        if is_hidden(link) or not link.get('href'): continue
        if id(link) in dd_triggers or id(link) in dd_links: continue
        
        # Check if it's inside a processed dropdown (double check)
        in_dropdown = False
        for parent in link.parents:
            if id(parent) in [id(p[2]) for p in dropdowns]:
                in_dropdown = True
                break
        if in_dropdown: continue
        
        if node := create_link_node(link, base_url, seen_urls):
            top_level.append(node)
    
    if top_level:
        print(f"     Added {len(top_level)} top-level links")
        tree.extend(top_level)
    
    return tree

# --- Utility Functions (unchanged) ---

def count_links(node):
    if node.type == 'link': return 1
    return sum(count_links(c) for c in node.children)

def get_depth(node, current=1):
    if not node.children: return current
    return max(get_depth(c, current+1) for c in node.children)

def validate_tree(tree, base_url):
    if not tree: return False, "Empty tree"
    
    total = sum(count_links(node) for node in tree)
    # FIX (x.com): Lowered min links to 2
    if total < 2: return False, f"Too few links: {total}"
    
    # FIX (tilde.town, tonsky.me, lite.cnn.com): Added max links
    if total > 100: return False, f"Too many links (likely content): {total}"
    
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
    
    # FIX (tonsky.me): Raise internal link ratio, but not too high
    if ratio < 0.25: return False, f"Low internal ratio: {ratio*100:.0f}%"
    
    return True, f"{total} links, {ratio*100:.0f}% internal, {len(tree)} top items"

def scrape(url):
    print(f"\n{'='*70}\n{url}\n{'='*70}")
    if not (html := fetch(url)): return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # BONUS: Add auto-detection of <template> tags
    for template in soup.find_all('template'):
        template.unwrap() # Replaces template tag with its contents
    
    # FIX: Add Smart Footer Suppression
    nav = find_primary_nav(soup, is_fallback=False)
    if not nav:
        print("   No primary nav found, checking footer...")
        nav = find_primary_nav(soup, is_fallback=True)
        if not nav:
            print("   No primary or footer nav found")
            return None
    
    tree = extract_navigation_tree(nav, soup, url)
    is_valid, msg = validate_tree(tree, url)
    print(f"   Result: {msg}")
    
    if not is_valid:
        # Don't give up if main nav fails, try footer
        if not nav.name == 'footer' and not nav.find_parent('footer'):
            print("   REJECTED. Trying footer as last resort...")
            nav_footer = find_primary_nav(soup, is_fallback=True)
            if nav_footer:
                tree_footer = extract_navigation_tree(nav_footer, soup, url)
                is_valid_footer, msg_footer = validate_tree(tree_footer, url)
                if is_valid_footer:
                    print(f"   Footer Result: {msg_footer}")
                    print("   ACCEPTED (Footer)")
                    tree = tree_footer
                    is_valid = True
                else:
                    print(f"   Footer REJECTED: {msg_footer}")
                    return None
            else:
                 print(f"   REJECTED: {msg}")
                 return None
        else:
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
    print(f"\n{'#'*70}\n# UNIVERSAL NAVIGATION SCRAPER v5.0 (SURGICAL)\n# Processing {len(URLS)} websites\n{'#'*7}")
    
    success, results = 0, []
    for i, url in enumerate(URLS, 1):
        print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
        try:
            if data := scrape(url):
                filename = f"nav_{urlparse(url).netloc.replace('www.', '')}.json"
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
        time.sleep(0.5) # Be gentle
    
    print(f"\n\n{'='*70}\n   FINAL: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}\n")
    
    for url, status, detail in results:
        symbol = "PASS" if status == "SUCCESS" else "FAIL"
        print(f"[{symbol}] {urlparse(url).netloc.replace('www.', ''):25s} {detail}")
    
    print(f"\n{'='*70}\nSuccess: {success} | Failed: {len(URLS)-success}\n{'='*70}\n")

if __name__ == "__main__":
    main()