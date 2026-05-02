# app.py
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
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hnszltswipxiqurkwydm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU")
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-twarvis-school-key-2024")
ADMIN = os.environ.get("ADMIN", "true") == "true"

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")

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

# ========== GOOGLE DRIVE FUNCTIONS ==========
def get_drive_service():
    """Get Google Drive service using credentials from environment variable"""
    if not GOOGLE_DRIVE_FOLDER_ID:
        print("❌ No Google Drive Folder ID")
        return None
    
    if not GOOGLE_CREDENTIALS:
        print("❌ No Google credentials in environment")
        return None
    
    try:
        # FIX: Replace literal \n with actual newlines
        creds_fixed = GOOGLE_CREDENTIALS.replace('\\n', '\n')
        creds_info = json.loads(creds_fixed)
        
        # Also fix private key if needed
        if 'private_key' in creds_info and '\\n' in creds_info['private_key']:
            creds_info['private_key'] = creds_info['private_key'].replace('\\n', '\n')
        
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        print("✅ Credentials loaded from environment")
        service = build("drive", "v3", credentials=creds)
        print("✅ Drive service built")
        return service
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return None
    except Exception as e:
        print(f"❌ Google Drive auth error: {e}")
        return None

def upload_to_drive(file_content, filename):
    """Upload file to Google Drive and return file ID"""
    print(f"📤 Attempting Google Drive upload: {filename}")
    
    service = get_drive_service()
    if not service:
        print("❌ No drive service available")
        return None
    
    try:
        file_metadata = {
            "name": filename,
            "parents": [GOOGLE_DRIVE_FOLDER_ID]
        }
        print(f"📁 Target folder ID: {GOOGLE_DRIVE_FOLDER_ID}")
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), 
            mimetype=get_content_type(filename), 
            resumable=True
        )
        
        drive_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        
        file_id = drive_file.get("id")
        print(f"✅ Google Drive upload successful! ID: {file_id}")
        return file_id
    except Exception as e:
        print(f"❌ Google Drive upload error: {e}")
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
        print(f"✅ Deleted from Google Drive: {drive_id}")
    except Exception as e:
        print(f"❌ Delete error: {e}")

def is_google_drive_configured():
    """Check if Google Drive is properly configured"""
    return bool(GOOGLE_DRIVE_FOLDER_ID and GOOGLE_CREDENTIALS and GOOGLE_DRIVE_AVAILABLE)

# ========== END GOOGLE DRIVE ==========

# Allowed file extensions
ALLOWED_EXTENSIONS = [
    '.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md',
    '.xls', '.xlsx', '.csv', '.jpg', '.jpeg', '.png', '.gif',
    '.zip', '.rar'
]

def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
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
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
    }
    return content_types.get(ext, 'application/octet-stream')

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
    inline_extensions = ['.pdf', '.txt', '.md', '.jpg', '.jpeg', '.png', '.gif', '.csv']
    return ext in inline_extensions

class UploadForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CS101"}))
    course = forms.CharField(max_length=100, label="Course Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Programming"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Description..."}), label="Description")
    file = forms.FileField(label="File", widget=forms.FileInput(attrs={"class": "form-file"}))

def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        notes = response.data if response.data else []
        for note in notes:
            if note.get("file_size") is None:
                note["file_size"] = 0
            if note.get("original_filename") is None:
                note["original_filename"] = note.get("filename", "")
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
                    
                    print(f"📤 Uploading file: {safe_filename}")
                    
                    # Upload to Supabase (always)
                    supabase.storage.from_("notes").upload(safe_filename, file_content)
                    print("✅ Uploaded to Supabase")
                    
                    # Upload to Google Drive (if configured)
                    drive_id = None
                    if is_google_drive_configured():
                        print("🔄 Attempting Google Drive backup...")
                        drive_id = upload_to_drive(file_content, safe_filename)
                        if drive_id:
                            print(f"✅ Google Drive backup successful! ID: {drive_id}")
                        else:
                            print("❌ Google Drive backup failed")
                    else:
                        print("⚠️ Google Drive not configured")
                    
                    # Save metadata
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "original_filename": file.name,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat(),
                        "file_size": len(file_content),
                        "drive_id": drive_id
                    }).execute()
                    print("✅ Metadata saved to database")
                    
                    message = f"✅ {file.name} uploaded successfully!"
                    if drive_id:
                        message += " (🔥 Backed up to Google Drive - 15GB storage)"
                    form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {str(e)}"
                print(f"❌ Upload error: {e}")
        else:
            error = "Please fill all fields."
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
        note["has_drive_backup"] = bool(note.get("drive_id"))
    return render(request, "browse.html", {"notes": notes, "query": query})

