from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

def get_main_dashboard(role: str):
    """PERSISTENT BOTTOM MENU (Reply Keyboard)"""
    buttons = [
        ["📦 New Shipment"],
        ["🔍 Track My Shipments", "👤 My Profile"]
    ]
    if role in ['admin', 'staff']:
        buttons.append(["🛠 Staff Panel", "👑 Admin Settings"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_main_menu(role: str):
    """Inline version of the main menu."""
    buttons = [
        [InlineKeyboardButton("📦 New Shipment", callback_data="new_shipment")],
        [InlineKeyboardButton("🔍 Track My Shipments", callback_data="track_shipment")],
        [InlineKeyboardButton("👤 My Profile", callback_data="view_profile")]
    ]
    if role in ['admin', 'staff']:
        buttons.append([InlineKeyboardButton("🛠 Staff Panel", callback_data="staff_panel")])
    if role == 'admin':
        buttons.append([InlineKeyboardButton("👑 Admin Control Panel", callback_data="admin_settings")])
    return InlineKeyboardMarkup(buttons)

def get_cancel_back():
    """Universal navigation for text input steps."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back_step"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_wizard")]
    ])

def get_simple_cancel():
    """Used for text entry steps like Airline/Origin/Dest where back is not yet available."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Shipment", callback_data="cancel_wizard")]
    ])

def get_confirmation_keyboard():
    """Review screen before Phase 1 (Rate Approval submission)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm and Submit for Review", callback_data="confirm_shipment")],
        [InlineKeyboardButton("📝 Edit Details", callback_data="open_edit_menu")],
        [InlineKeyboardButton("❌ Cancel Shipment", callback_data="cancel_wizard")]
    ])

def get_edit_menu():
    """
    The Deep Edit engine hub. 
    Labels updated for manual weight/pieces and explicit 'Cancel Editing'.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✈️ Airline", callback_data="edit_field_airline"),
         InlineKeyboardButton("🔢 AWB", callback_data="edit_field_awb")],
        [InlineKeyboardButton("📦 Pieces", callback_data="edit_field_pcs"),
         InlineKeyboardButton("⚖️ Normal Weight", callback_data="edit_field_gross")],
        [InlineKeyboardButton("⚖️ Chargeable Weight", callback_data="edit_field_chargeable")],
        [InlineKeyboardButton("📏 Dimensions", callback_data="edit_field_dims")],
        [InlineKeyboardButton("💰 Rates (USD)", callback_data="edit_field_rates")],
        [InlineKeyboardButton("🏠 Shipper", callback_data="edit_field_shipper")],
        [InlineKeyboardButton("🏢 Consignee", callback_data="edit_field_consignee")],
        [InlineKeyboardButton("🔔 Notify Party", callback_data="edit_field_notify")],
        [InlineKeyboardButton("📍 Origin/Dest", callback_data="edit_field_route")],
        [InlineKeyboardButton("🔙 Cancel Editing", callback_data="back_to_summary")]
    ])

def get_user_shipment_actions(shipment_id: str, status: str):
    """Buttons for 'My Shipments' list allowing editing until Delivered."""
    buttons = []
    if status != 'completed':
        buttons.append([InlineKeyboardButton("📝 Edit Shipment", callback_data=f"edit_hist_{shipment_id}")])
    
    if status == 'rate_approved':
        buttons.append([InlineKeyboardButton("💳 Upload Payment Proof", callback_data=f"start_upload_{shipment_id}")])
        
    return InlineKeyboardMarkup(buttons)

def get_shipment_approval_keyboard(shipment_id: str):
    """PHASE 1: Admin Rate Approval buttons."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve Rate", callback_data=f"rate_apprv_{shipment_id}")],
        [InlineKeyboardButton("❌ Reject Shipment", callback_data=f"rate_rejct_{shipment_id}")]
    ])

def get_payment_decision_keyboard(shipment_id: str):
    """PHASE 2: Admin Payment Verification buttons."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Approve Payment", callback_data=f"pay_apprv_{shipment_id}")],
        [InlineKeyboardButton("🚫 Reject Payment Proof", callback_data=f"pay_rejct_{shipment_id}")]
    ])
    
def get_upload_proof_button(shipment_id: str):
    """Button sent to User once Admin approves rate to initiate upload."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Upload Payment Proof", callback_data=f"start_upload_{shipment_id}")]
    ])

def get_staff_shipment_manage_keyboard(shipment_id: str):
    """Lifecycle management buttons for the Staff Panel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mark Booked", callback_data=f"st_upd_booked_{shipment_id}")],
        [InlineKeyboardButton("🛫 Mark Uplifted", callback_data=f"st_upd_uplifted_{shipment_id}")],
        [InlineKeyboardButton("✅ Mark Completed", callback_data=f"st_upd_completed_{shipment_id}")]
    ])

def get_admin_settings_menu():
    """Master Admin settings keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Change Exchange Rate", callback_data="set_ex_rate")],
        [InlineKeyboardButton("👥 Manage All Users", callback_data="adm_users")],
        [InlineKeyboardButton("📢 Send Announcement", callback_data="adm_broadcast")],
        [InlineKeyboardButton("📊 View System Stats", callback_data="adm_stats")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_to_main")]
    ])

def get_user_approval_keyboard(user_id: int):
    """Inline management for user approval requests."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve User", callback_data=f"usr_apprv_{user_id}_user"),
         InlineKeyboardButton("👔 Approve Staff", callback_data=f"usr_apprv_{user_id}_staff")],
        [InlineKeyboardButton("🚫 Block", callback_data=f"usr_block_{user_id}")]
    ])

def get_back_to_main():
    """Simple navigation button to return to dashboard."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]])

def get_airline_keyboard():
    """Maintains compatibility while using manual text entry for airlines."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Shipment", callback_data="cancel_wizard")]
    ])