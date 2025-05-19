import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Admin Configuration
ADMIN_IDS = 5950741458

# Store Configuration
STORE_WALLET = "DB3NZgGPsANwp5RBBMEK2A9ehWeN41QCELRt8WYyL8d8"
PRODUCT_PRICE = 0.1  # in SOL

# Helius API Configuration
HELIUS_API_KEY = os.getenv('HELIUS_API_KEY')
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Product Configuration
DEFAULT_PRODUCT = {
    "title": "Solana Memecoin Mastery Guide",
    "description": "Start your Solana side hustle today!",
    "price": 0.1,
    "download_link": os.getenv('DEFAULT_PRODUCT_LINK', '')
} 
