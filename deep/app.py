

# import requests
# from bs4 import BeautifulSoup
# import json, re, time
# from urllib.parse import urljoin, urlparse
# from collections import defaultdict

# URLS = [
#     'https://mailchimp.com',
#     'https://www.aweber.com',
#     'https://todoist.com',
#     'https://evernote.com',
#     'https://www.rescuetime.com',
#     'https://www.sendgrid.com',
#     'https://postmarkapp.com',
#     'https://www.wordpress.com',
#     'https://ghost.org',
#     'https://neocities.org',
#     'https://www.shopify.com',
#     'https://bigcartel.com',
#     'https://www.trello.com',
#     'https://www.teuxdeux.com',
#     'https://typedream.com',
#     'https://buffer.com/',
#     'https://write.as',
#     'https://gumroad.com/',
#     'https://carrd.co/'
# ]

# HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
# NOISE_KW = ['log in', 'login', 'sign in', 'signin', 'sign up', 'signup', 'get started', 'start free', 
#     'try free', 'free trial', 'book demo', 'request demo', 'watch demo', 'skip to', 'jump to', 'back to', 
#     'return to', 'go to', 'view all', 'see all', 'show all', 'learn more', 'read more', 'explore all',
#     'privacy policy', 'terms of service', 'cookie policy', 'gdpr', 'ccpa', 'twitter', 'facebook', 
#     'linkedin', 'instagram', 'youtube', 'github social', 'mastodon', 'discord', 'slack', 'tiktok', 
#     'reddit', 'english', 'español', 'français', 'deutsch', 'italiano', 'português', 'language', 
#     'currency', 'region', 'country']
# ICON_PAT = [r'an?\s+icon\s+of', r'chevron', r'arrow\s+(right|left|up|down)', r'caret',
#     r'^[▾▸►▼▲◄◀→←↑↓✓✕✗×]+$', r'right\s+pointing', r'left\s+pointing']

# def fetch(url):
#     try:
#         resp = requests.get(url, headers=HEADERS, timeout=15)
#         resp.raise_for_status()
#         return resp.text
#     except Exception as e:
#         print(f"   ❌ Fetch error: {str(e)[:100]}")
#         return None

# def clean_text(text):
#     if not text: return ""
#     for pat in ICON_PAT: text = re.sub(pat, '', text, flags=re.I)
#     text = re.sub(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹]|\\bNew\\b', '', text)
#     text = re.sub(r'\s+', ' ', text).strip()
#     return re.sub(r'^[^\w]+|[^\w]+$', '', text)

# def is_noise(text, elem):
#     if not text or len(text) < 2 or len(text) > 300: return True
#     text_lower = text.lower().strip()
#     if text_lower in NOISE_KW or any(kw in text_lower for kw in NOISE_KW if len(kw) > 5): return True
#     cls = ' '.join(elem.get('class', [])).lower()
#     if re.search(r'\bsr-only\b|\bvisually-hidden\b|\bhidden\b', cls): return True
#     for parent in list(elem.parents)[:10]:
#         if parent.name == 'footer': return True
#         p_cls = ' '.join(parent.get('class', [])).lower() + ' ' + parent.get('id', '').lower()
#         if re.search(r'\bfooter\b|\bcookie\b|\bsearch\b|\bmobile(?:-menu)?\b|\bsidebar\b|\boff-canvas\b', p_cls): 
#             return True
#     return False

# def is_visible(elem):
#     style = elem.get('style', '').lower().replace(' ', '')
#     if 'display:none' in style or 'visibility:hidden' in style: return False
#     cls = ' '.join(elem.get('class', [])).lower()
#     return not re.search(r'\bhidden\b|\binvisible\b|\bd-none\b', cls)

# def count_top_level(nav):
#     count = sum(len(ul.find_all('li', recursive=False)) for ul in nav.find_all('ul', recursive=False, limit=5))
#     if count: return count
#     for child in nav.children:
#         if hasattr(child, 'name') and child.name in ['div', 'nav']:
#             count = sum(len(ul.find_all('li', recursive=False)) for ul in child.find_all('ul', recursive=False, limit=5))
#             if count: return count
#     count = sum(1 for child in nav.children if hasattr(child, 'name') and child.name in ['a', 'button'] and is_visible(child))
#     if count: return count
#     return sum(1 for child in nav.find_all(['div', 'li'], recursive=False, limit=30) if child.find(['a', 'button'], recursive=False))

