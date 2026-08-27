# app.py - COMPLETE UPDATED VERSION with Admin Passcode Management
import os
import uuid
import json
import requests
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
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-key")
ADMIN = os.environ.get("ADMIN", "true") == "true"

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

from django import forms

# ========== SUPABASE ==========
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== CONSTANTS ==========
ALLOWED_EXTENSIONS = [
    '.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md',
    '.xls', '.xlsx', '.csv', '.jpg', '.jpeg', '.png', '.gif',
    '.zip', '.rar'
]

UNIVERSITIES = [
    "University of Dar es Salaam (UDSM)",
    "Sokoine University of Agriculture (SUA)",
    "Muhimbili University of Health and Allied Sciences (MUHAS)",
    "University of Dodoma (UDOM)",
    "Mzumbe University",
    "State University of Zanzibar (SUZA)",
    "Nelson Mandela African Institute of Science and Technology (NM-AIST)",
    "Ardhi University (ARU)",
    "Dar es Salaam Institute of Technology (DIT)",
    "College of Business Education (CBE)",
    "Institute of Finance Management (IFM)",
    "Tumaini University Makumira",
    "St. Augustine University of Tanzania (SAUT)",
    "Ruaha Catholic University (RUCU)",
    "Jordan University College (JUCO)",
    "Kampala International University (KIU) - Tanzania Campus",
    "Mount Meru University (MMU)",
    "Teofilo Kisanji University (TEKU)",
    "St. John's University of Tanzania (SJUT)",
    "Zanzibar University (ZU)",
    "University of Bagamoyo",
    "Kibabii University Tanzania Campus",
    "East and Southern African Management Institute (ESAMI)",
    "Moshi Co-operative University (MoCU)",
    "Tanzania Institute of Accountancy (TIA)",
    "National Institute of Transport (NIT)",
    "Tanzania Petroleum Institute (TPI)",
    "Mwalimu Nyerere Memorial Academy (MNMA)",
    "Dodoma University of Science and Technology",
    "Arusha Technical College (ATC)",
    "Karagwe Technical College",
    "Mbeya University of Science and Technology (MUST)",
    "Rukwa Technical College",
    "Tanga Technical College",
    "Kigoma Technical College",
    "Lindi Technical College",
    "Mtwara Technical College",
    "Tabora Technical College",
    "Iringa Technical College",
    "Morogoro Technical College",
    "Mwanza Technical College",
    "Kilimanjaro Technical College",
    "Singida Technical College",
    "Shinyanga Technical College",
    "Katavi Technical College",
    "Njombe Technical College",
    "Geita Technical College",
    "Simiyu Technical College",
    "Songwe Technical College",
    "Manyara Technical College",
]

# ========== FORMS ==========
class UploadForm(forms.Form):
    file = forms.FileField(label="File", widget=forms.FileInput(attrs={"class": "form-file", "required": True}))
    file_type = forms.ChoiceField(choices=[('notes', 'Notes'), ('pastpaper', 'Past Paper')], widget=forms.RadioSelect, initial='notes')
    module = forms.CharField(max_length=200, label="Module Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Computer Networks..."}))
    course = forms.CharField(max_length=200, label="Course Code", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CIT 3102..."}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Brief description..."}), label="Description", required=False)
    privacy = forms.ChoiceField(choices=[('public', 'Public'), ('private', 'Private')], widget=forms.RadioSelect, initial='public')
    passcode = forms.CharField(max_length=4, required=False, widget=forms.PasswordInput(attrs={"class": "passcode-input", "placeholder": "••••", "maxlength": "4"}))
    university = forms.ChoiceField(choices=[('', '-- Select your university --')] + [(u, u) for u in UNIVERSITIES] + [('Other', 'Other')], required=False, widget=forms.Select(attrs={"class": "form-select"}))
    custom_university = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Type your university name..."}))

# ========== HELPER FUNCTIONS ==========
def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    types = {
        '.pdf': 'application/pdf',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.csv': 'text/csv',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
    }
    return types.get(ext, 'application/octet-stream')

def get_file_icon(filename):
    ext = os.path.splitext(filename)[1].lower()
    icons = {
        '.pdf': '📄', '.ppt': '📊', '.pptx': '📊', '.doc': '📝', '.docx': '📝',
        '.xls': '📈', '.xlsx': '📈', '.txt': '📃', '.md': '📃', '.jpg': '🖼️',
        '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️', '.zip': '📦', '.rar': '📦',
    }
    return icons.get(ext, '📁')

def can_view_inline(filename):
    ext = os.path.splitext(filename)[1].lower()
    viewable = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.txt', '.md', '.csv']
    return ext in viewable

def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        notes = response.data if response.data else []
        for note in notes:
            note["original_filename"] = note.get("original_filename", note.get("filename", ""))
            note["file_size"] = note.get("file_size", 0)
            note["privacy"] = note.get("privacy", "public")
            note["file_type"] = note.get("file_type", "notes")
            note["university"] = note.get("university", "Not specified")
            note["passcode"] = note.get("passcode", "")
            note["can_view_inline"] = can_view_inline(note.get("filename", ""))
        return notes
    except Exception as e:
        print(f"Error: {e}")
        return []

def search_notes(query):
    try:
        response = supabase.table("notes").select("*").or_(f"module.ilike.%{query}%,course.ilike.%{query}%,description.ilike.%{query}%").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        return get_all_notes()

# ========== VIEWS ==========
def index(request):
    return render(request, "index.html")

