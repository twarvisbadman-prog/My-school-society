# app.py
import os
import mimetypes
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.urls import path
from supabase import create_client, Client

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hnszltswipxiqurkwydm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU")
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-twarvis-school-key-2024")
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

# Allowed file extensions - ALL TYPES
ALLOWED_EXTENSIONS = [
    # Documents
    '.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md', '.rtf', '.odt',
    # Spreadsheets
    '.xls', '.xlsx', '.csv', '.ods',
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico',
    # Archives
    '.zip', '.rar', '.7z', '.tar', '.gz',
    # Code files
    '.py', '.js', '.html', '.css', '.json', '.xml', '.cpp', '.c', '.java', 
    '.php', '.rb', '.go', '.swift', '.kt', '.sql',
    # Videos
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv',
    # Audio
    '.mp3', '.wav', '.ogg', '.flac', '.m4a',
    # Presentations
    '.pps', '.ppsx', '.key',
    # Other
    '.epub', '.mobi'
]

def get_content_type(filename):
    """Get proper MIME type for any file for inline viewing"""
    ext = os.path.splitext(filename)[1].lower()
    
    content_types = {
        # Documents
        '.pdf': 'application/pdf',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.rtf': 'application/rtf',
        '.odt': 'application/vnd.oasis.opendocument.text',
        # Spreadsheets
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.csv': 'text/csv',
        '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
        # Images
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        # Archives (will download)
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
        '.7z': 'application/x-7z-compressed',
        # Code
        '.py': 'text/x-python',
        '.js': 'application/javascript',
        '.html': 'text/html',
        '.css': 'text/css',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.cpp': 'text/x-c++src',
        '.c': 'text/x-csrc',
        '.java': 'text/x-java',
        # Media
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.mov': 'video/quicktime',
    }
    
    mime_type = content_types.get(ext)
    if mime_type:
        return mime_type
    
    guessed = mimetypes.guess_type(filename)[0]
    return guessed or 'application/octet-stream'

def can_view_inline(filename):
    """Check if file can be viewed inline in browser"""
    ext = os.path.splitext(filename)[1].lower()
    inline_extensions = [
        # Documents
        '.pdf', '.txt', '.md', '.rtf', '.csv',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
        # Code
        '.py', '.js', '.html', '.css', '.json', '.xml', '.cpp', '.c', '.java',
        # Media
        '.mp4', '.mp3', '.wav', '.ogg', '.mov',
        # Presentations
        '.ppt', '.pptx',
        # Word/Excel
        '.doc', '.docx', '.xls', '.xlsx'
    ]
    return ext in inline_extensions

def get_file_icon(filename):
    """Return appropriate emoji icon for file type"""
    ext = os.path.splitext(filename)[1].lower()
    icons = {
        '.pdf': '📄', '.ppt': '📊', '.pptx': '📊', '.doc': '📝', '.docx': '📝',
        '.xls': '📈', '.xlsx': '📈', '.txt': '📃', '.md': '📃', '.jpg': '🖼️',
        '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️', '.zip': '📦', '.rar': '📦',
        '.mp4': '🎬', '.mp3': '🎵', '.py': '🐍', '.js': '📜', '.html': '🌐',
        '.css': '🎨', '.json': '🔧', '.cpp': '⚙️', '.java': '☕', '.csv': '📊',
    }
    return icons.get(ext, '📁')

class UploadForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CS101"}))
    course = forms.CharField(max_length=100, label="Course Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Programming"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Description..."}), label="Description")
    file = forms.FileField(label="File", widget=forms.FileInput(attrs={"class": "form-file"}))

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
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{file.name.replace(' ', '_')}"
                    file_content = file.read()
                    
                    # Upload to Supabase
                    supabase.storage.from_("notes").upload(safe_filename, file_content)
                    
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
                        "file_type": ext
                    }).execute()
                    
                    message = f"✅ {file.name} uploaded successfully!"
                    form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {str(e)}"
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
    return render(request, "browse.html", {"notes": notes, "query": query})

def view_file(request, id):
    """View any file type INLINE in the browser"""
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        file_data = supabase.storage.from_("notes").download(note["filename"])
        
        content_type = get_content_type(note["filename"])
        response = HttpResponse(file_data, content_type=content_type)
        
        # FORCE inline viewing for ALL files that support it
        original_name = note.get('original_filename', note['filename'])
        
        if can_view_inline(note["filename"]):
            # Display directly in browser
            response["Content-Disposition"] = f"inline; filename=\"{original_name}\""
        else:
            # For unsupported files, still try inline with proper type
            response["Content-Disposition"] = f"inline; filename=\"{original_name}\""
        
        # Additional headers to help with inline viewing
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "public, max-age=3600"
        
        return response
    except Exception as e:
        return HttpResponse(f"Error loading file: {str(e)}", status=500)

def download_file(request, id):
    """Force download file"""
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
    
    for note in all_notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper()
        if ext:
            file_types[ext] = file_types.get(ext, 0) + 1
        module = note.get("module", "Unknown")
        modules[module] = modules.get(module, 0) + 1
        total_size += note.get("file_size", 0)
    
    stats = {
        "total_files": total_files,
        "file_types": file_types,
        "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:5]),
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }
    
    return render(request, "admin.html", {"notes": all_notes, "stats": stats, "admin": ADMIN})

def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)
    
    message = None
    error = None
    
    current_storage = os.environ.get("ADMIN_STORAGE_PREFERENCE", "supabase")
    google_drive_configured = bool(GOOGLE_DRIVE_FOLDER_ID)
    
    if request.method == "POST":
        storage_choice = request.POST.get("storage_preference", "supabase")
        
        if storage_choice == "google" and not google_drive_configured:
            error = "Google Drive is not configured."
        else:
            message = f"Storage preference set to: {storage_choice.upper()}"
    
    return render(request, "admin_settings.html", {
        "current_storage": current_storage,
        "google_drive_configured": google_drive_configured,
        "message": message,
        "error": error
    })
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
