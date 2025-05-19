import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_file='store.db'):
        self.db_file = db_file
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_file)

    def init_db(self):
        """Initialize the database with required tables."""
        conn = self.get_connection()
        c = conn.cursor()

        # Create products table
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL NOT NULL,
                photo_id TEXT,
                download_content TEXT,
                is_file BOOLEAN,
                file_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create buyers table
        c.execute('''
            CREATE TABLE IF NOT EXISTS buyers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                product_id INTEGER NOT NULL,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')

        # Create transactions table
        c.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signature TEXT UNIQUE NOT NULL,
                buyer_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (buyer_id) REFERENCES buyers (id)
            )
        ''')

        conn.commit()
        conn.close()

    def add_product(self, product_data):
        """Add a new product to the database."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO products (title, description, price, photo_id, download_content, is_file, file_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_data['title'],
            product_data['description'],
            product_data['price'],
            product_data.get('photo_id'),
            product_data.get('download_content'),
            product_data.get('is_file', False),
            product_data.get('file_name')
        ))
        
        product_id = c.lastrowid
        conn.commit()
        conn.close()
        return product_id

    def get_all_products(self):
        """Get all products from the database."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('SELECT * FROM products ORDER BY created_at DESC')
        products = []
        for row in c.fetchall():
            products.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'price': row[3],
                'photo_id': row[4],
                'download_content': row[5],
                'is_file': bool(row[6]),
                'file_name': row[7]
            })
        
        conn.close()
        return products

    def get_product(self, product_id):
        """Get a specific product by ID."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        row = c.fetchone()
        
        if row:
            product = {
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'price': row[3],
                'photo_id': row[4],
                'download_content': row[5],
                'is_file': bool(row[6]),
                'file_name': row[7]
            }
        else:
            product = None
        
        conn.close()
        return product

    def remove_product(self, product_id):
        """Remove a product from the database."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('DELETE FROM products WHERE id = ?', (product_id,))
        success = c.rowcount > 0
        
        conn.commit()
        conn.close()
        return success

    def add_buyer(self, user_id, username, product_id):
        """Add a new buyer to the database."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO buyers (user_id, username, product_id)
            VALUES (?, ?, ?)
        ''', (user_id, username, product_id))
        
        buyer_id = c.lastrowid
        conn.commit()
        conn.close()
        return buyer_id

    def add_transaction(self, signature, buyer_id, amount):
        """Add a new transaction to the database."""
        conn = self.get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT INTO transactions (signature, buyer_id, amount, status)
                VALUES (?, ?, ?, ?)
            ''', (signature, buyer_id, amount, 'completed'))
            
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        finally:
            conn.close()
        
        return success

    def get_store_stats(self):
        """Get store statistics."""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Get total buyers
        c.execute('SELECT COUNT(DISTINCT user_id) FROM buyers')
        total_buyers = c.fetchone()[0]
        
        # Get total sales
        c.execute('SELECT SUM(amount) FROM transactions')
        total_sales = c.fetchone()[0] or 0
        
        # Get active products
        c.execute('SELECT COUNT(*) FROM products')
        active_products = c.fetchone()[0]
        
        conn.close()
        
        return {
            'total_buyers': total_buyers,
            'total_sales': total_sales,
            'active_products': active_products
        }

    def get_buyers_list(self):
        """Get list of all buyers with their purchases."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT b.username, p.title, t.created_at
            FROM buyers b
            JOIN products p ON b.product_id = p.id
            JOIN transactions t ON t.buyer_id = b.id
            ORDER BY t.created_at DESC
        ''')
        
        buyers = []
        for row in c.fetchall():
            buyers.append({
                'username': row[0],
                'product': row[1],
                'purchase_date': row[2]
            })
        
        conn.close()
        return buyers

    def is_signature_used(self, signature):
        """Check if a transaction signature has been used."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM transactions WHERE signature = ?', (signature,))
        count = c.fetchone()[0]
        
        conn.close()
        return count > 0 