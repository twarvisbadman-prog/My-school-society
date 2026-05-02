# app.py - FIXED VERSION
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
SECRET_KEY = os.environ.get("SECRET_KEY")
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
    """Upload to Google Drive - FIXED VERSION"""
    service = get_drive_service()
    if not service:
        return None
    try:
        file_metadata = {"name": filename, "parents": [GOOGLE_DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), 
            mimetype=get_content_type(filename), 
            resumable=True
        )
        
        drive_file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            supportsAllDrives=True,
            fields="id, webViewLink"
        ).execute()
        
        return {"drive_id": drive_file.get("id"), "drive_link": drive_file.get("webViewLink")}
    except Exception as e:
        print(f"Upload error: {e}")
        return None

def is_google_drive_configured():
    return bool(GOOGLE_DRIVE_FOLDER_ID and os.path.exists(CREDS_PATH))

# Allowed file extensions
ALLOWED_EXTENSIONS = [
    '.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md',
    '.xls', '.xlsx', '.csv', '.jpg', '.jpeg', '.png', '.gif',
    '.zip', '.rar'
]

def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    types = {
        '.pdf': 'application/pdf', '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain', '.md': 'text/markdown', '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.csv': 'text/csv', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
    }
    return types.get(ext, 'application/octet-stream')

class UploadForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name")
    course = forms.CharField(max_length=100, label="Course Name")
    description = forms.CharField(widget=forms.Textarea, label="Description")
    file = forms.FileField(label="File")

def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception:
        return []

def search_notes(query):
    try:
        response = supabase.table("notes").select("*").or_(f"module.ilike.%{query}%,course.ilike.%{query}%,description.ilike.%{query}%").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception:
        return get_all_notes()

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
                    
                    # Upload to Google Drive
                    drive_info = None
                    if is_google_drive_configured():
                        drive_info = upload_to_drive(file_content, safe_filename)
                    
                    # Backup to Supabase
                    supabase.storage.from_("notes").upload(safe_filename, file_content)
                    
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat(),
                        "drive_id": drive_info.get("drive_id") if drive_info else None
                    }).execute()
                    
                    message = f"✅ {file.name} uploaded!"
                    if drive_info:
                        message += " (15GB Google Drive)"
                    form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {e}"
        else:
            error = "Please fill all fields."
    else:
        form = UploadForm()
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def browse_view(request):
    query = request.GET.get("q", "")
    notes = search_notes(query) if query else get_all_notes()
    for note in notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper().replace(".", "")
        note["file_ext"] = ext if ext else "FILE"
    return render(request, "browse.html", {"notes": notes, "query": query})

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
    result = [f"<h2>Google Drive Test</h2>", f"<p>Shared Drive ID: {GOOGLE_DRIVE_FOLDER_ID}</p>"]
    if is_google_drive_configured():
        drive_info = upload_to_drive(b"Test", f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        if drive_info:
            result.append("<p style='color:green'>✅ SUCCESS! 15GB Google Drive working!</p>")
        else:
            result.append("<p style='color:red'>❌ Upload failed. Check that the service account has Content Manager permission on the Shared Drive.</p>")
    else:
        result.append("<p style='color:red'>❌ Not configured</p>")
    return HttpResponse("<br>".join(result))

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