# def find_primary_nav(soup):
#     candidates = []
#     for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
#         if not is_visible(elem): continue
#         cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
#         if re.search(r'\bfooter\b|\bsidebar\b|\bmobile-menu\b|\boff-canvas\b|\bsearch\b', cls_id) or elem.find_parent('footer'): 
#             continue
#         top_cnt = count_top_level(elem)
#         if not (3 <= top_cnt <= 25): continue
        
#         score = 100
#         if elem.name == 'nav': score += 200
#         if elem.get('role') == 'navigation': score += 150
#         if re.search(r'\bnav\b|\bmenu\b|\bheader\b', cls_id): score += 80
#         if re.search(r'\bmain\b|\bprimary\b|\btop\b|\bglobal\b', cls_id): score += 120
#         pos = next((i for i, p in enumerate(elem.parents) if p.name == 'body'), 0)
#         score += 100 if pos <= 3 else (50 if pos <= 5 else -(pos-5)*20)
#         if elem.find('ul'): score += 40
#         if pos > 8: score -= 150
        
#         candidates.append((score, elem, top_cnt, len(elem.find_all(['a', 'button']))))
    
#     if not candidates: return None
#     best = max(candidates, key=lambda x: x[0])
#     print(f"   🎯 Nav found: {best[2]} top-level, {best[3]} total clickables, score={best[0]}")
#     return best[1]

# def find_dropdown_panel(trigger, soup):
#     if panel_id := trigger.get('aria-controls'):
#         if panel := soup.find(id=panel_id):
#             if panel.find(['a', 'button']): return panel
    
#     for attr in ['data-target', 'data-bs-target', 'data-dropdown', 'data-panel']:
#         if target := trigger.get(attr):
#             if panel := soup.find(id=target.lstrip('#')):
#                 if panel.find(['a', 'button']): return panel
    
#     if parent_li := trigger.find_parent('li'):
#         for child in parent_li.find_all(['ul', 'div', 'section'], recursive=False):
#             if child.find(['a', 'button']): return child
#         if panel := parent_li.find(['ul', 'div', 'section'], class_=re.compile(r'dropdown|submenu|mega|panel|flyout', re.I)):
#             if panel.find(['a', 'button']): return panel
    
#     if next_sib := trigger.find_next_sibling(['div', 'ul', 'section']):
#         if re.search(r'dropdown|menu|panel|flyout|mega', ' '.join(next_sib.get('class', [])).lower()):
#             if next_sib.find(['a', 'button']): return next_sib
    
#     if parent := trigger.parent:
#         if parent.name in ['li', 'div', 'nav']:
#             if next_sib := parent.find_next_sibling(['div', 'ul', 'section']):
#                 if re.search(r'dropdown|menu|panel', ' '.join(next_sib.get('class', [])).lower()):
#                     if next_sib.find(['a', 'button']): return next_sib
#     return None

# def extract_link_data(link, base_url, seen_urls):
#     href = link.get('href', '').strip()
#     if not href or href.startswith('javascript:') or href == '#': return None
    
#     title = clean_text(link.get_text(strip=True))
#     if not title or is_noise(title, link) or len(title) < 2 or len(title) > 200: return None
    
#     full_url = urljoin(base_url, href)
#     if full_url in seen_urls: return None
    
#     description = ""
#     for desc in link.find_all(['p', 'span', 'div'], class_=re.compile(r'\bdesc\b|\bsubtitle\b|\bcaption\b|\bsummary\b', re.I), limit=3):
#         desc_text = clean_text(desc.get_text(strip=True))
#         if desc_text and desc_text != title and 5 < len(desc_text) < 500:
#             description = desc_text
#             break
    
#     if not description:
#         if next_elem := link.find_next_sibling(['p', 'span', 'div']):
#             if not next_elem.find('a'):
#                 desc_text = clean_text(next_elem.get_text(strip=True))
#                 if desc_text and desc_text != title and 5 < len(desc_text) < 500:
#                     description = desc_text
    
#     seen_urls.add(full_url)
#     return {'title': title, 'description': description, 'url': full_url}

