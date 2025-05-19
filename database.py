import os
import psycopg2
from psycopg2.extras import DictCursor
import json

# Database connection parameters from environment variables
DB_URL = os.getenv('DATABASE_URL')

def get_connection():
    """Create a database connection."""
    return psycopg2.connect(DB_URL)

def init_db():
    """Initialize database tables."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Create products table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    price FLOAT NOT NULL,
                    photo_id TEXT,
                    download_content TEXT,
                    is_file BOOLEAN DEFAULT FALSE,
                    file_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create buyers table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS buyers (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    product_id INTEGER REFERENCES products(id),
                    purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transaction_signature TEXT UNIQUE
                )
            """)
            
            conn.commit()

def save_product(product):
    """Save a product to the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO products (title, description, price, photo_id, download_content, is_file, file_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                product['title'],
                product['description'],
                product['price'],
                product.get('photo_id'),
                product.get('download_content'),
                product.get('is_file', False),
                product.get('file_name')
            ))
            return cur.fetchone()[0]

def get_all_products():
    """Get all products from the database."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM products ORDER BY created_at DESC")
            return [dict(row) for row in cur.fetchall()]

def remove_product(product_title):
    """Remove a product from the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE title = %s", (product_title,))
            conn.commit()

def save_purchase(user_id, username, product_id, signature):
    """Save a purchase record."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO buyers (user_id, username, product_id, transaction_signature)
                VALUES (%s, %s, %s, %s)
            """, (user_id, username, product_id, signature))
            conn.commit()

def get_total_sales():
    """Get total sales amount."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT SUM(p.price) as total
                FROM buyers b
                JOIN products p ON b.product_id = p.id
            """)
            return cur.fetchone()[0] or 0

def get_buyers():
    """Get all buyers with their purchase details."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT b.*, p.title as product_title
                FROM buyers b
                JOIN products p ON b.product_id = p.id
                ORDER BY b.purchase_date DESC
            """)
            return [dict(row) for row in cur.fetchall()]

def is_signature_used(signature):
    """Check if a transaction signature has been used."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM buyers WHERE transaction_signature = %s", (signature,))
            return cur.fetchone() is not None

def get_product_by_id(product_id):
    """Get a product by its ID."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            result = cur.fetchone()
            return dict(result) if result else None 