"""Menu Scraper Application - Run with: python app.py"""

import os
import json
from datetime import datetime
from menu_scraper import MenuScraper, Config
from demo_urls import DEMO_URLS


def sanitize_filename(url: str) -> str:
    """Convert URL to safe filename"""
    filename = url.replace('https://', '').replace('http://', '').rstrip('/')
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']:
        filename = filename.replace(char, '_')
    return filename


def save_to_json(result: dict, output_dir: str = "scraped_menus"):
    """Save scrape result to JSON file"""
    os.makedirs(output_dir, exist_ok=True)
    url = result.get('url', 'unknown')
    filename = sanitize_filename(url)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(output_dir, f"{filename}_{timestamp}.json")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return filepath


def print_summary(result: dict):
    """Print scrape result summary"""
    print(f"\nURL: {result['url']}")
    
    if result['success']:
        meta = result.get('metadata', {})
        print(f"SUCCESS - Items: {meta.get('total_items', 0)}, "
              f"Depth: {meta.get('max_depth', 0)}, "
              f"Time: {meta.get('scrape_time_seconds', 0)}s")
        
        menu = result.get('menu', [])
        if menu:
            print("Top items:")
            for i, item in enumerate(menu[:5], 1):
                children = len(item.get('children', []))
                child_info = f" ({children} children)" if children else ""
                print(f"  {i}. {item['text'][:50]}{child_info}")
            if len(menu) > 5:
                print(f"  ... and {len(menu) - 5} more")
    else:
        print(f"FAILED - {result.get('error', 'Unknown error')}")


def scrape_urls(scraper: MenuScraper, urls: list, output_dir: str = "scraped_menus"):
    """Scrape multiple URLs and save results"""
    print(f"\nScraping {len(urls)} URLs\n")
    
    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        result = scraper.scrape(url, return_metadata=True)
        print_summary(result)
        filepath = save_to_json(result, output_dir)
        print(f"Saved: {filepath}\n")
        results.append(result)
    
    successful = sum(1 for r in results if r['success'])
    print(f"\nCompleted: {successful}/{len(results)} successful")
    print(f"Results saved to: {output_dir}/")
    
    return results


def main():
    """Main entry point"""
    print("Universal Menu Scraper\n")
    
    config = Config()
    scraper = MenuScraper(config)
    output_dir = "scraped_menus"
    
    print(f"Testing {len(DEMO_URLS)} demo sites:")
    for i, url in enumerate(DEMO_URLS, 1):
        print(f"  {i}. {url}")
    
    input("\nPress Enter to start...")
    scrape_urls(scraper, DEMO_URLS, output_dir)
    
    print("\nDone! Check results in scraped_menus/")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()