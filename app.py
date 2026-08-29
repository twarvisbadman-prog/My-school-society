# ============================================
# TWARVIS SCHOOL - SIMPLIFIED WORKING VERSION
# ============================================

import os
import uuid
import json
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

# ========== HARDCODE CREDENTIALS ==========
SUPABASE_URL = "https://hnszltswipxiqurkwydm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU"
SECRET_KEY = "django-insecure-twarvis-school-key-2024"
ADMIN = True

print("=" * 50)
print("🚀 STARTING TWARVIS SCHOOL")
print("=" * 50)

# ========== DJANGO SETTINGS ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY=SECRET_KEY,
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*", ".onrender.com", "localhost", "127.0.0.1"],
        INSTALLED_APPS=["django.contrib.staticfiles"],
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ],
        TEMPLATES=[{
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [BASE_DIR],
            "APP_DIRS": False,
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                ],
            },
        }],
        STATIC_URL="/static/",
        STATICFILES_DIRS=[BASE_DIR],
        CSRF_TRUSTED_ORIGINS=["https://*.onrender.com", "http://localhost:8000"],
        X_FRAME_OPTIONS="SAMEORIGIN",
    )

# ========== SUPABASE - TRY TO CONNECT ==========
print("📡 Connecting to Supabase...")

SUPABASE_WORKING = False

try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Test the connection
    test = supabase.table("notes").select("*").limit(1).execute()
    print(f"✅ Supabase connected! Found {len(test.data) if test.data else 0} notes")
    SUPABASE_WORKING = True
except Exception as e:
    print(f"❌ Supabase error: {e}")
    print("⚠️ Running with mock data")
    SUPABASE_WORKING = False
    
    # Mock Supabase
    class MockResponse:
        data = []
    
    class MockTable:
        def select(self, *args):
            return self
        def insert(self, data):
            return self
        def delete(self):
            return self
        def update(self, data):
            return self
        def eq(self, *args):
            return self
        def order(self, *args, **kwargs):
            return self
        def or_(self, *args):
            return self
        def execute(self):
            return MockResponse()
    
    class MockStorage:
        def from_(self, bucket):
            return self
        def upload(self, *args, **kwargs):
            return None
        def get_public_url(self, filename):
            return ""
        def download(self, filename):
            return b""
        def remove(self, *args):
            return None
    
    class MockSupabase:
        def __init__(self):
            self.table = MockTable()
            self.storage = MockStorage()
    
    supabase = MockSupabase()

# ========== MOCK DATA ==========
MOCK_NOTES = [
    {
        "id": 1,
        "filename": "sample1.pdf",
        "original_filename": "Computer Networks Notes.pdf",
        "module": "Computer Networks",
        "course": "CIT 3102",
        "description": "Complete notes on computer networks",
        "file_type": "notes",
        "privacy": "public",
        "passcode": "",
        "university": "University of Dar es Salaam (UDSM)",
        "uploaded_at": "2026-08-29T10:00:00",
        "file_size": 2048576,
        "can_view_inline": True
    },
    {
        "id": 2,
        "filename": "sample2.pdf",
        "original_filename": "Data Structures Past Paper.pdf",
        "module": "Data Structures",
        "course": "CIT 3103",
        "description": "Past paper from 2023",
        "file_type": "pastpaper",
        "privacy": "private",
        "passcode": "1234",
        "university": "University of Dodoma (UDOM)",
        "uploaded_at": "2026-08-28T15:00:00",
        "file_size": 1048576,
        "can_view_inline": True
    }
]

# ========== HELPERS ==========
def get_all_notes():
    if SUPABASE_WORKING:
        try:
            response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
            notes = response.data if response.data else []
            for note in notes:
                note["original_filename"] = note.get("original_filename", note.get("filename", ""))
            return notes
        except:
            return MOCK_NOTES
    return MOCK_NOTES

# ========== VIEWS ==========
def index(request):
    return render(request, "index.html")

