# app.py
import os
import io
import json
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.urls import path
from supabase import create_client, Client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hnszltswipxiqurkwydm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU")
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-twarvis-school-key-2024")
ADMIN = os.environ.get("ADMIN", "true") == "true"

# Google Drive configuration (admin only feature)
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
USE_GOOGLE_DRIVE = GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID

# Admin default storage preference
ADMIN_STORAGE_PREFERENCE = os.environ.get("ADMIN_STORAGE_PREFERENCE", "supabase")  # 'supabase' or 'google'

# Django settings
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

# Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Allowed file extensions
ALLOWED_EXTENSIONS = ['.pdf', '.ppt', '.pptx', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.md', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar']

def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
    }
    return content_types.get(ext, 'application/octet-stream')

# ========== GOOGLE DRIVE INTEGRATION (Admin Only) ==========
def get_drive_service():
    """Get Google Drive service using service account"""
    if not USE_GOOGLE_DRIVE:
        return None
    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(GOOGLE_SERVICE_ACCOUNT_JSON),
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"Google Drive auth error: {e}")
        return None

def upload_to_drive(file_content, filename):
    """Upload file to Google Drive and return file ID"""
    service = get_drive_service()
    if not service:
        return None
    
    try:
        file_metadata = {
            "name": filename,
            "parents": [GOOGLE_DRIVE_FOLDER_ID]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=get_content_type(filename))
        drive_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        return drive_file.get("id")
    except Exception as e:
        print(f"Google Drive upload error: {e}")
        return None

def delete_from_drive(drive_id):
    """Delete file from Google Drive"""
    if not drive_id:
        return
    service = get_drive_service()
    if not service:
        return
    try:
        service.files().delete(fileId=drive_id).execute()
    except Exception as e:
        print(f"Google Drive delete error: {e}")
# ========== END GOOGLE DRIVE INTEGRATION ==========

class UploadForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CS101"}))
    course = forms.CharField(max_length=100, label="Course Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Programming"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Description..."}), label="Description")
    file = forms.FileField(label="File", widget=forms.FileInput(attrs={"class": "form-file"}))

class EditNoteForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name", widget=forms.TextInput(attrs={"class": "form-input"}))
    course = forms.CharField(max_length=100, label="Course Name", widget=forms.TextInput(attrs={"class": "form-input"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}), label="Description")

def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error: {e}")
        return []

def search_notes(query):
    try:
        response = supabase.table("notes").select("*").or_(f"module.ilike.%{query}%,course.ilike.%{query}%,description.ilike.%{query}%").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        return get_all_notes()

def index(request):
    return render(request, "index.html")

def upload_view(request):
    # Users don't see any storage options - completely abstracted
    message = None
    error = None
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES["file"]
                ext = os.path.splitext(file.name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    error = "File type not allowed. Please upload PDF, PPT, DOC, XLS, TXT, JPG, PNG, or ZIP files."
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{file.name.replace(' ', '_')}"
                    file_content = file.read()
                    
                    # Admin decides storage - users never know
                    drive_id = None
                    storage_type = "supabase"
                    
                    # If admin prefers Google Drive and it's available, use it
                    if ADMIN and ADMIN_STORAGE_PREFERENCE == "google" and USE_GOOGLE_DRIVE:
                        drive_id = upload_to_drive(file_content, safe_filename)
                        if drive_id:
                            storage_type = "google"
                    
                    # Always upload to Supabase as primary or fallback
                    try:
                        supabase.storage.from_("notes").upload(safe_filename, file_content)
                        if storage_type != "google":
                            storage_type = "supabase"
                    except Exception as e:
                        if not drive_id:
                            raise Exception("Upload failed. Please try again.")
                    
                    # Save metadata
                    insert_data = {
                        "filename": safe_filename,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat(),
                        "storage": storage_type,
                        "drive_id": drive_id if drive_id else None
                    }
                    supabase.table("notes").insert(insert_data).execute()
                    
                    message = "✅ Your file has been uploaded successfully!"
                    form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {str(e)}"
        else:
            error = "Please fill all fields correctly."
    else:
        form = UploadForm()
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def browse_view(request):
    # Users only see files - no storage info
    query = request.GET.get("q", "").strip()
    notes = search_notes(query) if query else get_all_notes()
    for note in notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper().replace(".", "")
        note["file_ext"] = ext if ext else "FILE"
    # Users don't see admin controls
    return render(request, "browse.html", {"notes": notes, "query": query})

def view_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        
        # User just gets the file - no idea where it's stored
        if note.get("storage") == "google" and note.get("drive_id"):
            drive_url = f"https://drive.google.com/uc?id={note['drive_id']}&export=download"
            return redirect(drive_url)
        else:
            file_data = supabase.storage.from_("notes").download(note["filename"])
            response = HttpResponse(file_data, content_type=get_content_type(note["filename"]))
            disposition = "inline" if note["filename"].endswith('.pdf') else "attachment"
            response["Content-Disposition"] = f"{disposition}; filename=\"{note['filename']}\""
            return response
    except Exception as e:
        return HttpResponse("Unable to load file. Please try again later.", status=500)

def download_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        
        if note.get("storage") == "google" and note.get("drive_id"):
            drive_url = f"https://drive.google.com/uc?id={note['drive_id']}&export=download"
            return redirect(drive_url)
        else:
            file_data = supabase.storage.from_("notes").download(note["filename"])
            response = HttpResponse(file_data, content_type=get_content_type(note["filename"]))
            response["Content-Disposition"] = f"attachment; filename=\"{note['filename']}\""
            return response
    except Exception as e:
        return HttpResponse("Unable to download file. Please try again later.", status=500)

# ========== ADMIN ONLY FUNCTIONS ==========
def delete_file(request, id):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        
        if note.get("storage") == "google" and note.get("drive_id"):
            delete_from_drive(note["drive_id"])
        
        try:
            supabase.storage.from_("notes").remove([note["filename"]])
        except:
            pass
            
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect("/admin/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {str(e)}", status=500)

def edit_note(request, id):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    
    note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
    
    if request.method == "POST":
        form = EditNoteForm(request.POST)
        if form.is_valid():
            supabase.table("notes").update({
                "module": form.cleaned_data["module"],
                "course": form.cleaned_data["course"],
                "description": form.cleaned_data["description"]
            }).eq("id", id).execute()
            return redirect("/admin/")
    else:
        form = EditNoteForm(initial={
            "module": note.get("module", ""),
            "course": note.get("course", ""),
            "description": note.get("description", "")
        })
    
    return render(request, "admin_edit.html", {"form": form, "note": note})

def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    
    message = None
    if request.method == "POST":
        new_preference = request.POST.get("storage_preference", "supabase")
        global ADMIN_STORAGE_PREFERENCE
        # In production, save this to database or environment
        os.environ["ADMIN_STORAGE_PREFERENCE"] = new_preference
        message = f"Storage preference updated to: {new_preference}"
    
    return render(request, "admin_settings.html", {
        "current_preference": ADMIN_STORAGE_PREFERENCE,
        "google_drive_available": USE_GOOGLE_DRIVE,
        "message": message
    })

def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    
    all_notes = get_all_notes()
    total_files = len(all_notes)
    file_types = {}
    modules = {}
    storage_stats = {"supabase": 0, "google": 0}
    
    for note in all_notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper()
        if ext:
            file_types[ext] = file_types.get(ext, 0) + 1
        module = note.get("module", "Unknown")
        modules[module] = modules.get(module, 0) + 1
        storage_type = note.get("storage", "supabase")
        storage_stats[storage_type] = storage_stats.get(storage_type, 0) + 1
    
    stats = {
        "total_files": total_files,
        "file_types": file_types,
        "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:10]),
        "storage_stats": storage_stats,
        "current_storage_mode": ADMIN_STORAGE_PREFERENCE
    }
    
    return render(request, "admin.html", {"notes": all_notes, "stats": stats, "admin": ADMIN})

def serve_favicon_16(request):
    favicon_path = os.path.join(BASE_DIR, "favicon-16x16.png")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    return HttpResponse(status=204)

def serve_favicon_32(request):
    favicon_path = os.path.join(BASE_DIR, "favicon-32x32.png")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    return HttpResponse(status=204)

def serve_apple_touch(request):
    favicon_path = os.path.join(BASE_DIR, "apple-touch-icon.png")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    return HttpResponse(status=204)

def serve_webmanifest(request):
    favicon_path = os.path.join(BASE_DIR, "site.webmanifest")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="application/manifest+json")
    return HttpResponse(status=204)

def favicon(request):
    favicon_path = os.path.join(BASE_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/x-icon")
    return HttpResponse(status=204)
# ========== END ADMIN FUNCTIONS ==========

# URL patterns - Users only see basic routes, admin sees extra
urlpatterns = [
    path("", index),
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("favicon.ico", favicon),
    path("favicon-16x16.png", serve_favicon_16),
    path("favicon-32x32.png", serve_favicon_32),
    path("apple-touch-icon.png", serve_apple_touch),
    path("site.webmanifest", serve_webmanifest),
]

# Admin-only routes (not visible to regular users)
if ADMIN:
    urlpatterns += [
        path("admin/", admin_dashboard),
        path("admin/delete/<int:id>/", delete_file),
        path("admin/edit/<int:id>/", edit_note),
        path("admin/settings/", admin_settings),
    ]

application = get_wsgi_application()

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
