import logging
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

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- STATE DEFINITIONS ---
(
    NAMING, COMPANY, 
    AIRLINE, AWB, SPECS, DIMS, RATES, ADDRESSES, 
    CONFIRM, EDIT_FIELD, UPLOAD_PROOF, 
    SET_RATE, REJECT_REASON
) = range(13)

def main():
    print("🚀 Starting AERP Local Mode...")
    print("Priority Logic: Dashboard buttons now have global precedence.")
    
    # Initialize the Application
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()

    # --- 1. GLOBAL HIGH-PRIORITY HANDLERS ---
    # These are registered FIRST. They will interrupt any conversation (like shipment entry)
    # when a dashboard button is pressed. This fixes your "Buttons don't do anything" problem.
    
    application.add_handler(MessageHandler(filters.Text("📦 New Shipment"), shipment_handler.start_new_shipment))
    application.add_handler(MessageHandler(filters.Text("🔍 Track My Shipments"), shipment_handler.track_shipments))
    application.add_handler(MessageHandler(filters.Text("👤 My Profile"), shipment_handler.view_profile))
    application.add_handler(MessageHandler(filters.Text("👑 Admin Settings"), admin_handler.open_admin_settings))
    application.add_handler(MessageHandler(filters.Text("🛠 Staff Panel"), shipment_handler.track_shipments))

    # --- 2. GLOBAL CALLBACK HANDLERS ---
    # Handlers for the Admin Channel and universal 'Back' logic
    application.add_handler(CallbackQueryHandler(admin_handler.handle_rate_callback, pattern="^rate_"))
    application.add_handler(CallbackQueryHandler(admin_handler.handle_payment_callback, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_handler.handle_user_approval, pattern="^usr_"))
    application.add_handler(CallbackQueryHandler(start_handler.start, pattern="^back_to_main$"))
    application.add_handler(CallbackQueryHandler(shipment_handler.start_proof_upload, pattern="^start_upload_"))
    
    # --- 3. CONVERSATION HANDLER ---
    # Handles specific step-by-step logic
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_handler.start),
            CallbackQueryHandler(shipment_handler.start_new_shipment, pattern="^new_shipment$"),
            CallbackQueryHandler(shipment_handler.view_profile, pattern="^view_profile$"),
            CallbackQueryHandler(shipment_handler.track_shipments, pattern="^track_shipment$"),
        ],
        states={
            # Phase 0: Registration
            NAMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_handler.handle_registration_name)],
            COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_handler.handle_registration_company)],
            
            # Phase 1: Creation
            AIRLINE: [CallbackQueryHandler(shipment_handler.handle_airline, pattern="^air_")],
            AWB: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_awb)],
            SPECS: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_specs)],
            DIMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_dims)],
            RATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_rates)],
            ADDRESSES: [MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_handler.handle_addresses)],
            
            CONFIRM: [
                CallbackQueryHandler(shipment_handler.handle_confirm_and_request_review, pattern="^confirm_shipment$"),
                CallbackQueryHandler(shipment_handler.open_edit_menu_handler, pattern="^open_edit_menu$"),
                CallbackQueryHandler(shipment_handler.handle_addresses, pattern="^back_to_summary$")
            ],
            
            EDIT_FIELD: [
                CallbackQueryHandler(edit_handler.process_edit_selection, pattern="^edit_field_"),
                CallbackQueryHandler(shipment_handler.handle_airline, pattern="^air_"),
                CallbackQueryHandler(shipment_handler.handle_addresses, pattern="^back_to_summary$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.save_edit_input)
            ],
            
            # Phase 2: Upload
            UPLOAD_PROOF: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, shipment_handler.handle_file_upload)
            ],
            
            REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.save_rejection_reason)],
        },
        fallbacks=[
            CommandHandler("start", start_handler.start),
            CallbackQueryHandler(start_handler.start, pattern="^cancel_action$")
        ],
        allow_reentry=True
    )

    application.add_handler(conv_handler)

    # Start the Bot
    print("✅ AERP Live. Dashboard priority active. No bolding enabled.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()