def upload_view(request):
    message = None
    error = None
    
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES["file"]
                ext = os.path.splitext(file.name)[1].lower()
                
                if ext not in ALLOWED_EXTENSIONS:
                    error = f"File type not allowed."
                else:
                    file_type = form.cleaned_data.get("file_type", "notes")
                    module = form.cleaned_data.get("module", "")
                    course = form.cleaned_data.get("course", "")
                    description = form.cleaned_data.get("description", "")
                    privacy = form.cleaned_data.get("privacy", "public")
                    passcode = form.cleaned_data.get("passcode", "")
                    
                    university = form.cleaned_data.get("university", "")
                    if university == "Other":
                        university = form.cleaned_data.get("custom_university", "")
                    if not university:
                        university = "Not specified"
                    
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
                    
                    # Save metadata
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "original_filename": file.name,
                        "module": module,
                        "course": course,
                        "description": description,
                        "file_type": file_type,
                        "privacy": privacy,
                        "passcode": passcode if privacy == "private" else "",
                        "university": university,
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat(),
                        "file_size": len(file_content)
                    }).execute()
                    
                    message = f"✅ {file.name} uploaded successfully!"
                    form = UploadForm()
                        
            except Exception as e:
                error = f"Upload failed: {str(e)}"
                print(f"❌ ERROR: {error}")
        else:
            error = "Please fill all required fields."
    else:
        form = UploadForm()
    
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def browse_view(request):
    query = request.GET.get("q", "").strip()
    notes = search_notes(query) if query else get_all_notes()
    for note in notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper().replace(".", "")
        note["file_ext"] = ext if ext else "FILE"
        note["icon"] = get_file_icon(note.get("filename", ""))
        original = note.get("original_filename", note.get("filename", ""))
        note["display_name"] = original[:50] + "..." if len(original) > 50 else original
        note["can_view_inline"] = can_view_inline(note.get("filename", ""))
        note["is_private"] = note.get("privacy", "public") == "private"
        note["has_passcode"] = bool(note.get("passcode", ""))
        if not note.get("university"):
            note["university"] = "Not specified"
        if not note.get("file_type"):
            note["file_type"] = "notes"
    return render(request, "browse.html", {"notes": notes, "query": query})

def view_file(request, id):
    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        
        if not result.data:
            return HttpResponse("File not found", status=404)
        
        note = result.data[0]
        
        # ========== DIRECT FILE SERVING ==========
        file_data = supabase.storage.from_("notes").download(note["filename"])
        content_type = get_content_type(note["filename"])
        
        response = HttpResponse(file_data, content_type=content_type)
        response["Content-Disposition"] = f"inline; filename=\"{note.get('original_filename', note['filename'])}\""
        return response
        
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def download_file(request, id):
    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        
        if not result.data:
            return HttpResponse("File not found", status=404)
        
        note = result.data[0]
        
        if note.get("privacy") == "private":
            passcode = request.GET.get("passcode", "")
            if passcode != note.get("passcode", ""):
                return HttpResponse("Access Denied. Incorrect passcode.", status=403)
        
        file_data = supabase.storage.from_("notes").download(note["filename"])
        content_type = get_content_type(note["filename"])
        response = HttpResponse(file_data, content_type=content_type)
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

# ========== ADMIN PASCODE MANAGEMENT ==========
@csrf_exempt
def update_passcode(request, id):
    """Update the passcode for a private file"""
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)
    
    try:
        # Parse JSON data
        data = json.loads(request.body)
        new_passcode = data.get("passcode", "").strip()
        
        # Validate passcode
        if not new_passcode:
            return JsonResponse({"success": False, "error": "Passcode is required"})
        
        if not new_passcode.isdigit():
            return JsonResponse({"success": False, "error": "Passcode must contain only numbers"})
        
        if len(new_passcode) != 4:
            return JsonResponse({"success": False, "error": "Passcode must be exactly 4 digits"})
        
        # Check if the file exists and is private
        check_result = supabase.table("notes").select("*").eq("id", id).execute()
        if not check_result.data:
            return JsonResponse({"success": False, "error": "File not found"})
        
        note = check_result.data[0]
        if note.get("privacy") != "private":
            return JsonResponse({"success": False, "error": "File is not private"})
        
        # Update the passcode in Supabase
        supabase.table("notes").update({"passcode": new_passcode}).eq("id", id).execute()
        
        print(f"🔑 Passcode updated for file ID {id}: {new_passcode}")
        
        return JsonResponse({"success": True, "message": "Passcode updated successfully"})
        
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    except Exception as e:
        print(f"❌ Error updating passcode: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

# ========== ADMIN DASHBOARD ==========
def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    
    all_notes = get_all_notes()
    total_files = len(all_notes)
    file_types = {}
    modules = {}
    total_size = 0
    private_count = 0
    public_count = 0
    
    for note in all_notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper()
        if ext:
            file_types[ext] = file_types.get(ext, 0) + 1
        module = note.get("module", "Unknown")
        modules[module] = modules.get(module, 0) + 1
        total_size += note.get("file_size", 0)
        
        if note.get("privacy") == "private":
            private_count += 1
        else:
            public_count += 1
    
    stats = {
        "total_files": total_files,
        "file_types": file_types,
        "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:5]),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "private_count": private_count,
        "public_count": public_count
    }
    
    return render(request, "admin.html", {"notes": all_notes, "stats": stats, "admin": ADMIN})

def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    return render(request, "admin_settings.html", {})

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
    path("update-passcode/<int:id>/", update_passcode, name="update_passcode"),
    path("favicon.ico", favicon),
]

application = get_wsgi_application()
app = application

if __name__ == "__main__":
    from django.core.management import execute_from_command_line