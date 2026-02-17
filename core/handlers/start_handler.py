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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    The entry point for all users.
    Uses Database State Machine and respects Multi-Admin Config.
    """
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    query = update.callback_query
    if query:
        await query.answer()
    
    # CASE 1: User is not in the database - Initialize Registration
    if not user:
        # Check if this user is defined as an Admin in config
        is_system_admin = user_id in Config.ADMIN_IDS
        
        # Create a record. If they are a system admin, they are auto-approved.
        db.create_user({
            "telegram_id": user_id,
            "username": update.effective_user.username or "NoUsername",
            "full_name": "Pending",
            "company_name": "Pending",
            "role": "admin" if is_system_admin else "user",
            "is_approved": True if is_system_admin else False,
            "state": "REG_NAME"
        })
        
        text = (
            "🚀 Welcome to AERP Cargo System\n\n"
            "Your account is not registered. To gain access, please provide your details for review.\n\n"
            "Please enter your Full Name:"
        )
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    # CASE 2: User exists but registration is incomplete
    state = user.get('state')
    if state == "REG_NAME":
        await update.message.reply_text("Please enter your Full Name to continue registration:")
        return
    elif state == "REG_COMPANY":
        await update.message.reply_text("Please enter your Company Name to finish registration:")
        return

    # CASE 3: User exists but Admin has not approved yet
    if not user['is_approved']:
        # Final check: if they were added to ADMIN_IDS after their first start, auto-approve them now
        if user_id in Config.ADMIN_IDS:
            db.approve_user(user_id, "admin")
            user = db.get_user(user_id) # Refresh user data
        else:
            text = (
                "⏳ Account Pending\n\n"
                "Your registration is currently under review by our staff.\n"
                "You will be notified as soon as your access is granted."
            )
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return

    # CASE 4: User is approved (Admin, Staff, or User)
    welcome_text = (
        f"👋 Hello, {user['full_name']}!\n"
        f"Role: {user['role'].upper()}\n"
        f"Company: {user['company_name']}\n\n"
        f"Select an option from the menu below to proceed."
    )
    
    dashboard = get_main_dashboard(user['role'])
    
    if query:
        await query.message.reply_text(welcome_text, reply_markup=dashboard)
    else:
        await update.message.reply_text(welcome_text, reply_markup=dashboard)

async def handle_registration_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves Name to DB and moves state to REG_COMPANY. Role is never touched here."""
    user_id = update.effective_user.id
    name_input = update.message.text

    if name_input in ["📦 New Shipment", "🔍 Track My Shipments", "👤 My Profile", "🛠 Staff Panel", "👑 Admin Settings"]:
        await update.message.reply_text("⚠️ Registration in progress. Please enter your Full Name:")
        return

    # Update ONLY full_name and state. Role remains what it was (admin/user).
    db.supabase.table("profiles").update({
        "full_name": name_input,
        "state": "REG_COMPANY"
    }).eq("telegram_id", user_id).execute()

    await update.message.reply_text(f"Thank you, {name_input}.\nNow, please enter your Company Name:")

async def handle_registration_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalizes registration details and notifies Admin Channel."""
    user_id = update.effective_user.id
    company_input = update.message.text
    
    if company_input in ["📦 New Shipment", "🔍 Track My Shipments", "👤 My Profile", "🛠 Staff Panel", "👑 Admin Settings"]:
        await update.message.reply_text("⚠️ Registration in progress. Please enter your Company Name:")
        return

    # Update ONLY company_name and clear state. Role remains untouched.
    db.supabase.table("profiles").update({
        "company_name": company_input,
        "state": None
    }).eq("telegram_id", user_id).execute()

    user = db.get_user(user_id)

    # If they are already approved (auto-admin), show dashboard
    if user['is_approved']:
        await update.message.reply_text(
            f"✅ Profile updated! Welcome to the Admin team, {user['full_name']}.",
            reply_markup=get_main_dashboard(user['role'])
        )
    else:
        # Standard user needs to wait
        await update.message.reply_text(
            "✅ Registration Submitted!\n"
            "Staff will review your request and you will receive a notification here once approved."
        )
        
        # Notify Admin Channel
        admin_notif = (
            f"👤 New User Request\n\n"
            f"Name: {user['full_name']}\n"
            f"Company: {user['company_name']}\n"
            f"Telegram: @{update.effective_user.username or 'NoUsername'}\n"
            f"ID: {user_id}"
        )
        
        await context.bot.send_message(
            chat_id=Config.ADMIN_CHANNEL_ID,
            text=admin_notif,
            reply_markup=get_user_approval_keyboard(user_id)
        )