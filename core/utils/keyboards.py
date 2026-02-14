from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

def get_main_dashboard(role: str):
    """
    PERSISTENT BOTTOM MENU (Reply Keyboard)
    This stays at the bottom of the screen always.
    Text labels must match run_local.py Regex exactly.
    """
    buttons = [
        ["📦 New Shipment"],
        ["🔍 Track My Shipments", "👤 My Profile"]
    ]
    
    # Staff and Admin additional options
    if role in ['admin', 'staff']:
        buttons.append(["🛠 Staff Panel", "👑 Admin Settings"])
        
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_main_menu(role: str):
    """
    Inline version of the main menu for use within messages.
    """
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
    """Universal navigation for the wizard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
    ])

def get_airline_keyboard():
    """Selection for the shipment wizard."""
    airlines = ["ET (Ethiopian)", "TK (Turkish)", "EK (Emirates)", "QR (Qatar)"]
    buttons = [[InlineKeyboardButton(a, callback_data=f"air_{a}")] for a in airlines]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")])
    return InlineKeyboardMarkup(buttons)

def get_confirmation_keyboard():
    """Review screen before Phase 1 (Rate Approval submission)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm and Submit for Review", callback_data="confirm_shipment")],
        [InlineKeyboardButton("📝 Edit Details", callback_data="open_edit_menu")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
    ])

def get_edit_menu():
    """The Deep Edit engine allowing users to change any variable."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✈️ Airline", callback_data="edit_field_airline"),
         InlineKeyboardButton("🔢 AWB", callback_data="edit_field_awb")],
        [InlineKeyboardButton("📦 Pcs/Weight", callback_data="edit_field_specs"),
         InlineKeyboardButton("📏 Dimensions", callback_data="edit_field_dims")],
        [InlineKeyboardButton("💰 Rates (USD)", callback_data="edit_field_rates")],
        [InlineKeyboardButton("🏠 Shipper", callback_data="edit_field_shipper")],
        [InlineKeyboardButton("🏢 Consignee", callback_data="edit_field_consignee")],
        [InlineKeyboardButton("🔔 Notify Party", callback_data="edit_field_notify")],
        [InlineKeyboardButton("⬅️ Back to Summary", callback_data="back_to_summary")]
    ])

def get_shipment_approval_keyboard(shipment_id: str):
    """PHASE 1: Buttons for Admin to approve the Rate/Shipment."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve Rate", callback_data=f"rate_apprv_{shipment_id}")],
        [InlineKeyboardButton("❌ Reject Shipment", callback_data=f"rate_rejct_{shipment_id}")]
    ])

def get_upload_proof_button(shipment_id: str):
    """Button for User to start Phase 2 (Upload) after Rate is approved."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Upload Payment Proof", callback_data=f"start_upload_{shipment_id}")]
    ])

def get_payment_decision_keyboard(shipment_id: str):
    """
    PHASE 2: Buttons for Admin to verify Payment Proof.
    Matches Phase 1 structure for maximum delivery reliability in the Admin channel.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Approve Payment", callback_data=f"pay_apprv_{shipment_id}")],
        [InlineKeyboardButton("🚫 Reject Payment Proof", callback_data=f"pay_rejct_{shipment_id}")]
    ])

def get_admin_settings_menu():
    """Admin-only global settings menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Change Exchange Rate", callback_data="set_ex_rate")],
        [InlineKeyboardButton("👥 Manage Pending Users", callback_data="manage_users")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_to_main")]
    ])

def get_user_approval_keyboard(user_id: int):
    """Buttons for approving new users in the admin channel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve User", callback_data=f"usr_apprv_{user_id}_user"),
         InlineKeyboardButton("👔 Approve Staff", callback_data=f"usr_apprv_{user_id}_staff")],
        [InlineKeyboardButton("🚫 Block", callback_data=f"usr_block_{user_id}")]
    ])

def get_back_to_main():
    """Simple back button to return to dashboard."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]])