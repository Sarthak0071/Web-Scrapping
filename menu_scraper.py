"""Universal Menu Scraper - Core Library"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import json
import re
import time
import warnings

warnings.filterwarnings('ignore')


class Config:
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 2
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    MIN_MENU_ITEMS = 2
    MAX_MENU_DEPTH = 8
    MIN_CONFIDENCE_SCORE = 10
    EXCLUDED_PATHS = {'#', 'javascript:void', 'javascript:', '/cart', '/login', '/signin', '/signup', '/search', '/account', '/checkout'}
    EXCLUDED_KEYWORDS = {'login', 'sign in', 'sign up', 'register', 'cart', 'checkout', 'search', 'account', 'wishlist', 'compare', 'facebook', 'twitter', 'instagram', 'linkedin', 'youtube'}
    MENU_SELECTORS = ['nav', '[role="navigation"]', '[aria-label*="menu" i]', '[aria-label*="navigation" i]', '.navigation', '.nav', '.menu', '.header-nav', '#navigation', '#nav', '#menu', '#main-nav', '.main-menu', '.primary-menu', '.site-navigation']
    SUBMENU_INDICATORS = {'classes': ['submenu', 'dropdown', 'sub-menu', 'child', 'nested'], 'aria': ['aria-expanded', 'aria-haspopup'], 'tags': ['ul', 'ol', 'div']}


def normalize_url(url: str, base_url: str = "") -> str:
    try:
        if not url or url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            return ""
        if base_url and not url.startswith(('http://', 'https://')):
            url = urljoin(base_url, url)
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.rstrip('/')
    except:
        return ""


def is_noise_link(text: str, url: str, config: Config) -> bool:
    if not text or not url:
        return True
    text_lower = text.lower().strip()
    url_lower = url.lower()
    for excluded in config.EXCLUDED_PATHS:
        if url_lower.endswith(excluded) or excluded in url_lower:
            return True
    for keyword in config.EXCLUDED_KEYWORDS:
        if keyword in text_lower:
            return True
    if len(text_lower) < 2:
        return True
    if any(social in url_lower for social in ['facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com']):
        return True
    return False


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'[→←↑↓▼▲►◄»«]', '', text)


def fetch_html(url: str, timeout: int, config: Config) -> Tuple[Optional[str], Optional[str]]:
    headers = {'User-Agent': config.USER_AGENT}
    for attempt in range(config.MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text, None
        except requests.Timeout:
            if attempt == config.MAX_RETRIES - 1:
                return None, f"Timeout after {timeout}s"
        except requests.RequestException as e:
            if attempt == config.MAX_RETRIES - 1:
                return None, f"Request failed: {str(e)[:100]}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)[:100]}"
        time.sleep(0.5 * (attempt + 1))
    return None, "Max retries exceeded"


class MenuItem:
    def __init__(self, text: str, url: str, level: int = 0):
        self.text = clean_text(text)
        self.url = url
        self.level = level
        self.children = []
        self.parent = None
    
    def add_child(self, child: 'MenuItem'):
        child.parent = self
        child.level = self.level + 1
        self.children.append(child)
    
    def to_dict(self) -> Dict:
        result = {'text': self.text, 'url': self.url}
        if self.children:
            result['children'] = [child.to_dict() for child in self.children]
        return result


class MenuTree:
    def __init__(self, items: List[MenuItem], metadata: Dict = None):
        self.items = items
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict:
        return {'menu': [item.to_dict() for item in self.items], 'metadata': self.metadata}
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def get_stats(self) -> Dict:
        def count_items(items):
            return len(items) + sum(count_items(item.children) for item in items)
        def max_depth(items, current_depth=0):
            return current_depth if not items else max(max_depth(item.children, current_depth + 1) for item in items)
        return {'total_items': count_items(self.items), 'top_level_items': len(self.items), 'max_depth': max_depth(self.items)}


class MenuPatternScorer:
    SCORES = {'semantic_nav': 30, 'role_navigation': 25, 'aria_menu': 20, 'class_menu_primary': 15, 'class_menu': 10, 'id_menu': 10, 'has_nested_lists': 8, 'multiple_links': 5, 'header_location': 5, 'depth_indicator': 3}
    PENALTIES = {'footer_location': -15, 'sidebar': -10, 'breadcrumb': -20, 'social_links': -15, 'utility_nav': -10}
    
    def __init__(self):
        self.menu_keywords = ['menu', 'nav', 'navigation']
        self.primary_keywords = ['main', 'primary', 'header', 'top']
        self.exclude_keywords = ['footer', 'sidebar', 'side', 'breadcrumb', 'utility']
    
    def score_element(self, element, position_ratio: float = 0.0) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        if element.name == 'nav':
            score += self.SCORES['semantic_nav']
            reasons.append('semantic <nav> tag')
        if element.get('role') == 'navigation':
            score += self.SCORES['role_navigation']
            reasons.append('role="navigation"')
        
        aria_label = (element.get('aria-label', '') or '').lower()
        if any(kw in aria_label for kw in ['menu', 'navigation']):
            score += self.SCORES['aria_menu']
            reasons.append('aria-label contains menu/nav')
        
        classes = ' '.join(element.get('class', [])).lower()
        if any(kw in classes for kw in self.menu_keywords):
            score += self.SCORES['class_menu_primary'] if any(pk in classes for pk in self.primary_keywords) else self.SCORES['class_menu']
            reasons.append('primary menu class' if any(pk in classes for pk in self.primary_keywords) else 'menu/nav class')
        
        elem_id = (element.get('id', '')).lower()
        if any(kw in elem_id for kw in self.menu_keywords):
            score += self.SCORES['id_menu']
            reasons.append('menu/nav id')
        
        nested_lists = element.find_all('ul', recursive=True)
        if any(ul.find_parent('li') for ul in nested_lists):
            score += self.SCORES['has_nested_lists']
            reasons.append('nested list structure')
        
        links = element.find_all('a', recursive=True)
        if len(links) >= 3:
            score += self.SCORES['multiple_links']
            reasons.append(f'{len(links)} links found')
        
        if position_ratio < 0.3:
            score += self.SCORES['header_location']
            reasons.append('header location')
        
        if element.find(class_=re.compile(r'dropdown|submenu|has-child', re.I)):
            score += self.SCORES['depth_indicator']
            reasons.append('dropdown indicators')
        
        if 'footer' in classes or 'footer' in elem_id or element.find_parent('footer'):
            score += self.PENALTIES['footer_location']
            reasons.append('PENALTY: footer location')
        if element.get('role') == 'breadcrumb' or 'breadcrumb' in classes:
            score += self.PENALTIES['breadcrumb']
            reasons.append('PENALTY: breadcrumb')
        if any(kw in classes or kw in elem_id for kw in ['sidebar', 'aside']):
            score += self.PENALTIES['sidebar']
            reasons.append('PENALTY: sidebar')
        if any(kw in classes or kw in elem_id for kw in ['facebook', 'twitter', 'instagram', 'social']):
            score += self.PENALTIES['social_links']
            reasons.append('PENALTY: social links')
        
        return score, reasons


class MenuContainerDetector:
    def __init__(self, scorer: MenuPatternScorer, config: Config):
        self.scorer = scorer
        self.config = config
    
    def find_menu_containers(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict]:
        candidates = []
        
        for selector in self.config.MENU_SELECTORS:
            for elem in soup.select(selector):
                if elem not in [c['element'] for c in candidates]:
                    candidates.append({'element': elem, 'selector': selector, 'method': 'direct_selector'})
        
        for ul in soup.find_all('ul'):
            if ul.find_all('ul', recursive=False) and ul not in [c['element'] for c in candidates]:
                candidates.append({'element': ul, 'selector': 'nested-ul', 'method': 'structural_heuristic'})
        
        for container in soup.find_all(['div', 'header', 'aside']):
            if len(container.find_all('a', recursive=False)) >= 3 and container not in [c['element'] for c in candidates]:
                candidates.append({'element': container, 'selector': 'link-cluster', 'method': 'link_clustering'})
        
        total_elements = len(list(soup.find_all()))
        scored_candidates = []
        
        for candidate in candidates:
            elem = candidate['element']
            position_ratio = len(list(elem.find_all_previous())) / max(total_elements, 1)
            score, reasons = self.scorer.score_element(elem, position_ratio)
            
            if score >= self.config.MIN_CONFIDENCE_SCORE:
                scored_candidates.append({'element': elem, 'score': score, 'reasons': reasons, 'method': candidate['method'], 'selector': candidate['selector'], 'link_count': len(elem.find_all('a')), 'position_ratio': position_ratio})
        
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        return scored_candidates
    
    def get_best_menu(self, soup: BeautifulSoup, base_url: str = "") -> Optional[Dict]:
        containers = self.find_menu_containers(soup, base_url)
        return containers[0] if containers else None


class AdvancedSubmenuDetector:
    @staticmethod
    def find_submenu_in_li(li_element) -> Optional:
        if (direct_ul := li_element.find('ul', recursive=False)):
            return direct_ul
        
        for wrapper_tag in ['div', 'nav', 'section']:
            if (wrapper := li_element.find(wrapper_tag, recursive=False)) and (nested_ul := wrapper.find('ul')):
                return nested_ul
        
        for pattern in ['submenu', 'sub-menu', 'dropdown', 'mega-menu', 'dropdown-menu', 'sub-nav', 'children']:
            if submenu_container := li_element.find(class_=re.compile(pattern, re.I), recursive=False):
                if nested_ul := submenu_container.find('ul'):
                    return nested_ul
                if len(submenu_container.find_all('a', recursive=False)) > 0:
                    return submenu_container
        
        for ul in li_element.find_all('ul', limit=3):
            if ul.find_parent('li') == li_element:
                return ul
        
        for hidden in li_element.find_all(attrs={'aria-hidden': 'true'}, limit=3):
            if ul := hidden.find('ul'):
                return ul
        
        for div in li_element.find_all('div', recursive=False, limit=3):
            if len(div.find_all('a', limit=20)) >= 2:
                return div
        
        return None
    
    @staticmethod
    def extract_items_from_container(container, base_url: str, seen_urls: set, config: Config) -> List[Dict]:
        items = []
        
        if container.name == 'ul':
            for li in container.find_all('li', recursive=False):
                if link := li.find('a'):
                    text = link.get_text(strip=True)
                    url = normalize_url(link.get('href', ''), base_url)
                    if text and url and not is_noise_link(text, url, config) and url not in seen_urls:
                        seen_urls.add(url)
                        items.append({'text': text, 'url': url, 'element': li})
        elif container.name == 'div':
            for link in container.find_all('a', limit=50):
                text = link.get_text(strip=True)
                url = normalize_url(link.get('href', ''), base_url)
                if text and url and not is_noise_link(text, url, config) and url not in seen_urls:
                    seen_urls.add(url)
                    items.append({'text': text, 'url': url, 'element': link.parent})
        
        return items


class EnhancedHierarchyParser:
    def __init__(self, config: Config):
        self.config = config
        self.seen_urls = set()
        self.submenu_detector = AdvancedSubmenuDetector()
    
    def parse_menu_container(self, container, base_url: str) -> List[MenuItem]:
        self.seen_urls.clear()
        for strategy in [self._parse_nav_list, self._parse_nested_divs, self._parse_flat_links]:
            try:
                if items := strategy(container, base_url):
                    return items
            except:
                continue
        return []
    
    def _parse_nav_list(self, container, base_url: str) -> List[MenuItem]:
        top_ul = container.find('ul') or container.find(class_=re.compile(r'menu|nav|list', re.I))
        if not top_ul:
            return []
        
        top_lis = top_ul.find_all('li', recursive=False) or top_ul.find_all('li', limit=20)
        return [item for li in top_lis if (item := self._parse_list_item(li, base_url, 0))]
    
    def _parse_list_item(self, li_element, base_url: str, level: int) -> Optional[MenuItem]:
        if level >= self.config.MAX_MENU_DEPTH:
            return None
        
        link = li_element.find('a', recursive=False) or li_element.find('a')
        if not link:
            return None
        
        text = link.get_text(strip=True)
        url = normalize_url(link.get('href', ''), base_url)
        
        if not text or not url or is_noise_link(text, url, self.config) or url in self.seen_urls:
            return None
        
        self.seen_urls.add(url)
        item = MenuItem(text, url, level)
        
        if submenu_container := self.submenu_detector.find_submenu_in_li(li_element):
            if submenu_container.name == 'ul':
                for child_li in submenu_container.find_all('li', recursive=False):
                    if child_item := self._parse_list_item(child_li, base_url, level + 1):
                        item.add_child(child_item)
            elif submenu_container.name == 'div':
                for child_data in self.submenu_detector.extract_items_from_container(submenu_container, base_url, self.seen_urls, self.config):
                    child_item = MenuItem(child_data['text'], child_data['url'], level + 1)
                    item.add_child(child_item)
                    if child_data['element'] and (nested_container := self.submenu_detector.find_submenu_in_li(child_data['element'])):
                        for nested_data in self.submenu_detector.extract_items_from_container(nested_container, base_url, self.seen_urls, self.config)[:10]:
                            child_item.add_child(MenuItem(nested_data['text'], nested_data['url'], level + 2))
        
        return item
    
    def _parse_nested_divs(self, container, base_url: str) -> List[MenuItem]:
        potential_items = []
        for cls in ['menu-item', 'nav-item', 'item']:
            potential_items.extend(container.find_all(class_=re.compile(cls, re.I)))
        
        top_items = [item for item in potential_items if not (parent := item.find_parent(class_=re.compile('menu-item|nav-item', re.I))) or parent == item]
        return [item for div in top_items[:20] if (item := self._parse_div_item(div, base_url, 0))]
    
    def _parse_div_item(self, div_element, base_url: str, level: int) -> Optional[MenuItem]:
        if level >= self.config.MAX_MENU_DEPTH:
            return None
        
        link = div_element.find('a', recursive=False) or div_element.find('a')
        if not link:
            return None
        
        text = link.get_text(strip=True)
        url = normalize_url(link.get('href', ''), base_url)
        
        if not text or not url or is_noise_link(text, url, self.config) or url in self.seen_urls:
            return None
        
        self.seen_urls.add(url)
        item = MenuItem(text, url, level)
        
        for cls in ['submenu', 'dropdown', 'sub-menu', 'children']:
            if submenu := div_element.find(class_=re.compile(cls, re.I), recursive=False):
                for child_div in submenu.find_all(class_=re.compile('menu-item|nav-item', re.I), recursive=False):
                    if child_item := self._parse_div_item(child_div, base_url, level + 1):
                        item.add_child(child_item)
                break
        
        return item
    
    def _parse_flat_links(self, container, base_url: str) -> List[MenuItem]:
        items = []
        for link in container.find_all('a', limit=50):
            text = link.get_text(strip=True)
            url = normalize_url(link.get('href', ''), base_url)
            if text and url and not is_noise_link(text, url, self.config) and url not in self.seen_urls:
                self.seen_urls.add(url)
                items.append(MenuItem(text, url, 0))
        return items[:20]


class MenuScraper:
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.scorer = MenuPatternScorer()
        self.detector = MenuContainerDetector(self.scorer, self.config)
        self.parser = EnhancedHierarchyParser(self.config)
    
    def scrape(self, url: str, return_metadata: bool = True) -> Dict:
        start_time = time.time()
        result = {'success': False, 'url': url, 'menu': [], 'error': None}
        
        html, error = fetch_html(url, self.config.REQUEST_TIMEOUT, self.config)
        if not html:
            result['error'] = f"Failed to fetch URL: {error}"
            return result
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            result['error'] = f"Failed to parse HTML: {str(e)}"
            return result
        
        containers = self.detector.find_menu_containers(soup, url)
        if not containers:
            result['error'] = "No menu containers detected"
            return result
        
        menu_items = self.parser.parse_menu_container(containers[0]['element'], url)
        if not menu_items:
            result['error'] = "No menu items extracted from container"
            return result
        
        tree = MenuTree(menu_items)
        stats = tree.get_stats()
        
        result['success'] = True
        result['menu'] = [item.to_dict() for item in menu_items]
        result['error'] = None
        
        if return_metadata:
            result['metadata'] = {
                'scrape_time_seconds': round(time.time() - start_time, 3),
                'detection_score': containers[0]['score'],
                'detection_method': containers[0]['method'],
                'total_items': stats['total_items'],
                'top_level_items': stats['top_level_items'],
                'max_depth': stats['max_depth'],
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        return result
    
    def scrape_to_json(self, url: str, indent: int = 2) -> str:
        return json.dumps(self.scrape(url), indent=indent, ensure_ascii=False)