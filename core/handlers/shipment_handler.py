import uuid
from telegram import Update, constants
from telegram.ext import ContextTypes
from core.database.supabase_client import db
from core.utils.calculations import calculate_metrics
from core.utils.validators import is_float, validate_dims
from core.config import Config
from core.utils.keyboards import (
    get_airline_keyboard, get_confirmation_keyboard, 
    get_edit_menu, get_shipment_approval_keyboard,
    get_payment_decision_keyboard, get_cancel_back,
    get_upload_proof_button, get_back_to_main,
    get_main_dashboard, get_user_shipment_actions,
    get_simple_cancel
)

async def generate_summary(s, stage="review"):
    """Calculates metrics and formats summary with zero bolding."""
    l = float(s.get('length_cm', 0))
    w = float(s.get('width_cm', 0))
    h = float(s.get('height_cm', 0))
    pcs = int(s.get('pieces', 0))
    gross = float(s.get('gross_weight', 0))
    chargeable = float(s.get('chargeable_weight', 0))
    sale = float(s.get('sale_rate_usd', 0))
    ex = float(s.get('exchange_rate_etb', 1))

    # Calculate totals based on manual chargeable weight
    total_usd = round(chargeable * sale, 2)
    total_etb = round(total_usd * ex, 2)
    
    status_map = {
        "review": "Everything correct?",
        "pending_approval": "Awaiting Admin Rate Approval.",
        "payment_pending": "Payment proof submitted. Awaiting verification.",
        "booked": "Shipment booked and confirmed.",
        "uplifted": "Shipment has been uplifted.",
        "completed": "Shipment delivered."
    }

    return (
        f"📋 SHIPMENT SUMMARY\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✈️ Airline: {s.get('airline', 'N/A')}\n"
        f"📍 Route: {s.get('origin', 'N/A')} to {s.get('destination', 'N/A')}\n"
        f"🔢 AWB: {s.get('awb_number', 'N/A')}\n"
        f"📦 Pieces: {pcs} Pcs\n"
        f"⚖️ Normal Weight: {gross}kg\n"
        f"⚖️ Chargeable Weight: {chargeable}kg\n"
        f"📏 Dims: {l} x {w} x {h} cm\n"
        f"💵 Sale Rate: ${sale}\n"
        f"💰 Total: ${total_usd} ({total_etb} ETB)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏠 Shipper:\n{s.get('shipper_info', 'N/A')}\n\n"
        f"🏢 Consignee:\n{s.get('consignee_info', 'N/A')}\n\n"
        f"🔔 Notify:\n{s.get('notify_party', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Payment Status: {s.get('payment_status', 'unpaid').upper()}\n"
        f"Shipment Status: {status_map.get(s.get('shipment_status', stage), '')}"
    )

# --- PROFILE & TRACKING ---

async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    text = (
        f"👤 USER PROFILE\n\n"
        f"Name: {user['full_name']}\n"
        f"Company: {user['company_name']}\n"
        f"Role: {user['role'].upper()}\n"
        f"Status: Approved"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=get_back_to_main())
    else:
        await update.message.reply_text(text, reply_markup=get_back_to_main())

async def track_shipments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    shipments = db.get_user_shipments(user_id)
    if update.callback_query: await update.callback_query.answer()

    if not shipments:
        msg = "You have no shipments yet."
        if update.callback_query: await update.callback_query.edit_message_text(msg, reply_markup=get_back_to_main())
        else: await update.message.reply_text(msg, reply_markup=get_back_to_main())
        return

    msg_target = update.callback_query.message if update.callback_query else update.message
    await msg_target.reply_text("🔍 YOUR SHIPMENTS (Select to Edit or View):")

    for s in shipments:
        status_clean = s['shipment_status'].replace('_', ' ').title()
        text = (
            f"✈️ {s['airline']} | AWB: {s['awb_number']}\n"
            f"Payment: {s['payment_status'].upper()}\n"
            f"Status: {status_clean}"
        )
        await msg_target.reply_text(text, reply_markup=get_user_shipment_actions(s['id'], s['shipment_status']))

# --- SHIPMENT WIZARD & EDIT ENGINE (DB-STATE DRIVEN) ---

async def start_new_shipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.update_user_state(user_id, "SHIP_AIRLINE")
    text = "✈️ New Shipment\nEnter the Airline Name:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=get_simple_cancel())
    else:
        await update.message.reply_text(text, reply_markup=get_simple_cancel())