def view_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        file_data = supabase.storage.from_("notes").download(note["filename"])
        content_type = get_content_type(note["filename"])
        response = HttpResponse(file_data, content_type=content_type)
        response["Content-Disposition"] = f"inline; filename=\"{note.get('original_filename', note['filename'])}\""
        return response
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def download_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
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
        
        # Delete from Google Drive if exists
        if note.get("drive_id"):
            delete_from_drive(note["drive_id"])
        
        # Delete from Supabase
        supabase.storage.from_("notes").remove([note["filename"]])
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect("/admin/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {str(e)}", status=500)

def favicon(request):
    favicon_path = os.path.join(BASE_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/x-icon")
    return HttpResponse(status=204)

# ========== ADMIN DASHBOARD ==========
def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    
    all_notes = get_all_notes()
    total_files = len(all_notes)
    file_types = {}
    modules = {}
    total_size = 0
    drive_backup_count = 0
    
    for note in all_notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper()
        if ext:
            file_types[ext] = file_types.get(ext, 0) + 1
        module = note.get("module", "Unknown")
        modules[module] = modules.get(module, 0) + 1
        total_size += note.get("file_size", 0)
        if note.get("drive_id"):
            drive_backup_count += 1
    
    stats = {
        "total_files": total_files,
        "file_types": file_types,
        "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:5]),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "drive_backup_count": drive_backup_count,
        "google_drive_configured": is_google_drive_configured()
    }
    
    return render(request, "admin.html", {"notes": all_notes, "stats": stats, "admin": ADMIN})

def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    
    google_drive_configured = is_google_drive_configured()
    
    return render(request, "admin_settings.html", {
        "google_drive_configured": google_drive_configured
    })

def test_drive(request):
    if not ADMIN:
        return HttpResponse("Not authorized", status=403)
    
    result = []
    result.append("<h2 style='color:#00ff41;'>🔧 Google Drive Diagnostic Test</h2>")
    result.append(f"<p><strong>Google Drive Libraries:</strong> {'✅ Available' if GOOGLE_DRIVE_AVAILABLE else '❌ Not available'}</p>")
    result.append(f"<p><strong>Folder ID:</strong> {GOOGLE_DRIVE_FOLDER_ID[:30] if GOOGLE_DRIVE_FOLDER_ID else 'NOT SET'}...</p>")
    result.append(f"<p><strong>GOOGLE_CREDENTIALS env var:</strong> {'✅ SET' if GOOGLE_CREDENTIALS else '❌ NOT SET'}</p>")
    
    if is_google_drive_configured():
        result.append("<p style='color:green; font-weight:bold;'>✅ Google Drive is CONFIGURED</p>")
        
        # Try actual upload test
        test_content = b"Test file content for Google Drive verification"
        test_filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        result.append(f"<p>🔄 Attempting test upload: {test_filename}</p>")
        drive_id = upload_to_drive(test_content, test_filename)
        
        if drive_id:
            result.append(f"<p style='color:green;'>✅ TEST SUCCESSFUL! File uploaded to Google Drive with ID: {drive_id}</p>")
            result.append(f"<p>🔗 Check your Google Drive folder to see the test file</p>")
            # Clean up test file
            delete_from_drive(drive_id)
            result.append(f"<p>🧹 Test file cleaned up from Google Drive</p>")
        else:
            result.append("<p style='color:red;'>❌ TEST FAILED! Could not upload to Google Drive</p>")
            result.append("<p>Check Render logs for more details</p>")
    else:
        result.append("<p style='color:red; font-weight:bold;'>❌ Google Drive is NOT configured</p>")
        result.append("<p>Please add GOOGLE_DRIVE_FOLDER_ID and GOOGLE_CREDENTIALS environment variables in Render</p>")
    
    return HttpResponse("<br>".join(result))
# ========== END ADMIN DASHBOARD ==========

# ========== SERVE FAVICON FILES ==========
def serve_favicon_16(request):
    path = os.path.join(BASE_DIR, "favicon-16x16.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    return HttpResponse(status=204)

def serve_favicon_32(request):
    path = os.path.join(BASE_DIR, "favicon-32x32.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    return HttpResponse(status=204)

def serve_apple_touch(request):
    path = os.path.join(BASE_DIR, "apple-touch-icon.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    return HttpResponse(status=204)

def serve_webmanifest(request):
    path = os.path.join(BASE_DIR, "site.webmanifest")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return HttpResponse(f.read(), content_type="application/manifest+json")
    return HttpResponse(status=204)
# ========== END FAVICON ==========

# URL patterns
urlpatterns = [
    path("", index),
    path("admin/", admin_dashboard),
    path("admin/settings/", admin_settings),
    path("admin/test-drive/", test_drive),
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("favicon.ico", favicon),
    path("favicon-16x16.png", serve_favicon_16),
    path("favicon-32x32.png", serve_favicon_32),
    path("apple-touch-icon.png", serve_apple_touch),
    path("site.webmanifest", serve_webmanifest),
]

application = get_wsgi_application()
app = application

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