# def extract_sections(panel, base_url, seen_urls):
#     sections, processed = [], set()
#     panel_start = getattr(panel, 'sourceline', 0)
#     panel_end = panel_start + str(panel).count('\n') + 50
#     is_in = lambda e: panel_start <= getattr(e, 'sourceline', panel_start) <= panel_end
    
#     # Column-based
#     columns = []
#     for pat in [r'\bcol-|\bcolumn-|\bgrid-item', r'\bcol\b', r'\bmenu-col\b|\bmega-col\b']:
#         cols = panel.find_all(['div', 'section', 'li'], class_=re.compile(pat, re.I), limit=50)
#         if len(cols) >= 2: columns = cols; break
    
#     if len(columns) >= 2:
#         for col in columns:
#             if not is_in(col): continue
#             sec_title = None
#             for h in col.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong'], limit=3):
#                 if not h.find('a'):
#                     title_text = clean_text(h.get_text(strip=True))
#                     if title_text and 2 <= len(title_text) <= 150 and not is_noise(title_text, h):
#                         sec_title = title_text; break
            
#             items = []
#             for link in col.find_all(['a', 'button'], limit=300):
#                 if link.name == 'button' and not link.get('href'): continue
#                 if not is_in(link) or id(link) in processed: continue
#                 if sec_title and clean_text(link.get_text(strip=True)) == sec_title: continue
#                 if data := extract_link_data(link, base_url, seen_urls):
#                     items.append(data)
#                     processed.add(id(link))
            
#             if items: sections.append({'section_title': sec_title, 'items': items})
#         if sections: return sections
    
#     # Heading-based
#     headings = panel.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
#     if headings:
#         for i, h in enumerate(headings):
#             if not is_in(h) or h.find('a'): continue
#             sec_title = clean_text(h.get_text(strip=True))
#             if not sec_title or len(sec_title) < 2 or len(sec_title) > 150 or is_noise(sec_title, h): continue
            
#             next_h = headings[i+1] if i+1 < len(headings) else None
#             items, curr, iters = [], h.find_next(), 0
            
#             while curr and iters < 1000:
#                 iters += 1
#                 if not is_in(curr) or (next_h and (curr == next_h or next_h in list(curr.parents))) or panel not in list(curr.parents): 
#                     break
#                 if hasattr(curr, 'name') and curr.name in ['a', 'button'] and curr.get('href'):
#                     if id(curr) not in processed:
#                         if clean_text(curr.get_text(strip=True)) != sec_title:
#                             if data := extract_link_data(curr, base_url, seen_urls):
#                                 items.append(data)
#                                 processed.add(id(curr))
#                 try: curr = curr.find_next()
#                 except: break
            
#             if items: sections.append({'section_title': sec_title, 'items': items})
#         if sections: return sections
    
#     # List-based
#     for ul in [u for u in panel.find_all('ul', limit=100) if not u.find_parent('ul')]:
#         if not is_in(ul): continue
#         sec_title = None
#         if prev := ul.find_previous_sibling():
#             if prev.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
#                 sec_title = clean_text(prev.get_text(strip=True))
#                 if len(sec_title) < 2 or len(sec_title) > 150: sec_title = None
        
#         items = []
#         for link in ul.find_all(['a', 'button'], limit=300):
#             if link.get('href') and is_in(link) and id(link) not in processed:
#                 if data := extract_link_data(link, base_url, seen_urls):
#                     items.append(data)
#                     processed.add(id(link))
        
#         if items: sections.append({'section_title': sec_title, 'items': items})
#     if sections: return sections
    
#     # Flat
#     items = []
#     for link in panel.find_all(['a', 'button'], limit=1000):
#         if link.get('href') and is_in(link) and id(link) not in processed:
#             if data := extract_link_data(link, base_url, seen_urls):
#                 items.append(data)
#                 processed.add(id(link))
#     return [{'section_title': None, 'items': items}] if items else []

# def extract_navigation(nav, soup, base_url):
#     menus, seen_urls, seen_trig, dd_triggers, dd_links, js_rend = [], set(), set(), set(), set(), []
#     print("   🔍 Phase 1: Identifying dropdown triggers...")
#     dd_data = []
    
