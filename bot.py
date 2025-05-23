import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import requests
from config import *
from database import Database
import telegram
import asyncio
import os
from dotenv import load_dotenv

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add file handler for persistent logging
file_handler = logging.FileHandler('bot.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Load environment variables
load_dotenv()

# Verify required environment variables
required_vars = ['BOT_TOKEN', 'ADMIN_IDS', 'STORE_WALLET', 'HELIUS_API_KEY']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Conversation states for adding products
TITLE, DESCRIPTION, PRICE, PHOTO, DOWNLOAD_CONTENT = range(5)

# Initialize database
try:
    db = Database()
    logger.info("Database connection established successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when the command /start is issued."""
    # Reset product index when starting
    context.user_data['current_product_index'] = 0
    
    keyboard = [
        [InlineKeyboardButton("🛍 Browse Store", callback_data='browse')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 *Welcome to TeenBucks Store!*\n\n"
        "Your gateway to Solana memecoin success. 🚀\n\n"
        "Browse our digital products and start your journey today!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available products."""
    query = update.callback_query
    
    # Get all products from database
    products = db.get_all_products()
    if not products:
        await query.message.edit_text(
            "📭 No products available at the moment.",
            parse_mode='Markdown'
        )
        return
    
    # Get current product index from context or default to 0
    current_index = context.user_data.get('current_product_index', 0)
    
    # Handle navigation
    if query.data == 'next_product':
        current_index = (current_index + 1) % len(products)
    elif query.data == 'prev_product':
        current_index = (current_index - 1) % len(products)
    
    # Save current index
    context.user_data['current_product_index'] = current_index
    
    product = products[current_index]
    
    # Create navigation buttons
    nav_buttons = []
    if len(products) > 1:
        nav_buttons = [
            InlineKeyboardButton("⬅️", callback_data='prev_product'),
            InlineKeyboardButton(f"{current_index + 1}/{len(products)}", callback_data='ignore'),
            InlineKeyboardButton("➡️", callback_data='next_product')
        ]
    
    keyboard = [
        [InlineKeyboardButton(f"💳 Buy Now ({product['price']} SOL)", callback_data=f'buy_{product["id"]}')],
        nav_buttons,
        [InlineKeyboardButton("🔄 Refresh", callback_data='browse')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    product_text = (
        f"*🎯 {product['title']}*\n\n"
        f"💰 *Price:* {product['price']} SOL\n\n"
        f"📝 *Description:*\n{product['description']}\n\n"
        f"Click the button below to purchase!"
    )
    
    if product.get('photo_id'):
        await query.message.edit_media(
            media=InputMediaPhoto(
                media=product['photo_id'],
                caption=product_text,
                parse_mode='Markdown'
            ),
            reply_markup=reply_markup
        )
    else:
        await query.message.edit_text(
            product_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'browse':
        await show_products(update, context)
    elif query.data.startswith('buy_'):
        # Extract product ID from callback data
        product_id = int(query.data.split('_')[1])
        product = db.get_product_by_id(product_id)
        
        if not product:
            await query.message.edit_text(
                "❌ Product not found.",
                parse_mode='Markdown'
            )
            return
        
        # Store the product ID in context for verification
        context.user_data['current_product_id'] = product_id
        
        keyboard = [
            [InlineKeyboardButton("✅ I've Sent the Payment", callback_data=f'verify_{product_id}')],
            [InlineKeyboardButton("🔙 Back to Product", callback_data='browse')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"*💳 Payment Information*\n\n"
            f"Please send *{product['price']} SOL* to:\n"
            f"`{STORE_WALLET}`\n\n"
            f"*Important Notes:*\n"
            f"• Make sure to send exactly {product['price']} SOL\n"
            f"• Double-check the wallet address\n"
            f"• Keep your transaction signature ready\n\n"
            f"After sending, click the button below to verify your payment.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif query.data.startswith('verify_'):
        # Extract product ID from callback data
        product_id = int(query.data.split('_')[1])
        context.user_data['current_product_id'] = product_id
        context.user_data['waiting_for_signature'] = True
        
        await query.message.reply_text(
            "📝 Please paste the transaction signature to verify your payment.\n\n"
            "You can find this in your Solana wallet after making the payment."
        )
    elif query.data in ['next_product', 'prev_product']:
        await show_products(update, context)
    elif query.data == 'ignore':
        # Do nothing for the page counter button
        pass
    elif query.data == 'cancel_remove':
        await query.message.edit_text(
            "❌ Product removal cancelled.",
            parse_mode='Markdown'
        )
    elif query.data.startswith('remove_'):
        # Handle product removal
        product_title = query.data.replace('remove_', '')
        db.remove_product(product_title)
        
        # Update the message to show removal confirmation
        await query.message.edit_text(
            f"✅ *Product Removed Successfully*\n\n"
            f"The product '{product_title}' has been removed from the store.",
            parse_mode='Markdown'
        )

async def verify_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify the transaction signature."""
    if not context.user_data.get('waiting_for_signature'):
        return
    
    signature = update.message.text.strip()
    
    # Validate signature format
    if not signature or len(signature) < 32:
        await update.message.reply_text(
            "❌ Invalid transaction signature format. Please provide a valid Solana transaction signature."
        )
        return
    
    # Check if signature was already used
    if db.is_signature_used(signature):
        await update.message.reply_text(
            "❌ This transaction signature has already been used. Each payment can only be used once."
        )
        return
    
    # Get the product being purchased
    product_id = context.user_data.get('current_product_id')
    if not product_id:
        await update.message.reply_text(
            "❌ Product information not found. Please try the purchase process again."
        )
        return
        
    product = db.get_product_by_id(product_id)
    if not product:
        await update.message.reply_text(
            "❌ Product not found. Please try again."
        )
        return
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        "⏳ Verifying your payment... Please wait."
    )
    
    # Verify transaction using Helius API with retries
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                HELIUS_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [signature]
                },
                timeout=10  # Add timeout
            )
            
            if response.status_code == 200:
                tx_data = response.json()
                
                if tx_data.get('result'):
                    # Verify transaction details
                    tx_result = tx_data['result']
                    
                    # Check if transaction is confirmed
                    if not tx_result.get('meta', {}).get('status', {}).get('Ok'):
                        await processing_msg.edit_text(
                            "❌ Transaction is not confirmed yet. Please wait a few moments and try again."
                        )
                        return
                    
                    # Send the product content
                    try:
                        if product.get('is_file'):
                            await update.message.reply_document(
                                document=product['download_content'],
                                caption="✅ *Payment verified! Thank you for your purchase.*\n\n"
                                       "Here's your purchased file!",
                                parse_mode='Markdown'
                            )
                        elif product.get('download_content'):
                            await update.message.reply_text(
                                "✅ *Payment verified! Thank you for your purchase.*\n\n"
                                f"Here's your download link:\n{product['download_content']}",
                                parse_mode='Markdown'
                            )
                        else:
                            await update.message.reply_text(
                                "✅ *Payment verified! Thank you for your purchase.*\n\n"
                                "Thank you for your purchase!",
                                parse_mode='Markdown'
                            )
                        
                        # Save purchase record
                        user_id = update.effective_user.id
                        username = update.effective_user.username or str(user_id)
                        db.save_purchase(user_id, username, product_id, signature)
                        
                        # Clear the waiting state
                        context.user_data['waiting_for_signature'] = False
                        context.user_data.pop('current_product_id', None)
                        
                        # Delete processing message
                        await processing_msg.delete()
                        return
                        
                    except Exception as e:
                        logger.error(f"Error sending product content: {e}")
                        await processing_msg.edit_text(
                            "❌ Error delivering product content. Please contact support."
                        )
                        return
                
                await processing_msg.edit_text(
                    "❌ Transaction not found. Please make sure you've sent the correct signature."
                )
                return
                
            elif response.status_code == 429:  # Rate limit
                if attempt < max_retries - 1:
                    await processing_msg.edit_text(
                        f"⏳ Rate limit reached. Retrying in {retry_delay} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    await processing_msg.edit_text(
                        "❌ Rate limit reached. Please try again in a few minutes."
                    )
                    return
                    
            else:
                logger.error(f"Helius API error: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    await processing_msg.edit_text(
                        f"⏳ Error occurred. Retrying in {retry_delay} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    await processing_msg.edit_text(
                        "❌ Error verifying transaction. Please try again later."
                    )
                    return
                
        except requests.exceptions.Timeout:
            logger.error("Helius API request timed out")
            if attempt < max_retries - 1:
                await processing_msg.edit_text(
                    f"⏳ Request timed out. Retrying in {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)
                continue
            else:
                await processing_msg.edit_text(
                    "❌ Request timed out. Please try again later."
                )
                return
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during transaction verification: {e}")
            if attempt < max_retries - 1:
                await processing_msg.edit_text(
                    f"⏳ Network error. Retrying in {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)
                continue
            else:
                await processing_msg.edit_text(
                    "❌ Network error occurred. Please check your internet connection and try again."
                )
                return
                
        except Exception as e:
            logger.error(f"Unexpected error during transaction verification: {e}")
            await processing_msg.edit_text(
                "❌ An unexpected error occurred. Please try again later."
            )
            return
    
    await processing_msg.edit_text(
        "❌ Failed to verify transaction after multiple attempts. Please try again later."
    )

async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the product addition process."""
    if update.effective_user.id != ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 *Adding New Product*\n\n"
        "Please enter the product title:",
        parse_mode='Markdown'
    )
    return TITLE

async def add_product_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product title input."""
    context.user_data['new_product'] = {'title': update.message.text}
    
    await update.message.reply_text(
        "📝 *Product Title Set*\n\n"
        "Now, please enter the product description:",
        parse_mode='Markdown'
    )
    return DESCRIPTION

async def add_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product description input."""
    context.user_data['new_product']['description'] = update.message.text
    
    await update.message.reply_text(
        "💰 *Product Description Set*\n\n"
        "Now, please enter the product price in SOL (e.g., 0.1):",
        parse_mode='Markdown'
    )
    return PRICE

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product price input."""
    try:
        price = float(update.message.text)
        context.user_data['new_product']['price'] = price
        
        await update.message.reply_text(
            "🖼 *Product Price Set*\n\n"
            "Now, please send a photo for the product.\n"
            "Send /skip if you don't want to add a photo.",
            parse_mode='Markdown'
        )
        return PHOTO
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price format. Please enter a valid number (e.g., 0.1):"
        )
        return PRICE

async def add_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product photo input."""
    if update.message.text == '/skip':
        context.user_data['new_product']['photo_id'] = None
    else:
        # Get the largest photo size
        photo = update.message.photo[-1]
        context.user_data['new_product']['photo_id'] = photo.file_id
    
    await update.message.reply_text(
        "🔗 *Photo Set*\n\n"
        "Now, please either:\n"
        "1. Send a file to be delivered after purchase, or\n"
        "2. Enter a download link\n\n"
        "Send /skip if you don't want to add any content yet.",
        parse_mode='Markdown'
    )
    return DOWNLOAD_CONTENT

async def add_product_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product content input (file or download link)."""
    if update.message.text == '/skip':
        context.user_data['new_product']['download_content'] = None
        context.user_data['new_product']['is_file'] = False
    elif update.message.document:
        # Store file information
        context.user_data['new_product']['download_content'] = update.message.document.file_id
        context.user_data['new_product']['is_file'] = True
        context.user_data['new_product']['file_name'] = update.message.document.file_name
    else:
        # Store download link
        context.user_data['new_product']['download_content'] = update.message.text
        context.user_data['new_product']['is_file'] = False
    
    # Save the new product to database
    product_id = db.save_product(context.user_data['new_product'])
    
    # Clear the temporary data
    new_product = context.user_data.pop('new_product')
    
    # Send confirmation message
    confirmation_text = (
        "✅ *Product Added Successfully!*\n\n"
        f"*Title:* {new_product['title']}\n"
        f"*Price:* {new_product['price']} SOL\n"
        f"*Description:* {new_product['description']}\n"
        f"*Content Type:* {'File' if new_product.get('is_file') else 'Download Link'}\n\n"
        "The product is now available in the store!"
    )
    
    if new_product.get('photo_id'):
        await update.message.reply_photo(
            photo=new_product['photo_id'],
            caption=confirmation_text,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            confirmation_text,
            parse_mode='Markdown'
        )
    
    return ConversationHandler.END

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show store statistics (admin only)."""
    if update.effective_user.id != ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    total_sales = db.get_total_sales()
    buyers = db.get_buyers()
    products = db.get_all_products()
    
    stats = (
        "*📊 Store Statistics*\n\n"
        f"👥 *Total Buyers:* {len(buyers)}\n"
        f"💰 *Total Sales:* {total_sales} SOL\n"
        f"📦 *Active Products:* {len(products)}"
    )
    await update.message.reply_text(stats, parse_mode='Markdown')

async def show_buyers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show buyer list (admin only)."""
    if update.effective_user.id != ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    buyers = db.get_buyers()
    if not buyers:
        await update.message.reply_text("📭 No buyers yet.")
        return
    
    buyers_list = "*👥 Buyer List*\n\n"
    for buyer in buyers:
        buyers_list += f"• @{buyer['username']}: {buyer['product_title']}\n"
    
    await update.message.reply_text(buyers_list, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation."""
    context.user_data.pop('new_product', None)
    await update.message.reply_text(
        "❌ Operation cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a product (admin only)."""
    if update.effective_user.id != ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    products = db.get_all_products()
    if not products:
        await update.message.reply_text("📭 No products available to remove.")
        return
    
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            f"🗑 {product['title']} ({product['price']} SOL)",
            callback_data=f"remove_{product['title']}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data='cancel_remove')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🗑 *Select a product to remove:*\n\n"
        "Click on a product to remove it from the store.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot."""
    # Log the full error with traceback
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Get detailed error information
    error_type = type(context.error).__name__
    error_message = str(context.error)
    
    # Log specific error details
    logger.error(f"Error type: {error_type}")
    logger.error(f"Error message: {error_message}")
    
    if update:
        logger.error(f"Update: {update.to_dict()}")
    
    # Handle specific error types
    if isinstance(context.error, telegram.error.Conflict):
        logger.error("Bot instance conflict detected. Please ensure only one instance is running.")
        return
    
    elif isinstance(context.error, telegram.error.NetworkError):
        logger.error("Network error occurred. Please check your internet connection.")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Network error occurred. Please try again in a few moments."
            )
        return
    
    elif isinstance(context.error, telegram.error.BadRequest):
        logger.error(f"Bad request error: {error_message}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Invalid request. Please try again with correct parameters."
            )
        return
    
    elif isinstance(context.error, telegram.error.Unauthorized):
        logger.error("Bot token is invalid or has been revoked.")
        return
    
    elif isinstance(context.error, telegram.error.TimedOut):
        logger.error("Request timed out.")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Request timed out. Please try again."
            )
        return
    
    # For database errors
    elif isinstance(context.error, Exception) and "database" in error_message.lower():
        logger.error("Database error occurred.")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Database error occurred. Please try again later."
            )
        return
    
    # For other errors, try to notify the user with more specific message
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"❌ An error occurred: {error_type}\nPlease try again later or contact support if the issue persists."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

async def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Log startup
    logger.info("Starting bot application...")
    
    # Add conversation handler for adding products
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_product_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
            PHOTO: [
                MessageHandler(filters.PHOTO, add_product_photo),
                CommandHandler('skip', add_product_photo)
            ],
            DOWNLOAD_CONTENT: [
                MessageHandler(filters.Document.ALL, add_product_content),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_content),
                CommandHandler('skip', add_product_content)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("remove", remove_product))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("buyers", show_buyers))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_transaction))

    # Add error handler
    application.add_error_handler(error_handler)

    try:
        # Clean up any existing webhooks
        logger.info("Cleaning up existing webhooks...")
        await application.bot.delete_webhook(drop_pending_updates=True)
        
        # Start polling
        logger.info("Starting polling...")
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error during bot operation: {e}", exc_info=True)
        raise
    finally:
        # Ensure proper cleanup
        logger.info("Stopping bot application...")
        await application.stop()

if __name__ == '__main__':
    try:
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True) 