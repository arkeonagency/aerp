import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters,
    ContextTypes
)

# AERP Core Imports
from core.config import Config
from core.database.supabase_client import db
from core.handlers import (
    start_handler, 
    shipment_handler, 
    admin_handler
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def master_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    THE CENTRAL BRAIN (Master Message Router)
    Routes all text/media based on the user state stored in Supabase.
    Priority Logic: Dashboard buttons always override any state.
    """
    if not update.message: return
    
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""
    user = db.get_user(user_id)

    # 1. Handle Unregistered Users
    if not user:
        if text == "/start":
            await start_handler.start(update, context)
        else:
            await start_handler.handle_registration_name(update, context)
        return

    # 2. GLOBAL DASHBOARD PRIORITY (Overwrites States)
    if text == "📦 New Shipment":
        await shipment_handler.start_new_shipment(update, context)
        return
    elif text == "🔍 Track My Shipments":
        await shipment_handler.track_shipments(update, context)
        return
    elif text == "👤 My Profile":
        await shipment_handler.view_profile(update, context)
        return
    elif text == "🛠 Staff Panel":
        await admin_handler.open_staff_panel(update, context)
        return
    elif text == "👑 Admin Settings":
        await admin_handler.open_admin_settings(update, context)
        return
    elif text == "🏠 Back to Menu":
        db.update_user_state(user_id, None)
        await start_handler.start(update, context)
        return

    # 3. STATE-BASED ROUTING (Reads from Supabase)
    state = user.get('state')
    if not state:
        return

    # Registration States
    if state == "REG_NAME":
        await start_handler.handle_registration_name(update, context)
    elif state == "REG_COMPANY":
        await start_handler.handle_registration_company(update, context)
    
    # Shipment Wizard (Airline, Origin, Dest, AWB, etc.) & Edit Engine States
    elif state.startswith("SHIP_") or state.startswith("EDIT_INPUT_"):
        await shipment_handler.handle_shipment_text_input(update, context, user, text)
    
    # Phase 2: Payment Upload States (Receives Photo or PDF)
    elif state.startswith("UPLOAD_"):
        await shipment_handler.handle_phase2_upload(update, context, user)
    
    # Admin/Staff States (Exchange Rate, Announcements, Rejection Comments)
    elif state == "SET_EXCHANGE" or state.startswith("REJECT_") or state == "ADM_BROADCAST":
        await admin_handler.handle_admin_msg(update, context)

async def master_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    THE CENTRAL CALLBACK BRAIN
    Routes all Inline Button clicks for the entire organization.
    """
    query = update.callback_query
    data = query.data

    # --- Shipment Creation & Editing Logic ---
    # Catching: Confirmation, Edit Menu, History Selection, Navigation
    if (data == "confirm_shipment" or 
        data == "open_edit_menu" or 
        data.startswith("edit_field_") or 
        data == "back_to_summary" or
        data.startswith("edit_hist_") or
        data == "back_step" or
        data == "cancel_wizard"):
        await shipment_handler.handle_shipment_callbacks(update, context)
    
    # --- Admin & Staff Management Logic ---
    # Catching: Rate/Payment Approvals, User Management, Staff Lifecycle
    elif (data.startswith("rate_") or 
          data.startswith("pay_") or 
          data.startswith("usr_") or
          data.startswith("st_upd_") or
          data.startswith("adm_") or
          data == "set_ex_rate" or 
          data == "admin_settings"):
        await admin_handler.handle_admin_callbacks(update, context)
    
    # --- Phase 2: User Trigger ---
    # User clicks "Upload Payment Proof" from their chat notification
    elif data.startswith("start_upload_"):
        await shipment_handler.start_proof_upload(update, context)
    
    # --- UI & Profile Navigation ---
    elif data == "track_shipment":
        await shipment_handler.track_shipments(update, context)
    elif data == "view_profile":
        await shipment_handler.view_profile(update, context)
    
    # --- Universal State Reset (Back to Main) ---
    elif data == "back_to_main":
        user_id = update.effective_user.id
        db.update_user_state(user_id, None)
        await start_handler.start(update, context)

def main():
    print("🚀 Starting AERP Local Mode [Checkpoint ARK Final]")
    print("Logic: Manual Route Entry and Dashboard Priority Routing Active.")
    
    # Initialize the Application
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()

    # Register the Master Routers
    # Group 0: Messages (Dashboard + Wizard text input + Proof media)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, master_message_router), group=0)
    
    # Group 0: Callbacks (All Inline Buttons)
    application.add_handler(CallbackQueryHandler(master_callback_router), group=0)
    
    # Group 0: Command /start
    application.add_handler(CommandHandler("start", start_handler.start))

    # Deployment Note: This Master Router is 100% compatible with the api/index.py webhook
    print("✅ AERP Live. User editing and manual airline entry are now responsive.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()