#     # Type A: <li> with submenu
#     for li in nav.find_all('li', limit=200):
#         trig = next((c for c in li.find_all(['a', 'button'], recursive=False, limit=1)), None)
#         if not trig or not is_visible(trig): continue
#         trig_txt = clean_text(trig.get_text(strip=True))
#         if not trig_txt or len(trig_txt) < 2 or len(trig_txt) > 100 or is_noise(trig_txt, trig): continue
        
#         submenu = li.find(['ul', 'div', 'section'], recursive=False) or li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu|mega|panel', re.I))
#         if submenu and len(submenu.find_all(['a', 'button'])) >= 1:
#             if trig_txt.lower() not in seen_trig:
#                 dd_data.append((trig_txt, submenu, trig))
#                 seen_trig.add(trig_txt.lower())
#                 dd_triggers.add(id(trig))
    
#     # Type B: ARIA/data
#     for elem in nav.find_all(['button', 'a', 'div'], limit=200):
#         if not is_visible(elem) or not (elem.get('aria-expanded') or elem.get('aria-haspopup') or elem.get('data-toggle') or elem.get('data-target')): 
#             continue
#         trig_txt = clean_text(elem.get_text(strip=True))
#         if not trig_txt or len(trig_txt) < 2 or len(trig_txt) > 100 or is_noise(trig_txt, elem): continue
        
#         panel = find_dropdown_panel(elem, soup)
#         if not panel and elem.name == 'button':
#             print(f"      ⚠️  JS-rendered dropdown (skipped): '{trig_txt}'")
#             js_rend.append(trig_txt)
#             dd_triggers.add(id(elem))
#             continue
        
#         if panel and len(panel.find_all(['a', 'button'])) >= 1:
#             if trig_txt.lower() not in seen_trig:
#                 dd_data.append((trig_txt, panel, elem))
#                 seen_trig.add(trig_txt.lower())
#                 dd_triggers.add(id(elem))
    
#     print(f"   ✓ Found {len(dd_data)} dropdowns, {len(js_rend)} JS-rendered")
#     print("   🔍 Phase 2: Extracting dropdown contents...")
    
#     for trig_txt, panel, _ in dd_data:
#         for link in panel.find_all(['a', 'button']): dd_links.add(id(link))
#         sections = extract_sections(panel, base_url, seen_urls)
#         if sections:
#             total = sum(len(s['items']) for s in sections)
#             print(f"      ✅ '{trig_txt}': {total} items, {len(sections)} sections")
#             menus.append({'menu_name': trig_txt, 'sections': sections})
    
#     print("   🔍 Phase 3: Extracting top-level links...")
#     top_items = []
#     for link in nav.find_all(['a', 'button'], limit=1000):
#         if not is_visible(link) or (link.name == 'a' and not link.get('href')): continue
#         link_id = id(link)
#         if link_id in dd_triggers or link_id in dd_links: continue
#         if parent_li := link.find_parent('li'):
#             if parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I)): continue
#         if link.name == 'a':
#             if data := extract_link_data(link, base_url, seen_urls): top_items.append(data)
    
#     if top_items:
#         print(f"      ✅ Top-level: {len(top_items)} items")
#         menus.append({'menu_name': 'Navigation', 'sections': [{'section_title': None, 'items': top_items}]})
    
#     return menus

# def validate(menus, base_url):
#     if not menus: return False, "No menus extracted"
#     total = sum(len(s['items']) for m in menus for s in m['sections'])
#     if total < 3: return False, f"Too few items: {total}"
    
#     domain = urlparse(base_url).netloc.replace('www.', '')
#     internal = sum(1 for m in menus for s in m['sections'] for i in s['items'] if domain in urlparse(i['url']).netloc)
#     ratio = internal / total if total > 0 else 0
#     if ratio < 0.20: return False, f"Low internal ratio: {ratio*100:.0f}%"
    
#     url_counts = defaultdict(int)
#     for m in menus:
#         for s in m['sections']:
#             for item in s['items']: url_counts[item['url']] += 1
    
#     dups = sum(1 for count in url_counts.values() if count > 2)
#     if dups > total * 0.3: return False, f"Too many duplicates: {dups}/{total}"
    
#     return True, f"{total} items, {ratio*100:.0f}% internal, {len(menus)} menus"

# def scrape(url):
#     print(f"\n{'='*70}\n🌐 {url}\n{'='*70}")
#     if not (html := fetch(url)): return None
    
