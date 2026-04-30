# app.py
import os
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from supabase import create_client, Client

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hnszltswipxiqurkwydm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU")
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-twarvis-school-key-2024")
ADMIN = os.environ.get("ADMIN", "true") == "true"

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
                    error = "File type not allowed."
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{file.name.replace(' ', '_')}"
                    file_content = file.read()
                    supabase.storage.from_("notes").upload(safe_filename, file_content)
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat()
                    }).execute()
                    message = "✅ File uploaded successfully!"
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
    return render(request, "browse.html", {"notes": notes, "query": query, "admin": ADMIN})

def view_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        file_data = supabase.storage.from_("notes").download(note["filename"])
        response = HttpResponse(file_data, content_type=get_content_type(note["filename"]))
        disposition = "inline" if note["filename"].endswith('.pdf') else "attachment"
        response["Content-Disposition"] = f"{disposition}; filename=\"{note['filename']}\""
        return response
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def download_file(request, id):
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        file_data = supabase.storage.from_("notes").download(note["filename"])
        response = HttpResponse(file_data, content_type=get_content_type(note["filename"]))
        response["Content-Disposition"] = f"attachment; filename=\"{note['filename']}\""
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
        return redirect("/browse/")
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
    
    # Get all files
    all_notes = get_all_notes()
    
    # Get statistics
    total_files = len(all_notes)
    file_types = {}
    modules = {}
    
    for note in all_notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper()
        if ext:
            file_types[ext] = file_types.get(ext, 0) + 1
        module = note.get("module", "Unknown")
        modules[module] = modules.get(module, 0) + 1
    
    stats = {
        "total_files": total_files,
        "file_types": file_types,
        "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:5])
    }
    
    return render(request, "admin.html", {"notes": all_notes, "stats": stats, "admin": ADMIN})
# ========== END ADMIN DASHBOARD ==========

# URL patterns
urlpatterns = [
    path("", index),
    path("admin/", admin_dashboard),  # Admin portal route
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("favicon.ico", favicon),
]

application = get_wsgi_application()

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
