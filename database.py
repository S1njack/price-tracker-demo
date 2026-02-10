#!/usr/bin/env python3
"""
Database handler for price tracker
Supports product groups for cross-retailer comparison
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

class PriceDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            data_dir = os.environ.get('PRICE_TRACKER_DATA', '.')
            db_path = os.path.join(data_dir, 'prices.db')
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Product groups - links same product across retailers
        c.execute('''CREATE TABLE IF NOT EXISTS product_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT UNIQUE,
            name TEXT NOT NULL,
            brand TEXT,
            category TEXT,
            created_at TEXT
        )''')

        # Products table - individual product listings per retailer
        c.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            name TEXT NOT NULL,
            product_id TEXT,
            brand TEXT,
            category TEXT,
            url TEXT NOT NULL UNIQUE,
            retailer TEXT NOT NULL,
            current_price REAL,
            last_checked TEXT,
            FOREIGN KEY (group_id) REFERENCES product_groups(id)
        )''')

        # Price history table
        c.execute('''CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )''')

        # Create indexes for faster queries
        c.execute('CREATE INDEX IF NOT EXISTS idx_products_group ON products(group_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_history_product ON price_history(product_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON price_history(timestamp)')

        conn.commit()
        conn.close()

    def create_product_group(self, model: str, name: str, brand: str, category: str) -> int:
        """Create a new product group"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            c.execute('''INSERT INTO product_groups (model, name, brand, category, created_at)
                         VALUES (?, ?, ?, ?, ?)''',
                      (model, name, brand, category, datetime.now().isoformat()))
            group_id = c.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Group already exists, get its ID
            c.execute('SELECT id FROM product_groups WHERE model = ?', (model,))
            group_id = c.fetchone()[0]

        conn.close()
        return group_id

    def get_or_create_group(self, model: str, name: str, brand: str, category: str) -> int:
        """Get existing group or create new one"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('SELECT id FROM product_groups WHERE model = ?', (model,))
        result = c.fetchone()

        if result:
            group_id = result[0]
        else:
            c.execute('''INSERT INTO product_groups (model, name, brand, category, created_at)
                         VALUES (?, ?, ?, ?, ?)''',
                      (model, name, brand, category, datetime.now().isoformat()))
            group_id = c.lastrowid
            conn.commit()

        conn.close()
        return group_id

    def add_product(self, product, retailer: str, group_id: Optional[int] = None) -> int:
        """Add or update product"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check if product already exists (by URL)
        c.execute('SELECT id FROM products WHERE url = ?', (product.url,))
        existing = c.fetchone()

        if existing:
            # Update existing product
            c.execute('''UPDATE products
                         SET name=?, product_id=?, brand=?, category=?,
                             current_price=?, last_checked=?, group_id=?
                         WHERE id=?''',
                      (product.name, product.product_id, product.brand,
                       product.category, product.current_price,
                       product.last_checked, group_id, existing[0]))
            product_db_id = existing[0]
        else:
            # Insert new product
            c.execute('''INSERT INTO products
                         (group_id, name, product_id, brand, category, url, retailer, current_price, last_checked)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (group_id, product.name, product.product_id, product.brand,
                       product.category, product.url, retailer,
                       product.current_price, product.last_checked))
            product_db_id = c.lastrowid

        conn.commit()
        conn.close()
        return product_db_id

    def add_price_history(self, product_id: int, price: float):
        """Add price to history"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''INSERT INTO price_history (product_id, price, timestamp)
                     VALUES (?, ?, ?)''',
                  (product_id, price, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def update_product_price(self, product_id: int, price: float):
        """Update current_price and last_checked for a product"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''UPDATE products SET current_price = ?, last_checked = ?
                     WHERE id = ?''',
                  (price, datetime.now().isoformat(), product_id))

        conn.commit()
        conn.close()

    def backfill_price_history(self, product_id: int, history_data: list) -> int:
        """
        Backfill price history with historical data (e.g. from PriceSpy)

        Only inserts records with timestamps BEFORE the earliest existing record
        for this product, preventing mixing backfill data with real scraped data.
        Checks for exact duplicates before inserting.

        Args:
            product_id: The product to backfill history for
            history_data: List of {'date': 'YYYY-MM-DD', 'price': float}

        Returns:
            Count of inserted records
        """
        if not history_data:
            return 0

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Find the earliest existing record for this product
        c.execute('''SELECT MIN(timestamp) FROM price_history WHERE product_id = ?''',
                  (product_id,))
        result = c.fetchone()
        earliest_existing = result[0] if result and result[0] else None

        inserted = 0
        for entry in history_data:
            date_str = entry.get('date')
            price = entry.get('price')

            if not date_str or not price:
                continue

            # Normalize to ISO timestamp for consistency
            timestamp = f"{date_str}T00:00:00"

            # Only insert if before earliest existing record
            if earliest_existing and timestamp >= earliest_existing:
                continue

            # Check for exact duplicate
            c.execute('''SELECT id FROM price_history
                         WHERE product_id = ? AND timestamp = ? AND price = ?''',
                      (product_id, timestamp, price))
            if c.fetchone():
                continue

            c.execute('''INSERT INTO price_history (product_id, price, timestamp)
                         VALUES (?, ?, ?)''',
                      (product_id, price, timestamp))
            inserted += 1

        conn.commit()
        conn.close()
        return inserted

    def get_all_products(self) -> List[Dict]:
        """Get all products with group info"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''SELECT p.*, g.model as group_model
                     FROM products p
                     LEFT JOIN product_groups g ON p.group_id = g.id
                     ORDER BY p.name''')
        products = [dict(row) for row in c.fetchall()]

        conn.close()
        return products

    def get_products_by_group(self, group_id: int) -> List[Dict]:
        """Get all products in a group (same product, different retailers)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''SELECT * FROM products WHERE group_id = ? ORDER BY current_price''',
                  (group_id,))
        products = [dict(row) for row in c.fetchall()]

        conn.close()
        return products

    def get_all_groups(self) -> List[Dict]:
        """Get all product groups with cheapest price info"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT
                g.*,
                COUNT(p.id) as retailer_count,
                MIN(p.current_price) as min_price,
                MAX(p.current_price) as max_price,
                AVG(p.current_price) as avg_price
            FROM product_groups g
            LEFT JOIN products p ON g.id = p.group_id
            GROUP BY g.id
            ORDER BY g.name
        ''')

        groups = [dict(row) for row in c.fetchall()]
        conn.close()
        return groups

    def get_price_history(self, product_id: int, days: int = 30) -> List[Dict]:
        """Get price history for a product"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''SELECT * FROM price_history
                     WHERE product_id = ?
                     ORDER BY timestamp DESC
                     LIMIT ?''', (product_id, days * 24))

        history = [dict(row) for row in c.fetchall()]
        conn.close()
        return history

    def get_group_price_comparison(self, group_id: int) -> Dict:
        """Get price comparison for all retailers in a group"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get group info
        c.execute('SELECT * FROM product_groups WHERE id = ?', (group_id,))
        row = c.fetchone()
        if row is None:
            conn.close()
            return None

        group = dict(row)

        # Get all products in group
        c.execute('''SELECT * FROM products
                     WHERE group_id = ?
                     ORDER BY current_price ASC''', (group_id,))
        products = [dict(row) for row in c.fetchall()]

        conn.close()

        if products:
            cheapest = products[0]
            most_expensive = products[-1]
            price_range = most_expensive['current_price'] - cheapest['current_price']
        else:
            cheapest = most_expensive = None
            price_range = 0

        return {
            'group': group,
            'products': products,
            'cheapest': cheapest,
            'most_expensive': most_expensive,
            'price_range': price_range,
            'retailer_count': len(products)
        }

    def delete_product(self, product_id: int):
        """Delete a specific product and its price history. If group becomes empty, delete the group too."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Get the group_id before deleting
        c.execute('SELECT group_id FROM products WHERE id = ?', (product_id,))
        result = c.fetchone()
        group_id = result[0] if result else None

        # Delete price history first (foreign key constraint)
        c.execute('DELETE FROM price_history WHERE product_id = ?', (product_id,))

        # Delete the product
        c.execute('DELETE FROM products WHERE id = ?', (product_id,))

        # Check if group is now empty and delete it
        if group_id:
            c.execute('SELECT COUNT(*) FROM products WHERE group_id = ?', (group_id,))
            remaining_products = c.fetchone()[0]

            if remaining_products == 0:
                # No products left in group, delete the group
                c.execute('DELETE FROM product_groups WHERE id = ?', (group_id,))
                print(f"  Deleted empty group {group_id}")

        conn.commit()
        conn.close()

    def delete_group(self, group_id: int):
        """Delete a product group and all associated products"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Get all products in the group
        c.execute('SELECT id FROM products WHERE group_id = ?', (group_id,))
        product_ids = [row[0] for row in c.fetchall()]

        # Delete price history for all products in group
        for product_id in product_ids:
            c.execute('DELETE FROM price_history WHERE product_id = ?', (product_id,))

        # Delete all products in group
        c.execute('DELETE FROM products WHERE group_id = ?', (group_id,))

        # Delete the group itself
        c.execute('DELETE FROM product_groups WHERE id = ?', (group_id,))

        conn.commit()
        conn.close()

    def cleanup_orphaned_groups(self):
        """Remove product groups that have no associated products"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Find and delete orphaned groups
        c.execute('''
            DELETE FROM product_groups
            WHERE id IN (
                SELECT pg.id
                FROM product_groups pg
                LEFT JOIN products p ON pg.id = p.group_id
                WHERE p.id IS NULL
            )
        ''')

        deleted_count = c.rowcount
        conn.commit()
        conn.close()

        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} orphaned product groups")

        return deleted_count