#     soup = BeautifulSoup(html, 'html.parser')
#     if not (nav := find_primary_nav(soup)):
#         print("   ❌ No primary navigation found")
#         return None
    
#     menus = extract_navigation(nav, soup, url)
#     is_valid, msg = validate(menus, url)
#     print(f"   📊 Result: {msg}")
    
#     if not is_valid:
#         print(f"   ❌ REJECTED: {msg}")
#         return None
    
#     print("   ✅ ACCEPTED")
#     return {
#         'website': url, 'domain': urlparse(url).netloc,
#         'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'menus': menus
#     }

# def main():
#     print(f"\n{'#'*70}\n# UNIVERSAL HTML NAVIGATION SCRAPER v2.0\n# Master Plan Implementation\n# Processing {len(URLS)} websites\n{'#'*70}")
    
#     success, results = 0, []
#     for i, url in enumerate(URLS, 1):
#         print(f"\n{'#'*70}\n# [{i}/{len(URLS)}]\n{'#'*70}")
#         try:
#             if data := scrape(url):
#                 menu_names = {}
#                 for menu in data['menus']:
#                     name = menu['menu_name']
#                     if name in menu_names:
#                         menu_names[name] += 1
#                         menu['menu_name'] = f"{name} ({menu_names[name]})"
#                     else:
#                         menu_names[name] = 1
                
#                 filename = f"{urlparse(url).netloc.replace('www.', '')}.json"
#                 with open(filename, 'w', encoding='utf-8') as f:
#                     json.dump(data, f, indent=2, ensure_ascii=False)
#                 print(f"   💾 Saved: {filename}")
#                 success += 1
#                 results.append((url, 'SUCCESS', filename))
#             else:
#                 results.append((url, 'FAILED', 'Validation failed'))
#         except Exception as e:
#             print(f"   ❌ Exception: {str(e)[:200]}")
#             import traceback
#             traceback.print_exc()
#             results.append((url, 'ERROR', str(e)[:100]))
#         time.sleep(2)
    
#     print(f"\n\n{'='*70}\n{'='*70}\n   FINAL RESULTS: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}\n{'='*70}\n")
#     print(f"📋 DETAILED RESULTS:\n{'='*70}")
#     for url, status, detail in results:
#         symbol = "✅" if status == "SUCCESS" else "❌"
#         print(f"{symbol} {urlparse(url).netloc.replace('www.', ''):30s} {status:10s} {detail}")
#     print(f"{'='*70}\n")
    
#     if success > 0:
#         print(f"✅ Successfully scraped {success} websites:")
#         for url, status, detail in results:
#             if status == "SUCCESS": print(f"   • {detail}")
#         print()
    
#     if failures := [r for r in results if r[1] != "SUCCESS"]:
#         print(f"❌ Failed to scrape {len(failures)} websites:")
#         for url, status, detail in failures:
#             print(f"   • {urlparse(url).netloc.replace('www.', '')}: {detail}")
#         print()
    
#     print(f"📊 STATISTICS:\n   Success Rate: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n   Failures: {len(failures)}\n   Errors: {sum(1 for r in results if r[1] == 'ERROR')}\n")

# if __name__ == "__main__":
#     main()





import requests
from bs4 import BeautifulSoup
import json, re, time
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import List, Optional

URLS = [
    # Your Original List
    'https://mailchimp.com',
    'https://www.aweber.com',
    'https://todoist.com',
    'https://evernote.com',
    'https://www.rescuetime.com',
    'https://www.sendgrid.com',
    'https://postmarkapp.com',
    'https://www.wordpress.com',
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
    'https://www.berkshirehathaway.com',
    'https://x.com',
    'https://manpages.debian.org',
    'https://stuffandnonsense.co.uk',

    'https://example.com',
    'https://motherfuckingwebsite.com',
    'https://bettermotherfuckingwebsite.com',
    'https://plaintextlist.com',
    'https://w3.org',
    'https://stallman.org',
    'https://paulgraham.com',
    'https://news.ycombinator.com',
    'https://lite.cnn.com',
    'https://text.npr.org',
    'https://tilde.town',
    'https://suckless.org',
    'https://catb.org/~esr/',
    'https://n-gate.com',
    'https://info.cern.ch',
    'https://projecteuler.net',
    'https://lukesmith.xyz',
    'https://www.gnu.org',
    'https://www.cs.princeton.edu/'
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
SKIP_TEXT = ['skip to', 'sr-only', 'visually-hidden']
ICON_CHARS = re.compile(r'[▾▸►▼▲◄◀→←↑↓✓✕✗×›‹]')

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
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'^[^\w]+|[^\w]+$', '', text)

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
    parents_list = list(elem.parents)
    for i, p in enumerate(parents_list):
        if i >= 12: break
        if p.name == 'footer': return True
        cls_id = ' '.join(p.get('class', [])).lower() + ' ' + p.get('id', '').lower()
        if re.search(r'\bfooter\b', cls_id): return True
    return False

