from telegram import Update, constants
from telegram.ext import ContextTypes, ConversationHandler
from core.database.supabase_client import db
from core.utils.validators import validate_dims
from core.utils.calculations import calculate_metrics
from core.utils.keyboards import get_edit_menu, get_confirmation_keyboard, get_airline_keyboard

# This handler focuses specifically on the EDIT_FIELD state logic
async def process_edit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when a user clicks a specific field button in the Edit Menu"""
    query = update.callback_query
    await query.answer()
    
    field = query.data.replace("edit_field_", "")
    context.user_data['editing_now'] = field
    
    prompts = {
        "airline": "✈️ Select new **Airline**:",
        "awb": "🔢 Enter new **AWB Number**:",
        "specs": "📦 Enter new **Pieces, Gross Weight** (e.g., 15, 300):",
        "dims": "📏 Enter new **Dimensions LxWxH** (e.g., 100x60x80):",
        "rates": "💰 Enter new **Approved Rate, Sale Rate** (e.g., 4.2, 5.0):",
        "shipper": "🏠 Enter new **Shipper Details**:",
        "consignee": "🏢 Enter new **Consignee Details**:",
        "notify": "🔔 Enter new **Notify Party Details**:"
    }
    
    prompt_text = prompts.get(field, "Enter new value:")
    
    if field == "airline":
        await query.edit_message_text(prompt_text, reply_markup=get_airline_keyboard(), parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(prompt_text, parse_mode=constants.ParseMode.MARKDOWN)
    
    # We stay in the EDIT_FIELD state
    return 7 # Matches the EDIT_FIELD state ID in api/index.py

async def save_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the text input for the field currently being edited"""
    field = context.user_data.get('editing_now')
    text = update.message.text
    s = context.user_data['shipment']
    
    try:
        if field == "awb": 
            s['awb'] = text
        elif field == "specs":
            parts = text.split(',')
            s['pcs'], s['gross_weight'] = int(parts[0].strip()), float(parts[1].strip())
        elif field == "dims":
            dims = validate_dims(text)
            s['l'], s['w'], s['h'] = dims[0], dims[1], dims[2]
        elif field == "rates":
            parts = text.split(',')
            s['app_rate'], s['sale_rate'] = float(parts[0].strip()), float(parts[1].strip())
        elif field == "shipper": 
            s['shipper'] = text
        elif field == "consignee": 
            s['consignee'] = text
        elif field == "notify": 
            s['notify'] = text
        elif field == "airline":
            # If they typed it instead of clicking
            s['airline'] = text

        # Recalculate metrics based on new data
        results = calculate_metrics(s['l'], s['w'], s['h'], s['pcs'], s['gross_weight'], s['sale_rate'], s['ex_rate'])
        s.update(results)

        # Show updated summary
        from core.handlers.shipment_handler import generate_summary
        summary = await generate_summary(s)
        
        await update.message.reply_text(
            "✅ **Field Updated Successfully!**\n\n" + summary,
            reply_markup=get_confirmation_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return 6 # Returns to CONFIRM state

    except Exception as e:
        await update.message.reply_text(f"❌ **Invalid Format.**\nPlease try again or use the correct format (e.g., for weights use `10, 250`)")
        return 7 # Stay in EDIT_FIELD