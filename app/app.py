#!/usr/bin/env python3
"""
Ultimate Menu Scraper for 100+ HTML-based Websites
Parallel processing, robust error handling, adaptive patterns
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
import logging
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import random
from pathlib import Path

# Import configuration
from urls import URLS, CONFIG, SITE_OVERRIDES, USER_AGENTS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(CONFIG['log_file']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Enhanced skip patterns
SKIP_PATTERNS = [
    r'^get\s+(a\s+)?(demo|started|free|quote)', r'^sign\s+(up|in)', r'^log\s*in',
    r'^try\s+(free|now|it)', r'^contact\s+(us|sales)', r'^request\s+(demo|quote)',
    r'^download\s+', r'^watch\s+(demo|video)', r'^view\s+all', r'^see\s+all',
    r'^learn\s+more$', r'^start\s+(free|now)', r'^pricing$', r'^support$',
    r'^buy\s+now', r'^free\s+trial', r'^book\s+(a|demo)', r'^schedule\s+',
    r'^talk\s+to', r'^join\s+(us|now|free)', r'^subscribe$', r'^register$',
]

EXCLUDE_TEXT = [
    'english', 'select a language', 'log in', 'login', 'sign in', 'sign up',
    'get a demo', 'get started', 'try for free', 'pricing', 'support', 'contact',
    'careers', 'about us', 'free trial', 'sign up free', 'get started free',
]

USER_MENU_INDICATORS = [
    r'account', r'profile', r'user', r'settings', r'dashboard', r'my\s+',
    r'inbox', r'notification', r'logout', r'sign\s+out', r'preferences',
    r'billing', r'subscription', r'upgrade', r'admin', r'workspace',
]

PUBLIC_NAV_KEYWORDS = [
    'product', 'solution', 'resource', 'feature', 'why', 'company', 'pricing',
    'enterprise', 'for', 'use case', 'industry', 'platform', 'service',
    'integration', 'customer', 'partner', 'developer', 'learn', 'about',
]

class MenuScraper:
    """Enhanced menu scraper with adaptive patterns"""
    
    def __init__(self):
        self.session = requests.Session()
        self.stats = {'success': 0, 'failed': 0, 'skipped': 0}
        self.ensure_output_dir()
    
    def ensure_output_dir(self):
        """Create output directory if it doesn't exist"""
        Path(CONFIG['output_dir']).mkdir(exist_ok=True)
    
    def get_headers(self) -> Dict[str, str]:
        """Get random user agent headers"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def fetch_html(self, url: str, attempt: int = 1) -> Optional[str]:
        """Fetch HTML with retry logic"""
        try:
            response = self.session.get(
                url,
                headers=self.get_headers(),
                timeout=CONFIG['timeout'],
                allow_redirects=True
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if attempt < CONFIG['retry_attempts']:
                delay = CONFIG['retry_delay'] * (2 ** (attempt - 1))
                logger.warning(f"Attempt {attempt} failed for {url}, retrying in {delay}s: {str(e)}")
                time.sleep(delay)
                return self.fetch_html(url, attempt + 1)
            logger.error(f"Failed to fetch {url} after {attempt} attempts: {str(e)}")
            return None
    
    def is_site(self, url: str, domain: str) -> bool:
        """Check if URL belongs to specific domain"""
        return domain in urlparse(url).netloc.lower()
    
    def has_class_pattern(self, elem, pattern: str) -> bool:
        """Check if element has class matching pattern"""
        if not elem:
            return False
        # Check element itself
        if elem.get('class') and re.search(pattern, ' '.join(elem.get('class', [])), re.I):
            return True
        # Check immediate parent
        parent = elem.find_parent(['div', 'nav', 'header', 'li'])
        if parent and parent.get('class'):
            return bool(re.search(pattern, ' '.join(parent.get('class', [])), re.I))
        return False
    
    def is_user_menu(self, text: str, elem) -> bool:
        """Determine if this is user account menu"""
        # Check text content
        if any(re.search(p, text.lower()) for p in USER_MENU_INDICATORS):
            return True
        # Check classes
        if self.has_class_pattern(elem, r'user|account|profile|avatar|settings|auth|login'):
            return True
        # Check for user avatar images
        if elem.find('img', alt=re.compile(r'user|account|profile|avatar', re.I)):
            return True
        return False
    
    def is_public_nav_trigger(self, text: str, elem) -> bool:
        """Check if element is public navigation trigger"""
        # Check for public navigation keywords
        if any(k in text.lower() for k in PUBLIC_NAV_KEYWORDS):
            return True
        # Short text is likely navigation
        if len(text.lower().split()) <= 3:
            return True
        # Check classes
        if self.has_class_pattern(elem, r'main.*nav|primary.*nav|global.*nav|top.*nav|site.*nav'):
            return True
        return False
    
    def get_navigation_containers(self, soup: BeautifulSoup, base_url: str) -> List[Tuple[str, any]]:
        """Find main navigation containers with enhanced detection"""
        containers = []
        
        # Strategy 1: Headers (exclude user/auth headers)
        for header in soup.find_all('header', limit=5):
            classes = ' '.join(header.get('class', [])).lower()
            if not re.search(r'user|account|auth|login|footer|sidebar', classes):
                containers.append(('header', header))
        
        # Strategy 2: Navigation with specific classes
        nav_patterns = [
            r'main.*nav', r'primary.*nav', r'global.*nav', r'top.*nav',
            r'site.*nav', r'desktop.*nav', r'header.*nav'
        ]
        for pattern in nav_patterns:
            for nav in soup.find_all('nav', class_=re.compile(pattern, re.I), limit=3):
                containers.append((f'nav-{pattern[:10]}', nav))
        
        # Strategy 3: Role-based navigation
        for nav in soup.find_all(attrs={'role': 'navigation'}, limit=5):
            classes = ' '.join(nav.get('class', [])).lower()
            if not re.search(r'user|account|footer|sidebar|breadcrumb', classes):
                containers.append(('role-nav', nav))
        
        # Strategy 4: Common navigation IDs
        for nav_id in ['nav', 'navigation', 'main-nav', 'primary-nav', 'header-nav']:
            if elem := soup.find(id=nav_id):
                containers.append((f'id-{nav_id}', elem))
        
        # Strategy 5: Site-specific overrides
        for domain, config in SITE_OVERRIDES.items():
            if self.is_site(base_url, domain):
                if 'container_selector' in config:
                    for elem in soup.select(config['container_selector']):
                        containers.append((f'override-{domain}', elem))
        
        # Fallback: Use entire document
        if not containers:
            containers.append(('fallback-body', soup))
        
        return containers[:8]  # Limit to top 8 containers
    
    def find_nav_triggers(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Find navigation menu triggers with 50+ pattern variations"""
        triggers, seen = [], set()
        domain = urlparse(base_url).netloc
        
        for container_type, container in self.get_navigation_containers(soup, base_url):
            # Site-specific patterns first
            if domain in SITE_OVERRIDES:
                override = SITE_OVERRIDES[domain]
                if 'trigger_pattern' in override:
                    for elem in container.find_all(['button', 'a'], class_=re.compile(override['trigger_pattern'], re.I)):
                        if self._add_trigger(elem, triggers, seen, 'site-override'):
                            continue
            
            # ARIA attributes (most reliable)
            for attr in [{'aria-expanded': True}, {'aria-haspopup': True}]:
                for elem in container.find_all(['button', 'a', 'div'], attrs=attr, limit=20):
                    self._add_trigger(elem, triggers, seen, 'aria-attr')
            
            # Class-based patterns (50+ variations)
            class_patterns = [
                r'dropdown.*toggle', r'dropdown.*trigger', r'dropdown.*button',
                r'menu.*trigger', r'menu.*toggle', r'menu.*button',
                r'nav.*trigger', r'nav.*toggle', r'nav.*button',
                r'has.*dropdown', r'has.*submenu', r'has.*menu',
                r'with.*dropdown', r'with.*submenu',
                r'parent.*item', r'parent.*link',
                r'expandable', r'collapsible',
                r'mega.*menu.*trigger', r'mega.*menu.*toggle',
                r'flyout.*trigger', r'flyout.*toggle',
                r'accordion.*trigger', r'accordion.*header',
                r'tab.*trigger', r'tab.*button',
            ]
            
            for pattern in class_patterns:
                for elem in container.find_all(['button', 'a', 'div', 'li'], class_=re.compile(pattern, re.I), limit=15):
                    self._add_trigger(elem, triggers, seen, f'class-{pattern[:15]}')
            
            # Data attributes
            for attr in ['data-toggle', 'data-trigger', 'data-target']:
                for elem in container.find_all(['button', 'a'], attrs={attr: True}, limit=15):
                    self._add_trigger(elem, triggers, seen, f'data-{attr}')
            
            # Structural patterns (li > a/button with sibling ul/div)
            for li in container.find_all('li', limit=30):
                if (trigger := li.find(['a', 'button'], recursive=False)) and \
                   li.find(['ul', 'div', 'nav'], recursive=False):
                    self._add_trigger(trigger, triggers, seen, 'structural-li')
            
            # Stop if we found enough triggers
            if len(triggers) >= CONFIG['max_menus_per_site']:
                break
        
        return triggers[:CONFIG['max_menus_per_site']]
    
    def _add_trigger(self, elem, triggers: List, seen: set, trigger_type: str) -> bool:
        """Helper to add trigger if valid"""
        if not elem:
            return False
        
        text = elem.get_text(strip=True)
        if not text or len(text) < 2 or len(text) > 50:
            return False
        
        text_lower = text.lower()
        if text_lower in seen:
            return False
        
        if self.is_user_menu(text, elem):
            return False
        
        if not self.is_public_nav_trigger(text, elem):
            return False
        
        triggers.append({
            'element': elem,
            'menu_name': text,
            'panel_id': elem.get('aria-controls') or elem.get('aria-owns') or elem.get('data-target'),
            'type': trigger_type,
            'trigger_element': elem
        })
        seen.add(text_lower)
        return True
    
    def is_valid_panel(self, panel) -> bool:
        """Check if panel has reasonable number of links"""
        if not panel:
            return False
        links = panel.find_all('a', href=True)
        return CONFIG['min_links_per_panel'] <= len(links) <= CONFIG['max_links_per_menu']
    
    def score_panel(self, panel) -> int:
        """Score panel quality"""
        if not panel:
            return 0
        
        classes = ' '.join(panel.get('class', [])).lower()
        links = panel.find_all('a', href=True)
        link_count = len(links)
        
        if not (CONFIG['min_links_per_panel'] <= link_count <= CONFIG['max_links_per_menu']):
            return 0
        
        score = 0
        
        # Link count score
        if 5 <= link_count <= 40:
            score += 4
        elif 2 <= link_count <= 50:
            score += 2
        
        # Class name score
        if re.search(r'mega.*menu|dropdown.*menu|submenu|nav.*panel|menu.*panel', classes):
            score += 5
        elif re.search(r'menu|dropdown|nav|content|panel|flyout', classes):
            score += 3
        
        # Hidden state score (menus are often hidden by default)
        style = panel.get('style', '').replace(' ', '').lower()
        if 'display:none' in style or 'visibility:hidden' in style or panel.get('aria-hidden') == 'true':
            score += 3
        
        # ARIA role score
        if panel.get('role') in ['menu', 'navigation', 'menubar', 'group']:
            score += 3
        
        # Structure score (has headings)
        if panel.find_all(['h2', 'h3', 'h4', 'h5', 'h6'], limit=1):
            score += 2
        
        # Public navigation keywords
        text = panel.get_text(strip=True).lower()
        keyword_count = sum(1 for k in PUBLIC_NAV_KEYWORDS if k in text)
        if keyword_count >= 3:
            score += 4
        elif keyword_count >= 1:
            score += 2
        
        return score
    
    def find_panel_for_trigger(self, soup: BeautifulSoup, trigger_info: Dict, base_url: str) -> Optional[any]:
        """Find dropdown panel with multiple strategies"""
        elem = trigger_info['trigger_element']
        panel_id = trigger_info.get('panel_id')
        domain = urlparse(base_url).netloc
        
        # Site-specific panel finding
        if domain in SITE_OVERRIDES:
            override = SITE_OVERRIDES[domain]
            if 'panel_pattern' in override:
                # Check siblings
                for sibling in [elem.find_next_sibling(), elem.find_previous_sibling()]:
                    if sibling and re.search(override['panel_pattern'], ' '.join(sibling.get('class', [])), re.I):
                        if self.is_valid_panel(sibling):
                            return sibling
                # Check parent's children
                if parent := elem.find_parent(['div', 'li', 'nav']):
                    for child in parent.find_all(class_=re.compile(override['panel_pattern'], re.I), recursive=False):
                        if self.is_valid_panel(child):
                            return child
        
        # Strategy 1: ID-based lookup
        if panel_id:
            for finder in [
                lambda: soup.find(id=panel_id),
                lambda: soup.find(attrs={'aria-labelledby': panel_id}),
                lambda: soup.find(attrs={'data-id': panel_id})
            ]:
                if (panel := finder()) and self.is_valid_panel(panel):
                    return panel
        
        # Strategy 2: Immediate siblings
        for sibling in [elem.find_next_sibling(), elem.find_previous_sibling()]:
            if sibling and sibling.name in ['div', 'ul', 'nav', 'section']:
                classes = ' '.join(sibling.get('class', [])).lower()
                if re.search(r'dropdown|mega|menu|submenu|panel|content|flyout', classes):
                    if self.is_valid_panel(sibling):
                        return sibling
        
        # Strategy 3: Parent's children
        if parent := elem.find_parent(['li', 'div', 'nav', 'header']):
            for child in parent.find_all(['div', 'ul', 'nav', 'section'], recursive=False, limit=10):
                if child != elem and elem not in child.parents and self.is_valid_panel(child):
                    return child
        
        # Strategy 4: Score-based ranking
        search_container = elem.find_parent(['header', 'nav']) or soup
        candidates = []
        
        for panel in search_container.find_all(['div', 'ul', 'nav', 'section'], limit=40):
            if panel == elem or elem in panel.parents:
                continue
            score = self.score_panel(panel)
            if score > 3:
                candidates.append((score, panel))
        
        if candidates:
            return max(candidates, key=lambda x: x[0])[1]
        
        return None
    
    def should_skip_link(self, title: str) -> bool:
        """Check if link should be skipped"""
        title_lower = title.lower().strip()
        return any(re.search(p, title_lower) for p in SKIP_PATTERNS) or title_lower in EXCLUDE_TEXT
    
    def extract_item_data(self, link, base_url: str) -> Optional[Dict]:
        """Extract menu item data"""
        href = link.get('href', '')
        if not href or href in ['#', 'javascript:void(0)', 'javascript:;', 'javascript:']:
            return None
        
        # Find title
        title = ""
        title_selectors = [
            lambda: link.find(class_=re.compile(r'title|heading|name|label|text', re.I)),
            lambda: link.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b']),
            lambda: link.find('span'),
            lambda: next((t.strip() for t in link.stripped_strings if 2 <= len(t) < 150), None),
            lambda: link.get('aria-label', '').strip(),
            lambda: link.get('title', '').strip()
        ]
        
        for selector in title_selectors:
            try:
                result = selector()
                if result:
                    title = result.get_text(strip=True) if hasattr(result, 'get_text') else result
                    if title:
                        break
            except:
                continue
        
        # Find description
        desc = ""
        desc_selectors = [
            lambda: link.find(class_=re.compile(r'desc|description|subtitle|summary|excerpt', re.I)),
            lambda: link.find('p'),
            lambda: link.find('small')
        ]
        
        for selector in desc_selectors:
            try:
                if elem := selector():
                    text = elem.get_text(strip=True)
                    if text and text != title:
                        desc = text
                        break
            except:
                continue
        
        # Clean and validate
        title = re.sub(r'\s+', ' ', title).strip()
        desc = re.sub(r'\s+', ' ', desc).strip()[:CONFIG['max_desc_length']]
        
        if not (2 <= len(title) <= CONFIG['max_title_length']) or self.should_skip_link(title):
            return None
        
        url = urljoin(base_url, href)
        if url in [base_url, base_url + '/']:
            return None
        
        return {
            'title': title,
            'description': desc,
            'url': url
        }
    
    def extract_menu_sections(self, panel, base_url: str) -> List[Dict]:
        """Extract hierarchical menu structure"""
        sections = []
        processed_links = set()
        
        # Strategy 1: Column-based containers
        containers = panel.find_all(
            ['div', 'ul', 'nav', 'section', 'li'],
            class_=re.compile(r'column|col-|grid|section|group|category|menu-group|nav-group', re.I),
            limit=20
        )
        
        for container in containers:
            links = container.find_all('a', href=True)
            if len(links) < CONFIG['min_links_per_panel']:
                continue
            
            # Find section title
            title = None
            for finder in [
                lambda: container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']),
                lambda: container.find(class_=re.compile(r'title|heading|category|section.*title', re.I))
            ]:
                if elem := finder():
                    title = elem.get_text(strip=True)
                    if len(title) < 100:
                        break
                    title = None
            
            # Extract items
            items = []
            for link in links:
                if id(link) in processed_links:
                    continue
                if data := self.extract_item_data(link, base_url):
                    items.append(data)
                    processed_links.add(id(link))
            
            if items:
                sections.append({
                    'section_title': title,
                    'items': items
                })
        
        # Strategy 2: Heading-based sections
        if not sections:
            for heading in panel.find_all(['h2', 'h3', 'h4', 'h5', 'h6'], limit=15):
                title = heading.get_text(strip=True)
                if not title or len(title) > 100:
                    continue
                
                # Find links until next heading
                items = []
                next_elem = heading.find_next_sibling()
                while next_elem and next_elem.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    for link in next_elem.find_all('a', href=True):
                        if id(link) not in processed_links:
                            if data := self.extract_item_data(link, base_url):
                                items.append(data)
                                processed_links.add(id(link))
                    next_elem = next_elem.find_next_sibling()
                
                if items:
                    sections.append({
                        'section_title': title,
                        'items': items
                    })
        
        # Strategy 3: List-based sections
        if not sections:
            for ul in panel.find_all('ul', recursive=True, limit=10):
                if ul.find_parent('ul'):
                    continue
                items = []
                for link in ul.find_all('a', href=True, recursive=True):
                    if id(link) not in processed_links:
                        if data := self.extract_item_data(link, base_url):
                            items.append(data)
                            processed_links.add(id(link))
                if items:
                    sections.append({
                        'section_title': None,
                        'items': items
                    })
        
        # Strategy 4: Flat extraction
        if not sections:
            items = []
            for link in panel.find_all('a', href=True):
                if data := self.extract_item_data(link, base_url):
                    items.append(data)
            if items:
                sections.append({
                    'section_title': None,
                    'items': items
                })
        
        # Remove duplicate URLs
        seen_urls = set()
        for section in sections:
            section['items'] = [
                item for item in section['items']
                if item['url'] not in seen_urls and not seen_urls.add(item['url'])
            ]
        
        return [s for s in sections if s['items']]
    
    def scrape_website(self, url: str) -> Optional[Dict]:
        """Main scraping function"""
        domain = urlparse(url).netloc.replace('www.', '')
        
        # Check if already scraped
        output_file = os.path.join(CONFIG['output_dir'], f"{domain}_success.json")
        if CONFIG['resume_mode'] and os.path.exists(output_file):
            logger.info(f"⏭️  Skipping {domain} (already scraped)")
            self.stats['skipped'] += 1
            return None
        
        logger.info(f"🔍 Scraping {domain}...")
        
        # Fetch HTML
        html = self.fetch_html(url)
        if not html:
            return self._handle_failure(url, "Failed to fetch HTML")
        
        # Parse and find triggers
        soup = BeautifulSoup(html, 'html.parser')
        triggers = self.find_nav_triggers(soup, url)
        
        if not triggers:
            return self._handle_failure(url, "No navigation triggers found")
        
        logger.info(f"   Found {len(triggers)} potential menus")
        
        # Extract menu data
        menu_data = {
            'website': url,
            'domain': domain,
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'menus': []
        }
        
        global_seen_urls = set()
        seen_menu_names = set()
        
        for trigger in triggers:
            menu_name = trigger['menu_name']
            if menu_name.lower() in seen_menu_names:
                continue
            
            # Find panel
            panel = self.find_panel_for_trigger(soup, trigger, url)
            if not panel or not self.is_valid_panel(panel):
                logger.debug(f"   ⚠️  No valid panel for '{menu_name}'")
                continue
            
            # Extract sections
            sections = self.extract_menu_sections(panel, url)
            if not sections:
                continue
            
            # Remove globally seen URLs
            for section in sections:
                section['items'] = [
                    item for item in section['items']
                    if item['url'] not in global_seen_urls and not global_seen_urls.add(item['url'])
                ]
            
            sections = [s for s in sections if s['items']]
            
            if sections:
                total_items = sum(len(s['items']) for s in sections)
                logger.info(f"   ✅ '{menu_name}': {total_items} items in {len(sections)} sections")
                menu_data['menus'].append({
                    'menu_name': menu_name,
                    'sections': sections
                })
                seen_menu_names.add(menu_name.lower())
        
        if menu_data['menus']:
            total_menus = len(menu_data['menus'])
            total_items = sum(len(s['items']) for m in menu_data['menus'] for s in m['sections'])
            logger.info(f"✅ {domain}: {total_menus} menus, {total_items} total items")
            self.stats['success'] += 1
            return menu_data
        else:
            return self._handle_failure(url, "No valid menus extracted")
    
    def _handle_failure(self, url: str, reason: str) -> None:
        """Handle scraping failure"""
        domain = urlparse(url).netloc.replace('www.', '')
        logger.warning(f"❌ {domain}: {reason}")
        self.stats['failed'] += 1
        
        if CONFIG['save_failures']:
            failure_data = {
                'website': url,
                'domain': domain,
                'failed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reason': reason
            }
            output_file = os.path.join(CONFIG['output_dir'], f"{domain}_failed.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(failure_data, f, indent=2, ensure_ascii=False)
        
        return None
    
    def save_result(self, data: Dict):
        """Save scraped data to JSON"""
        if not data:
            return
        
        domain = data['domain']
        output_file = os.path.join(CONFIG['output_dir'], f"{domain}_success.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def scrape_parallel(self, urls: List[str]):
        """Scrape multiple websites in parallel"""
        logger.info(f"🚀 Starting parallel scraping of {len(urls)} websites...")
        logger.info(f"   Workers: {CONFIG['max_workers']}, Timeout: {CONFIG['timeout']}s")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=CONFIG['max_workers']) as executor:
            future_to_url = {executor.submit(self.scrape_website, url): url for url in urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        self.save_result(result)
                    
                    # Rate limiting
                    time.sleep(CONFIG['rate_limit_delay'])
                    
                except Exception as e:
                    domain = urlparse(url).netloc.replace('www.', '')
                    logger.error(f"❌ {domain}: Unexpected error - {str(e)}")
                    self.stats['failed'] += 1
        
        elapsed = time.time() - start_time
        self._print_summary(elapsed)
    
    def _print_summary(self, elapsed: float):
        """Print scraping summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 SCRAPING SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Successful: {self.stats['success']}")
        logger.info(f"❌ Failed: {self.stats['failed']}")
        logger.info(f"⏭️  Skipped: {self.stats['skipped']}")
        logger.info(f"⏱️  Time: {elapsed:.2f}s ({elapsed/60:.2f} minutes)")
        logger.info(f"📁 Output: {CONFIG['output_dir']}/")
        logger.info("="*60)
        
        # Success rate
        total_attempted = self.stats['success'] + self.stats['failed']
        if total_attempted > 0:
            success_rate = (self.stats['success'] / total_attempted) * 100
            logger.info(f"🎯 Success Rate: {success_rate:.1f}%")
        
        logger.info("\n💡 Next steps:")
        logger.info(f"   - Check successful results in: {CONFIG['output_dir']}/*_success.json")
        if self.stats['failed'] > 0:
            logger.info(f"   - Review failures in: {CONFIG['output_dir']}/*_failed.json")
        logger.info("="*60 + "\n")


def main():
    """Main entry point"""
    print("\n" + "🌐 ULTIMATE MENU SCRAPER v2.0" .center(60, "="))
    print(f"Target: {len(URLS)} websites")
    print(f"Mode: Parallel ({CONFIG['max_workers']} workers)")
    print(f"Output: {CONFIG['output_dir']}/")
    print("="*60 + "\n")
    
    scraper = MenuScraper()
    scraper.scrape_parallel(URLS)
    
    print("\n✨ Scraping complete! Check the output directory for results.\n")


if __name__ == "__main__":
    main()


