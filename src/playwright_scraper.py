from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dataclasses import dataclass
import json
import time
import re
from typing import Optional, Dict
import logging

@dataclass
class Product:
    """Product data model"""
    id: Optional[int]
    name: str
    category: str
    url: str
    current_price: float
    last_checked: str

    # Additional extracted attributes
    product_id: Optional[str] = None  # SKU/Product ID from retailer
    brand: Optional[str] = None       # Brand name

class PlaywrightPriceScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
    def __enter__(self):
        # Context manager entry
        self.playwright = sync_playwright().start()

        # Advanced stealth settings to avoid detection
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-setuid-sandbox',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-infobars',
                '--window-size=1920,1080',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-client-side-phishing-detection',
                '--disable-component-extensions-with-background-pages',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-features=TranslateUI',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-renderer-backgrounding',
                '--disable-sync',
                '--metrics-recording-only',
                '--no-zygote',
                '--enable-features=NetworkService,NetworkServiceInProcess',
            ]
        )

        # Create context with realistic browser fingerprint
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='en-NZ',
            timezone_id='Pacific/Auckland',
            screen={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            has_touch=False,
            java_script_enabled=True,
            extra_http_headers={
                'Accept-Language': 'en-NZ,en-US;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        )

        # Inject scripts to hide automation
        self.context.add_init_script("""
            // Overwrite the `plugins` property to use a custom getter.
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Overwrite the `plugins` length property
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Overwrite the `languages` property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-NZ', 'en-US', 'en']
            });

            // Remove webdriver property from window.navigator
            delete Object.getPrototypeOf(navigator).webdriver;

            // Mock chrome runtime
            window.chrome = {
                runtime: {}
            };

            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        # Block unnecessary resources to speed up and reduce fingerprint
        self.context.route("**/*.{png,jpg,jpeg,gif,svg,mp4,mp3,webm,webp,woff,woff2,ttf}", lambda route: route.abort())

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

def scrape_pbtech(url, headless=True, return_product=False, context=None):
    """Scrape price from PBTech.co.nz"""
    def _scrape(ctx):
        page = ctx.new_page()
        try:
            print(f"Loading: {url}")
            page.goto(url, wait_until='domcontentloaded')
            page.wait_for_selector('.js-customer-price', timeout=10000)

            price_element = page.locator('.js-customer-price').first
            price_text = price_element.inner_text()
            print(f"Raw text: {price_text}")
            cleaned = price_text.replace('Excluding GST', '').replace('Including GST', '').replace('$', '').replace(',', '').strip()
            match = re.search(r'(\d+)\.?(\d{2})?', cleaned)

            if match:
                dollars = match.group(1)
                cents = match.group(2) or '00'
                price = float(f"{dollars}.{cents}")
                print(f"✅ Price: ${price:.2f}")

                if return_product:
                    # Extract product details
                    product_name = page.locator('h1').first.inner_text() if page.locator('h1').count() > 0 else "Unknown"

                    # Extract product code from URL (e.g., NBKLEN1482200)
                    product_id = None
                    url_match = re.search(r'/product/([A-Z0-9]+)/', url)
                    if url_match:
                        product_id = url_match.group(1)

                    return Product(
                        id=None,
                        name=product_name,
                        category="Unknown",
                        url=url,
                        current_price=price,
                        last_checked=time.strftime('%Y-%m-%d %H:%M:%S'),
                        product_id=product_id,
                        brand=None
                    )

                return price

        except Exception as e:
            print(f'❌ Error: {e}')
            return None
        finally:
            page.close()

    if context:
        return _scrape(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _scrape(scraper.context)

def scrape_acquire(url, headless=True, return_product=False, context=None):
    """Scrape price from Acquire.co.nz"""
    # Use a mutable container so the inner function can update the URL after redirects
    url_ref = [url]

    def _scrape(ctx):
        page = ctx.new_page()
        try:
            print(f"Loading: {url_ref[0]}")
            page.goto(url_ref[0], wait_until='domcontentloaded')
            # Capture the canonical URL after any redirects
            final_url = page.url
            if final_url and final_url != url_ref[0] and '/p/' in final_url:
                url_ref[0] = final_url
                print(f"  Resolved to: {url_ref[0]}")
            page.wait_for_selector('.price', timeout=10000)

            # Try to get price with GST first (usually what customers see)
            price_gst = page.locator('.price-actual.tax1').first
            price_text_gst = price_gst.inner_text()
            print(f"Raw GST Price: {price_text_gst}")

            # Parse the price
            cleaned = price_text_gst.replace('$', '').replace(',', '').strip()
            match = re.search(r'(\d+)\.?(\d{2})?', cleaned)

            price = None
            if match:
                dollars = match.group(1)
                cents = match.group(2) or '00'
                price = float(f"{dollars}.{cents}")
                print(f"✅ Price (inc GST): ${price:.2f}")
            else:
                # Fallback: try no GST price
                price_no_gst = page.locator('.price-actual.tax0').first
                price_text_no_gst = price_no_gst.inner_text()
                print(f"Raw No GST price: {price_text_no_gst}")

                cleaned = price_text_no_gst.replace('$', '').replace(',', '').strip()
                match = re.search(r'(\d+)\.?(\d{2})?', cleaned)

                if match:
                    dollars = match.group(1)
                    cents = match.group(2) or '00'
                    price = float(f"{dollars}.{cents}")
                    print(f"✅ Price (ex GST): ${price:.2f}")

            if price and return_product:
                # Extract product details
                product_name = page.locator('h1').first.inner_text() if page.locator('h1').count() > 0 else "Unknown"

                # Try to extract brand
                brand = None
                try:
                    if product_name:
                        brand_match = re.match(r'^([A-Za-z]+)', product_name)
                        if brand_match:
                            brand = brand_match.group(1)
                except:
                    pass

                return Product(
                    id=None,
                    name=product_name,
                    category="Unknown",
                    url=url_ref[0],
                    current_price=price,
                    last_checked=time.strftime('%Y-%m-%d %H:%M:%S'),
                    product_id=None,
                    brand=brand
                )

            return price

        except Exception as e:
            print(f"❌ Error: {e}")
            return None
        finally:
            page.close()

    if context:
        return _scrape(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _scrape(scraper.context)

def scrape_jbhifi(url, headless=True, return_product=False, context=None):
    """Scrape price from JB Hi-Fi using data-testid"""
    def _scrape(ctx):
        page = ctx.new_page()
        try:
            print(f"Loading: {url}")
            page.goto(url, wait_until='domcontentloaded')

            # Wait for price element with data-testid
            page.wait_for_selector('[data-testid="ticket-price"]', timeout=10000)

            # Get price element
            price_element = page.locator('[data-testid="ticket-price"]').first
            price_text = price_element.inner_text()
            print(f"Raw text: {price_text}")

            # Parse the price
            cleaned = price_text.replace('$', '').replace(',', '').strip()
            match = re.search(r'(\d+)\.?(\d{2})?', cleaned)

            if match:
                dollars = match.group(1)
                cents = match.group(2) or '00'
                price = float(f"{dollars}.{cents}")
                print(f"✅ Price: ${price:.2f}")

                if return_product:
                    # Extract product details
                    product_name = page.locator('h1').first.inner_text() if page.locator('h1').count() > 0 else "Unknown"

                    # Try to extract brand from page
                    brand = None
                    try:
                        # JB Hi-Fi often has brand in the product name
                        if product_name:
                            brand_match = re.match(r'^([A-Za-z]+)', product_name)
                            if brand_match:
                                brand = brand_match.group(1)
                    except:
                        pass

                    # Extract product ID/SKU
                    product_id = None
                    try:
                        page_text = page.inner_text('body')
                        # Try multiple patterns
                        patterns = [
                            r'Model[:\s]+([A-Z0-9-_]+)',
                            r'SKU[:\s]+([A-Z0-9-_]+)',
                            r'Product[:\s]?Code[:\s]+([A-Z0-9-_]+)',
                            r'Item[:\s]?Code[:\s]+([A-Z0-9-_]+)',
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, page_text, re.IGNORECASE)
                            if match:
                                product_id = match.group(1)
                                print(f"✓ Found model/SKU: {product_id}")
                                break
                    except Exception as e:
                        print(f"✗ Could not extract model: {e}")

                    return Product(
                        id=None,
                        name=product_name,
                        category="Unknown",
                        url=url,
                        current_price=price,
                        last_checked=time.strftime('%Y-%m-%d %H:%M:%S'),
                        product_id=product_id,
                        brand=brand
                    )

                return price

        except Exception as e:
            print(f"❌ Error: {e}")
            return None
        finally:
            page.close()

    if context:
        return _scrape(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _scrape(scraper.context)

# ============================================================================
# SEARCH FUNCTIONS - Find products across retailers
# ============================================================================

def search_pricespy(query, retailer_domains, headless=True, context=None):
    """
    Search PriceSpy NZ and extract product URLs for specific retailers

    Args:
        query: Product search query
        retailer_domains: Dict mapping retailer names to their domains
        context: Optional shared browser context

    Returns:
        Dict of {retailer_name: product_url}
    """
    def _search(ctx):
        page = ctx.new_page()
        results = {}

        try:
            print(f"\n{'='*60}")
            print(f"🔍 Searching PriceSpy NZ for: {query}")
            print(f"{'='*60}")

            # PriceSpy NZ search URL
            search_url = f"https://pricespy.co.nz/search?search={query.replace(' ', '+')}"
            page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            try:
                page.wait_for_selector('a[href*="product.php"]', timeout=10000)
            except Exception:
                pass

            # Click on first product result to see all retailer offers
            product_links = page.locator('a[href*="product.php"]').all()

            if not product_links:
                print("❌ No products found on PriceSpy")
                return results

            # Click first product
            first_product_url = product_links[0].get_attribute('href')
            if not first_product_url.startswith('http'):
                first_product_url = f"https://pricespy.co.nz{first_product_url}"

            print(f"📍 Opening product page: {first_product_url}")
            page.goto(first_product_url, wait_until='domcontentloaded', timeout=30000)
            try:
                page.wait_for_selector('a[href*="/click/"]', timeout=10000)
            except Exception:
                pass

            # Now extract retailer links from the offers section
            print(f"\n🏪 Looking for retailer offers...")

            # PriceSpy shows retailer offers with "Go to store" buttons
            offer_links = page.locator('a[href*="/click/"]').all()

            for retailer_name, domain in retailer_domains.items():
                print(f"\n  Searching for {retailer_name}...")

                for link in offer_links:
                    try:
                        # Check if the link or nearby text contains retailer name
                        parent = link.locator('xpath=../..')  # Go up to parent container
                        text_content = parent.inner_text().lower()

                        retailer_match = (
                            domain.split('.')[0] in text_content or
                            retailer_name.lower() in text_content
                        )

                        if retailer_match:
                            # Get the actual retailer URL by following the redirect
                            click_url = link.get_attribute('href')
                            if not click_url.startswith('http'):
                                click_url = f"https://pricespy.co.nz{click_url}"

                            # Open in new page to get final URL
                            new_page = ctx.new_page()
                            try:
                                print(f"    Following link...")
                                new_page.goto(click_url, wait_until='domcontentloaded', timeout=15000)
                                final_url = new_page.url

                                # Verify it's the correct retailer and a product page
                                if domain in final_url and any(path in final_url for path in ['/product/', '/p/', '/products/']):
                                    print(f"    ✅ Found: {final_url[:70]}...")
                                    results[retailer_name] = final_url
                                    new_page.close()
                                    break
                            except Exception as e:
                                print(f"    ⚠️  Failed to follow link: {e}")
                            finally:
                                if not new_page.is_closed():
                                    new_page.close()

                    except Exception as e:
                        continue

                if retailer_name not in results:
                    print(f"    ❌ Not found")

            print(f"\n{'='*60}")
            print(f"✅ Found {len(results)} retailer(s): {', '.join(results.keys())}")
            print(f"{'='*60}\n")

            return results

        except Exception as e:
            print(f"❌ PriceSpy search failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            page.close()

        return results

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)


def _normalize_date(date_val):
    """Normalize various date formats to YYYY-MM-DD string"""
    from datetime import datetime as dt

    if isinstance(date_val, (int, float)):
        # Unix timestamp - could be seconds or milliseconds
        ts = date_val
        if ts > 1e12:  # milliseconds
            ts = ts / 1000
        try:
            return dt.fromtimestamp(ts).strftime('%Y-%m-%d')
        except (ValueError, OSError):
            return None

    if isinstance(date_val, str):
        # ISO format: 2024-01-15T00:00:00Z
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d',
                     '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S.%f',
                     '%Y-%m-%dT%H:%M:%S.%fZ']:
            try:
                return dt.strptime(date_val.strip(), fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        # Try unix timestamp as string
        try:
            return _normalize_date(float(date_val))
        except ValueError:
            pass

    return None


def _normalize_price_points(points):
    """Convert various price point formats to standard [{'date': 'YYYY-MM-DD', 'price': float}]"""
    normalized = []

    for point in points:
        date_str = None
        price = None

        if isinstance(point, dict):
            # {date: ..., price: ...} or {x: ..., y: ...} or {timestamp: ..., value: ...}
            for date_key in ['date', 'x', 'timestamp', 'time', 't', 'created', 'day']:
                if date_key in point:
                    date_str = _normalize_date(point[date_key])
                    if date_str:
                        break
            for price_key in ['price', 'y', 'value', 'v', 'min', 'lowest', 'amount']:
                if price_key in point and point[price_key] is not None:
                    try:
                        price = float(point[price_key])
                        if price > 0:
                            break
                    except (ValueError, TypeError):
                        continue

        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            # [timestamp, price] or [date_str, price]
            date_str = _normalize_date(point[0])
            try:
                price = float(point[1])
            except (ValueError, TypeError):
                pass

        if date_str and price and price > 0:
            normalized.append({'date': date_str, 'price': price})

    return normalized


def _deep_search_prices(obj, depth=0):
    """Recursively search nested JSON for price history arrays"""
    if depth > 8:
        return []

    price_keys = ['priceHistory', 'price_history', 'chartData', 'chart_data',
                  'series', 'data', 'points', 'prices', 'history',
                  'priceData', 'price_data', 'datasets', 'values',
                  'graphData', 'graph_data', 'statistics', 'stats',
                  'lowestPrices', 'lowest_prices', 'pricePoints']

    if isinstance(obj, dict):
        for key in price_keys:
            if key in obj:
                val = obj[key]
                if isinstance(val, list) and len(val) >= 3:
                    normalized = _normalize_price_points(val)
                    if len(normalized) >= 3:
                        return normalized
                elif isinstance(val, dict):
                    result = _deep_search_prices(val, depth + 1)
                    if result:
                        return result

        # Search all dict values
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                result = _deep_search_prices(val, depth + 1)
                if result:
                    return result

    elif isinstance(obj, list):
        # Check if this list itself is price points
        if len(obj) >= 3:
            normalized = _normalize_price_points(obj)
            if len(normalized) >= 3:
                return normalized
        # Search list items
        for item in obj:
            if isinstance(item, (dict, list)):
                result = _deep_search_prices(item, depth + 1)
                if result:
                    return result

    return []


def _extract_from_page_scripts(page):
    """Extract price data from page JavaScript variables"""
    scripts_to_check = [
        'window.__NEXT_DATA__',
        'window.INITIAL_STATE',
        'window.__INITIAL_STATE__',
        'window.__data',
        'window.__PRELOADED_STATE__',
    ]

    for script_var in scripts_to_check:
        try:
            data = page.evaluate(f'''() => {{
                try {{ return {script_var}; }} catch(e) {{ return null; }}
            }}''')
            if data:
                result = _deep_search_prices(data)
                if result:
                    return result
        except Exception:
            continue

    return []


def _parse_pricespy_api_response(responses):
    """Iterate captured API responses and extract price arrays"""
    for response_data in responses:
        try:
            if isinstance(response_data, dict):
                result = _deep_search_prices(response_data)
                if result:
                    return result
            elif isinstance(response_data, list):
                normalized = _normalize_price_points(response_data)
                if len(normalized) >= 3:
                    return normalized
                result = _deep_search_prices(response_data)
                if result:
                    return result
        except Exception:
            continue
    return []


def search_pricespy_product(query, headless=True, context=None):
    """
    Search PriceSpy NZ and return the PriceSpy product page URL itself

    Unlike search_pricespy() which follows retailer redirect links,
    this returns the PriceSpy product page URL (e.g. https://pricespy.co.nz/product.php?p=12345)
    for use with scrape_pricespy_history().

    Args:
        query: Product search query
        context: Optional shared browser context

    Returns:
        PriceSpy product page URL string, or None if not found
    """
    def _search(ctx):
        page = ctx.new_page()
        try:
            print(f"\n{'='*60}")
            print(f"🔍 Searching PriceSpy NZ for product page: {query}")
            print(f"{'='*60}")

            search_url = f"https://pricespy.co.nz/search?search={query.replace(' ', '+')}"
            page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            try:
                page.wait_for_selector('a[href*="product.php"]', timeout=10000)
            except Exception:
                pass

            product_links = page.locator('a[href*="product.php"]').all()

            if not product_links:
                print("❌ No products found on PriceSpy")
                return None

            first_product_url = product_links[0].get_attribute('href')
            if not first_product_url.startswith('http'):
                first_product_url = f"https://pricespy.co.nz{first_product_url}"

            print(f"✅ Found PriceSpy product page: {first_product_url}")
            return first_product_url

        except Exception as e:
            print(f"❌ PriceSpy product search failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            page.close()

        return None

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)


def scrape_pricespy_history(url, headless=True):
    """
    Navigate to a PriceSpy product page and extract price history data

    Uses three strategies in order:
    1. Network interception - capture JSON API responses containing price/history data
    2. Page script extraction - check window.__NEXT_DATA__, INITIAL_STATE etc.
    3. Deep search - recursively search captured JSON for price point arrays

    NOTE: Always creates its own scraper because it calls context.unroute()
    which would affect other pages if sharing a context.

    Args:
        url: PriceSpy product page URL (e.g. https://pricespy.co.nz/product.php?p=12345)
        headless: Run browser in headless mode

    Returns:
        List of {'date': 'YYYY-MM-DD', 'price': float} sorted ascending, or []
    """
    with PlaywrightPriceScraper(headless=headless) as scraper:
        # Don't block images on PriceSpy - the chart may need them
        scraper.context.unroute("**/*.{png,jpg,jpeg,gif,svg,mp4,mp3,webm,webp,woff,woff2,ttf}")
        page = scraper.context.new_page()

        captured_responses = []

        def handle_response(response):
            """Capture JSON responses that may contain price history"""
            try:
                content_type = response.headers.get('content-type', '')
                url_lower = response.url.lower()

                # Capture all JSON responses from PriceSpy's BFF API and any other JSON endpoints
                is_bff = '_internal/bff' in url_lower
                is_json = 'json' in content_type
                is_pricespy = 'pricespy.co.nz' in url_lower

                if response.status == 200 and (is_bff or (is_json and is_pricespy)):
                    try:
                        data = response.json()
                        captured_responses.append(data)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on('response', handle_response)

        try:
            print(f"\n{'='*60}")
            print(f"📊 Scraping PriceSpy price history: {url}")
            print(f"{'='*60}")

            # Navigate directly to the statistics section
            stats_url = url if '#statistics' in url else f"{url}#statistics"
            page.goto(stats_url, wait_until='domcontentloaded', timeout=30000)
            try:
                page.wait_for_load_state('networkidle', timeout=15000)
            except Exception:
                pass

            # Dismiss cookie consent dialog if present (blocks clicks on PriceSpy)
            try:
                consent_frame = page.frame_locator('iframe[id*="sp_message"]')
                accept_btn = consent_frame.locator('button[title*="Accept"], button:has-text("Accept"), button:has-text("OK"), button:has-text("Agree")')
                if accept_btn.count() > 0:
                    accept_btn.first.click(timeout=3000)
                    page.wait_for_timeout(1000)
                    print("  Dismissed cookie consent dialog")
            except Exception:
                pass

            # Try clicking on price history / statistics tab to trigger data load
            # a[href*="statistics"] and a:has-text("Price history") confirmed on PriceSpy
            for tab_selector in [
                'a[href*="statistics"]',
                'a:has-text("Price history")',
                'a:has-text("Statistics")',
                'a[href*="history"]',
            ]:
                try:
                    tab = page.locator(tab_selector).first
                    if tab.is_visible(timeout=1000):
                        tab.click(timeout=5000)
                        try:
                            page.wait_for_load_state('networkidle', timeout=15000)
                        except Exception:
                            pass
                        print(f"  📈 Clicked tab: {tab_selector}")
                        break
                except Exception:
                    continue

            print(f"  Captured {len(captured_responses)} API responses")

            # Strategy 1: Parse captured API responses
            if captured_responses:
                print("  Strategy 1: Parsing captured API responses...")
                history = _parse_pricespy_api_response(captured_responses)
                if history:
                    history.sort(key=lambda x: x['date'])
                    print(f"  ✅ Found {len(history)} price points from API responses")
                    return history

            # Strategy 2: Extract from page scripts
            print("  Strategy 2: Checking page scripts...")
            history = _extract_from_page_scripts(page)
            if history:
                history.sort(key=lambda x: x['date'])
                print(f"  ✅ Found {len(history)} price points from page scripts")
                return history

            # Strategy 3: Deep search all captured data
            if captured_responses:
                print("  Strategy 3: Deep searching all captured data...")
                for resp in captured_responses:
                    history = _deep_search_prices(resp)
                    if history:
                        history.sort(key=lambda x: x['date'])
                        print(f"  ✅ Found {len(history)} price points from deep search")
                        return history

            print("  ❌ No price history data found")
            return []

        except Exception as e:
            print(f"❌ PriceSpy history scrape failed: {e}")
            import traceback
            traceback.print_exc()

    return []


def search_via_pricespy(query, headless=True, context=None):
    """
    Two-stage search: Use PriceSpy to find retailers, then scrape each retailer's page

    This is more reliable because:
    1. PriceSpy aggregates all NZ retailers in one search
    2. We get accurate product data directly from each retailer
    3. Model numbers are extracted from the actual product pages

    Args:
        query: Product search term
        headless: Run browser in headless mode
        context: Optional shared browser context

    Returns:
        List of dicts: [{'retailer': ..., 'url': ..., 'product': Product}, ...]
    """
    def _run(ctx):
        print(f"\n{'='*60}")
        print(f"🔍 TWO-STAGE SEARCH: {query}")
        print(f"{'='*60}\n")

        # Stage 1: Search PriceSpy to find which retailers have the product
        print("📍 STAGE 1: Searching PriceSpy NZ to find retailers...")

        retailer_domains = {
            'PBTech': 'pbtech.co.nz',
            'Noel Leeming': 'noelleeming.co.nz',
            'JB Hi-Fi': 'jbhifi.co.nz',
            'Acquire': 'acquire.co.nz',
        }

        retailer_urls = search_pricespy(query, retailer_domains, headless=headless, context=ctx)

        if not retailer_urls:
            print("\n❌ No retailers found on PriceSpy")
            return []

        print(f"\n✅ PriceSpy found product at {len(retailer_urls)} retailers")

        # Check if any retailers are missing and search them directly
        missing_retailers = [name for name in retailer_domains.keys() if name not in retailer_urls]

        if missing_retailers:
            print(f"\n⚠️  Missing from PriceSpy: {', '.join(missing_retailers)}")
            print(f"📍 Searching missing retailers directly...\n")

            direct_search_map = {
                'PBTech': search_pbtech,
                'Noel Leeming': search_noelleeming,
                'JB Hi-Fi': search_jbhifi,
                'Acquire': search_acquire,
            }

            def _search_missing(retailer):
                search_func = direct_search_map.get(retailer)
                if not search_func:
                    return retailer, None
                try:
                    print(f"\n  {'='*50}")
                    print(f"  Direct search: {retailer}")
                    print(f"  Query: {query}")
                    print(f"  {'='*50}")
                    found_url = search_func(query, headless=headless, return_all=False, context=ctx)
                    if found_url:
                        if isinstance(found_url, list):
                            found_url = found_url[0] if found_url else None
                        if found_url:
                            print(f"  ✅ Found at {retailer}: {found_url[:80]}...")
                            return retailer, found_url
                        else:
                            print(f"  ❌ Not found at {retailer} (empty result)")
                    else:
                        print(f"  ❌ Not found at {retailer} (None returned)")
                except Exception as e:
                    print(f"  ❌ {retailer} search failed: {e}")
                    import traceback
                    traceback.print_exc()
                return retailer, None

            for r in missing_retailers:
                retailer, found_url = _search_missing(r)
                if found_url:
                    retailer_urls[retailer] = found_url

        print(f"\n✅ Total: Found product at {len(retailer_urls)} retailers")
        print(f"📍 STAGE 2: Scraping each retailer's product page...\n")

        # Stage 2: Scrape each retailer's product page (in parallel)
        results = []
        scraper_map = {
            'PBTech': scrape_pbtech,
            'Noel Leeming': scrape_noelleeming,
            'JB Hi-Fi': scrape_jbhifi,
            'Acquire': scrape_acquire,
        }

        def _scrape_retailer(retailer_name, retailer_url):
            print(f"\n{'='*60}")
            print(f"Scraping {retailer_name}...")
            print(f"{'='*60}")

            scraper_func = scraper_map.get(retailer_name)
            if not scraper_func:
                print(f"⚠️  No scraper available for {retailer_name}")
                return None

            try:
                product = scraper_func(retailer_url, headless=headless, return_product=True, context=ctx)

                if product:
                    print(f"\n✅ {retailer_name} - {product.name[:60]}")
                    print(f"   Price: ${product.current_price:.2f}")
                    if product.product_id:
                        print(f"   Model: {product.product_id}")
                    if product.brand:
                        print(f"   Brand: {product.brand}")

                    return {
                        'retailer': retailer_name,
                        'url': retailer_url,
                        'product': product
                    }
                else:
                    print(f"❌ Failed to scrape {retailer_name}")

            except Exception as e:
                print(f"❌ Error scraping {retailer_name}: {e}")
                import traceback
                traceback.print_exc()

            return None

        for name, url in retailer_urls.items():
            result = _scrape_retailer(name, url)
            if result:
                results.append(result)

        print(f"\n{'='*60}")
        print(f"✅ COMPLETED: Successfully scraped {len(results)}/{len(retailer_urls)} retailers")
        print(f"{'='*60}\n")

        return results

    if context:
        return _run(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _run(scraper.context)


def search_google_shopping(query, retailer_domains, headless=True, context=None):
    """
    Search Google Shopping and extract product URLs for specific retailers

    Args:
        query: Product search query
        retailer_domains: Dict mapping retailer names to their domains
                         e.g., {'PBTech': 'pbtech.co.nz', 'Noel Leeming': 'noelleeming.co.nz'}
        context: Optional shared browser context

    Returns:
        Dict of {retailer_name: product_url}
    """
    def _search(ctx):
        page = ctx.new_page()
        results = {}

        try:
            print(f"\n{'='*60}")
            print(f"🔍 Searching Google Shopping for: {query}")
            print(f"{'='*60}")

            # Use regular Google search (less restrictive than Shopping)
            # Add "buy" to get shopping results
            search_query = f"buy {query} nz"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                pass

            # Check if we hit a CAPTCHA
            if 'sorry' in page.url or 'unusual traffic' in page.content().lower():
                print("⚠️  Google bot detection triggered")
                return results

            # For each retailer, look for their products in results
            for retailer_name, domain in retailer_domains.items():
                print(f"\n🏪 Looking for {retailer_name} ({domain})...")

                try:
                    # Find product links that contain the retailer's domain
                    # Regular Google search has different structures
                    link_selectors = [
                        f'a[href*="{domain}"]',
                        f'a[href*="{domain.split(".")[0]}"]',  # Match just the name part
                    ]

                    for selector in link_selectors:
                        links = page.locator(selector).all()

                        if links:
                            print(f"  Found {len(links)} potential links")

                            for link in links[:3]:  # Check first 3 matches
                                href = link.get_attribute('href')

                                if not href:
                                    continue

                                # Google Shopping links are often redirects
                                # Click the link and get the final URL
                                if domain in href:
                                    # Direct link to retailer
                                    product_url = href

                                    # Clean up Google tracking parameters
                                    if '?' in product_url:
                                        # Keep only the base URL and essential params
                                        product_url = product_url.split('&')[0]

                                    # Verify it's a product page
                                    if '/product/' in product_url or '/p/' in product_url or '/products/' in product_url:
                                        print(f"  ✅ Found: {product_url[:80]}...")
                                        results[retailer_name] = product_url
                                        break

                                elif 'google.com' in href and domain in link.inner_text():
                                    # Google redirect link - need to click through
                                    print(f"  📍 Clicking through Google redirect...")

                                    # Open in new page to get final URL
                                    new_page = ctx.new_page()
                                    try:
                                        new_page.goto(href, wait_until='domcontentloaded', timeout=15000)
                                        final_url = new_page.url

                                        if domain in final_url and ('/product/' in final_url or '/p/' in final_url or '/products/' in final_url):
                                            print(f"  ✅ Redirected to: {final_url[:80]}...")
                                            results[retailer_name] = final_url
                                            new_page.close()
                                            break
                                    except Exception as e:
                                        print(f"  ⚠️  Redirect failed: {e}")
                                    finally:
                                        if not new_page.is_closed():
                                            new_page.close()

                            if retailer_name in results:
                                break  # Found for this retailer, move to next

                    if retailer_name not in results:
                        print(f"  ❌ Not found on {retailer_name}")

                except Exception as e:
                    print(f"  ❌ Error searching {retailer_name}: {e}")

            print(f"\n{'='*60}")
            print(f"✅ Found {len(results)} retailer(s): {', '.join(results.keys())}")
            print(f"{'='*60}\n")

            return results

        except Exception as e:
            print(f"❌ Google Shopping search failed: {e}")
            return results
        finally:
            if not page.is_closed():
                page.close()

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)

def search_pbtech(query, headless=True, return_all=False, context=None):
    """
    Search PBTech and return matching product URLs

    Args:
        query: Search term
        headless: Run browser in headless mode
        return_all: If True, return list of all matches; if False, return first match
        context: Optional shared browser context

    Returns:
        List of URLs if return_all=True, single URL if return_all=False
    """
    MAX_RESULTS = 5

    def _search(ctx):
        page = ctx.new_page()
        try:
            print(f"Searching PBTech for: {query}")
            search_url = f"https://www.pbtech.co.nz/search?sf={query.replace(' ', '+')}&search_type="

            page.goto(search_url, wait_until='load', timeout=40000)
            try:
                page.wait_for_selector('a[href*="/product/"]', timeout=15000)
            except Exception:
                pass

            content = page.content()

            # Extract all product URLs from the search results page
            # PBTech URLs follow pattern: /product/CODE/Product-Name
            raw_urls = re.findall(r'href="(/product/[A-Z][A-Z0-9]+/[^"]+)"', content)

            if not raw_urls:
                # Fallback: try without leading slash
                raw_urls = re.findall(r'href="(product/[A-Z][A-Z0-9]+/[^"]+)"', content)

            if raw_urls:
                # Deduplicate while preserving order
                seen = set()
                found_urls = []
                for url_path in raw_urls:
                    clean = url_path.split('?')[0]
                    if clean not in seen:
                        seen.add(clean)
                        if clean.startswith('/'):
                            found_urls.append(f"https://www.pbtech.co.nz{clean}")
                        else:
                            found_urls.append(f"https://www.pbtech.co.nz/{clean}")

                print(f"  Found {len(found_urls)} unique products")

                if found_urls:
                    if return_all:
                        result = found_urls[:MAX_RESULTS]
                        print(f"✓ Returning {len(result)} products")
                        return result
                    else:
                        print(f"✓ Found: {found_urls[0]}")
                        return found_urls[0]

            print("✗ No results found")
        except Exception as e:
            print(f"✗ Error: {e}")
        finally:
            page.close()

        return [] if return_all else None

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)


def search_noelleeming(query, headless=True, return_all=False, context=None):
    """
    Search Noel Leeming and return matching product URLs

    Args:
        query: Search term
        headless: Run browser in headless mode
        return_all: If True, return list of all matches; if False, return first match
        context: Optional shared browser context

    Returns:
        List of URLs if return_all=True, single URL if return_all=False
    """
    MAX_RESULTS = 5

    def _search(ctx):
        page = ctx.new_page()
        try:
            print(f"Searching Noel Leeming for: {query}")
            search_url = f"https://www.noelleeming.co.nz/search?q={query.replace(' ', '+')}"
            page.goto(search_url, wait_until='load', timeout=40000)
            try:
                page.wait_for_selector('a[href*="/p/"]', timeout=15000)
            except Exception:
                pass

            content = page.content()
            product_urls = re.findall(r'href="(/p/[^"]+)"', content)

            if not product_urls:
                product_urls = re.findall(r'href="(https://www\.noelleeming\.co\.nz/p/[^"]+)"', content)

            if product_urls:
                print(f"  Found {len(product_urls)} product links")
                found_urls = []
                seen = set()

                for url in product_urls:
                    clean = url.split('?')[0]
                    if clean not in seen:
                        seen.add(clean)
                        if not clean.startswith('http'):
                            found_urls.append(f"https://www.noelleeming.co.nz{clean}")
                        else:
                            found_urls.append(clean)

                    if not return_all and len(found_urls) >= 1:
                        break
                    if return_all and len(found_urls) >= MAX_RESULTS:
                        break

                if found_urls:
                    if return_all:
                        print(f"✓ Found {len(found_urls)} products")
                        return found_urls
                    else:
                        print(f"✓ Found: {found_urls[0]}")
                        return found_urls[0]

            print("✗ No results found")
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            page.close()

        return [] if return_all else None

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)


def search_jbhifi(query, headless=True, return_all=False, context=None):
    """
    Search JB Hi-Fi and return matching product URLs

    Args:
        query: Search term
        headless: Run browser in headless mode
        return_all: If True, return list of all matches; if False, return first match
        context: Optional shared browser context

    Returns:
        List of URLs if return_all=True, single URL if return_all=False
    """
    MAX_RESULTS = 5

    def _search(ctx):
        page = ctx.new_page()
        try:
            print(f"Searching JB Hi-Fi for: {query}")
            search_url = f"https://www.jbhifi.co.nz/search?query={query.replace(' ', '+')}"
            page.goto(search_url, wait_until='load', timeout=40000)
            try:
                page.wait_for_selector('a[href*="/products/"]', timeout=15000)
            except Exception:
                pass

            content = page.content()
            product_urls = re.findall(r'href="(/products/[^"]+)"', content)

            if not product_urls:
                product_urls = re.findall(r'href="(https://www\.jbhifi\.co\.nz/products/[^"]+)"', content)

            if product_urls:
                print(f"  Found {len(product_urls)} product links")
                found_urls = []
                seen = set()

                for url in product_urls:
                    clean = url.split('?')[0]
                    if clean not in seen:
                        seen.add(clean)
                        if not clean.startswith('http'):
                            found_urls.append(f"https://www.jbhifi.co.nz{clean}")
                        else:
                            found_urls.append(clean)

                    if not return_all and len(found_urls) >= 1:
                        break
                    if return_all and len(found_urls) >= MAX_RESULTS:
                        break

                if found_urls:
                    if return_all:
                        print(f"✓ Found {len(found_urls)} products")
                        return found_urls
                    else:
                        print(f"✓ Found: {found_urls[0]}")
                        return found_urls[0]

            print("✗ No results found")
        except Exception as e:
            print(f"✗ Error: {e}")
        finally:
            page.close()

        return [] if return_all else None

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)


def search_acquire(query, headless=True, return_all=False, context=None):
    """
    Search Acquire and return matching product URLs

    Args:
        query: Search term
        headless: Run browser in headless mode
        return_all: If True, return list of all matches; if False, return first match
        context: Optional shared browser context

    Returns:
        List of URLs if return_all=True, single URL if return_all=False
    """
    MAX_RESULTS = 5

    def _search(ctx):
        page = ctx.new_page()
        try:
            print(f"Searching Acquire for: {query}")
            search_url = f"https://acquire.co.nz/p/?q={query.replace(' ', '+')}"
            page.goto(search_url, wait_until='load', timeout=40000)
            try:
                page.wait_for_selector('article a[href*="av="]', timeout=15000)
            except Exception:
                pass

            # Acquire uses article links with /p/?av=ID format
            # Find product links in article tags
            product_links = page.locator('article a[href*="av="]').all()

            if product_links:
                print(f"  Found {len(product_links)} products")
                found_urls = []
                max_products = min(MAX_RESULTS if return_all else 1, len(product_links))

                for i, link in enumerate(product_links[:max_products]):
                    try:
                        product_text = link.inner_text()[:50]
                        print(f"  Checking ({i+1}/{max_products}): {product_text}")

                        # Get the link href
                        href = link.get_attribute('href')
                        if href:
                            if not href.startswith('http'):
                                if href.startswith('/'):
                                    product_url = f"https://acquire.co.nz{href}"
                                else:
                                    product_url = f"https://acquire.co.nz/{href}"
                            else:
                                product_url = href

                            if return_all:
                                # Navigate to resolve av= URLs to canonical product pages
                                try:
                                    page.goto(product_url, wait_until='load', timeout=15000)
                                    final_url = page.url
                                    if '/p/' in final_url and 'av=' not in final_url:
                                        found_urls.append(final_url)
                                    else:
                                        found_urls.append(product_url)
                                except Exception:
                                    found_urls.append(product_url)
                            else:
                                # For single result, navigate to get canonical URL
                                try:
                                    page.goto(product_url, wait_until='load', timeout=15000)
                                    final_url = page.url

                                    # The final URL should be the full product URL
                                    if '/p/' in final_url and 'av=' not in final_url:
                                        print(f"✓ Found: {final_url}")
                                        return final_url
                                    else:
                                        # Use the av= URL as fallback
                                        print(f"✓ Found: {product_url}")
                                        return product_url
                                except Exception as e:
                                    print(f"  ⚠️  Could not navigate to product page: {e}")
                                    print(f"✓ Using: {product_url}")
                                    return product_url
                    except Exception as e:
                        print(f"  ⚠️  Error processing link {i+1}: {e}")
                        continue

                if found_urls:
                    print(f"✓ Found {len(found_urls)} products")
                    return found_urls

            print("✗ No results found")
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            page.close()

        return [] if return_all else None

    if context:
        return _search(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _search(scraper.context)


# ============================================================================
# SCRAPER FUNCTIONS
# ============================================================================

def scrape_noelleeming(url, headless=True, return_product=False, context=None):
    """
    Scrape price from Noel Leeming - tries data-price first, then class selectors

    Args:
        url: Product URL
        headless: Run in headless mode
        return_product: If True, returns Product object; if False, returns just price float
        context: Optional shared browser context

    Returns:
        Product object or float price
    """
    def _scrape(ctx):
        page = ctx.new_page()
        try:
            print(f"Loading: {url}")
            page.goto(url, wait_until='domcontentloaded')

            price = None
            product_name = None
            product_id = None
            brand = None

            # Extract price
            print("Trying data-price attribute...")
            if page.locator('[data-price]').count() > 0:
                price_value = page.locator('[data-price]').first.get_attribute('data-price')
                print(f"Found data-price: {price_value}")

                # Clean the price (remove $, commas, etc.)
                cleaned = price_value.replace('$', '').replace(',', '').strip()
                price = float(cleaned)
                print(f"✅ Price (from data-price): ${price:.2f}")

            if price is None:
                print("Trying class selectors...")
                page.wait_for_selector('.price.sale', timeout=10000)

                # Get dollars
                dollars_element = page.locator('.price_dollars').first
                dollars = dollars_element.inner_text().strip()
                print(f"Dollars: {dollars}")

                # Get cents
                cents_element = page.locator('.price_cents').first
                cents = cents_element.inner_text().strip()
                print(f"Cents: {cents}")

                # Combine and convert
                price = float(f"{dollars}.{cents}")
                print(f"✅ Price (from classes): ${price:.2f}")

            # Extract additional attributes if requested
            if return_product:
                # Product name - usually in h1 or title
                if page.locator('h1').count() > 0:
                    product_name = page.locator('h1').first.inner_text().strip()
                    print(f"📦 Name: {product_name}")

                # Product ID (Model number) - try multiple sources
                # 1. Look for "Model:" or "SKU:" text on page
                try:
                    page_text = page.inner_text('body')

                    # Try multiple patterns for model/SKU
                    patterns = [
                        r'Model[:\s]+([A-Z0-9-_]+)',  # Model: ABC123
                        r'SKU[:\s]+([A-Z0-9-_]+)',     # SKU: ABC123
                        r'Part[:\s]?#[:\s]+([A-Z0-9-_]+)',  # Part# ABC123
                        r'Model\s+Code[:\s]+([A-Z0-9-_]+)',  # Model Code: ABC123
                        r'Product[:\s]?Code[:\s]+([A-Z0-9-_]+)',  # Product Code: ABC123
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, page_text, re.IGNORECASE)
                        if match:
                            product_id = match.group(1)
                            print(f"✓ Found model/SKU: {product_id} (pattern: {pattern[:20]})")
                            break

                    if not product_id:
                        print("✗ No model/SKU pattern matched")
                except Exception as e:
                    print(f"✗ Error finding Model: {e}")
                    pass

                # 2. Try data-model or data-sku attribute
                if not product_id and page.locator('[data-model]').count() > 0:
                    product_id = page.locator('[data-model]').first.get_attribute('data-model')

                # 3. Try data-sku attribute
                if not product_id and page.locator('[data-sku]').count() > 0:
                    product_id = page.locator('[data-sku]').first.get_attribute('data-sku')

                # 4. Try JSON-LD for sku/mpn
                if not product_id:
                    try:
                        jsonld_scripts = page.locator('script[type="application/ld+json"]').all()
                        for script in jsonld_scripts:
                            content = script.inner_text()
                            data = json.loads(content)
                            if isinstance(data, dict):
                                data = [data]
                            for item in data:
                                if item.get('@type') == 'Product':
                                    product_id = item.get('sku') or item.get('mpn')
                                    if product_id:
                                        break
                    except:
                        pass

                # 5. Extract from URL as last resort
                if not product_id:
                    match = re.search(r'/([^/]+)\.html', url)
                    if match:
                        product_id = match.group(1)

                if product_id:
                    print(f"🔢 Model/SKU: {product_id}")

                # Brand - try JSON-LD first
                try:
                    jsonld_scripts = page.locator('script[type="application/ld+json"]').all()
                    for script in jsonld_scripts:
                        content = script.inner_text()
                        data = json.loads(content)

                        if isinstance(data, dict):
                            data = [data]

                        for item in data:
                            if item.get('@type') == 'Product' and 'brand' in item:
                                if isinstance(item['brand'], dict):
                                    brand = item['brand'].get('name')
                                else:
                                    brand = item['brand']
                                break
                except:
                    pass

                # Fallback: look for brand in meta tags
                if not brand and page.locator('meta[property="product:brand"]').count() > 0:
                    brand = page.locator('meta[property="product:brand"]').first.get_attribute('content')

                if brand:
                    print(f"🏷️  Brand: {brand}")

                # Return Product object
                return Product(
                    id=None,
                    name=product_name or "Unknown",
                    category="Unknown",  # Can be set by caller
                    url=url,
                    current_price=price,
                    last_checked=time.strftime('%Y-%m-%d %H:%M:%S'),
                    product_id=product_id,
                    brand=brand
                )

            # Return just the price
            return price

        except Exception as e:
            print(f"❌ Error: {e}")
            try:
                page.screenshot(path='noelleeming_error.png')
                print("Error screenshot saved")
            except Exception:
                pass
            return None
        finally:
            page.close()

    if context:
        return _scrape(context)
    with PlaywrightPriceScraper(headless=headless) as scraper:
        return _scrape(scraper.context)
