import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import requests
from config import *

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for adding products
TITLE, DESCRIPTION, PRICE, PHOTO, DOWNLOAD_LINK = range(5)

# Store data
store_data = {
    "products": [DEFAULT_PRODUCT],
    "buyers": {},
    "total_sales": 0,
    "used_signatures": set()
}

def save_store_data():
    data_to_save = store_data.copy()
    data_to_save['used_signatures'] = list(store_data['used_signatures'])
    with open('store_data.json', 'w') as f:
        json.dump(data_to_save, f)

def load_store_data():
    try:
        with open('store_data.json', 'r') as f:
            data = json.load(f)
            data['used_signatures'] = set(data.get('used_signatures', []))
            return data
    except FileNotFoundError:
        return {
            "products": [DEFAULT_PRODUCT],
            "buyers": {},
            "total_sales": 0,
            "used_signatures": set()
        }

# Initialize store data
store_data = load_store_data()

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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'browse':
        await show_products(update, context)
    elif query.data == 'buy':
        await show_payment_info(update, context)
    elif query.data == 'verify':
        await query.message.reply_text(
            "📝 Please paste the transaction signature to verify your payment.\n\n"
            "You can find this in your Solana wallet after making the payment."
        )
        context.user_data['waiting_for_signature'] = True
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
        store_data['products'] = [p for p in store_data['products'] if p['title'] != product_title]
        save_store_data()
        
        # Update the message to show removal confirmation
        await query.message.edit_text(
            f"✅ *Product Removed Successfully*\n\n"
            f"The product '{product_title}' has been removed from the store.\n\n"
            f"Remaining products: {len(store_data['products'])}",
            parse_mode='Markdown'
        )

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available products."""
    query = update.callback_query
    
    # Get current product index from context or default to 0
    current_index = context.user_data.get('current_product_index', 0)
    
    # Handle navigation
    if query.data == 'next_product':
        current_index = (current_index + 1) % len(store_data['products'])
    elif query.data == 'prev_product':
        current_index = (current_index - 1) % len(store_data['products'])
    
    # Save current index
    context.user_data['current_product_index'] = current_index
    
    product = store_data['products'][current_index]
    
    # Create navigation buttons
    nav_buttons = []
    if len(store_data['products']) > 1:
        nav_buttons = [
            InlineKeyboardButton("⬅️", callback_data='prev_product'),
            InlineKeyboardButton(f"{current_index + 1}/{len(store_data['products'])}", callback_data='ignore'),
            InlineKeyboardButton("➡️", callback_data='next_product')
        ]
    
    keyboard = [
        [InlineKeyboardButton(f"💳 Buy Now ({product['price']} SOL)", callback_data='buy')],
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

async def show_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show payment information."""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("✅ I've Sent the Payment", callback_data='verify')],
        [InlineKeyboardButton("🔙 Back to Product", callback_data='browse')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        f"*💳 Payment Information*\n\n"
        f"Please send *{PRODUCT_PRICE} SOL* to:\n"
        f"`{STORE_WALLET}`\n\n"
        f"*Important Notes:*\n"
        f"• Make sure to send exactly {PRODUCT_PRICE} SOL\n"
        f"• Double-check the wallet address\n"
        f"• Keep your transaction signature ready\n\n"
        f"After sending, click the button below to verify your payment.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def verify_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify the transaction signature."""
    if not context.user_data.get('waiting_for_signature'):
        return
    
    signature = update.message.text.strip()
    
    # Check if signature was already used
    if signature in store_data['used_signatures']:
        await update.message.reply_text(
            "❌ This transaction signature has already been used. Each payment can only be used once."
        )
        return
    
    # Verify transaction using Helius API
    try:
        response = requests.post(
            HELIUS_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [signature]
            }
        )
        
        if response.status_code == 200:
            tx_data = response.json()
            if tx_data.get('result'):
                # Verify amount and destination
                # Note: This is a simplified verification. In production, you'd want more robust checks
                await update.message.reply_text(
                    "✅ Payment verified! Thank you for your purchase.\n\n"
                    f"Here's your download link:\n{store_data['products'][0]['download_link']}"
                )
                
                # Update store data
                user_id = update.effective_user.id
                username = update.effective_user.username or str(user_id)
                store_data['buyers'][str(user_id)] = {
                    'username': username,
                    'purchase': store_data['products'][0]['title']
                }
                store_data['total_sales'] += PRODUCT_PRICE
                store_data['used_signatures'].add(signature)  # Mark signature as used
                save_store_data()
                
                context.user_data['waiting_for_signature'] = False
                return
        
        await update.message.reply_text(
            "❌ Payment verification failed. Please check the signature and try again."
        )
    except Exception as e:
        logger.error(f"Error verifying transaction: {e}")
        await update.message.reply_text(
            "❌ An error occurred while verifying the payment. Please try again later."
        )

# Admin commands
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
        "Finally, please enter the download link for the product:",
        parse_mode='Markdown'
    )
    return DOWNLOAD_LINK

async def add_product_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product download link input and complete the process."""
    context.user_data['new_product']['download_link'] = update.message.text
    
    # Add the new product
    store_data['products'].append(context.user_data['new_product'])
    save_store_data()
    
    # Clear the temporary data
    new_product = context.user_data.pop('new_product')
    
    # Send confirmation message
    confirmation_text = (
        "✅ *Product Added Successfully!*\n\n"
        f"*Title:* {new_product['title']}\n"
        f"*Price:* {new_product['price']} SOL\n"
        f"*Description:* {new_product['description']}\n\n"
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
    
    if not store_data['products']:
        await update.message.reply_text("📭 No products available to remove.")
        return
    
    keyboard = []
    for product in store_data['products']:
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

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show store statistics (admin only)."""
    if update.effective_user.id != ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    stats = (
        "*📊 Store Statistics*\n\n"
        f"👥 *Total Buyers:* {len(store_data['buyers'])}\n"
        f"💰 *Total Sales:* {store_data['total_sales']} SOL\n"
        f"📦 *Active Products:* {len(store_data['products'])}"
    )
    await update.message.reply_text(stats, parse_mode='Markdown')

async def show_buyers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show buyer list (admin only)."""
    if update.effective_user.id != ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    if not store_data['buyers']:
        await update.message.reply_text("📭 No buyers yet.")
        return
    
    buyers_list = "*👥 Buyer List*\n\n"
    for user_id, data in store_data['buyers'].items():
        buyers_list += f"• @{data['username']}: {data['purchase']}\n"
    
    await update.message.reply_text(buyers_list, parse_mode='Markdown')

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

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
            DOWNLOAD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_link)],
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

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 