async def handle_shipment_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    user_id = user['telegram_id']
    state = user['state']
    
    # 1. Airline Name
    if state == "SHIP_AIRLINE":
        ship_id = str(uuid.uuid4())
        db.create_shipment({"id": ship_id, "created_by": user_id, "airline": text, "shipment_status": "quotation_created", "payment_status": "unpaid"})
        db.update_user_state(user_id, f"SHIP_ORIGIN_{ship_id}")
        await update.message.reply_text("📍 Enter Origin City:", reply_markup=get_cancel_back())

    # 2. Origin
    elif state.startswith("SHIP_ORIGIN_"):
        ship_id = state.split("_")[-1]
        db.update_shipment(ship_id, {"origin": text})
        db.update_user_state(user_id, f"SHIP_DEST_{ship_id}")
        await update.message.reply_text("🏁 Enter Destination City:", reply_markup=get_cancel_back())

    # 3. Destination
    elif state.startswith("SHIP_DEST_"):
        ship_id = state.split("_")[-1]
        db.update_shipment(ship_id, {"destination": text})
        db.update_user_state(user_id, f"SHIP_AWB_{ship_id}")
        await update.message.reply_text("🔢 Enter AWB Number:", reply_markup=get_cancel_back())

    # 4. AWB
    elif state.startswith("SHIP_AWB_"):
        ship_id = state.split("_")[-1]
        db.update_shipment(ship_id, {"awb_number": text})
        db.update_user_state(user_id, f"SHIP_PIECES_{ship_id}")
        await update.message.reply_text("🔢 Enter Total Pieces:", reply_markup=get_cancel_back())

    # 5. Pieces
    elif state.startswith("SHIP_PIECES_"):
        ship_id = state.split("_")[-1]
        if text.isdigit():
            db.update_shipment(ship_id, {"pieces": int(text)})
            db.update_user_state(user_id, f"SHIP_GROSS_{ship_id}")
            await update.message.reply_text("⚖️ Enter Normal Weight (kg):", reply_markup=get_cancel_back())
        else: await update.message.reply_text("⚠️ Enter a valid number:")

    # 6. Normal Weight (Gross)
    elif state.startswith("SHIP_GROSS_"):
        ship_id = state.split("_")[-1]
        try:
            val = float(text)
            db.update_shipment(ship_id, {"gross_weight": val})
            db.update_user_state(user_id, f"SHIP_CHARGEABLE_{ship_id}")
            await update.message.reply_text("⚖️ Enter Chargeable Weight (kg):", reply_markup=get_cancel_back())
        except: await update.message.reply_text("⚠️ Enter a valid number:")

    # 7. Chargeable Weight
    elif state.startswith("SHIP_CHARGEABLE_"):
        ship_id = state.split("_")[-1]
        try:
            val = float(text)
            db.update_shipment(ship_id, {"chargeable_weight": val})
            db.update_user_state(user_id, f"SHIP_DIMS_{ship_id}")
            await update.message.reply_text("📏 Enter Dimensions LxWxH (e.g., 120x80x100 or 12*5*7):", reply_markup=get_cancel_back())
        except: await update.message.reply_text("⚠️ Enter a valid number:")

    # 8. Dimensions
    elif state.startswith("SHIP_DIMS_"):
        ship_id = state.split("_")[-1]
        dims = validate_dims(text)
        if dims:
            db.update_shipment(ship_id, {"length_cm": dims[0], "width_cm": dims[1], "height_cm": dims[2], "exchange_rate_etb": db.get_setting('exchange_rate')})
            db.update_user_state(user_id, f"SHIP_RATES_{ship_id}")
            await update.message.reply_text("💰 Enter Approved Rate, Sale Rate in USD (e.g., 4.5, 5.2):", reply_markup=get_cancel_back())
        else: await update.message.reply_text("⚠️ Use format: LxWxH")

    # 9. Rates
    elif state.startswith("SHIP_RATES_"):
        ship_id = state.split("_")[-1]
        try:
            parts = text.split(',')
            db.update_shipment(ship_id, {"approved_rate_usd": float(parts[0].strip()), "sale_rate_usd": float(parts[1].strip())})
            db.update_user_state(user_id, f"SHIP_SHIPPER_{ship_id}")
            await update.message.reply_text("🏠 Enter Shipper Details:", reply_markup=get_cancel_back())
        except: await update.message.reply_text("⚠️ Use format: AppRate, SaleRate")

    # 10. Shipper
    elif state.startswith("SHIP_SHIPPER_"):
        ship_id = state.split("_")[-1]
        db.update_shipment(ship_id, {"shipper_info": text})
        db.update_user_state(user_id, f"SHIP_CONSIGNEE_{ship_id}")
        await update.message.reply_text("🏢 Enter Consignee Details:", reply_markup=get_cancel_back())

    # 11. Consignee
    elif state.startswith("SHIP_CONSIGNEE_"):
        ship_id = state.split("_")[-1]
        db.update_shipment(ship_id, {"consignee_info": text})
        db.update_user_state(user_id, f"SHIP_NOTIFY_{ship_id}")
        await update.message.reply_text("🔔 Enter Notify Party Details:", reply_markup=get_cancel_back())

    # 12. Notify & Show Summary
    elif state.startswith("SHIP_NOTIFY_"):
        ship_id = state.split("_")[-1]
        db.update_shipment(ship_id, {"notify_party": text})
        db.update_user_state(user_id, f"SHIP_CONFIRM_{ship_id}")
        summary = await generate_summary(db.get_shipment(ship_id), stage="review")
        await update.message.reply_text(summary, reply_markup=get_confirmation_keyboard())

    # --- EDIT MODE INPUTS ---
    elif state.startswith("EDIT_INPUT_"):
        parts = state.split("_")
        field = parts[2]
        ship_id = parts[3]
        try:
            if field == "awb": db.update_shipment(ship_id, {"awb_number": text})
            elif field == "airline": db.update_shipment(ship_id, {"airline": text})
            elif field == "route": 
                r = text.split(' to ')
                db.update_shipment(ship_id, {"origin": r[0], "destination": r[1]})
            elif field == "pcs": db.update_shipment(ship_id, {"pieces": int(text)})
            elif field == "gross": db.update_shipment(ship_id, {"gross_weight": float(text)})
            elif field == "chargeable": db.update_shipment(ship_id, {"chargeable_weight": float(text)})
            elif field == "dims":
                d = validate_dims(text)
                db.update_shipment(ship_id, {"length_cm": d[0], "width_cm": d[1], "height_cm": d[2]})
            elif field == "rates":
                p = text.split(',')
                db.update_shipment(ship_id, {"approved_rate_usd": float(p[0].strip()), "sale_rate_usd": float(p[1].strip())})
            elif field == "shipper": db.update_shipment(ship_id, {"shipper_info": text})
            elif field == "consignee": db.update_shipment(ship_id, {"consignee_info": text})
            elif field == "notify": db.update_shipment(ship_id, {"notify_party": text})

            db.update_shipment_status(ship_id, "quotation_created")
            db.update_user_state(user_id, f"SHIP_CONFIRM_{ship_id}")
            summary = await generate_summary(db.get_shipment(ship_id), stage="review")
            await update.message.reply_text(f"✅ Field updated. Shipment reset for re-approval.\n\n{summary}", reply_markup=get_confirmation_keyboard())
        except:
            await update.message.reply_text("⚠️ Invalid format. Please try again.")

