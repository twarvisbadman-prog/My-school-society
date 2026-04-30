# app.py
import os
from datetime import datetime
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
import PyPDF2
from io import BytesIO
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hnszltswipxiqurkwydm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_-e3PeDcAUub955RltKMxdQ_bpSy1FHM")
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-twarvis-school-key-2024")
ADMIN = os.environ.get("ADMIN", "true") == "true"

# Supabase client (no Client type hint!)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# Django minimal settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
settings.configure(
    DEBUG=True,
    SECRET_KEY=SECRET_KEY,
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    INSTALLED_APPS=[
        "django.contrib.staticfiles",
    ],
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

# Forms
class UploadForm(forms.Form):
    module = forms.CharField(max_length=100, label="Module Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CS101"}))
    course = forms.CharField(max_length=100, label="Course Name", widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Introduction to Programming"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Brief description of the notes or paper..."}), label="Description")
    file = forms.FileField(label="PDF File", widget=forms.FileInput(attrs={"class": "form-file", "accept": ".pdf"}))

# Helper functions
def get_all_notes():
    try:
        response = supabase.table("notes").select("*").order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching notes: {e}")
        return []

def search_notes(query):
    try:
        # Simple search using PostgreSQL ilike
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
                if not file.name.endswith(".pdf"):
                    error = "Only PDF files are allowed."
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}_{file.name.replace(' ', '_')}"
                    
                    # Upload to Supabase storage
                    file_content = file.read()
                    supabase.storage.from_("notes").upload(filename, file_content)
                    
                    # Save metadata to Supabase table
                    supabase.table("notes").insert({
                        "filename": filename,
                        "module": form.cleaned_data["module"],
                        "course": form.cleaned_data["course"],
                        "description": form.cleaned_data["description"],
                        "uploader": "user",
                        "uploaded_at": datetime.now().isoformat()
                    }).execute()
                    
                    message = "File uploaded successfully!"
                    form = UploadForm()  # Reset form
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
    
    # Get unique courses and modules for filter sidebar
    all_notes = get_all_notes()
    courses = sorted(set(n.get("course", "") for n in all_notes if n.get("course")))
    modules = sorted(set(n.get("module", "") for n in all_notes if n.get("module")))
    
    return render(request, "browse.html", {
        "notes": notes,
        "query": query,
        "courses": courses,
        "modules": modules,
        "admin": ADMIN,
    })

def view_pdf(request, id):
    try:
        # Get note metadata
        response = supabase.table("notes").select("*").eq("id", id).execute()
        if not response.data:
            return HttpResponse("Note not found", status=404)
        note = response.data[0]
        
        # Get public URL from Supabase storage
        public_url = supabase.storage.from_("notes").get_public_url(note["filename"])
        
        return render(request, "view.html", {"note": note, "pdf_url": public_url})
    except Exception as e:
        return HttpResponse(f"Error loading PDF: {str(e)}", status=500)

def download_pdf(request, id):
    try:
        response = supabase.table("notes").select("*").eq("id", id).execute()
        if not response.data:
            return HttpResponse("Note not found", status=404)
        note = response.data[0]
        
        # Download file from Supabase storage
        file_data = supabase.storage.from_("notes").download(note["filename"])
        
        # Create response with PDF
        file_response = HttpResponse(file_data, content_type="application/pdf")
        file_response["Content-Disposition"] = f"attachment; filename=\"{note['filename']}\""
        return file_response
    except Exception as e:
        return HttpResponse(f"Download failed: {str(e)}", status=500)

def delete_file(request, id):
    if not ADMIN:
        return HttpResponse("Not authorized. Set ADMIN=true to enable deletion.", status=403)
    
    try:
        # Get note metadata
        response = supabase.table("notes").select("*").eq("id", id).execute()
        if not response.data:
            return HttpResponse("Note not found", status=404)
        note = response.data[0]
        
        # Delete from storage
        supabase.storage.from_("notes").remove([note["filename"]])
        
        # Delete from database
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

# URL patterns
urlpatterns = [
    path("", index),
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_pdf),
    path("download/<int:id>/", download_pdf),
    path("delete/<int:id>/", delete_file),
    path("favicon.ico", favicon),
]

# WSGI application
application = get_wsgi_application()

# Run locally if executed directly
if __name__ == "__main__":
    from django.core.management import runserver
    runserver.run("0.0.0.0:8000")
