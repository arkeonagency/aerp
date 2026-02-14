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