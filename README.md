# TeenBucks Store Telegram Bot

A Telegram bot that acts as a digital store for Solana memecoin-related digital products.

## Features

- 🛍 Clean and minimal user interface
- 💳 Solana payment integration
- 🔒 Secure transaction verification
- 👨‍💻 Admin panel for store management
- 📊 Sales statistics and buyer tracking

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:
   ```
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_IDS=comma_separated_admin_telegram_ids
   HELIUS_API_KEY=your_helius_api_key
   DEFAULT_PRODUCT_LINK=your_default_product_download_link
   ```

4. Run the bot:
   ```bash
   python bot.py
   ```

## Admin Commands

- `/add <title> <description> <price> <download_link>` - Add a new product
- `/remove <product_title>` - Remove a product
- `/stats` - Show store statistics
- `/buyers` - List all buyers and their purchases

## User Flow

1. Start the bot with `/start`
2. Browse available products
3. Click "Buy Now" to see payment information
4. Send SOL to the provided wallet address
5. Paste transaction signature to verify payment
6. Receive download link upon successful verification

## Security

- Admin access is restricted to specified Telegram user IDs
- Transaction verification is done through Helius API
- All sensitive data is stored in environment variables

## Contributing

Feel free to submit issues and enhancement requests! 