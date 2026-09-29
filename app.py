# app.py - FULL VERSION with Cloudflare R2 + Supabase Auth + Admin Panel
import os
import uuid
import json
import re
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
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ============================================================
# LOAD .env FOR LOCAL DEVELOPMENT
# ============================================================
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Loaded .env file")
except ImportError:
    pass

# ============================================================
# SAFE ENV VAR LOADER
# ============================================================
def env(key, default=""):
    val = os.environ.get(key, "").strip()
    return val if val else default

# ============================================================
# CONFIGURATION
# ============================================================
SECRET_KEY = env("SECRET_KEY", "django-insecure-twarvis-school-key-2024")
DEBUG = env("DEBUG", "False").lower() == "true"

SUPABASE_URL = env("SUPABASE_URL", "https://hnszltswipxiqurkwydm.supabase.co")
SUPABASE_KEY = env(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhuc3psdHN3aXB4aXF1cmt3eWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTEyODcsImV4cCI6MjA5MzEyNzI4N30.JsSgMXE9JMqJAAZd-riwrr-D-5MURL6WCfuNTrAtoWU"
)

R2_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID", "5b7111f929b3cd22162e7a20ef69a09a")
R2_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY", "0cebef92f4316520d5553049763e957eb7f3f778e51cd57eeaa9b797a013d6c7")
R2_BUCKET_NAME = env("R2_BUCKET_NAME", "pdf")
R2_ENDPOINT_URL = env("R2_ENDPOINT_URL", "https://29d150504a083e2cf780e2115ebc9b28.r2.cloudflarestorage.com")
R2_PUBLIC_URL = env("R2_PUBLIC_URL", "https://pub-062ab58e23db4e31a628e6f6273a014c.r2.dev").rstrip("/")

SECRET_ADMIN_PATH = env("SECRET_ADMIN_PATH", "admin-portal-twarvis-9x7k2m4p8q3z5w6v")
ADMIN = True

_allowed = env("ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]

_csrf = env("CSRF_TRUSTED_ORIGINS", "https://*.onrender.com,http://localhost:8000")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(",") if o.strip()]

# ============================================================
# CONFIG SANITY CHECK
# ============================================================
print("=" * 60)
print("🚀 TWARVIS SCHOOL — R2 + Auth + Admin")
print("=" * 60)
print(f"📡 Supabase URL:  {SUPABASE_URL[:50]}")
print(f"🔑 Supabase Key:  {'✅ VALID JWT' if SUPABASE_KEY.startswith('eyJ') else '❌ INVALID'}")
print(f"☁️  R2 Bucket:    {R2_BUCKET_NAME}")
print(f"☁️  R2 Endpoint:  {R2_ENDPOINT_URL[:50]}")
print(f"☁️  R2 Public:    {R2_PUBLIC_URL[:50]}")
print(f"🔐 Admin URL:     /{SECRET_ADMIN_PATH}/")
print(f"🐛 Debug:         {DEBUG}")
print("=" * 60)

if not SUPABASE_KEY.startswith("eyJ"):
    print("❌ FATAL: SUPABASE_KEY is invalid!")
    raise SystemExit(1)

print("✅ Supabase key format is valid (starts with 'eyJ')")

# ============================================================
# DJANGO SETTINGS
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not settings.configured:
    settings.configure(
        DEBUG=DEBUG,
        SECRET_KEY=SECRET_KEY,
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=ALLOWED_HOSTS,
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
        CSRF_TRUSTED_ORIGINS=CSRF_TRUSTED_ORIGINS,
        X_FRAME_OPTIONS="SAMEORIGIN",
        USE_TZ=True,
        TIME_ZONE="Africa/Dar_es_Salaam",
    )

from django import forms

# ============================================================
# SUPABASE CLIENT
# ============================================================
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected!")
except Exception as e:
    print(f"❌ Supabase connection FAILED: {e}")
    raise SystemExit(1)

# ============================================================
# CLOUDFLARE R2 CLIENT
# ============================================================
r2_client = None
try:
    if R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT_URL:
        r2_client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        print("✅ Cloudflare R2 client initialized!")
    else:
        print("⚠️  R2 credentials missing — uploads will fail")
except Exception as e:
    print(f"⚠️  R2 client init failed: {e}")
    r2_client = None

