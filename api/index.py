import os
import asyncio
from fastapi import FastAPI, Request, Response
from telegram import Update, constants
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ConversationHandler, 
    filters
)

# AERP Core Imports
from core.config import Config
from core.handlers import (
    start_handler, 
    shipment_handler, 
    admin_handler, 
    edit_handler
)

# Initialize FastAPI app
app = FastAPI()

# Initialize Telegram Application
# We use a global variable to reuse the application instance in serverless warm starts
tg_app = Application.builder().token(Config.TELEGRAM_TOKEN).build()

# --- STATE DEFINITIONS ---
# Matching all previous Eureka milestones
(
    NAMING, COMPANY, 
    AIRLINE, AWB, SPECS, DIMS, RATES, ADDRESSES, 
    CONFIRM, EDIT_FIELD, UPLOAD_PROOF, 
    SET_RATE, REJECT_REASON
) = range(13)

# --- CONVERSATION HANDLER SETUP ---
# This manages the entire user lifecycle from registration to shipment creation
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start_handler.start),
        CallbackQueryHandler(shipment_handler.start_new_shipment, pattern="^new_shipment$"),
        CallbackQueryHandler(admin_handler.open_admin_settings, pattern="^admin_settings$"),
    ],
    states={
        # Milestone 2: Registration
        NAMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_handler.handle_registration_name)],
        COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_handler.handle_registration_company)],
        
        # Milestone 3: Shipment Creation
        AIRLINE: [CallbackQueryHandler(shipment_handler.handle_airline, pattern="^air_")],
        AWB: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_awb)],
        SPECS: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_specs)],
        DIMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_dims)],
        RATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_rates)],
        ADDRESSES: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_addresses)],
        
        # Milestone 4: The Review & Confirmation Hub
        CONFIRM: [
            CallbackQueryHandler(shipment_handler.handle_confirm_and_request_files, pattern="^confirm_shipment$"),
            CallbackQueryHandler(shipment_handler.open_edit_menu_handler, pattern="^open_edit_menu$"),
            CallbackQueryHandler(shipment_handler.handle_addresses, pattern="^back_to_summary$")
        ],
        
        # Milestone 4 & 6: The "Everything Editable" Engine
        EDIT_FIELD: [
            CallbackQueryHandler(edit_handler.process_edit_selection, pattern="^edit_field_"),
            CallbackQueryHandler(shipment_handler.handle_airline, pattern="^air_"), # For airline edits
            CallbackQueryHandler(shipment_handler.handle_addresses, pattern="^back_to_summary$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.save_edit_input)
        ],
        
        # Milestone 5: File Upload Workflow
        UPLOAD_PROOF: [
            MessageHandler(filters.PHOTO | filters.Document.ALL, shipment_handler.handle_file_upload)
        ],

        # Milestone 6: Admin Actions
        REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.save_rejection_reason)],
    },
    fallbacks=[
        CommandHandler("start", start_handler.start),
        CallbackQueryHandler(start_handler.start, pattern="^back_to_main$"),
        CallbackQueryHandler(start_handler.start, pattern="^cancel_action$")
    ],
    allow_reentry=True,
    name="aerp_main_conversation"
)

# Register handlers to the application
tg_app.add_handler(conv_handler)

# Global Callback Handlers (Actions that happen outside of the specific wizard flow)
# These handle User Approvals and Payment Approvals from the Admin Channel
tg_app.add_handler(CallbackQueryHandler(admin_handler.handle_payment_callback, pattern="^pay_"))
tg_app.add_handler(CallbackQueryHandler(admin_handler.handle_user_approval, pattern="^usr_"))

# --- VERCEL SERVERLESS ROUTE ---

@app.post("/")
async def process_update(request: Request):
    """
    This is the primary endpoint for Telegram Webhooks.
    Vercel calls this function every time a message is sent to the bot.
    """
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        
        # Use asyncio to process the update within the PTB framework
        async with tg_app:
            await tg_app.process_update(update)
            
        return Response(status_code=200)
    except Exception as e:
        print(f"Error processing update: {e}")
        return Response(status_code=500)

@app.get("/")
async def health_check():
    """Simple check to confirm the bot is online"""
    return {
        "status": "AERP Online",
        "system": "Advanced Enterprise Resource Planner for Cargo",
        "version": "1.0.0-Eureka"
    }

# Entry point for local testing (not used by Vercel)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)