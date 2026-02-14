from telegram import Update, constants
from telegram.ext import ContextTypes, ConversationHandler
from core.database.supabase_client import db
from core.utils.keyboards import (
    get_admin_settings_menu, 
    get_user_approval_keyboard,
    get_upload_proof_button,
    get_airline_keyboard, get_confirmation_keyboard, 
    get_edit_menu, get_shipment_approval_keyboard,
    get_payment_decision_keyboard, get_cancel_back,
    get_upload_proof_button, get_back_to_main,
    get_main_dashboard
    get_back_to_main
)
from core.config import Config

# States for Admin Conversations
# Synchronized with run_local.py
(
    NAMING, COMPANY, AIRLINE, AWB, SPECS, DIMS, RATES, ADDRESSES, 
    CONFIRM, EDIT_FIELD, UPLOAD_PROOF, 
    SET_RATE, REJECT_REASON
) = range(13)

async def open_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Hybrid Handler: Opens the Admin Control Panel.
    Supports Dashboard (Text) and Inline (Callback) triggers.
    """
    query = update.callback_query
    rate = db.get_setting('exchange_rate')
    
    text = (
        f"👑 Admin Control Panel\n\n"
        f"Current Global Exchange Rate: {rate} ETB\n"
        f"Updating this will only affect new shipments."
    )
    markup = get_admin_settings_menu()

    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
        
    return ConversationHandler.END

# --- GLOBAL SETTINGS LOGIC ---

async def start_set_exchange_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by 'set_ex_rate' callback from Admin Menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📈 Enter the new Exchange Rate (USD to ETB):",
        reply_markup=get_back_to_main()
    )
    return SET_RATE

async def save_exchange_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes text input for new exchange rate."""
    text = update.message.text
    try:
        new_rate = float(text)
        db.update_setting('exchange_rate', new_rate)
        await update.message.reply_text(
            f"✅ Exchange Rate updated to: {new_rate} ETB",
            reply_markup=get_back_to_main()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please enter a numeric value (e.g. 56.5):")
        return SET_RATE

# --- PHASE 1: RATE / SHIPMENT APPROVAL ---

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Phase 1 Rate Approval from the Admin Channel."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    data = query.data
    shipment_id = data.split("_")[-1]
    shipment = db.get_shipment(shipment_id)

    if data.startswith("rate_apprv_"):
        db.update_shipment_status(shipment_id, "rate_approved")

        # Persistent Update: Update Admin Card in Channel
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ RATE APPROVED BY STAFF\nWaiting for user payment proof."
        )
        
        # Notify User (No bolding)
        await context.bot.send_message(
            chat_id=shipment['created_by'],
            text=(
                f"✅ Shipment Rate Approved!\n"
                f"AWB: {shipment['awb_number']}\n"
                f"Total USD: {float(shipment['sale_rate_usd']) * float(shipment['chargeable_weight'])}\n\n"
                f"Please click the button below to upload your payment proof."
            ),
            reply_markup=get_upload_proof_button(shipment_id)
        )

    elif data.startswith("rate_rejct_"):
        context.user_data['reject_target_id'] = shipment_id
        context.user_data['reject_type'] = "RATE_REJECTION"
        await query.message.reply_text("📝 Please type the reason for rejecting this shipment/rate:")
        return REJECT_REASON

# --- PHASE 2: PAYMENT VERIFICATION ---

async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Phase 2 Payment verification from the Admin Channel."""
    query = update.callback_query
    if not query:
        return
        
    await query.answer()
    data = query.data
    shipment_id = data.split("_")[-1]
    shipment = db.get_shipment(shipment_id)

    if data.startswith("pay_apprv_"):
        # Update Status to Booked
        db.update_shipment(shipment_id, {
            "payment_status": "paid",
            "shipment_status": "booked" 
        })

        # Update Admin Card in Channel
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ PAYMENT VERIFIED AND SHIPMENT BOOKED"
        )
        
        # Notify User (No bolding)
        await context.bot.send_message(
            chat_id=shipment['created_by'],
            text=(
                f"💰 Payment Verified!\n"
                f"AWB: {shipment['awb_number']}\n\n"
                f"Your shipment is now officially BOOKED. We will notify you of further updates."
            )
        )

    elif data.startswith("pay_rejct_"):
        context.user_data['reject_target_id'] = shipment_id
        context.user_data['reject_type'] = "PAYMENT_REJECTION"
        await query.message.reply_text("📝 Please type the reason why the payment proof was rejected:")
        return REJECT_REASON

async def save_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends rejection comment to user and resets appropriate status."""
    reason = update.message.text
    shipment_id = context.user_data.get('reject_target_id')
    reject_type = context.user_data.get('reject_type')
    shipment = db.get_shipment(shipment_id)

    if reject_type == "RATE_REJECTION":
        title = "❌ Shipment/Rate Rejected"
        db.update_shipment_status(shipment_id, "quotation_created")
    else:
        title = "❌ Payment Proof Rejected"
        db.update_shipment_status(shipment_id, "rate_approved", "unpaid")

    await context.bot.send_message(
        chat_id=shipment['created_by'],
        text=f"{title}\nAWB: {shipment['awb_number']}\n\nComment from Staff:\n{reason}"
    )
    
    await update.message.reply_text("✅ Rejection sent to user.")
    return ConversationHandler.END

# --- USER ACCESS MANAGEMENT ---

async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approves or blocks new registrations from the Admin Channel."""
    query = update.callback_query
    if not query:
        return
        
    await query.answer()
    data = query.data
    parts = data.split("_") 
    target_id = int(parts[2])

    if "apprv" in data:
        role = parts[3]
        db.approve_user(target_id, role)
        await query.edit_message_text(f"✅ User ID {target_id} approved as {role.upper()}.")
        
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎉 Account Approved!\n"
                f"You have been granted {role.upper()} access.\n\n"
                f"Use the dashboard menu at the bottom of your screen to begin."
            )
        )
    elif "block" in data:
        await query.edit_message_text(f"🚫 User ID {target_id} has been blocked.")