def browse_view(request):
    notes = get_all_notes()
    for note in notes:
        note["display_name"] = note.get("module", note.get("original_filename", note.get("filename", "Untitled")))
        note["is_private"] = note.get("privacy") == "private"
        note["has_passcode"] = bool(note.get("passcode"))
        note["university"] = note.get("university", "Not specified")
    return render(request, "browse.html", {"notes": notes, "query": ""})

def upload_view(request):
    error = None
    message = None
    
    if request.method == "POST":
        if not SUPABASE_WORKING:
            error = "❌ Supabase is not connected. Uploads disabled."
        else:
            try:
                file = request.FILES.get("file")
                if file:
                    module = request.POST.get("module", "Untitled")
                    course = request.POST.get("course", "N/A")
                    description = request.POST.get("description", "")
                    privacy = request.POST.get("privacy", "public")
                    passcode = request.POST.get("passcode", "")
                    university = request.POST.get("university", "Not specified")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{file.name.replace(' ', '_')}"
                    
                    file_content = file.read()
                    
                    supabase.storage.from_("notes").upload(
                        safe_filename,
                        file_content,
                        {"content-type": file.content_type or "application/octet-stream"}
                    )
                    
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "original_filename": file.name,
                        "module": module,
                        "course": course,
                        "description": description,
                        "file_type": "notes",
                        "privacy": privacy,
                        "passcode": passcode if privacy == "private" else "",
                        "university": university,
                        "uploaded_at": datetime.now().isoformat(),
                        "file_size": len(file_content)
                    }).execute()
                    
                    message = f"✅ {file.name} uploaded!"
                else:
                    error = "Please select a file"
            except Exception as e:
                error = f"Upload failed: {str(e)}"
    
    return render(request, "upload.html", {"form": None, "message": message, "error": error})

def view_file(request, id):
    notes = get_all_notes()
    note = None
    for n in notes:
        if str(n.get("id")) == str(id):
            note = n
            break
    
    if not note:
        return HttpResponse("File not found", status=404)
    
    return render(request, "view.html", {"note": note, "pdf_url": "#", "admin": ADMIN})

def download_file(request, id):
    notes = get_all_notes()
    note = None
    for n in notes:
        if str(n.get("id")) == str(id):
            note = n
            break
    
    if not note:
        return HttpResponse("File not found", status=404)
    
    response = HttpResponse(b"Sample content", content_type="application/octet-stream")
    response["Content-Disposition"] = f"attachment; filename=\"{note.get('original_filename', 'file')}\""
    return response

def delete_file(request, id):
    if not ADMIN:
        return HttpResponse("Not authorized", status=403)
    return redirect("/admin/")

@csrf_exempt
def update_passcode(request, id):
    return JsonResponse({"success": True})

def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied", status=403)
    notes = get_all_notes()
    stats = {"total_files": len(notes), "private_count": 0, "public_count": 0, "top_modules": {}}
    return render(request, "admin.html", {"notes": notes, "stats": stats, "admin": ADMIN})

def admin_settings(request):
    return render(request, "admin_settings.html")

def calculator_view(request):
    return render(request, "calculator.html")

def hackathon_view(request):
    return render(request, "hackathon.html")

def free_courses_view(request):
    return render(request, "free_courses.html")

def favicon(request):
    return HttpResponse(status=204)

# ========== URLS ==========
urlpatterns = [
    path("", index),
    path("admin/", admin_dashboard),
    path("admin/settings/", admin_settings),
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("update-passcode/<int:id>/", update_passcode),
    path("calculator/", calculator_view),
    path("hackathon/", hackathon_view),
    path("free-courses/", free_courses_view),
    path("favicon.ico", favicon),
]

application = get_wsgi_application()
app = application

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    port = os.environ.get("PORT", 8000)
    execute_from_command_line([__name__, "runserver", f"0.0.0.0:{port}"])
