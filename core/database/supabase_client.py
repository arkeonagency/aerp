from supabase import create_client, Client
from core.config import Config

class Database:
    def __init__(self):
        self.supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    # --- USER & STATE OPERATIONS ---

    def get_user(self, telegram_id: int):
        """Fetch user profile and their current database-stored state."""
        res = self.supabase.table("profiles").select("*").eq("telegram_id", telegram_id).execute()
        return res.data[0] if res.data else None

    def create_user(self, data: dict):
        """Register a new user profile."""
        return self.supabase.table("profiles").insert(data).execute()

    def update_user_state(self, telegram_id: int, state: str = None):
        """
        Saves the user's current step in the database.
        Ensures buttons and messages work perfectly on Vercel.
        """
        return self.supabase.table("profiles").update({"state": state}).eq("telegram_id", telegram_id).execute()

    def approve_user(self, telegram_id: int, role: str = 'user'):
        """Approve a pending user and assign a role."""
        return self.supabase.table("profiles").update({
            "is_approved": True, 
            "role": role,
            "state": None
        }).eq("telegram_id", telegram_id).execute()

    def get_all_users(self):
        """Fetch every registered user for Admin Management."""
        res = self.supabase.table("profiles").select("*").order("created_at", desc=True).execute()
        return res.data

    def get_pending_users(self):
        """List all users waiting for access approval."""
        res = self.supabase.table("profiles").select("*").eq("is_approved", False).execute()
        return res.data

    def delete_user(self, telegram_id: int):
        """Remove a user from the system."""
        return self.supabase.table("profiles").delete().eq("telegram_id", telegram_id).execute()

    def get_broadcast_list(self):
        """Get all approved user IDs for announcements."""
        res = self.supabase.table("profiles").select("telegram_id").eq("is_approved", True).execute()
        return [item['telegram_id'] for item in res.data]

    # --- SHIPMENT OPERATIONS ---

    def create_shipment(self, data: dict):
        """Create a new shipment record."""
        return self.supabase.table("shipments").insert(data).execute()

    def update_shipment(self, shipment_id: str, data: dict):
        """Update any shipment variable."""
        return self.supabase.table("shipments").update(data).eq("id", shipment_id).execute()

    def get_shipment(self, shipment_id: str):
        """Fetch a specific shipment by UUID."""
        res = self.supabase.table("shipments").select("*").eq("id", shipment_id).execute()
        return res.data[0] if res.data else None

    def get_user_shipments(self, telegram_id: int):
        """Fetch all shipments created by a specific user."""
        res = self.supabase.table("shipments").select("*").eq("created_by", telegram_id).order("created_at", desc=True).execute()
        return res.data

    def get_all_shipments(self):
        """Fetch all shipments in the system for the Staff Panel."""
        res = self.supabase.table("shipments").select("*, profiles(full_name)").order("created_at", desc=True).execute()
        return res.data

    def update_shipment_status(self, shipment_id: str, status: str, payment_status: str = None):
        """Transitions shipment through the lifecycle."""
        update_data = {"shipment_status": status}
        if payment_status:
            update_data["payment_status"] = payment_status
        return self.supabase.table("shipments").update(update_data).eq("id", shipment_id).execute()

    def delete_shipment(self, shipment_id: str):
        """Remove a shipment record."""
        return self.supabase.table("shipments").delete().eq("id", shipment_id).execute()

    # --- SYSTEM STATS & SETTINGS ---

    def get_db_stats(self):
        """Aggregate counts for the Admin Dashboard."""
        users_count = self.supabase.table("profiles").select("telegram_id", count="exact").execute()
        shipments_count = self.supabase.table("shipments").select("id", count="exact").execute()
        return {
            "users": users_count.count,
            "shipments": shipments_count.count
        }

    def get_setting(self, key: str):
        """Fetch global settings like exchange_rate."""
        res = self.supabase.table("settings").select("value").eq("key", key).execute()
        return float(res.data[0]['value']) if res.data else 1.0

    def update_setting(self, key: str, value: float):
        """Update global settings."""
        return self.supabase.table("settings").update({"value": value}).eq("key", key).execute()

    # --- MEDIA & STORAGE ---

    async def upload_file(self, file_path: str, file_path_db: str, file_content: bytes, mime_type: str):
        """Uploads files to Supabase Storage and returns the public link."""
        self.supabase.storage.from_(Config.SUPABASE_BUCKET).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": mime_type}
        )
        return self.supabase.storage.from_(Config.SUPABASE_BUCKET).get_public_url(file_path)

db = Database()