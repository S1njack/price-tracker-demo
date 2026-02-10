#!/usr/bin/env python3
"""
Secure Flask API for Price Tracker
Implements security best practices
"""

from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import os
import re
import sys
import secrets
import threading
from datetime import datetime, timedelta
import logging
sys.path.append('.')

from database import PriceDatabase
from src.playwright_scraper import (
    PlaywrightPriceScraper,
    scrape_pbtech, scrape_noelleeming,
    scrape_jbhifi, scrape_acquire,
    search_pbtech, search_noelleeming,
    search_jbhifi, search_acquire,
    search_google_shopping, search_pricespy,
    search_via_pricespy,
    search_pricespy_product, scrape_pricespy_history,
)

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# Configure logging (don't expose sensitive info)
data_dir = os.environ.get('PRICE_TRACKER_DATA', '.')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(data_dir, 'api.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask with security headers
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024  # 16KB max request size

# CORS - Restrict to your frontend domain in production
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Rate limiting to prevent abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

db = PriceDatabase()

# ============================================================================
# SECURITY MIDDLEWARE
# ============================================================================

def sanitize_input(text):
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return None
    # Remove potentially dangerous characters
    text = re.sub(r'[<>\'";`]', '', str(text))
    # Limit length
    return text[:500]


def validate_query(query):
    """Validate search query"""
    if not query or not isinstance(query, str):
        return False
    # Must be reasonable length
    if len(query) < 2 or len(query) > 200:
        return False
    # Only allow alphanumeric, spaces, hyphens
    if not re.match(r'^[a-zA-Z0-9\s\-]+$', query):
        return False
    return True


def validate_category(category):
    """Validate category against whitelist"""
    allowed_categories = [
        'Electronics', 'Laptops', 'Tablets', 'Monitors',
        'Peripherals', 'Components', 'Storage', 'Networking'
    ]
    return category in allowed_categories


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response


@app.errorhandler(Exception)
def handle_error(error):
    """Handle errors without exposing sensitive information"""
    logger.error(f"Error: {str(error)}", exc_info=True)

    # Don't expose internal error details to users
    if isinstance(error, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    return jsonify({'error': 'An error occurred'}), 500


# ============================================================================
# SEARCH FUNCTION (with timeout and limits)
# ============================================================================

def search_product_via_google_shopping(query, product_model=None, headless=True):
    """
    Search using Google Shopping to find products across retailers
    More reliable than searching each retailer directly
    """
    # Validate inputs
    if not validate_query(query):
        raise ValueError("Invalid query")

    if product_model:
        product_model = sanitize_input(product_model)

    results = []

    # Define retailers and their domains
    retailer_domains = {
        'PBTech': 'pbtech.co.nz',
        'Noel Leeming': 'noelleeming.co.nz',
        'JB Hi-Fi': 'jbhifi.co.nz',
        'Acquire': 'acquire.co.nz'
    }

    # Map domains to scraper functions
    scraper_map = {
        'PBTech': scrape_pbtech,
        'Noel Leeming': scrape_noelleeming,
        'JB Hi-Fi': scrape_jbhifi,
        'Acquire': scrape_acquire
    }

    try:
        # Search PriceSpy NZ for all retailers at once
        logger.info(f"Searching PriceSpy NZ for: {query}")
        retailer_urls = search_pricespy(query, retailer_domains, headless=headless)

        # Scrape each found URL in parallel
        def scrape_retailer_url(retailer_name, url):
            """Scrape a specific retailer URL"""
            try:
                logger.info(f"Scraping {retailer_name}: {url}")
                scrape_func = scraper_map[retailer_name]
                product = scrape_func(url, headless=headless, return_product=True)

                if product:
                    # Verify model if provided
                    if product_model and product.product_id:
                        if product.product_id.lower() != product_model.lower():
                            logger.warning(f"Model mismatch for {retailer_name}")
                            return None

                    return {
                        'retailer': retailer_name,
                        'url': url,
                        'product': product
                    }
            except Exception as e:
                logger.error(f"{retailer_name} scraping failed: {str(e)}")
                return None

            return None

        # Execute scraping sequentially (Playwright sync API cannot cross threads)
        for name, url in retailer_urls.items():
            result = scrape_retailer_url(name, url)
            if result:
                results.append(result)

    except Exception as e:
        logger.error(f"Google Shopping search failed: {str(e)}")

    return results


def search_product_across_retailers(query, product_model=None, headless=True):
    """
    Two-stage search using PriceSpy:
    1. Search PriceSpy NZ to find which retailers have the product
    2. Scrape each retailer's product page for accurate data with model numbers

    Falls back to direct retailer scraping if PriceSpy fails
    """
    # Validate inputs
    if not validate_query(query):
        raise ValueError("Invalid query")

    if product_model:
        product_model = sanitize_input(product_model)

    # Use a single browser instance for the entire search
    with PlaywrightPriceScraper(headless=headless) as scraper:
        ctx = scraper.context

        # Try PriceSpy two-stage search first
        logger.info(f"🔍 Using PriceSpy two-stage search for: {query}")
        try:
            results = search_via_pricespy(query, headless=headless, context=ctx)
            if results:
                logger.info(f"✅ PriceSpy search returned {len(results)} products")
                results = _filter_search_results(results, query)
                logger.info(f"After filtering: {len(results)} products")
                return results
            else:
                logger.warning("⚠️  PriceSpy found no results, falling back to direct scraping")
        except Exception as e:
            logger.error(f"❌ PriceSpy search failed: {e}, falling back to direct scraping")

        # Fallback: Direct retailer scraping
        logger.info("🔄 Using direct retailer scraping as fallback")
        results = []

        retailers = [
            ('PBTech', search_pbtech, scrape_pbtech),
            ('Noel Leeming', search_noelleeming, scrape_noelleeming),
            ('JB Hi-Fi', search_jbhifi, scrape_jbhifi),
            ('Acquire', search_acquire, scrape_acquire),
        ]

        def search_retailer(retailer_name, search_func, scrape_func):
            """Search a single retailer and return ALL matching products"""
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Searching {retailer_name}...")
                logger.info(f"Query: {query}")
                logger.info(f"{'='*60}")

                # Get all matching URLs (up to 10 per retailer)
                logger.info(f"Calling {search_func.__name__} with return_all=True")
                urls = search_func(query, headless=headless, return_all=True, context=ctx)
                logger.info(f"Returned {len(urls) if isinstance(urls, list) else 'single URL' if urls else 'no'} URLs")

                # If search function doesn't support return_all, fallback to single result
                if urls is None or (isinstance(urls, str)):
                    # Old style - single URL
                    urls = [urls] if urls else []
                elif not urls:
                    # No results found - don't truncate query
                    urls = []

                if not urls:
                    logger.warning(f"Not available at {retailer_name}")
                    return []

                # Scrape each URL and collect products
                products = []
                for url in urls[:10]:  # Limit to 10 products per retailer
                    try:
                        product = scrape_func(url, headless=headless, return_product=True, context=ctx)

                        if product:
                            # Check if product name is relevant to query
                            query_keywords = set(query.lower().split())
                            product_keywords = set(product.name.lower().split())

                            # At least one keyword should match
                            if query_keywords & product_keywords:
                                logger.info(f"✅ {product.name[:60]}... ${product.current_price}")
                                products.append({
                                    'retailer': retailer_name,
                                    'url': url,
                                    'product': product
                                })
                            else:
                                logger.info(f"⚠️  Skipped (irrelevant): {product.name[:50]}...")
                    except Exception as e:
                        logger.error(f"Failed to scrape URL: {e}")
                        continue

                if products:
                    logger.info(f"✅ {retailer_name}: Found {len(products)} variants")
                    return products
                else:
                    logger.warning(f"No matching products at {retailer_name}")
                    return []

            except Exception as e:
                logger.error(f"{retailer_name} error: {e}")
                import traceback
                traceback.print_exc()

            return []

        # Execute searches sequentially (Playwright sync API cannot cross threads)
        for name, search_fn, scrape_fn in retailers:
            retailer_results = search_retailer(name, search_fn, scrape_fn)
            if isinstance(retailer_results, list):
                results.extend(retailer_results)
            elif retailer_results:
                results.append(retailer_results)

        results = _filter_search_results(results, query)
        logger.info(f"After filtering: {len(results)} products")
        return results


def _filter_search_results(results, query):
    """
    Filter search results to remove duplicates, accessories, and color/storage variants

    - Deduplicates by URL
    - Keeps only one product per retailer (best match / first found)
    - Removes accessories (cases, chargers, cables, etc.) unless the query
      itself is searching for an accessory
    - Filters out mismatched storage variants (e.g. 512GB when query says 256GB)
    """
    import re

    accessory_words = [
        'case', 'cover', 'protector', 'screen protector', 'tempered glass',
        'charger', 'charging', 'cable', 'adapter', 'dock', 'docking',
        'stand', 'mount', 'holder', 'sleeve', 'pouch', 'bag', 'backpack',
        'strap', 'band', 'keyboard', 'mouse', 'stylus', 'pen',
        'film', 'skin', 'decal', 'sticker', 'folio',
        'earbuds', 'earphones', 'headset', 'speaker',
        'hub', 'dongle', 'memory card', 'sd card', 'usb',
        'insurance', 'applecare', 'warranty', 'protection plan',
        'refurbished', 'renewed', 'pre-owned',
    ]

    query_lower = query.lower()
    query_is_accessory = any(word in query_lower for word in accessory_words)

    # Extract storage size from query (e.g. "256GB") to filter mismatched variants
    query_storage = re.search(r'(\d+)\s*[gt]b', query_lower)
    query_storage_val = query_storage.group(1) if query_storage else None

    seen_urls = set()
    seen_retailers = set()
    filtered = []

    for result in results:
        url = result.get('url', '')
        retailer = result.get('retailer', '')
        product = result.get('product')
        if not product:
            continue

        # Deduplicate by URL
        clean_url = url.split('?')[0].rstrip('/')
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        name_lower = product.name.lower()

        # Filter accessories (only if query is NOT for an accessory)
        if not query_is_accessory:
            is_accessory = any(word in name_lower for word in accessory_words)
            if is_accessory:
                logger.info(f"  Filtered accessory: {product.name[:60]}")
                continue

        # Filter mismatched storage variants
        if query_storage_val:
            product_storages = re.findall(r'(\d+)\s*[gt]b', name_lower)
            if product_storages and query_storage_val not in product_storages:
                logger.info(f"  Filtered storage mismatch: {product.name[:60]}")
                continue

        # Keep only one product per retailer
        if retailer in seen_retailers:
            logger.info(f"  Filtered duplicate retailer: {retailer} - {product.name[:50]}")
            continue
        seen_retailers.add(retailer)

        filtered.append(result)

    return filtered


def _clean_search_query(name):
    """
    Clean a verbose product name into a short PriceSpy search query

    e.g. "Apple MacBook Air 13-inch with M4 Chip, 256GB/16GB (Midnight)"
      -> "MacBook Air M4 256GB"
    e.g. "Samsung Galaxy S24 Ultra 5G 256GB (Titanium Violet) [~Refurbished: Excellent]"
      -> "Samsung Galaxy S24 Ultra 256GB"
    """
    import re

    # Remove anything in brackets/parentheses
    query = re.sub(r'\[.*?\]', '', name)
    query = re.sub(r'\(.*?\)', '', query)

    # Remove commas and clean punctuation
    query = re.sub(r'[,~\[\](){}<>]', ' ', query)

    # Remove size notations like "13-inch", "15.6-inch"
    query = re.sub(r'\d+\.?\d*-inch', '', query, flags=re.IGNORECASE)

    # Remove RAM/storage combos like "256GB/16GB" -> keep first (storage)
    query = re.sub(r'(\d+GB)/\d+GB', r'\1', query, flags=re.IGNORECASE)

    # Remove common noise words
    noise_words = [
        'refurbished', 'excellent', 'good', 'fair', 'renewed', 'certified',
        'unlocked', 'sim-free', 'with', 'chip', 'the', 'and', 'for',
        'black', 'white', 'silver', 'gold', 'grey', 'gray', 'blue', 'red',
        'green', 'pink', 'purple', 'midnight', 'starlight', 'titanium',
        'graphite', 'space', 'teal', 'ultramarine', 'violet', 'yellow',
        'orange', 'cream', 'lavender', 'coral', 'mint',
    ]
    words = query.split()
    words = [w for w in words if w.lower().strip('~,-./:') not in noise_words]
    query = ' '.join(words)

    # Remove 5G
    query = re.sub(r'\b5G\b', '', query, flags=re.IGNORECASE)

    # Clean up extra whitespace
    query = re.sub(r'\s+', ' ', query).strip()

    # If still too long (>60 chars), take first 6 words
    words = query.split()
    if len(words) > 6:
        query = ' '.join(words[:6])

    return query


def backfill_pricespy_history_for_group(group_id):
    """
    Backfill price history from PriceSpy for all products in a group

    Orchestrates the full flow:
    1. Get group info
    2. Search PriceSpy for the product page
    3. Scrape price history from PriceSpy
    4. Backfill history into all products in the group
    """
    try:
        logger.info(f"📊 Backfilling PriceSpy history for group {group_id}")

        comparison = db.get_group_price_comparison(group_id)
        if not comparison:
            logger.warning(f"Group {group_id} not found")
            return

        group_name = comparison['group']['name']
        products = comparison['products']

        if not products:
            logger.warning(f"No products in group {group_id}")
            return

        search_query = _clean_search_query(group_name)
        logger.info(f"  Product: {group_name}")
        logger.info(f"  Search query: {search_query}")
        logger.info(f"  Products in group: {len(products)}")

        # Search PriceSpy for this product
        pricespy_url = search_pricespy_product(search_query)
        if not pricespy_url:
            logger.warning(f"  Product not found on PriceSpy")
            return

        # Scrape price history
        history_data = scrape_pricespy_history(pricespy_url)
        if not history_data:
            logger.warning(f"  No price history available on PriceSpy")
            return

        logger.info(f"  Got {len(history_data)} historical price points")

        # Backfill into all products in the group
        total_inserted = 0
        for product in products:
            inserted = db.backfill_price_history(product['id'], history_data)
            total_inserted += inserted
            logger.info(f"  Product {product['id']} ({product['retailer']}): {inserted} records inserted")

        logger.info(f"✅ Backfill complete: {total_inserted} total records inserted")

    except Exception as e:
        logger.error(f"Backfill failed for group {group_id}: {e}")


# ============================================================================
# API ENDPOINTS WITH SECURITY
# ============================================================================

@app.route('/api/products', methods=['GET'])
@limiter.limit("100 per hour")
def get_products():
    """Get all tracked products"""
    try:
        products = db.get_all_products()
        return jsonify(products)
    except Exception as e:
        logger.error(f"Failed to get products: {e}")
        return jsonify({'error': 'Failed to retrieve products'}), 500


@app.route('/api/products/<int:product_id>/history', methods=['GET'])
@limiter.limit("100 per hour")
def get_history(product_id):
    """Get price history for a product"""
    try:
        if product_id < 1 or product_id > 1000000:
            return jsonify({'error': 'Invalid product ID'}), 400

        days = request.args.get('days', 30, type=int)
        history = db.get_price_history(product_id, days)
        return jsonify(history)
    except Exception as e:
        logger.error(f"Failed to get history for product {product_id}: {e}")
        return jsonify({'error': 'Failed to retrieve history'}), 500


@app.route('/api/groups', methods=['GET'])
@limiter.limit("100 per hour")
def get_groups():
    """Get all product groups"""
    try:
        # Clean up any orphaned groups first
        db.cleanup_orphaned_groups()
        groups = db.get_all_groups()
        return jsonify(groups)
    except Exception as e:
        logger.error(f"Failed to get groups: {e}")
        return jsonify({'error': 'Failed to retrieve groups'}), 500


@app.route('/api/groups/<int:group_id>', methods=['GET'])
@limiter.limit("100 per hour")
def get_group(group_id):
    """Get specific product group"""
    try:
        # Validate group_id
        if group_id < 1 or group_id > 1000000:
            return jsonify({'error': 'Invalid group ID'}), 400

        comparison = db.get_group_price_comparison(group_id)
        return jsonify(comparison)
    except Exception as e:
        logger.error(f"Failed to get group {group_id}: {e}")
        return jsonify({'error': 'Failed to retrieve comparison'}), 500


@app.route('/api/products', methods=['POST'])
@limiter.limit("10 per hour")  # Strict limit for expensive operations
def add_product():
    """
    Add product - Rate limited to prevent abuse
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate and sanitize inputs
        query = sanitize_input(data.get('query'))
        model = sanitize_input(data.get('model'))
        category = data.get('category', 'Electronics')

        if not query or not validate_query(query):
            return jsonify({'error': 'Invalid query'}), 400

        if not validate_category(category):
            return jsonify({'error': 'Invalid category'}), 400

        logger.info(f"Adding product: {query}")

        # Search retailers in parallel (improved with better stealth)
        results = search_product_across_retailers(query, model, headless=True)

        if not results:
            return jsonify({
                'error': 'Product not found in any retailer',
                'searched': query
            }), 404

        # Create product group
        group_id = None
        if results and results[0]['product'].product_id:
            first_product = results[0]['product']
            group_id = db.get_or_create_group(
                model=first_product.product_id or query,
                name=first_product.name[:200],  # Limit length
                brand=first_product.brand[:100] if first_product.brand else 'Unknown',
                category=category
            )

        # Add products to database
        added = []
        for result in results:
            product = result['product']
            product.category = category

            product_id = db.add_product(product, result['retailer'], group_id)
            db.add_price_history(product_id, product.current_price)

            added.append({
                'id': product_id,
                'group_id': group_id,
                'retailer': result['retailer'],
                'name': product.name[:200],
                'price': float(product.current_price),
                'url': result['url'],
                'model': product.product_id,
                'brand': product.brand
            })

        # Calculate comparison
        cheapest = min(added, key=lambda x: x['price'])
        most_expensive = max(added, key=lambda x: x['price'])

        logger.info(f"Added product: {len(added)} retailers found")

        return jsonify({
            'success': True,
            'found': len(added),
            'group_id': group_id,
            'products': added,
            'cheapest': cheapest,
            'most_expensive': most_expensive,
            'price_range': float(most_expensive['price'] - cheapest['price']),
            'savings': float(most_expensive['price'] - cheapest['price'])
        })

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        return jsonify({'error': 'Failed to add product'}), 500


@app.route('/api/check-prices', methods=['POST'])
@limiter.limit("5 per hour")  # Very strict - expensive operation
def check_prices():
    """Check prices - Heavily rate limited"""
    try:
        products = db.get_all_products()
        updated = []

        # Limit to prevent abuse
        if len(products) > 100:
            return jsonify({'error': 'Too many products to check'}), 400

        for product in products:
            url = product['url']

            try:
                if 'pbtech.co.nz' in url:
                    new_price = scrape_pbtech(url)
                elif 'noelleeming.co.nz' in url:
                    new_price = scrape_noelleeming(url)
                elif 'jbhifi.co' in url:
                    new_price = scrape_jbhifi(url)
                elif 'acquire.co.nz' in url:
                    new_price = scrape_acquire(url)
                else:
                    continue

                if new_price and new_price != product['current_price']:
                    db.add_price_history(product['id'], new_price)
                    updated.append({
                        'id': product['id'],
                        'name': product['name'],
                        'retailer': product['retailer'],
                        'old_price': float(product['current_price']),
                        'new_price': float(new_price),
                        'change': float(new_price - product['current_price'])
                    })

            except Exception as e:
                logger.error(f"Error checking {product['name']}: {e}")
                continue

        return jsonify({
            'success': True,
            'checked': len(products),
            'updated': len(updated),
            'changes': updated
        })

    except Exception as e:
        logger.error(f"Error checking prices: {e}")
        return jsonify({'error': 'Failed to check prices'}), 500


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@limiter.limit("20 per hour")
def delete_product(product_id):
    """Delete a specific product"""
    try:
        # Validate product_id
        if product_id < 1 or product_id > 1000000:
            return jsonify({'error': 'Invalid product ID'}), 400

        # Delete from database
        db.delete_product(product_id)
        logger.info(f"Deleted product {product_id}")

        return jsonify({
            'success': True,
            'message': f'Product {product_id} deleted'
        })
    except Exception as e:
        logger.error(f"Failed to delete product {product_id}: {e}")
        return jsonify({'error': 'Failed to delete product'}), 500


@app.route('/api/groups/<int:group_id>', methods=['DELETE'])
@limiter.limit("20 per hour")
def delete_group(group_id):
    """Delete a product group and all its products"""
    try:
        # Validate group_id
        if group_id < 1 or group_id > 1000000:
            return jsonify({'error': 'Invalid group ID'}), 400

        # Delete from database
        db.delete_group(group_id)
        logger.info(f"Deleted group {group_id}")

        return jsonify({
            'success': True,
            'message': f'Group {group_id} and all products deleted'
        })
    except Exception as e:
        logger.error(f"Failed to delete group {group_id}: {e}")
        return jsonify({'error': 'Failed to delete group'}), 500


@app.route('/api/search-preview', methods=['POST'])
@limiter.limit("15 per hour")
def search_preview():
    """
    Search retailers and return preview without adding to database
    Returns product details for user to select which ones to add
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        query = sanitize_input(data.get('query'))
        category = data.get('category', 'Electronics')

        if not query or not validate_query(query):
            return jsonify({'error': 'Invalid query'}), 400

        if not validate_category(category):
            return jsonify({'error': 'Invalid category'}), 400

        logger.info(f"Preview search: {query}")

        # Search all retailers
        results = search_product_across_retailers(query, None, headless=True)

        if not results:
            return jsonify({
                'error': 'No products found',
                'searched': query
            }), 404

        # Format results with product details for preview
        preview_results = []
        for result in results:
            product = result['product']
            preview_results.append({
                'retailer': result['retailer'],
                'url': result['url'],
                'name': product.name[:200] if product.name else 'Unknown',
                'price': float(product.current_price),
                'brand': product.brand or 'Unknown',
                'model': product.product_id or '',
                'category': category
            })

        return jsonify({
            'success': True,
            'query': query,
            'found': len(preview_results),
            'products': preview_results
        })

    except ValueError as e:
        logger.warning(f"Validation error in preview: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error in preview search: {e}")
        return jsonify({'error': 'Search failed'}), 500


@app.route('/api/products/add-selected', methods=['POST'])
@limiter.limit("10 per hour")
def add_selected_products():
    """
    Add selected products from search preview to database
    """
    try:
        data = request.get_json()

        if not data or 'products' not in data:
            return jsonify({'error': 'No products provided'}), 400

        selected_products = data['products']
        category = data.get('category', 'Electronics')

        if not validate_category(category):
            return jsonify({'error': 'Invalid category'}), 400

        if not selected_products or len(selected_products) == 0:
            return jsonify({'error': 'No products selected'}), 400

        logger.info(f"Adding {len(selected_products)} selected products")

        # Create product group from first product
        group_id = None
        first_product = selected_products[0]
        if first_product.get('model'):
            group_id = db.get_or_create_group(
                model=first_product['model'],
                name=first_product['name'][:200],
                brand=first_product.get('brand', 'Unknown')[:100],
                category=category
            )

        # Add each selected product
        added = []
        for prod_data in selected_products:
            from src.playwright_scraper import Product
            product = Product(
                id=None,
                name=prod_data['name'],
                category=category,
                url=prod_data['url'],
                current_price=prod_data['price'],
                last_checked=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                product_id=prod_data.get('model'),
                brand=prod_data.get('brand')
            )

            product_id = db.add_product(product, prod_data['retailer'], group_id)
            db.add_price_history(product_id, product.current_price)

            added.append({
                'id': product_id,
                'group_id': group_id,
                'retailer': prod_data['retailer'],
                'name': product.name[:200],
                'price': float(product.current_price),
                'url': prod_data['url']
            })

        logger.info(f"Added {len(added)} products to database")

        # Backfill price history from PriceSpy in background
        if group_id:
            thread = threading.Thread(
                target=backfill_pricespy_history_for_group,
                args=(group_id,),
                daemon=True
            )
            thread.start()
            logger.info(f"Started background PriceSpy history backfill for group {group_id}")

        return jsonify({
            'success': True,
            'added': len(added),
            'group_id': group_id,
            'products': added
        })

    except Exception as e:
        logger.error(f"Error adding selected products: {e}")
        return jsonify({'error': 'Failed to add products'}), 500


@app.route('/api/groups/<int:group_id>/backfill', methods=['POST'])
@limiter.limit("5 per hour")
def backfill_group(group_id):
    """Manually trigger PriceSpy price history backfill for a group"""
    try:
        if group_id < 1 or group_id > 1000000:
            return jsonify({'error': 'Invalid group ID'}), 400

        comparison = db.get_group_price_comparison(group_id)
        if not comparison:
            return jsonify({'error': 'Group not found'}), 404

        thread = threading.Thread(
            target=backfill_pricespy_history_for_group,
            args=(group_id,),
            daemon=True
        )
        thread.start()
        logger.info(f"Started manual PriceSpy history backfill for group {group_id}")

        return jsonify({
            'success': True,
            'status': 'pending',
            'message': f'Backfill started for group {group_id}'
        })

    except Exception as e:
        logger.error(f"Error starting backfill: {e}")
        return jsonify({'error': 'Failed to start backfill'}), 500


@app.route('/api/health', methods=['GET'])
@limiter.limit("60 per minute")
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'products': len(db.get_all_products()),
        'groups': len(db.get_all_groups())
    })


# ============================================================================
# PRODUCTION CONFIGURATION
# ============================================================================

if __name__ == '__main__':
    # Check for required environment variables in production
    if os.environ.get('FLASK_ENV') == 'production':
        required_vars = ['SECRET_KEY', 'ALLOWED_ORIGINS']
        missing = [var for var in required_vars if not os.environ.get(var)]
        if missing:
            logger.error(f"Missing required environment variables: {missing}")
            exit(1)

    logger.info("="*60)
    logger.info("🔒 Secure Price Tracker API Starting")
    logger.info("="*60)
    logger.info(f"Server: http://localhost:5000")
    logger.info(f"Allowed Origins: {ALLOWED_ORIGINS}")
    logger.info("="*60)

    # In production, use a proper WSGI server (gunicorn, uwsgi)
    # Never use Flask's development server in production
    app.run(
        host='127.0.0.1',  # Only localhost in development
        port=5000,
        debug=os.environ.get('FLASK_ENV') != 'production'
    )
