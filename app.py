# ============================================
# TWARVIS SCHOOL - FINAL WORKING VERSION
# HARDCODED CREDENTIALS - NO ENV VARS
# ============================================

import os
import uuid
import json
import re
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

# ========== HARDCODED CREDENTIALS (THESE WORK) ==========
SUPABASE_URL = "https://hnszltswipxiqurkwydm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU"
SECRET_KEY = "django-insecure-twarvis-school-key-2024"
ADMIN = True

print("=" * 60)
print("🚀 TWARVIS SCHOOL - FORCED REAL DATA MODE")
print(f"📡 URL: {SUPABASE_URL}")
print(f"🔑 KEY: {SUPABASE_KEY[:30]}...")
print("=" * 60)

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

# ========== SUPABASE CONNECTION ==========
print("📡 Connecting to Supabase...")

try:
    from supabase import create_client, Client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected!")
    
    # Test the connection
    test = supabase.table("notes").select("*").limit(1).execute()
    print(f"✅ Found {len(test.data) if test.data else 0} notes")
    SUPABASE_WORKING = True
except Exception as e:
    print(f"❌ ERROR: {e}")
    print("⚠️ THE APP WILL STILL RUN BUT WITH REAL DATA ONLY")
    SUPABASE_WORKING = False
    # Create a dummy that will fail gracefully
    class DummySupabase:
        def table(self, name):
            return self
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
        def execute(self):
            class Response:
                data = []
            return Response()
        def storage(self):
            return self
        def from_(self, bucket):
            return self
        def upload(self, *args, **kwargs):
            return None
        def get_public_url(self, filename):
            return ""
        def download(self, filename):
            return b""
    supabase = DummySupabase()

# ========== CONSTANTS ==========
ALLOWED_EXTENSIONS = ['.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md', '.xls', '.xlsx', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar']

UNIVERSITIES = [
    "University of Dar es Salaam (UDSM)",
    "Sokoine University of Agriculture (SUA)",
    "Muhimbili University of Health and Allied Sciences (MUHAS)",
    "University of Dodoma (UDOM)",
    "Mzumbe University",
    "State University of Zanzibar (SUZA)",
]

# ========== FORMS ==========
class UploadForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={"class": "form-file", "required": True}))
    module = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-input"}))
    course = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-input"}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))
    privacy = forms.ChoiceField(choices=[('public', 'Public'), ('private', 'Private')], widget=forms.RadioSelect, initial='public')
    passcode = forms.CharField(max_length=4, required=False, widget=forms.PasswordInput(attrs={"class": "passcode-input"}))
    university = forms.ChoiceField(choices=[('', '-- Select --')] + [(u, u) for u in UNIVERSITIES], required=False)

# ========== HELPERS ==========
def get_all_notes():
    try:
        if SUPABASE_WORKING:
            response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
            return response.data if response.data else []
        else:
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def search_notes(query):
    notes = get_all_notes()
    if not query:
        return notes
    query = query.lower()
    return [n for n in notes if query in str(n.get("module", "")).lower() or query in str(n.get("course", "")).lower()]

# ========== VIEWS ==========
def index(request):
    return render(request, "index.html")

def browse_view(request):
    query = request.GET.get("q", "").strip()
    notes = search_notes(query) if query else get_all_notes()
    
    for note in notes:
        note["display_name"] = note.get("module", note.get("original_filename", note.get("filename", "Untitled")))
        note["is_private"] = note.get("privacy") == "private"
        note["has_passcode"] = bool(note.get("passcode"))
        note["university"] = note.get("university", "Not specified")
        note["original_filename"] = note.get("original_filename", note.get("filename", ""))
    
    return render(request, "browse.html", {"notes": notes, "query": query})

def upload_view(request):
    message = None
    error = None
    
    if request.method == "POST":
        if not SUPABASE_WORKING:
            error = "❌ Cannot upload - Supabase not connected"
            return render(request, "upload.html", {"form": UploadForm(), "message": message, "error": error})
        
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES["file"]
                ext = os.path.splitext(file.name)[1].lower()
                
                if ext not in ALLOWED_EXTENSIONS:
                    error = "File type not allowed."
                else:
                    module = form.cleaned_data.get("module", "")
                    course = form.cleaned_data.get("course", "")
                    description = form.cleaned_data.get("description", "")
                    privacy = form.cleaned_data.get("privacy", "public")
                    passcode = form.cleaned_data.get("passcode", "")
                    university = form.cleaned_data.get("university", "Not specified")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    unique_id = str(uuid.uuid4())[:8]
                    safe_filename = f"{timestamp}_{unique_id}_{file.name.replace(' ', '_')}"
                    
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
                    form = UploadForm()
                        
            except Exception as e:
                error = f"Upload failed: {str(e)}"
        else:
            error = "Please fill all required fields."
    else:
        form = UploadForm()
    
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def view_file(request, id):
    notes = get_all_notes()
    note = None
    for n in notes:
        if str(n.get("id")) == str(id):
            note = n
            break
    
    if not note:
        return HttpResponse("File not found", status=404)
    
    if note.get("privacy") == "private":
        correct = note.get("passcode", "")
        entered = request.GET.get("passcode", "")
        
        if not entered:
            return render(request, "passcode.html", {"file_id": id, "filename": note.get("original_filename", "file")})
        
        if entered != correct:
            return render(request, "passcode.html", {"file_id": id, "filename": note.get("original_filename", "file"), "error": "Wrong passcode"})
    
    file_url = supabase.storage.from_("notes").get_public_url(note["filename"])
    
    context = {
        "note": note,
        "pdf_url": file_url,
        "admin": ADMIN
    }
    return render(request, "view.html", context)

def download_file(request, id):
    notes = get_all_notes()
    note = None
    for n in notes:
        if str(n.get("id")) == str(id):
            note = n
            break
    
    if not note:
        return HttpResponse("File not found", status=404)
    
    if note.get("privacy") == "private":
        correct = note.get("passcode", "")
        entered = request.GET.get("passcode", "")
        
        if not entered:
            return HttpResponse("Access Denied. Private file.", status=403)
        
        if entered != correct:
            return HttpResponse("Access Denied. Wrong passcode.", status=403)
    
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

@csrf_exempt
def update_passcode(request, id):
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    
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
        return HttpResponse("Access Denied.", status=403)
    
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
        return HttpResponse("Access Denied.", status=403)
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
    
