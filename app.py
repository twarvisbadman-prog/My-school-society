# app.py - COMPLETE WORKING VERSION
import os
import io
import json
import mimetypes
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from supabase import create_client, Client

# Google Drive imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-key")
ADMIN = os.environ.get("ADMIN", "true") == "true"
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

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

# Credentials path
CREDS_PATH = "/etc/secrets/google-credentials.json"
if not os.path.exists(CREDS_PATH):
    CREDS_PATH = os.path.join(BASE_DIR, "google-credentials.json")

def get_drive_service():
    """Get Google Drive service"""
    if not GOOGLE_DRIVE_FOLDER_ID:
        return None
    if not os.path.exists(CREDS_PATH):
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDS_PATH,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def upload_to_drive(file_content, filename):
    """Upload to Google Drive"""
    service = get_drive_service()
    if not service:
        return None
    try:
        file_metadata = {"name": filename, "parents": [GOOGLE_DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype="application/octet-stream",
            resumable=True
        )
        drive_file = service.files().create(
            body=file_metadata,
            media_body=media,
            supportsAllDrives=True,
            fields="id"
        ).execute()
        return drive_file.get("id")
    except Exception as e:
        print(f"Upload error: {e}")
        return None

def is_google_drive_configured():
    return bool(GOOGLE_DRIVE_FOLDER_ID and os.path.exists(CREDS_PATH))

# Allowed file extensions
ALLOWED_EXTENSIONS = [
    '.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md',
    '.xls', '.xlsx', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar'
]

def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.csv': 'text/csv',
    }
    return types.get(ext, 'application/octet-stream')

class UploadForm(forms.Form):
    module = forms.CharField(max_length=100)
    course = forms.CharField(max_length=100)
    description = forms.CharField(widget=forms.Textarea)
    file = forms.FileField()

def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error: {e}")
        return []

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
                    error = "File type not allowed."
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{file.name.replace(' ', '_')}"
                    file_content = file.read()
                    
                    # Upload to Supabase (primary)
                    supabase.storage.from_("notes").upload(safe_filename, file_content)
                    
                    # Upload to Google Drive (backup)
                    drive_id = None
                    if is_google_drive_configured():
                        drive_id = upload_to_drive(file_content, safe_filename)
                    
                    # Save metadata
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat(),
                        "drive_id": drive_id
                    }).execute()
                    
                    message = f"✅ {file.name} uploaded!"
                    if drive_id:
                        message += " (Backed up to Google Drive)"
                    form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {e}"
        else:
            error = "Please fill all fields."
    else:
        form = UploadForm()
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def browse_view(request):
    notes = get_all_notes()
    for note in notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper().replace(".", "")
        note["file_ext"] = ext if ext else "FILE"
    return render(request, "browse.html", {"notes": notes})

def view_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        file_data = supabase.storage.from_("notes").download(note["filename"])
        response = HttpResponse(file_data, content_type=get_content_type(note["filename"]))
        response["Content-Disposition"] = f"inline; filename=\"{note['filename']}\""
        return response
    except Exception as e:
        return HttpResponse(f"Error: {e}", status=500)

def download_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        file_data = supabase.storage.from_("notes").download(note["filename"])
        response = HttpResponse(file_data, content_type=get_content_type(note["filename"]))
        response["Content-Disposition"] = f"attachment; filename=\"{note['filename']}\""
        return response
    except Exception as e:
        return HttpResponse(f"Download failed: {e}", status=500)

def delete_file(request, id):
    if not ADMIN:
        return HttpResponse("Not authorized.", status=403)
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        supabase.storage.from_("notes").remove([note["filename"]])
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect("/admin/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {e}", status=500)

def favicon(request):
    return HttpResponse(status=204)

def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    all_notes = get_all_notes()
    return render(request, "admin.html", {"notes": all_notes, "admin": ADMIN})

def test_drive(request):
    if not ADMIN:
        return HttpResponse("Not authorized", status=403)
    if not GOOGLE_DRIVE_FOLDER_ID:
        return HttpResponse("No Drive ID set. Add GOOGLE_DRIVE_FOLDER_ID environment variable.")
    if not os.path.exists(CREDS_PATH):
        return HttpResponse("No credentials file. Add google-credentials.json as a Secret File.")
    
    result = upload_to_drive(b"Test file content", f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    if result:
        return HttpResponse("✅ SUCCESS! Google Drive is working! Your files have 15GB backup storage.")
    else:
        return HttpResponse("❌ Failed. Make sure you created a SHARED DRIVE and added the service account as Content Manager.")

urlpatterns = [
    path("", index),
    path("admin/", admin_dashboard),
    path("admin/test-drive/", test_drive),
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("favicon.ico", favicon),
]

application = get_wsgi_application()
app = application

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
