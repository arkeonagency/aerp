import logging
import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
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

# Initialize FastAPI app
app = FastAPI()

# Initialize the Bot Application (Global instance for Vercel reuse)
ptb_application = Application.builder().token(Config.TELEGRAM_TOKEN).build()

# --- THE CENTRAL BRAIN: MASTER MESSAGE ROUTER ---

async def master_message_router(update: Update, context):
    """
    Routes all text/media inputs.
    Vercel processes this on every single webhook hit.
    """
    if not update.message:
        return
    
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""
    user = db.get_user(user_id)

    # 1. HANDLE UNREGISTERED USERS
    if not user:
        if text == "/start":
            await start_handler.start(update, context)
        else:
            # Catch registration flow inputs (Name/Company)
            await start_handler.handle_registration_name(update, context)
        return

    # 2. GLOBAL DASHBOARD OVERRIDES (Priority Logic)
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

    # 3. STATE-BASED ROUTING (Reads current step from Supabase)
    state = user.get('state')
    if not state:
        return

    # User Registration Flow
    if state == "REG_NAME":
        await start_handler.handle_registration_name(update, context)
    elif state == "REG_COMPANY":
        await start_handler.handle_registration_company(update, context)
    
    # Phase 1 & Edit Engine: Creation Wizard & Modifications
    elif state.startswith("SHIP_") or state.startswith("EDIT_INPUT_"):
        await shipment_handler.handle_shipment_text_input(update, context, user, text)
    
    # Phase 2: Payment Receipt Upload (Handles Photos and Documents)
    elif state.startswith("UPLOAD_"):
        await shipment_handler.handle_phase2_upload(update, context, user)
    
    # Admin System Management (Exchange Rate, Broadcasts, Rejection Comments)
    elif state == "SET_EXCHANGE" or state == "ADM_BROADCAST" or state.startswith("REJECT_"):
        await admin_handler.handle_admin_msg(update, context)

# --- THE CENTRAL CALLBACK BRAIN: MASTER CALLBACK ROUTER ---

async def master_callback_router(update: Update, context):
    """
    Routes all Inline Button clicks for the entire organization.
    """
    query = update.callback_query
    data = query.data

    # --- Shipment Wizard & Editing Buttons ---
    if (data == "confirm_shipment" or 
        data == "open_edit_menu" or 
        data.startswith("edit_field_") or 
        data == "back_to_summary" or
        data.startswith("edit_hist_") or
        data == "back_step" or
        data == "cancel_wizard"):
        await shipment_handler.handle_shipment_callbacks(update, context)
    
    # --- Admin Decision & Management Buttons ---
    elif (data.startswith("rate_") or 
          data.startswith("pay_") or 
          data.startswith("usr_") or
          data.startswith("st_upd_") or
          data.startswith("adm_") or
          data == "set_ex_rate" or 
          data == "admin_settings"):
        await admin_handler.handle_admin_callbacks(update, context)
    
    # --- Phase 2 Initiation ---
    elif data.startswith("start_upload_"):
        await shipment_handler.start_proof_upload(update, context)
    
    # --- Universal Navigation ---
    elif data == "track_shipment":
        await shipment_handler.track_shipments(update, context)
    elif data == "view_profile":
        await shipment_handler.view_profile(update, context)
    elif data == "back_to_main":
        user_id = update.effective_user.id
        db.update_user_state(user_id, None)
        await start_handler.start(update, context)

# --- VERCEL INFRASTRUCTURE ---

# Register the logic into the PTB instance
ptb_application.add_handler(CommandHandler("start", start_handler.start))
ptb_application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, master_message_router))
ptb_application.add_handler(CallbackQueryHandler(master_callback_router))

@app.post("/api/index")
async def webhook(request: Request):
    """
    Main Webhook Entry Point.
    Processes the JSON post from Telegram servers.
    """
    try:
        # Check if the application is currently running
        if not ptb_application.running:
            await ptb_application.initialize()
            
        data = await request.json()
        update = Update.de_json(data, ptb_application.bot)
        
        # Process the update through our routers
        await ptb_application.process_update(update)
        
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Webhook Error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/")
async def index():
    return {"message": "AERP Enterprise Bot is active and running on Vercel."}