# --- CALLBACK HANDLERS ---

async def handle_shipment_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    await query.answer()

    if data == "confirm_shipment":
        state = user.get('state', '')
        if state.startswith("SHIP_CONFIRM_"):
            ship_id = state.split("_")[-1]
            db.update_user_state(user_id, None)
            await query.edit_message_text("🚀 Shipment Submitted for Rate Review.")
            shipment = db.get_shipment(ship_id)
            admin_summary = await generate_summary(shipment, stage="pending_approval")
            admin_msg = await context.bot.send_message(
                chat_id=Config.ADMIN_CHANNEL_ID,
                text=f"🚨 NEW SHIPMENT REVIEW REQUEST\nFrom: {user['full_name']}\nID: {ship_id}\n\n{admin_summary}",
                reply_markup=get_shipment_approval_keyboard(ship_id)
            )
            db.update_shipment(ship_id, {"admin_message_id": admin_msg.message_id})

    elif data == "open_edit_menu":
        await query.edit_message_text("📝 Select field to edit:", reply_markup=get_edit_menu())

    elif data.startswith("edit_hist_"):
        ship_id = data.replace("edit_hist_", "")
        db.update_user_state(user_id, f"SHIP_CONFIRM_{ship_id}")
        summary = await generate_summary(db.get_shipment(ship_id))
        await query.message.reply_text(f"Editing Shipment Mode:\n\n{summary}", reply_markup=get_confirmation_keyboard())

    elif data.startswith("edit_field_"):
        field = data.replace("edit_field_", "")
        ship_id = user['state'].split("_")[-1]
        db.update_user_state(user_id, f"EDIT_INPUT_{field}_{ship_id}")
        prompts = {"airline": "Enter Airline Name:", "awb": "Enter AWB Number:", "pcs": "Enter Total Pieces:", "gross": "Enter Normal Weight:", "chargeable": "Enter Chargeable Weight:", "dims": "Enter Dims LxWxH:", "rates": "Enter AppRate, SaleRate:", "shipper": "Enter Shipper:", "consignee": "Enter Consignee:", "notify": "Enter Notify:", "route": "Enter new Route (e.g. Dubai to Addis):"}
        await query.edit_message_text(prompts.get(field, "Enter new value:"), reply_markup=get_simple_cancel())

    elif data == "back_to_summary":
        # Cancel Editing: Just return to the summary screen
        ship_id = user['state'].split("_")[-1]
        summary = await generate_summary(db.get_shipment(ship_id))
        await query.edit_message_text(summary, reply_markup=get_confirmation_keyboard())

    elif data == "cancel_wizard":
        db.update_user_state(user_id, None)
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=user_id, text="❌ Action cancelled.", reply_markup=get_main_dashboard(user['role']))

    elif data == "back_step":
        await handle_back_step(update, context, user)

