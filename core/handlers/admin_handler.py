import asyncio
from telegram import Update, constants
from telegram.ext import ContextTypes
from core.database.supabase_client import db
from core.utils.keyboards import (
    get_admin_settings_menu, 
    get_user_approval_keyboard,
    get_upload_proof_button,
    get_back_to_main,
    get_main_dashboard,
    get_staff_shipment_manage_keyboard,
    get_user_shipment_actions
)
from core.config import Config

async def open_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    THE MASTER ADMIN ENTRY POINT.
    Supports both Dashboard (text) and Inline (callback) triggers.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    # Permission check
    if user['role'] not in ['admin', 'staff']:
        return

    rate = db.get_setting('exchange_rate')
    text = (
        f"👑 Admin Control Panel\n\n"
        f"Current Global Exchange Rate: {rate} ETB\n"
        f"Updating this only affects new shipments."
    )
    markup = get_admin_settings_menu()

    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

async def handle_admin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Master Admin Message Router for text inputs.
    Handles Exchange Rate, Announcements, and Rejection Reasons.
    """
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    text = update.message.text
    user = db.get_user(user_id)
    
    if user['role'] not in ['admin', 'staff']:
        return

    # --- STATE HANDLING: EXCHANGE RATE ---
    if user.get('state') == "SET_EXCHANGE":
        try:
            new_rate = float(text)
            db.update_setting('exchange_rate', new_rate)
            db.update_user_state(user_id, None)
            await update.message.reply_text(
                f"✅ Exchange Rate updated to: {new_rate} ETB", 
                reply_markup=get_main_dashboard(user['role'])
            )
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid numeric value (e.g. 56.5):")
        return

    # --- STATE HANDLING: BROADCAST (ANNOUNCEMENTS) ---
    if user.get('state') == "ADM_BROADCAST":
        db.update_user_state(user_id, None)
        target_ids = db.get_broadcast_list()
        count = 0
        
        await update.message.reply_text(f"📢 Starting broadcast to {len(target_ids)} users...")
        
        for tid in target_ids:
            try:
                await context.bot.send_message(
                    chat_id=tid, 
                    text=f"📢 ANNOUNCEMENT\n\n{text}"
                )
                count += 1
                await asyncio.sleep(0.05) # Prevent Telegram flood limits
            except:
                continue
                
        await update.message.reply_text(
            f"✅ Broadcast complete. Successfully sent to {count} users.", 
            reply_markup=get_main_dashboard(user['role'])
        )
        return

    # --- STATE HANDLING: REJECTION REASONS ---
    if user.get('state') and user['state'].startswith("REJECT_"):
        await process_admin_rejection(update, context, user, text)
        return

async def process_admin_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, text: str):
    """Helper to process rejection text based on stored state."""
    state_parts = user['state'].split("_") # REJECT_TYPE_ID
    reject_type = state_parts[1]
    shipment_id = state_parts[2]
    shipment = db.get_shipment(shipment_id)
    
    if reject_type == "RATE":
        title = "❌ Shipment Rate Rejected"
        new_status = "quotation_created"
        db.update_shipment_status(shipment_id, new_status)
    else:
        title = "❌ Payment Proof Rejected"
        new_status = "rate_approved"
        db.update_shipment_status(shipment_id, new_status, "unpaid")

    # Notify User with the appropriate Re-submit/Edit buttons!
    await context.bot.send_message(
        chat_id=shipment['created_by'], 
        text=f"{title}\nAWB: {shipment['awb_number']}\n\nComment from Staff:\n{text}\n\nPlease fix the issue and resubmit.",
        reply_markup=get_user_shipment_actions(shipment_id, new_status)
    )
    
    db.update_user_state(user['telegram_id'], None)
    await update.message.reply_text(
        "✅ Comment has been sent to the user.", 
        reply_markup=get_main_dashboard(user['role'])
    )

# --- STAFF PANEL (GLOBAL QUEUE) ---

async def open_staff_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists recent shipments for manual lifecycle management."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if query: await query.answer()
    
    shipments = db.get_all_shipments()
    if not shipments:
        msg = "No shipments found in the system database."
        if query: await query.edit_message_text(msg, reply_markup=get_back_to_main())
        else: await update.message.reply_text(msg, reply_markup=get_back_to_main())
        return

    await (query.message.reply_text if query else update.message.reply_text)(
        "🛠 STAFF MANAGEMENT QUEUE\n(Showing last 10 shipments)"
    )
    
    for s in shipments[:10]:
        status = s['shipment_status'].replace('_', ' ').title()
        owner = s.get('profiles', {}).get('full_name', 'Unknown User')
        text = (
            f"✈️ {s['airline']} | AWB: {s['awb_number']}\n"
            f"👤 User: {owner}\n"
            f"📝 Status: {status}\n"
            f"💰 Payment: {s['payment_status'].upper()}"
        )
        await (query.message.reply_text if query else update.message.reply_text)(
            text, reply_markup=get_staff_shipment_manage_keyboard(s['id'])
        )

# --- CALLBACK HANDLERS (ADMIN / STAFF ACTIONS) ---

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master Callback Router for all Admin and Staff inline buttons."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    await query.answer()

    parts = data.split("_")
    ship_id = parts[-1]

    # 1. SYSTEM SETTINGS & STATS
    if data == "adm_stats":
        stats = db.get_db_stats()
        text = (
            f"📊 SYSTEM STATISTICS\n\n"
            f"Total Registered Users: {stats['users']}\n"
            f"Total Shipment Records: {stats['shipments']}"
        )
        await query.edit_message_text(text, reply_markup=get_back_to_main())

    elif data == "adm_users":
        users = db.get_all_users()
        await query.edit_message_text("👥 USER MANAGEMENT LIST (Last 15):")
        for u in users[:15]:
            status = "Approved" if u['is_approved'] else "Pending"
            user_text = (
                f"👤 {u['full_name']}\n"
                f"Company: {u['company_name']}\n"
                f"Role: {u['role'].upper()}\n"
                f"Status: {status}"
            )
            await query.message.reply_text(
                user_text, 
                reply_markup=get_user_approval_keyboard(u['telegram_id'])
            )

    elif data == "adm_broadcast":
        db.update_user_state(user_id, "ADM_BROADCAST")
        await query.edit_message_text(
            "📢 ANNOUNCEMENT MODE\n\n"
            "Type the message you want to broadcast to all approved users below:", 
            reply_markup=get_back_to_main()
        )

    elif data == "set_ex_rate":
        db.update_user_state(user_id, "SET_EXCHANGE")
        await query.edit_message_text(
            "📈 Enter the new USD to ETB Exchange Rate:", 
            reply_markup=get_back_to_main()
        )

    # 2. PHASE 1 & 2 APPROVALS / REJECTIONS
    elif data.startswith("rate_apprv_"):
        shipment = db.get_shipment(ship_id)
        db.update_shipment_status(ship_id, "rate_approved")
        await query.edit_message_text(f"{query.message.text}\n\n✅ RATE APPROVED")
        await context.bot.send_message(
            chat_id=shipment['created_by'], 
            text=f"✅ Rate Approved for AWB: {shipment['awb_number']}.\n"
                 f"You can now upload your payment proof receipt.", 
            reply_markup=get_upload_proof_button(ship_id)
        )

    elif data.startswith("rate_rejct_"):
        db.update_user_state(user_id, f"REJECT_RATE_{ship_id}")
        await query.message.reply_text("📝 Please type the reason for Rate Rejection:")

    elif data.startswith("pay_apprv_"):
        shipment = db.get_shipment(ship_id)
        db.update_shipment(ship_id, {"payment_status": "paid", "shipment_status": "booked"})
        await query.edit_message_text(f"{query.message.caption if query.message.caption else query.message.text}\n\n✅ PAYMENT VERIFIED")
        await context.bot.send_message(
            chat_id=shipment['created_by'], 
            text=f"💰 Payment Verified for AWB: {shipment['awb_number']}.\n"
                 f"Shipment is now officially Booked."
        )

    elif data.startswith("pay_rejct_"):
        db.update_user_state(user_id, f"REJECT_PAYMENT_{ship_id}")
        await query.message.reply_text("📝 Please type the reason for Payment Rejection:")

    # 3. STAFF LIFECYCLE MANAGEMENT (BOOKED -> UPLIFTED -> COMPLETED)
    elif data.startswith("st_upd_"):
        new_status = parts[2] # booked, uplifted, completed
        db.update_shipment_status(ship_id, new_status)
        await query.edit_message_text(f"{query.message.text}\n\n✅ Lifecycle status updated to {new_status.upper()}")
        
        shipment = db.get_shipment(ship_id)
        await context.bot.send_message(
            chat_id=shipment['created_by'], 
            text=f"📦 STATUS UPDATE\nAWB: {shipment['awb_number']} is now {new_status.upper()}."
        )

    # 4. USER ACCESS MANAGEMENT (APPROVE / BLOCK)
    elif data.startswith("usr_apprv_"):
        tid = int(parts[2])
        role = parts[3]
        db.approve_user(tid, role)
        await query.edit_message_text(f"✅ Approved User ID {tid} as {role.upper()}")
        await context.bot.send_message(
            tid, 
            f"🎉 Account Approved!\n"
            f"You have been granted {role.upper()} access.", 
            reply_markup=get_main_dashboard(role)
        )

    elif data.startswith("usr_block_"):
        tid = int(parts[2])
        db.delete_user(tid)
        await query.edit_message_text(f"🚫 User ID {tid} has been blocked and removed.")

    # 5. NAVIGATION RE-ENTRY
    elif data == "admin_settings":
        await open_admin_settings(update, context)