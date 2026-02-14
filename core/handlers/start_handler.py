from telegram import Update, constants
from telegram.ext import ContextTypes, ConversationHandler
from core.database.supabase_client import db
from core.utils.keyboards import (
    get_main_menu, 
    get_user_approval_keyboard, 
    get_back_to_main,
    get_main_dashboard
)
from core.config import Config

# Conversation states
NAMING, COMPANY = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    The entry point for all users. 
    Deployed via /start, 'Back' buttons, or manual dashboard resets.
    """
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    # Hybrid handling: Check if triggered by Inline Button (Callback) or Dashboard/Command (Message)
    query = update.callback_query
    if query:
        await query.answer()
    
    # CASE 1: User is not in the database at all
    if not user:
        text = (
            "🚀 Welcome to AERP Cargo System\n\n"
            "Your account is not registered. To gain access, please provide your details for Admin review.\n\n"
            "Please enter your Full Name:"
        )
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return NAMING

    # CASE 2: User exists but Admin has not clicked Approve yet
    if not user['is_approved']:
        text = "⏳ Account Pending\n\nYour registration is currently under review by our staff. You will be notified once approved."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

    # CASE 3: User is approved - Trigger the Persistent Bottom Dashboard
    welcome_text = (
        f"👋 Hello, {user['full_name']}!\n"
        f"Role: {user['role'].upper()}\n"
        f"Company: {user['company_name']}\n\n"
        f"The dashboard menu is available at the bottom of your screen. Select an option to proceed."
    )
    
    # get_main_dashboard provides the ReplyKeyboardMarkup (The 'always-there' buttons)
    dashboard = get_main_dashboard(user['role'])
    
    if query:
        # If we are editing an inline message, we send a new message to 'pop up' the dashboard
        await query.message.reply_text(welcome_text, reply_markup=dashboard)
    else:
        # Standard response to /start or text message
        await update.message.reply_text(welcome_text, reply_markup=dashboard)
        
    return ConversationHandler.END

async def handle_registration_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the name input during registration."""
    # Check if the user tried to click a dashboard button before they were approved
    if update.message.text in ["📦 New Shipment", "🔍 Track My Shipments", "👤 My Profile"]:
        await update.message.reply_text("❌ Your account is not approved yet. Please finish entering your name:")
        return NAMING

    context.user_data['reg_full_name'] = update.message.text
    await update.message.reply_text("🏢 Enter your Company Name:")
    return COMPANY

async def handle_registration_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalizes registration, saves to Supabase, and notifies Admin Channel."""
    user_id = update.effective_user.id
    full_name = context.user_data.get('reg_full_name')
    company = update.message.text
    username = update.effective_user.username or "NoUsername"
    
    # Save new record to Supabase
    db.create_user({
        "telegram_id": user_id,
        "username": username,
        "full_name": full_name,
        "company_name": company,
        "role": "user",
        "is_approved": False
    })

    await update.message.reply_text("✅ Registration Submitted!\nStaff will review your request and you will be notified here.")
    
    # Notify Admin Channel (Standard text format, no bolding)
    admin_notif = (
        f"👤 New User Request\n\n"
        f"Name: {full_name}\n"
        f"Company: {company}\n"
        f"Telegram: @{username}\n"
        f"ID: {user_id}"
    )
    
    await context.bot.send_message(
        chat_id=Config.ADMIN_CHANNEL_ID,
        text=admin_notif,
        reply_markup=get_user_approval_keyboard(user_id)
    )
    return ConversationHandler.END