async def handle_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    current_state = user['state']
    ship_id = current_state.split("_")[-1]
    steps = ["SHIP_AIRLINE", "SHIP_ORIGIN", "SHIP_DEST", "SHIP_AWB", "SHIP_PIECES", "SHIP_GROSS", "SHIP_CHARGEABLE", "SHIP_DIMS", "SHIP_RATES", "SHIP_SHIPPER", "SHIP_CONSIGNEE", "SHIP_NOTIFY", "SHIP_CONFIRM"]
    try:
        current_base = "_".join(current_state.split("_")[:2])
        idx = steps.index(current_base)
        if idx > 0:
            db.update_user_state(user['telegram_id'], f"{steps[idx-1]}_{ship_id}")
            prompts = {"SHIP_AIRLINE": "✈️ Airline Name:", "SHIP_ORIGIN": "📍 Origin City:", "SHIP_DEST": "🏁 Destination City:", "SHIP_AWB": "🔢 AWB Number:", "SHIP_PIECES": "🔢 Total Pieces:", "SHIP_GROSS": "⚖️ Normal Weight:", "SHIP_CHARGEABLE": "⚖️ Chargeable Weight:", "SHIP_DIMS": "📏 Dimensions LxWxH:", "SHIP_RATES": "💰 AppRate, SaleRate:", "SHIP_SHIPPER": "🏠 Shipper:", "SHIP_CONSIGNEE": "🏢 Consignee:", "SHIP_NOTIFY": "🔔 Notify Party:"}
            await update.callback_query.edit_message_text(prompts.get(steps[idx-1]), reply_markup=get_cancel_back())
    except: await start_new_shipment(update, context)

# --- PHASE 2: UPLOAD ---

async def start_proof_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shipment_id = query.data.replace("start_upload_", "")
    db.update_user_state(update.effective_user.id, f"UPLOAD_1_{shipment_id}")
    context.user_data['proofs'] = []
    await query.edit_message_text("💳 Payment Proof Upload\nSend the first file now (Photo or PDF):")

async def handle_phase2_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id, state = user['telegram_id'], user['state']
    ship_id = state.split("_")[-1]
    
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        mime, ext, f_type = "image/jpeg", ".jpg", "photo"
    elif update.message.document:
        file = await update.message.document.get_file()
        mime = update.message.document.mime_type
        ext = ".pdf" if "pdf" in mime else ".dat"
        f_type = "doc"
    else:
        await update.message.reply_text("❌ Send a Photo or PDF.")
        return

    f_bytes = await file.download_as_bytearray()
    f_path = f"{user_id}/{ship_id}/{uuid.uuid4()}{ext}"
    p_url = await db.upload_file(f_path, f_path, bytes(f_bytes), mime)
    
    if 'proofs' not in context.user_data: context.user_data['proofs'] = []
    context.user_data['proofs'].append({"url": p_url, "type": f_type})
    
    if len(context.user_data['proofs']) < 2:
        db.update_user_state(user_id, f"UPLOAD_2_{ship_id}")
        await update.message.reply_text(f"📥 Received file 1/2. Send the second:")
    else:
        urls = [f['url'] for f in context.user_data['proofs']]
        db.update_shipment(ship_id, {"files": urls, "payment_status": "unpaid", "shipment_status": "payment_received"})
        db.update_user_state(user_id, None)
        await update.message.reply_text("✅ Payment Proof Submitted!", reply_markup=get_main_dashboard(user['role']))
        
        for f in context.user_data['proofs']:
            if f['type'] == "photo": await context.bot.send_photo(chat_id=Config.ADMIN_CHANNEL_ID, photo=f['url'])
            else: await context.bot.send_document(chat_id=Config.ADMIN_CHANNEL_ID, document=f['url'])
        
        summary = await generate_summary(db.get_shipment(ship_id), stage="payment_pending")
        decision_msg = await context.bot.send_message(chat_id=Config.ADMIN_CHANNEL_ID, text=f"💰 PAYMENT VERIFICATION REQUIRED\nID: {ship_id}\n\n{summary}", reply_markup=get_payment_decision_keyboard(ship_id))
        db.update_shipment(ship_id, {"admin_message_id": decision_msg.message_id})
        context.user_data['proofs'] = []