def find_primary_nav(soup):
    candidates = []
    for elem in soup.find_all(['nav', 'header', 'div'], limit=100):
        if is_hidden(elem): continue
        cls_id = ' '.join(elem.get('class', [])).lower() + ' ' + elem.get('id', '').lower()
        if re.search(r'\bfooter\b|\bsidebar\b|\bmobile-menu\b|\boff-canvas\b', cls_id) or elem.find_parent('footer'): 
            continue
        
        link_count = len(elem.find_all(['a', 'button']))
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
        
        while curr and iterations < 500:
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

def build_tree_from_container(container, base_url, seen_urls, depth=0, max_depth=4):
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
            
            child_nodes = build_tree_from_container(col, base_url, seen_urls, depth+1)
            if child_nodes:
                if col_title:
                    nodes.append(NavNode(type='section', title=col_title, children=child_nodes))
                else:
                    nodes.extend(child_nodes)
        
        if nodes: return nodes
    
    if sections := detect_sections_by_headings(container):
        for sec_title, links in sections:
            child_nodes = []
            for link in links:
                if id(link) in processed: continue
                if node := create_link_node(link, base_url, seen_urls):
                    child_nodes.append(node)
                    processed.add(id(link))
            
            if child_nodes:
                nodes.append(NavNode(type='section', title=sec_title, children=child_nodes))
        
        if nodes: return nodes
    
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
            if node := create_link_node(link, base_url, seen_urls):
                child_nodes.append(node)
                processed.add(id(link))
        
        if child_nodes:
            if sec_title:
                nodes.append(NavNode(type='section', title=sec_title, children=child_nodes))
            else:
                nodes.extend(child_nodes)
    
    if nodes: return nodes
    
    for link in container.find_all(['a', 'button'], limit=500):
        if id(link) in processed: continue
        if node := create_link_node(link, base_url, seen_urls):
            nodes.append(node)
            processed.add(id(link))
    
    return nodes

def create_link_node(link, base_url, seen_urls):
    href = link.get('href', '').strip()
    if not href or href.startswith('javascript:') or href == '#': return None
    
    title = clean_text(link.get_text(strip=True))
    if not title or should_skip(title, link): return None
    if is_footer(link): return None
    
    full_url = urljoin(base_url, href)
    if full_url in seen_urls: return None
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
        
        children = build_tree_from_container(panel, base_url, seen_urls)
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
        
        if parent_li := link.find_parent('li'):
            if parent_li.find(['ul', 'div'], class_=re.compile(r'dropdown|submenu', re.I)):
                continue
        
        if node := create_link_node(link, base_url, seen_urls):
            top_level.append(node)
    
    if top_level:
        print(f"      Added {len(top_level)} top-level links")
        tree.extend(top_level)
    
    return tree

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
    
    if ratio < 0.15: return False, f"Low internal ratio: {ratio*100:.0f}%"
    
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
    print(f"\n{'#'*70}\n# UNIVERSAL NAVIGATION SCRAPER v3.0 FIXED\n# Processing {len(URLS)} websites\n{'#'*70}")
    
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
        time.sleep(2)
    
    print(f"\n\n{'='*70}\n   FINAL: {success}/{len(URLS)} ({success/len(URLS)*100:.1f}%)\n{'='*70}\n")
    
    for url, status, detail in results:
        symbol = "PASS" if status == "SUCCESS" else "FAIL"
        print(f"[{symbol}] {urlparse(url).netloc.replace('www.', ''):25s} {detail}")
    
    print(f"\n{'='*70}\nSuccess: {success} | Failed: {len(URLS)-success}\n{'='*70}\n")

if __name__ == "__main__":
    main()