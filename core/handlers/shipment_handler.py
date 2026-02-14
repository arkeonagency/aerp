import uuid
from telegram import Update, constants
from telegram.ext import ContextTypes, ConversationHandler
from core.database.supabase_client import db
from core.utils.calculations import calculate_metrics
from core.utils.validators import is_float, validate_dims
from core.config import Config
from core.utils.keyboards import (
    get_airline_keyboard, get_confirmation_keyboard, 
    get_edit_menu, get_shipment_approval_keyboard,
    get_payment_decision_keyboard, get_cancel_back,
    get_upload_proof_button, get_back_to_main,
    get_main_dashboard
)

# States
(
    AIRLINE, AWB, SPECS, DIMS, RATES, ADDRESSES, 
    CONFIRM, EDIT_FIELD, UPLOAD_PROOF
) = range(2, 11)

async def generate_summary(s, stage="review"):
    """
    Calculates metrics and formats summary.
    No bold markers (**) are used here.
    """
    results = calculate_metrics(
        float(s['l']), float(s['w']), float(s['h']), 
        int(s['pcs']), float(s['gross_weight']), 
        float(s['sale_rate']), float(s['ex_rate'])
    )
    s.update(results) 
    
    status_map = {
        "review": "Everything correct?",
        "pending_approval": "Awaiting Admin Rate Approval.",
        "payment_pending": "Payment proof submitted. Awaiting verification.",
        "booked": "Shipment booked and confirmed."
    }
    
    status_text = status_map.get(stage, "")

    return (
        f"📋 SHIPMENT SUMMARY\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✈️ Airline: {s['airline']}\n"
        f"🔢 AWB: {s['awb']}\n"
        f"📦 Cargo: {s['pcs']} Pcs | {s['gross_weight']}kg\n"
        f"📏 Dims: {s['l']} x {s['w']} x {s['h']} cm\n"
        f"⚖️ Chargeable: {s['chargeable_weight']}kg\n"
        f"💵 Sale Rate: ${s['sale_rate']}\n"
        f"💰 Total: ${s['total_usd']} ({s['total_etb']} ETB)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏠 Shipper:\n{s['shipper']}\n\n"
        f"🏢 Consignee:\n{s['consignee']}\n\n"
        f"🔔 Notify:\n{s['notify']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{status_text}"
    )

# --- PROFILE & TRACKING (HYBRID SUPPORT) ---

async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches user profile. Supports Dashboard and Inline buttons."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if query:
        await query.answer()

    user = db.get_user(user_id)
    text = (
        f"👤 USER PROFILE\n\n"
        f"Name: {user['full_name']}\n"
        f"Company: {user['company_name']}\n"
        f"Role: {user['role'].upper()}\n"
        f"Status: Approved"
    )
    
    if query:
        await query.edit_message_text(text, reply_markup=get_back_to_main())
    else:
        await update.message.reply_text(text, reply_markup=get_back_to_main())
    
    return ConversationHandler.END

async def track_shipments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches shipments for tracking. Supports Dashboard and Inline buttons."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if query:
        await query.answer()

    shipments = db.get_user_shipments(user_id)
    
    if not shipments:
        msg = "You have no shipments yet."
        if query:
            await query.edit_message_text(msg, reply_markup=get_back_to_main())
        else:
            await update.message.reply_text(msg, reply_markup=get_back_to_main())
        return ConversationHandler.END

    text = "🔍 YOUR SHIPMENTS\n\n"
    for s in shipments:
        status = s['shipment_status'].replace('_', ' ').title()
        text += f"✈️ {s['airline']} | AWB: {s['awb_number']}\nStatus: {status}\n\n"
    
    if query:
        await query.edit_message_text(text, reply_markup=get_back_to_main())
    else:
        await update.message.reply_text(text, reply_markup=get_back_to_main())
    
    return ConversationHandler.END

# --- SHIPMENT WIZARD ---

async def start_new_shipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the wizard from any entry point."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "✈️ New Shipment\nSelect the Airline carrier:",
            reply_markup=get_airline_keyboard()
        )
    else:
        await update.message.reply_text(
            "✈️ New Shipment\nSelect the Airline carrier:",
            reply_markup=get_airline_keyboard()
        )
    return AIRLINE

