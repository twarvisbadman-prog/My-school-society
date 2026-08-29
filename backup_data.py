# backup_data.py - Run this before deploying!
import os
import json
from datetime import datetime
from supabase import create_client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Please set SUPABASE_URL and SUPABASE_KEY in .env")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("📦 Backing up all notes...")

try:
    response = supabase.table("notes").select("*").execute()
    notes = response.data if response.data else []
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_notes_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(notes, f, indent=2, default=str)
    
    print(f"✅ Backed up {len(notes)} notes")
    print(f"📁 File saved: {filename}")
    
except Exception as e:
    print(f"❌ Backup failed: {e}")
