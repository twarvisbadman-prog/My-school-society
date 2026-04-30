# app.py
import os
import sys
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, FileResponse
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
        USE_TZ=False,
    )

from django import forms

# Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Allowed file extensions
ALLOWED_EXTENSIONS = ['.pdf', '.ppt', '.pptx', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.md', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar']

def get_content_type(filename):
    """Return appropriate content type for file"""
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

# Forms
class UploadForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name")
    course = forms.CharField(max_length=100, label="Course Name")
    description = forms.CharField(widget=forms.Textarea, label="Description")
    file = forms.FileField(label="File")

# Helper functions
def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error: {e}")
        return []

def search_notes(query):
    try:
        response = supabase.table("notes").select("*")\
            .or_(f"module.ilike.%{query}%,course.ilike.%{query}%,description.ilike.%{query}%")\
            .order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Search error: {e}")
        return get_all_notes()

# Views
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
                filename = file.name
                
                # Check file extension
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    error = f"File type not allowed. Allowed: PDF, PPT, DOC, XLS, TXT, JPG, PNG, ZIP"
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = f"{timestamp}_{filename.replace(' ', '_')}"
                    
                    # Upload to Supabase storage
                    file_content = file.read()
                    supabase.storage.from_("notes").upload(safe_filename, file_content)
                    
                    # Save metadata
                    supabase.table("notes").insert({
                        "filename": safe_filename,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat()
                    }).execute()
                    
                    message = "File uploaded successfully!"
                    form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {str(e)}"
        else:
            error = "Please fill all fields correctly."
    else:
        form = UploadForm()
    
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def browse_view(request):
    query = request.GET.get("q", "").strip()
    if query:
        notes = search_notes(query)
    else:
        notes = get_all_notes()
    
    all_notes = get_all_notes()
    courses = sorted(set(n.get("course", "") for n in all_notes if n.get("course")))
    modules = sorted(set(n.get("module", "") for n in all_notes if n.get("module")))
    
    # Add file extension info
    for note in notes:
        note["file_ext"] = os.path.splitext(note.get("filename", ""))[1].upper().replace(".", "")
    
    return render(request, "browse.html", {
        "notes": notes,
        "query": query,
        "courses": courses,
        "modules": modules,
        "admin": ADMIN,
    })

def view_file(request, id):
    try:
        response = supabase.table("notes").select("*").eq("id", id).execute()
        if not response.data:
            return HttpResponse("File not found", status=404)
        note = response.data[0]
        
        # Download file from Supabase storage
        file_data = supabase.storage.from_("notes").download(note["filename"])
        
        # Get content type
        content_type = get_content_type(note["filename"])
        
        # Return file with correct headers
        file_response = HttpResponse(file_data, content_type=content_type)
        
        # For PDFs, display inline; for others, download
        if note["filename"].endswith('.pdf'):
            file_response["Content-Disposition"] = f"inline; filename=\"{note['filename']}\""
        else:
            file_response["Content-Disposition"] = f"attachment; filename=\"{note['filename']}\""
        
        return file_response
        
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def download_file(request, id):
    try:
        response = supabase.table("notes").select("*").eq("id", id).execute()
        if not response.data:
            return HttpResponse("File not found", status=404)
        note = response.data[0]
        
        file_data = supabase.storage.from_("notes").download(note["filename"])
        content_type = get_content_type(note["filename"])
        
        file_response = HttpResponse(file_data, content_type=content_type)
        file_response["Content-Disposition"] = f"attachment; filename=\"{note['filename']}\""
        return file_response
        
    except Exception as e:
        return HttpResponse(f"Download failed: {str(e)}", status=500)

def delete_file(request, id):
    if not ADMIN:
        return HttpResponse("Not authorized.", status=403)
    
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        supabase.storage.from_("notes").remove([note["filename"]])
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect("/browse/?deleted=1")
    except Exception as e:
        return HttpResponse(f"Deletion failed: {str(e)}", status=500)

def favicon(request):
    favicon_path = os.path.join(BASE_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/x-icon")
    return HttpResponse(status=204)

def health_check(request):
    return HttpResponse("OK", status=200)

# URL patterns
urlpatterns = [
    path("", index),
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("favicon.ico", favicon),
    path("health/", health_check),
]

application = get_wsgi_application()

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