# ============================================================
# CONSTANTS
# ============================================================
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

# ============================================================
# FORMS
# ============================================================
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


class EditForm(forms.Form):
    """Form for editing note metadata in admin panel."""
    module = forms.CharField(max_length=200, required=True,
                             widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Computer Networks"}))
    course = forms.CharField(max_length=200, required=True,
                             widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CIT 3102"}))
    description = forms.CharField(required=False,
                                  widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Brief description..."}))
    university = forms.CharField(max_length=200, required=False,
                                 widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., UDSM"}))
    file_type = forms.ChoiceField(
        choices=[('notes', 'Notes'), ('pastpaper', 'Past Paper')],
        widget=forms.Select(attrs={"class": "form-select"})
    )

# ============================================================
# R2 HELPERS
# ============================================================
def upload_to_r2(file_obj, key, content_type="application/octet-stream"):
    if not r2_client:
        print("❌ R2 client not initialized")
        return None
    try:
        file_obj.seek(0)
        r2_client.upload_fileobj(
            file_obj, R2_BUCKET_NAME, key,
            ExtraArgs={"ContentType": content_type, "CacheControl": "max-age=86400"},
        )
        url = f"{R2_PUBLIC_URL}/{key}"
        print(f"✅ Uploaded to R2: {url}")
        return url
    except ClientError as e:
        print(f"❌ R2 upload failed: {e}")
        return None
    except Exception as e:
        print(f"❌ R2 upload exception: {e}")
        return None


def delete_from_r2(key):
    if not r2_client:
        return False
    try:
        r2_client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        print(f"✅ Deleted from R2: {key}")
        return True
    except ClientError as e:
        print(f"❌ R2 delete failed: {e}")
        return False


def get_r2_public_url(key):
    return f"{R2_PUBLIC_URL}/{key}"


def get_r2_file_bytes(key):
    if not r2_client:
        return None
    try:
        response = r2_client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
        return response["Body"].read()
    except ClientError as e:
        print(f"❌ R2 download failed: {e}")
        return None

# ============================================================
# HELPER FUNCTIONS
# ============================================================
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

# ============================================================
# PASSCODE HTML
# ============================================================
def get_passcode_html(file_id, filename, error=None):
    error_html = f'<div class="error-msg" style="color:#ff4444;font-size:0.85rem;margin-top:12px;background:rgba(255,68,68,0.05);padding:10px;border-radius:10px;border:1px solid rgba(255,68,68,0.1);">{error}</div>' if error else '<div class="error-msg" id="passcodeError" style="color:#ff4444;font-size:0.85rem;margin-top:12px;display:none;background:rgba(255,68,68,0.05);padding:10px;border-radius:10px;border:1px solid rgba(255,68,68,0.1);">❌ Incorrect passcode. Please try again.</div>'
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Passcode Required | Student Hub</title>
    <link rel="icon" type="image/png" href="/apple-touch-icon.png">
    <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700;14..32,800;14..32,900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:'Inter',sans-serif; background:#fafaf9; min-height:100vh; display:flex; align-items:center; justify-content:center; overflow-x:hidden; padding:20px; }}
        .container {{ position:relative; z-index:2; max-width:450px; width:100%; }}
        .card {{ background:#ffffff; border:1px solid #e7e5e4; border-radius:28px; padding:40px 35px; box-shadow:0 28px 64px -20px rgba(28,25,23,.22); text-align:center; }}
        .card .lock-icon {{ display:inline-flex; align-items:center; justify-content:center; width:82px; height:82px; margin-bottom:18px; border-radius:50%; background:#fef3c7; color:#b45309; font-size:2rem; }}
        .card h1 {{ font-size:1.6rem; font-weight:800; color:#1c1917; margin-bottom:8px; }}
        .card .sub-text {{ color:#57534e; font-size:0.88rem; margin-bottom:16px; }}
        .card .filename {{ color:#44403c; font-size:0.85rem; margin-bottom:20px; padding:12px; background:#f5f5f4; border-radius:12px; border:1px solid #e7e5e4; word-break:break-all; }}
        .card .passcode-hint {{ color:#78716c; font-size:0.72rem; margin-bottom:12px; }}
        .card input {{ width:100%; padding:16px 18px; background:#fafaf9; border:1px solid #e7e5e4; border-radius:16px; color:#1c1917; font-size:1.4rem; font-family:'Courier New',monospace; letter-spacing:12px; text-align:center; transition:0.25s; outline:none; }}
        .card input:focus {{ border-color:#ea580c; background:#ffffff; box-shadow:0 0 0 4px rgba(234,88,12,.12); }}
        {error_html}
        .card button {{ width:100%; padding:15px; margin-top:16px; background:linear-gradient(120deg,#c2410c,#be185d); border:none; border-radius:999px; color:#fff; font-weight:800; font-size:1rem; cursor:pointer; transition:0.25s; box-shadow:0 8px 22px -8px rgba(219,39,119,.5); }}
        .card button:hover {{ transform:translateY(-2px); box-shadow:0 12px 28px -8px rgba(219,39,119,.6); }}
        .back-link {{ display:inline-block; margin-top:16px; color:#57534e; text-decoration:none; font-size:0.85rem; }}
        .back-link:hover {{ color:#c2410c; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <span class="lock-icon"><i class="fas fa-lock"></i></span>
            <h1>🔒 Private Document</h1>
            <p class="sub-text">Enter the passcode to view this document</p>
            <div class="filename"><i class="fas fa-file"></i> {filename}</div>
            <p class="passcode-hint">Enter the 4-digit passcode set by the uploader</p>
            <input type="password" id="passcodeInput" placeholder="••••" maxlength="4" inputmode="numeric" autofocus>
            {error_html}
            <button id="unlockBtn"><i class="fas fa-unlock"></i> Unlock Document</button>
            <div style="margin-top:12px;">
                <a href="/browse/" class="back-link"><i class="fas fa-arrow-left"></i> Back to Browse</a>
            </div>
        </div>
    </div>
    <script>
        const input = document.getElementById('passcodeInput');
        const btn = document.getElementById('unlockBtn');
        const error = document.getElementById('passcodeError');
        const fileId = {file_id};
        if (error) {{ error.style.display = 'none'; }}
        input.addEventListener('input', function() {{
            this.value = this.value.replace(/\\D/g, '').slice(0, 4);
            if (error) {{ error.classList.remove('show'); error.style.display = 'none'; }}
        }});
        btn.addEventListener('click', function() {{
            const passcode = input.value.trim();
            if (passcode.length === 4) {{
                window.location.href = `/view/{file_id}/?passcode=${{passcode}}`;
            }} else {{
                if (error) {{ error.textContent = '❌ Please enter a 4-digit passcode'; error.classList.add('show'); error.style.display = 'block'; }}
                input.value = ''; input.focus();
            }}
        }});
        input.addEventListener('keydown', function(e) {{ if (e.key === 'Enter') btn.click(); }});
        input.focus();
    </script>
</body>
</html>
'''

# ============================================================
# SERVE ROOT FILES
# ============================================================
def serve_root_file(request, filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename or ".." in safe_name or safe_name.startswith("."):
        return HttpResponse("Not found", status=404)

    file_path = os.path.join(BASE_DIR, safe_name)
    if not os.path.exists(file_path):
        return HttpResponse("Not found", status=404)

    ext = os.path.splitext(safe_name)[1].lower()
    content_types = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
        ".ico": "image/x-icon", ".css": "text/css", ".js": "application/javascript",
        ".json": "application/json", ".txt": "text/plain", ".xml": "application/xml",
        ".pdf": "application/pdf", ".woff": "font/woff", ".woff2": "font/woff2",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    try:
        with open(file_path, "rb") as f:
            data = f.read()
        response = HttpResponse(data, content_type=content_type)
        response["Cache-Control"] = "public, max-age=2592000"
        return response
    except Exception as e:
        print(f"Error serving {safe_name}: {e}")
        return HttpResponse("Error", status=500)

def favicon_view(request):
    icon_path = os.path.join(BASE_DIR, "apple-touch-icon.png")
    if os.path.exists(icon_path):
        try:
            with open(icon_path, "rb") as f:
                data = f.read()
            response = HttpResponse(data, content_type="image/png")
            response["Cache-Control"] = "public, max-age=2592000"
            return response
        except Exception as e:
            print(f"Favicon error: {e}")
    return HttpResponse(status=204)

# ============================================================
# MAIN VIEWS
# ============================================================
def index(request):
    return render(request, "index.html")

def upload_view(request):
    # Require login
    if not request.session.get("user_id"):
        return redirect("/login/")

    user_id = request.session.get("user_id")
    user_name = request.session.get("user_name", "Anonymous")

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
                    file_size = len(file_content)

                    r2_key = f"notes/{safe_filename}"
                    content_type = file.content_type or get_content_type(file.name)

                    file.seek(0)
                    r2_url = upload_to_r2(file, r2_key, content_type=content_type)

                    if not r2_url:
                        error = "Upload to storage failed. Please try again."
                    else:
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
                            "uploader": user_name,
                            "user_id": user_id,
                            "uploaded_at": datetime.now().isoformat(),
                            "file_size": file_size,
                            "downloads": 0,
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

    return render(request, "upload.html", {
        "form": form,
        "message": message,
        "error": error,
        "user_name": user_name,
    })

def browse_view(request):
    query = request.GET.get("q", "").strip()
    notes = search_notes(query) if query else get_all_notes()

    for note in notes:
        ext = os.path.splitext(note.get("filename", ""))[1].upper().replace(".", "")
        note["file_ext"] = ext if ext else "FILE"
        note["icon"] = get_file_icon(note.get("filename", ""))

        if note.get("module") and note.get("module") != "":
            note["display_name"] = note.get("module")
        else:
            original = note.get("original_filename", note.get("filename", ""))
            cleaned = re.sub(r'^\d{8}_\d{6}_', '', original)
            note["display_name"] = cleaned[:50] + "..." if len(cleaned) > 50 else cleaned

        note["can_view_inline"] = can_view_inline(note.get("filename", ""))
        note["is_private"] = note.get("privacy", "public") == "private"
        note["has_passcode"] = bool(note.get("passcode", ""))

        if not note.get("university"):
            note["university"] = "Not specified"
        if not note.get("file_type"):
            note["file_type"] = "notes"
        if not note.get("module"):
            note["module"] = "Untitled"
        if not note.get("course"):
            note["course"] = "N/A"

    return render(request, "browse.html", {"notes": notes, "query": query})

def view_file(request, id):
    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        if not result.data:
            return HttpResponse("File not found", status=404)

        note = result.data[0]

        if note.get("privacy") == "private":
            correct_passcode = note.get("passcode", "")
            get_passcode = request.GET.get("passcode", "")

            if not get_passcode:
                return HttpResponse(get_passcode_html(id, note.get("original_filename", note.get("filename", ""))))

            if get_passcode != correct_passcode:
                return HttpResponse(get_passcode_html(id, note.get("original_filename", note.get("filename", "")), "❌ Incorrect passcode. Please try again."))

        r2_key = f"notes/{note['filename']}"
        file_url = get_r2_public_url(r2_key)

        note["can_view_inline"] = can_view_inline(note.get("filename", ""))
        note["is_pdf"] = os.path.splitext(note.get("filename", ""))[1].lower() == '.pdf'
        note["is_image"] = os.path.splitext(note.get("filename", ""))[1].lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
        note["is_text"] = os.path.splitext(note.get("filename", ""))[1].lower() in ['.txt', '.md', '.csv', '.json', '.xml']

        note["text_content"] = ""
        if note["is_text"] and file_url:
            try:
                response = requests.get(file_url, timeout=10)
                if response.status_code == 200:
                    note["text_content"] = response.text
            except:
                pass

        return render(request, "view.html", {
            "note": note,
            "pdf_url": file_url,
            "admin": ADMIN,
        })

    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def download_file(request, id):
    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        if not result.data:
            return HttpResponse("File not found", status=404)

        note = result.data[0]

        if note.get("privacy") == "private":
            correct_passcode = note.get("passcode", "")
            get_passcode = request.GET.get("passcode", "")

            if not get_passcode:
                return HttpResponse("Access Denied. This file is private. Please view it first to unlock.", status=403)

            if get_passcode != correct_passcode:
                return HttpResponse("Access Denied. Incorrect passcode.", status=403)

        r2_key = f"notes/{note['filename']}"
        file_data = get_r2_file_bytes(r2_key)
        if file_data is None:
            return HttpResponse("File not found in storage", status=404)

        # Increment downloads counter (non-blocking, best effort)
        try:
            current = note.get("downloads", 0) or 0
            supabase.table("notes").update({"downloads": current + 1}).eq("id", id).execute()
        except Exception:
            pass

        content_type = get_content_type(note["filename"])
        response = HttpResponse(file_data, content_type=content_type)
        response["Content-Disposition"] = f"attachment; filename=\"{note.get('original_filename', note['filename'])}\""
        return response

    except Exception as e:
        return HttpResponse(f"Download failed: {str(e)}", status=500)

def delete_file(request, id):
    """Admin delete."""
    if not ADMIN:
        return HttpResponse("Not authorized.", status=403)
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        delete_from_r2(f"notes/{note['filename']}")
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect(f"/{SECRET_ADMIN_PATH}/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {str(e)}", status=500)

def delete_own_file(request, id):
    """User deletes their own file."""
    if not request.session.get("user_id"):
        return redirect("/login/")

    user_id = request.session.get("user_id")
    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        if not result.data:
            return HttpResponse("File not found", status=404)

        note = result.data[0]
        if note.get("user_id") != user_id:
            return HttpResponse("Not authorized to delete this file.", status=403)

        delete_from_r2(f"notes/{note['filename']}")
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect("/dashboard/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {str(e)}", status=500)

def favicon(request):
    return HttpResponse(status=204)

# ============================================================
# AUTH VIEWS
# ============================================================
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if not email or not password:
            return render(request, "login.html", {"error": "Please fill in all fields."})

        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
            if response.user and response.session:
                request.session["user_id"] = response.user.id
                request.session["user_email"] = response.user.email
                request.session["user_name"] = email.split("@")[0]
                return redirect("/dashboard/")
            return render(request, "login.html", {"error": "Invalid email or password."})
        except Exception as e:
            err = str(e)
            if "Invalid login" in err or "invalid" in err.lower():
                return render(request, "login.html", {"error": "Invalid email or password."})
            return render(request, "login.html", {"error": "Login failed. Please try again."})

    if request.session.get("user_id"):
        return redirect("/dashboard/")
    return render(request, "login.html")


def signup_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm = request.POST.get("confirm_password", "").strip()
        full_name = request.POST.get("full_name", "").strip()

        if not email or not password or not full_name:
            return render(request, "signup.html", {"error": "All fields are required."})
        if password != confirm:
            return render(request, "signup.html", {"error": "Passwords do not match."})
        if len(password) < 6:
            return render(request, "signup.html", {"error": "Password must be at least 6 characters."})

        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {"data": {"full_name": full_name}}
            })
            return render(request, "login.html", {
                "message": "Account created! Check your email to verify, then sign in."
            })
        except Exception as e:
            err = str(e)
            if "already registered" in err.lower() or "already exists" in err.lower():
                return render(request, "signup.html", {"error": "This email is already registered. Try signing in."})
            return render(request, "signup.html", {"error": f"Signup failed: {err}"})

    if request.session.get("user_id"):
        return redirect("/dashboard/")
    return render(request, "signup.html")


def logout_view(request):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    request.session.flush()
    return redirect("/")


def dashboard_view(request):
    if not request.session.get("user_id"):
        return redirect("/login/")

    user_id = request.session.get("user_id")
    user_email = request.session.get("user_email", "")
    user_name = request.session.get("user_name", "User")
    user_initial = user_name[0].upper() if user_name else "U"

    try:
        response = supabase.table("notes").select("*").eq("user_id", user_id).order("uploaded_at", desc=True).execute()
        my_notes = response.data if response.data else []
    except Exception:
        my_notes = []

    total = len(my_notes)
    public_count = sum(1 for n in my_notes if n.get("privacy") != "private")
    private_count = sum(1 for n in my_notes if n.get("privacy") == "private")
    downloads_count = sum((n.get("downloads", 0) or 0) for n in my_notes)

    return render(request, "dashboard.html", {
        "user_name": user_name,
        "user_email": user_email,
        "user_initial": user_initial,
        "my_notes": my_notes,
        "stats": {
            "total": total,
            "public": public_count,
            "private": private_count,
            "downloads": downloads_count,
        },
    })


def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            return render(request, "forgot_password.html", {"error": "Please enter your email."})

        try:
            supabase.auth.reset_password_email(email, {
                "redirect_to": "https://twarvis-school.onrender.com/reset-password/"
            })
            return render(request, "forgot_password.html", {
                "message": "Check your email! We sent you a password reset link."
            })
        except Exception:
            return render(request, "forgot_password.html", {"error": "Could not send reset email. Try again."})

    return render(request, "forgot_password.html")


def reset_password_view(request):
    if request.method == "POST":
        password = request.POST.get("password", "").strip()
        confirm = request.POST.get("confirm_password", "").strip()
        access_token = request.POST.get("access_token", "").strip()

        if not password or not confirm:
            return render(request, "reset_password.html", {"error": "Both fields required.", "access_token": access_token})
        if password != confirm:
            return render(request, "reset_password.html", {"error": "Passwords do not match.", "access_token": access_token})
        if len(password) < 6:
            return render(request, "reset_password.html", {"error": "Password must be at least 6 characters.", "access_token": access_token})

        try:
            supabase.auth.update_user({"password": password})
            return render(request, "reset_password.html", {
                "message": "Password updated! You can now sign in with your new password."
            })
        except Exception as e:
            return render(request, "reset_password.html", {"error": f"Reset failed: {str(e)}"})

    access_token = request.GET.get("access_token", "")
    return render(request, "reset_password.html", {"access_token": access_token})


def google_oauth_view(request):
    """Redirect to Google OAuth via Supabase."""
    try:
        response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://twarvis-school.onrender.com/dashboard/"
            }
        })
        return redirect(response.url)
    except Exception as e:
        return HttpResponse(f"OAuth error: {e}", status=500)

# ============================================================
# ADMIN VIEWS
# ============================================================
@csrf_exempt
def update_passcode(request, id):
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        new_passcode = data.get("passcode", "").strip()

        if not new_passcode or not new_passcode.isdigit() or len(new_passcode) != 4:
            return JsonResponse({"success": False, "error": "Passcode must be exactly 4 digits"})

        check_result = supabase.table("notes").select("*").eq("id", id).execute()
        if not check_result.data:
            return JsonResponse({"success": False, "error": "File not found"})

        note = check_result.data[0]
        if note.get("privacy") != "private":
            return JsonResponse({"success": False, "error": "File is not private"})

        supabase.table("notes").update({"passcode": new_passcode}).eq("id", id).execute()
        return JsonResponse({"success": True, "message": "Passcode updated successfully"})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def update_metadata(request, id):
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        check_result = supabase.table("notes").select("*").eq("id", id).execute()
        if not check_result.data:
            return JsonResponse({"success": False, "error": "File not found"})

        allowed_fields = ["module", "course", "description", "university", "file_type"]
        update_data = {}
        for field in allowed_fields:
            if field in data:
                update_data[field] = str(data[field]).strip()

        if not update_data:
            return JsonResponse({"success": False, "error": "No valid fields to update"})

        if "file_type" in update_data and update_data["file_type"] not in ["notes", "pastpaper"]:
            return JsonResponse({"success": False, "error": "Invalid file_type"})

        supabase.table("notes").update(update_data).eq("id", id).execute()
        return JsonResponse({"success": True, "message": "Metadata updated", "updated": update_data})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def admin_edit(request, id):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)

    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        if not result.data:
            return HttpResponse("File not found", status=404)

        note = result.data[0]
        error_message = None

        if request.method == "POST":
            module = request.POST.get("module", "").strip()
            course = request.POST.get("course", "").strip()
            description = request.POST.get("description", "").strip()
            university = request.POST.get("university", "").strip()
            file_type = request.POST.get("file_type", "notes").strip()

            if not module or not course:
                error_message = "Module and Course are required."
            else:
                supabase.table("notes").update({
                    "module": module,
                    "course": course,
                    "description": description,
                    "university": university or "Not specified",
                    "file_type": file_type,
                }).eq("id", id).execute()
                return redirect(f"/{SECRET_ADMIN_PATH}/")

        form = EditForm(initial={
            "module": note.get("module", ""),
            "course": note.get("course", ""),
            "description": note.get("description", ""),
            "university": note.get("university", ""),
            "file_type": note.get("file_type", "notes"),
        })

        return render(request, "admin_edit.html", {
            "note": note,
            "form": form,
            "error": error_message,
        })

    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


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
        "public_count": public_count,
    }

    return render(request, "admin.html", {"notes": all_notes, "stats": stats, "admin": ADMIN})


def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied. Admin only.", status=403)

    google_drive_configured = bool(
        env("GOOGLE_DRIVE_FOLDER_ID", "") and
        env("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    )

    return render(request, "admin_settings.html", {
        "google_drive_configured": google_drive_configured,
    })

# ============================================================
# OTHER PAGE VIEWS
# ============================================================
def about_view(request):
    try:
        return render(request, "about.html")
    except Exception as e:
        return HttpResponse(f"About page error: {e}", status=500)

def calculator_view(request):
    return render(request, "calculator.html")

def hackathon_view(request):
    try:
        return render(request, "hackerthon.html")
    except Exception as e:
        return HttpResponse(f"Hackathon page error: {e}", status=500)

def free_courses_view(request):
    try:
        return render(request, "free_course.html")
    except Exception as e:
        return HttpResponse(f"Free courses error: {e}", status=500)

def scanner_view(request):
    try:
        return render(request, "scanner.html")
    except Exception as e:
        return HttpResponse(f"Scanner error: {e}", status=500)

def autoquiz_view(request):
    path = os.path.join(BASE_DIR, "autoquiz.html")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
            return HttpResponse(html, content_type="text/html")
        except Exception as e:
            return HttpResponse(f"Error loading AutoQuiz: {e}", status=500)
    return HttpResponse("AutoQuiz page not found.", status=404)

# ============================================================
# URLS
# ============================================================
urlpatterns = [
    path("", index),

    # ========== AUTH ==========
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("delete-own/<int:id>/", delete_own_file, name="delete_own_file"),
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("reset-password/", reset_password_view, name="reset_password"),
    path("auth/google/", google_oauth_view, name="google_oauth"),

    # ========== ADMIN ==========
    path(f"{SECRET_ADMIN_PATH}/", admin_dashboard, name="admin_dashboard"),
    path(f"{SECRET_ADMIN_PATH}/settings/", admin_settings, name="admin_settings"),
    path("admin_edit/<int:id>/", admin_edit, name="admin_edit"),

    # ========== ROOT FILES / FAVICON ==========
    path("apple-touch-icon.png", serve_root_file, {"filename": "apple-touch-icon.png"}, name="apple_icon"),
    path("apple-touch-icon-precomposed.png", serve_root_file, {"filename": "apple-touch-icon.png"}),
    path("favicon.ico", favicon_view, name="favicon"),
    path("favicon.png", favicon_view, name="favicon_png"),

    # ========== MAIN PAGES ==========
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("update-passcode/<int:id>/", update_passcode, name="update_passcode"),
    path("update-metadata/<int:id>/", update_metadata, name="update_metadata"),

    # ========== ABOUT ==========
    path("about.html", about_view, name="about"),
    path("about/", about_view, name="about_alt"),

    # ========== CALCULATOR ==========
    path("calculator.html", calculator_view),
    path("calculator/", calculator_view, name="calculator"),

    # ========== HACKATHON ==========
    path("hackerthon.html", hackathon_view),
    path("hackerthon/", hackathon_view, name="hackerthon"),
    path("hackathon.html", hackathon_view),
    path("hackathon/", hackathon_view, name="hackathon"),

    # ========== FREE COURSES ==========
    path("free_course.html", free_courses_view),
    path("free_course/", free_courses_view, name="free_course"),
    path("free_courses.html", free_courses_view),
    path("free-courses/", free_courses_view, name="free_courses"),

    # ========== AUTOQUIZ ==========
    path("autoquiz.html", autoquiz_view, name="autoquiz"),
    path("autoquiz/", autoquiz_view, name="autoquiz_alt"),

    # ========== SCANNER ==========
    path("scanner.html", scanner_view, name="scanner"),
    path("scanner/", scanner_view, name="scanner_alt"),

    # ========== GENERIC ROOT FILE SERVER (must be LAST) ==========
    path("<str:filename>", serve_root_file, name="root_file"),
]

application = get_wsgi_application()
app = application

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    port = os.environ.get("PORT", 8000)
    execute_from_command_line([__name__, "runserver", f"0.0.0.0:{port}"])