async def handle_airline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    airline_name = query.data.replace("air_", "")
    context.user_data['shipment'] = {'airline': airline_name}
    await query.edit_message_text(
        f"✈️ Airline: {airline_name}\n\n🔢 Enter the AWB Number:",
        reply_markup=get_cancel_back()
    )
    return AWB

async def handle_awb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['shipment']['awb'] = update.message.text
    await update.message.reply_text("📦 Enter Pieces, Gross Weight (e.g., 10, 250):", reply_markup=get_cancel_back())
    return SPECS

async def handle_specs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split(',')
        context.user_data['shipment'].update({
            'pcs': int(parts[0].strip()), 
            'gross_weight': float(parts[1].strip())
        })
        await update.message.reply_text("📏 Enter Dimensions LxWxH in cm (e.g., 120x80x100 or 12*5*7):", reply_markup=get_cancel_back())
        return DIMS
    except:
        await update.message.reply_text("❌ Invalid format. Use: Pieces, Weight (e.g., 10, 250)")
        return SPECS

async def handle_dims(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dims = validate_dims(update.message.text)
    if not dims:
        await update.message.reply_text("❌ Invalid format. Use LxWxH (e.g., 120x80x100 or 12*5*7):")
        return DIMS
    context.user_data['shipment'].update({'l': dims[0], 'w': dims[1], 'h': dims[2]})
    context.user_data['shipment']['ex_rate'] = db.get_setting('exchange_rate')
    await update.message.reply_text(f"💰 Enter Approved Rate, Sale Rate in USD (e.g., 4.5, 5.2):", reply_markup=get_cancel_back())
    return RATES

async def handle_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split(',')
        context.user_data['shipment'].update({
            'app_rate': float(parts[0].strip()), 
            'sale_rate': float(parts[1].strip())
        })
        await update.message.reply_text("🏠 Enter Shipper Details:", reply_markup=get_cancel_back())
        return ADDRESSES
    except:
        await update.message.reply_text("❌ Invalid format. Use: AppRate, SaleRate (e.g., 4.5, 5.2)")
        return RATES

async def handle_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = context.user_data['shipment']
    if 'shipper' not in s:
        s['shipper'] = update.message.text
        await update.message.reply_text("🏢 Enter Consignee Details:", reply_markup=get_cancel_back())
        return ADDRESSES
    elif 'consignee' not in s:
        s['consignee'] = update.message.text
        await update.message.reply_text("🔔 Enter Notify Party Details:", reply_markup=get_cancel_back())
        return ADDRESSES
    else:
        if not update.callback_query:
            s['notify'] = update.message.text
        
        summary_text = await generate_summary(s, stage="review")
        if update.callback_query:
            await update.callback_query.edit_message_text(summary_text, reply_markup=get_confirmation_keyboard())
        else:
            await update.message.reply_text(summary_text, reply_markup=get_confirmation_keyboard())
        return CONFIRM

# --- PHASE 1: SUBMIT FOR RATE APPROVAL ---
async def handle_confirm_and_request_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves shipment and notifies Admin Channel for Phase 1 Approval."""
    query = update.callback_query
    await query.answer()
    
    user = db.get_user(update.effective_user.id)
    s = context.user_data['shipment']
    
    shipment_record = {
        "created_by": user['telegram_id'], "airline": s['airline'], "awb_number": s['awb'],
        "pieces": s['pcs'], "gross_weight": s['gross_weight'], "length_cm": s['l'], "width_cm": s['w'], "height_cm": s['h'],
        "volumetric_weight": s['vol_weight'], "chargeable_weight": s['chargeable_weight'],
        "approved_rate_usd": s['app_rate'], "sale_rate_usd": s['sale_rate'],
        "exchange_rate_etb": s['ex_rate'], "shipper_info": s['shipper'],
        "consignee_info": s['consignee'], "notify_party": s['notify'],
        "shipment_status": "quotation_created"
    }
    
    result = db.create_shipment(shipment_record)
    shipment_id = result.data[0]['id']
    
    await query.edit_message_text("🚀 Shipment Submitted for Rate Review.\nYou will be notified once the staff approves the rates.")
    
    # Notify Admin (The Decision Card logic)
    admin_summary = await generate_summary(s, stage="pending_approval")
    admin_msg = await context.bot.send_message(
        chat_id=Config.ADMIN_CHANNEL_ID,
        text=f"🚨 NEW SHIPMENT REVIEW REQUEST\nFrom: {user['full_name']}\nID: {shipment_id}\n\n{admin_summary}",
        reply_markup=get_shipment_approval_keyboard(shipment_id)
    )
    
    db.update_shipment(shipment_id, {"admin_message_id": admin_msg.message_id})
    return ConversationHandler.END

# --- PHASE 2: UPLOAD PAYMENT PROOF ---
async def start_proof_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates Phase 2 after user clicks notification button."""
    query = update.callback_query
    await query.answer()
    
    shipment_id = query.data.replace("start_upload_", "")
    context.user_data['uploading_id'] = shipment_id
    context.user_data['proof_files'] = []
    
    await query.edit_message_text(
        "💳 Payment Proof Upload\nRequirement: 2 Files (Photo or PDF)\n\n👉 Send the first file now:"
    )
    return UPLOAD_PROOF

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes uploads and Replicates Phase 1 successful logic for Admin Buttons."""
    shipment_id = context.user_data.get('uploading_id')
    user_id = update.effective_user.id
    
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        mime, ext, f_type = "image/jpeg", ".jpg", "photo"
    elif update.message.document:
        file = await update.message.document.get_file()
        mime = update.message.document.mime_type
        ext = ".pdf" if "pdf" in mime else ".dat"
        f_type = "doc"
    else:
        await update.message.reply_text("❌ Unsupported format. Please send a Photo or PDF.")
        return UPLOAD_PROOF

    file_bytes = await file.download_as_bytearray()
    file_path = f"{user_id}/{shipment_id}/{uuid.uuid4()}{ext}"
    p_url = await db.upload_file(file_path, bytes(file_bytes), mime)
    
    context.user_data['proof_files'].append({"url": p_url, "type": f_type})
    count = len(context.user_data['proof_files'])

    if count < 2:
        await update.message.reply_text(f"📥 Received file {count}/2. Send the second file:")
        return UPLOAD_PROOF
    else:
        # Save proof files to DB
        urls = [f['url'] for f in context.user_data['proof_files']]
        db.update_shipment(shipment_id, {"files": urls, "payment_status": "unpaid"})
        
        user = db.get_user(user_id)
        await update.message.reply_text(
            "✅ Payment Proof Submitted!\nStaff will verify the payment shortly.",
            reply_markup=get_main_dashboard(user['role'])
        )
        
        # ADMIN CHANNEL: Send Media individually to avoid mixed media album errors
        for f in context.user_data['proof_files']:
            if f['type'] == "photo":
                await context.bot.send_photo(chat_id=Config.ADMIN_CHANNEL_ID, photo=f['url'])
            else:
                await context.bot.send_document(chat_id=Config.ADMIN_CHANNEL_ID, document=f['url'])
        
        # ADMIN CHANNEL: REPLICATING PHASE 1 SUCCESS
        # Send Phase 2 Decision Card (Text Card + Decision Buttons)
        shipment = db.get_shipment(shipment_id)
        summary = await generate_summary(shipment, stage="payment_pending")
        
        # Add live links to the files inside the decision card text
        proof_links = "\n".join([f"📄 Proof {i+1}: {url}" for i, url in enumerate(urls)])
        
        decision_text = (
            f"💰 PAYMENT VERIFICATION REQUIRED\n"
            f"ID: {shipment_id}\n\n"
            f"{proof_links}\n\n"
            f"{summary}"
        )
        
        # This is the exact method that worked for Phase 1 Rate Approval
        decision_msg = await context.bot.send_message(
            chat_id=Config.ADMIN_CHANNEL_ID,
            text=decision_text,
            reply_markup=get_payment_decision_keyboard(shipment_id)
        )
        
        db.update_shipment(shipment_id, {"admin_message_id": decision_msg.message_id})
        
        return ConversationHandler.END

# --- EDITING LOGIC ---
async def open_edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Edit Shipment Mode", reply_markup=get_edit_menu())
    return EDIT_FIELD