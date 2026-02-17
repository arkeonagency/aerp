import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID")
    # The name of the bucket you created in Supabase Storage
    SUPABASE_BUCKET = "shipment-proofs"

    # Multi-Admin Support
    # In your .env file, add: ADMIN_IDS=7332957928,12345678,00000000
    _raw_admins = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip()]