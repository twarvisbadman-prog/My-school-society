# ============================================
# TWARVIS SCHOOL - REAL DATA ONLY
# NO MOCK DATA - WILL FAIL IF SUPABASE FAILS
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
from supabase import create_client, Client

# ========== ENVIRONMENT VARIABLES ==========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
ADMIN = os.environ.get("ADMIN", "false") == "true"

# ========== VALIDATE - NO DEFAULTS ==========
if not SUPABASE_URL:
    raise ValueError("❌ SUPABASE_URL environment variable is required!")
if not SUPABASE_KEY:
    raise ValueError("❌ SUPABASE_KEY environment variable is required!")
if not SECRET_KEY:
    raise ValueError("❌ SECRET_KEY environment variable is required!")

print("=" * 50)
print("🚀 TWARVIS SCHOOL - REAL DATA MODE")
print(f"📡 Connecting to: {SUPABASE_URL}")
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

# ========== SUPABASE - REAL CONNECTION ==========
print("📡 Connecting to Supabase...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Supabase connected!")

# Test the connection
test = supabase.table("notes").select("*").limit(1).execute()
print(f"✅ Found {len(test.data) if test.data else 0} notes in database")

# ========== HELPERS ==========
def get_all_notes():
    response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
    notes = response.data if response.data else []
    for note in notes:
        note["original_filename"] = note.get("original_filename", note.get("filename", ""))
    return notes

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
        try:
            file = request.FILES.get("file")
            if not file:
                error = "Please select a file"
            else:
                module = request.POST.get("module", "Untitled")
                course = request.POST.get("course", "N/A")
                description = request.POST.get("description", "")
                privacy = request.POST.get("privacy", "public")
                passcode = request.POST.get("passcode", "")
                university = request.POST.get("university", "Not specified")
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = str(uuid.uuid4())[:8]
                safe_filename = f"{timestamp}_{unique_id}_{file.name.replace(' ', '_')}"
                
                file_content = file.read()
                
                # Upload to storage
                supabase.storage.from_("notes").upload(
                    safe_filename,
                    file_content,
                    {"content-type": file.content_type or "application/octet-stream"}
                )
                
                # Save to database
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
    
    # Check if private
    if note.get("privacy") == "private":
        correct = note.get("passcode", "")
        entered = request.GET.get("passcode", "")
        
        if not entered:
            return render(request, "passcode.html", {"file_id": id, "filename": note.get("original_filename", "file")})
        
        if entered != correct:
            return render(request, "passcode.html", {"file_id": id, "filename": note.get("original_filename", "file"), "error": "Wrong passcode"})
    
    # Get real file URL
    file_url = supabase.storage.from_("notes").get_public_url(note["filename"])
    
    return render(request, "view.html", {"note": note, "pdf_url": file_url, "admin": ADMIN})

def download_file(request, id):
    notes = get_all_notes()
    note = None
    for n in notes:
        if str(n.get("id")) == str(id):
            note = n
            break
    
    if not note:
        return HttpResponse("File not found", status=404)
    
    # Check if private
    if note.get("privacy") == "private":
        correct = note.get("passcode", "")
        entered = request.GET.get("passcode", "")
        
        if not entered:
            return HttpResponse("Access Denied. Private file.", status=403)
        
        if entered != correct:
            return HttpResponse("Access Denied. Wrong passcode.", status=403)
    
    # Download REAL file from Supabase
    try:
        file_data = supabase.storage.from_("notes").download(note["filename"])
        response = HttpResponse(file_data, content_type="application/octet-stream")
        response["Content-Disposition"] = f"attachment; filename=\"{note.get('original_filename', note['filename'])}\""
        return response
    except Exception as e:
        return HttpResponse(f"Download failed: {str(e)}", status=500)

def delete_file(request, id):
    if not ADMIN:
        return HttpResponse("Not authorized.", status=403)
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        supabase.storage.from_("notes").remove([note["filename"]])
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect("/admin/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {str(e)}", status=500)

def favicon(request):
    return HttpResponse(status=204)

@csrf_exempt
def update_passcode(request, id):
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        new_passcode = data.get("passcode", "").strip()
        
        if not new_passcode or len(new_passcode) != 4 or not new_passcode.isdigit():
            return JsonResponse({"success": False, "error": "Passcode must be 4 digits"})
        
        supabase.table("notes").update({"passcode": new_passcode}).eq("id", id).execute()
        return JsonResponse({"success": True, "message": "Passcode updated"})
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    
    notes = get_all_notes()
    stats = {
        "total_files": len(notes),
        "private_count": len([n for n in notes if n.get("privacy") == "private"]),
        "public_count": len([n for n in notes if n.get("privacy") != "private"]),
        "top_modules": {}
    }
    return render(request, "admin.html", {"notes": notes, "stats": stats, "admin": ADMIN})

def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    return render(request, "admin_settings.html")

def calculator_view(request):
    return render(request, "calculator.html")

def hackathon_view(request):
    return render(request, "hackathon.html")

def free_courses_view(request):
    return render(request, "free_courses.html")

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
    
