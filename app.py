# app.py - SECURE VERSION (Data Safe)
import os
import uuid
import json
import re
import html
import logging
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from supabase import create_client, Client

# ========== ENVIRONMENT VARIABLES ==========
# SECURE: No defaults that give admin access!
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  # Will use different keys later
SECRET_KEY = os.environ.get("SECRET_KEY")
ADMIN = os.environ.get("ADMIN", "false") == "true"  # CHANGED: Default false!
DEBUG = os.environ.get("DEBUG", "False") == "True"  # CHANGED: Default false!

# ========== VALIDATION ==========
if not SUPABASE_URL:
    raise ValueError("❌ SUPABASE_URL environment variable is required!")
if not SUPABASE_KEY:
    raise ValueError("❌ SUPABASE_KEY environment variable is required!")
if not SECRET_KEY:
    raise ValueError("❌ SECRET_KEY environment variable is required!")

# ========== LOGGING ==========
logging.basicConfig(
    level=logging.INFO if not DEBUG else logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== DJANGO SETTINGS ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Safe ALLOWED_HOSTS
ALLOWED_HOSTS_ENV = os.environ.get("ALLOWED_HOSTS", "")
if ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(",")]
else:
    if DEBUG:
        ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1"]
    else:
        # Production hosts - UPDATE THESE!
        ALLOWED_HOSTS = [
            "your-domain.com",
            "www.your-domain.com",
            "your-app.onrender.com",
            # Add your actual domains here
        ]

if not settings.configured:
    settings.configure(
        DEBUG=DEBUG,
        SECRET_KEY=SECRET_KEY,
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=ALLOWED_HOSTS,
        INSTALLED_APPS=[
            "django.contrib.staticfiles",
            "django.contrib.sessions",  # Added for security
        ],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",  # Added
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
        CSRF_TRUSTED_ORIGINS=[
            "https://*.onrender.com",
            "http://localhost:8000",
            "https://*.pages.dev",
            "https://*.workers.dev"
        ],
        X_FRAME_OPTIONS="SAMEORIGIN",
        SECURE_SSL_REDIRECT=not DEBUG,
        SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEBUG,
        SECURE_HSTS_PRELOAD=not DEBUG,
        SESSION_COOKIE_SECURE=not DEBUG,
        CSRF_COOKIE_SECURE=not DEBUG,
    )

from django import forms

# ========== SUPABASE (Using different keys for security) ==========
# NOTE: Keep using the same key for now to maintain compatibility
# Will implement separate keys in future update
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

# ========== SECURITY HELPERS ==========
def sanitize_input(value):
    """Sanitize user input to prevent XSS"""
    if value:
        return html.escape(str(value).strip())
    return ""

def log_security_event(event_type, details, request=None):
    """Log security events for monitoring"""
    ip = request.META.get('REMOTE_ADDR', 'unknown') if request else 'unknown'
    logger.warning(f"[{event_type}] IP: {ip} - {details}")

def rate_limit(request, action, limit=10, period=60):
    """Simple rate limiting using in-memory (replaces with Redis in production)"""
    # Simple in-memory rate limiting for single instance
    from django.core.cache import cache
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f"ratelimit_{action}_{ip}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, period)
    return True

def validate_file_security(file):
    """Validate uploaded file for security"""
    # Size limit: 50MB
    if file.size > 50 * 1024 * 1024:
        return False, "File too large (max 50MB)"
    
    # Check file extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' not allowed"
    
    return True, "Valid"

# ========== FORMS ==========
class UploadForm(forms.Form):
    file = forms.FileField(
        label="File", 
        widget=forms.FileInput(attrs={"class": "form-file", "required": True})
    )
    file_type = forms.ChoiceField(
        choices=[('notes', 'Notes'), ('pastpaper', 'Past Paper')],
        widget=forms.RadioSelect,
        initial='notes'
    )
    module = forms.CharField(
        max_length=200,
        label="Module Name",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Computer Networks..."})
    )
    course = forms.CharField(
        max_length=200,
        label="Course Code",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., CIT 3102..."})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Brief description..."}),
        label="Description",
        required=False
    )
    privacy = forms.ChoiceField(
        choices=[('public', 'Public'), ('private', 'Private')],
        widget=forms.RadioSelect,
        initial='public'
    )
    passcode = forms.CharField(
        max_length=4,
        required=False,
        widget=forms.PasswordInput(attrs={"class": "passcode-input", "placeholder": "••••", "maxlength": "4"})
    )
    university = forms.ChoiceField(
        choices=[('', '-- Select your university --')] + [(u, u) for u in UNIVERSITIES] + [('Other', 'Other')],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    custom_university = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Type your university name..."})
    )

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
        logger.error(f"Error fetching notes: {e}")
        return []

def search_notes(query):
    try:
        # Sanitize query
        query = sanitize_input(query)
        response = supabase.table("notes").select("*").or_(
            f"module.ilike.%{query}%,course.ilike.%{query}%,description.ilike.%{query}%"
        ).order("uploaded_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return get_all_notes()

# ========== PASSCODE HTML TEMPLATE ==========
def get_passcode_html(file_id, filename, error=None):
    error_html = f'<div class="error-msg" style="color:#ff4444;font-size:0.85rem;margin-top:12px;background:rgba(255,68,68,0.05);padding:10px;border-radius:10px;border:1px solid rgba(255,68,68,0.1);">{error}</div>' if error else '<div class="error-msg" id="passcodeError" style="color:#ff4444;font-size:0.85rem;margin-top:12px;display:none;background:rgba(255,68,68,0.05);padding:10px;border-radius:10px;border:1px solid rgba(255,68,68,0.1);">❌ Incorrect passcode. Please try again.</div>'
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Passcode Required | Twarvis School</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700;14..32,800;14..32,900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family:'Inter',sans-serif;
            background:#0a0a1a;
            min-height:100vh;
            display:flex;
            align-items:center;
            justify-content:center;
            overflow-x:hidden;
        }}
        #matrix-canvas {{
            position:fixed;
            top:0;
            left:0;
            width:100%;
            height:100%;
            z-index:0;
            background:linear-gradient(180deg,#0a0a2e 0%,#0a0a20 50%,#0a0a1a 100%);
        }}
        .container {{
            position:relative;
            z-index:2;
            max-width:450px;
            width:90%;
            padding:20px;
            animation:fadeInUp 0.6s ease;
        }}
        @keyframes fadeInUp {{
            from {{ opacity:0; transform:translateY(20px); }}
            to {{ opacity:1; transform:translateY(0); }}
        }}
        .card {{
            background:rgba(0,0,0,0.7);
            border:2px solid rgba(255,152,0,0.15);
            border-radius:28px;
            padding:40px 35px;
            backdrop-filter:blur(10px);
            box-shadow:0 0 60px rgba(255,152,0,0.03);
            text-align:center;
            animation:float 3s ease-in-out infinite;
        }}
        @keyframes float {{
            0%,100%{{transform:translateY(0px)}}
            50%{{transform:translateY(-6px)}}
        }}
        .card .lock-icon {{
            font-size:4rem;
            color:#ff9800;
            margin-bottom:16px;
            display:block;
            animation:pulse 2s ease-in-out infinite;
        }}
        @keyframes pulse {{
            0%,100%{{transform:scale(1);opacity:0.8}}
            50%{{transform:scale(1.05);opacity:1}}
        }}
        .card h1 {{
            font-size:1.8rem;
            font-weight:800;
            color:#fff;
            margin-bottom:8px;
        }}
        .card .sub-text {{
            color:rgba(255,255,255,0.25);
            font-size:0.85rem;
            margin-bottom:4px;
        }}
        .card .filename {{
            color:rgba(255,255,255,0.4);
            font-size:0.85rem;
            margin-bottom:20px;
            padding:10px;
            background:rgba(255,255,255,0.02);
            border-radius:12px;
            border:1px solid rgba(255,255,255,0.04);
            word-break:break-all;
        }}
        .card .passcode-hint {{
            color:rgba(255,255,255,0.12);
            font-size:0.7rem;
            margin-bottom:12px;
        }}
        .card input {{
            width:100%;
            padding:14px 18px;
            background:rgba(255,255,255,0.03);
            border:2px solid rgba(255,152,0,0.1);
            border-radius:16px;
            color:#fff;
            font-size:1.4rem;
            font-family:monospace;
            letter-spacing:12px;
            text-align:center;
            transition:0.3s;
            outline:none;
        }}
        .card input:focus {{
            border-color:rgba(255,152,0,0.3);
            box-shadow:0 0 30px rgba(255,152,0,0.05);
        }}
        .card input::placeholder {{
            letter-spacing:2px;
            font-size:0.9rem;
            color:rgba(255,255,255,0.08);
        }}
        {error_html}
        .card button {{
            width:100%;
            padding:14px;
            margin-top:16px;
            background:linear-gradient(135deg,#ff9800,#ff6b00);
            border:none;
            border-radius:50px;
            color:#fff;
            font-weight:700;
            font-size:1.05rem;
            cursor:pointer;
            transition:0.3s;
            animation:btnGlow 2s ease-in-out infinite;
        }}
        @keyframes btnGlow {{
            0%,100%{{box-shadow:0 0 20px rgba(255,152,0,0.1)}}
            50%{{box-shadow:0 0 40px rgba(255,152,0,0.25)}}
        }}
        .card button:hover {{
            transform:scale(1.02);
            box-shadow:0 0 50px rgba(255,152,0,0.3);
        }}
        .back-link {{
            display:inline-block;
            margin-top:16px;
            color:rgba(100,180,255,0.2);
            text-decoration:none;
            font-size:0.85rem;
            transition:0.3s;
        }}
        .back-link:hover {{
            color:#4a7cf7;
        }}
        @media(max-width:480px){{
            .card{{padding:30px 20px}}
            .card h1{{font-size:1.4rem}}
            .card input{{font-size:1.2rem;letter-spacing:8px}}
        }}
    </style>
</head>
<body>
    <canvas id="matrix-canvas"></canvas>
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
        const canvas = document.getElementById('matrix-canvas');
        const ctx = canvas.getContext('2d');
        function resizeCanvas() {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }}
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        const chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        const drops = [];
        const columns = Math.ceil(canvas.width / 20);
        for (let i = 0; i < columns; i++) drops[i] = Math.random() * -200;
        function drawRain() {{
            ctx.fillStyle = 'rgba(10, 10, 30, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            for (let i = 0; i < drops.length; i++) {{
                const char = chars[Math.floor(Math.random() * chars.length)];
                const x = i * 20;
                const y = drops[i] * 20;
                ctx.fillStyle = '#ff9800';
                ctx.shadowBlur = 8;
                ctx.shadowColor = '#ff980055';
                ctx.font = 'bold 18px monospace';
                if (y > 0 && y < canvas.height + 50) ctx.fillText(char, x, y);
                ctx.shadowBlur = 0;
                if (drops[i] * 20 > canvas.height + 50 && Math.random() > 0.98) drops[i] = 0;
                drops[i] += 0.4 + Math.random() * 0.3;
            }}
            requestAnimationFrame(drawRain);
        }}
        drawRain();

        const input = document.getElementById('passcodeInput');
        const btn = document.getElementById('unlockBtn');
        const error = document.getElementById('passcodeError');
        const fileId = {file_id};

        if (error) {{
            error.style.display = 'none';
        }}

        input.addEventListener('input', function() {{
            this.value = this.value.replace(/\\D/g, '').slice(0, 4);
            if (error) {{
                error.classList.remove('show');
                error.style.display = 'none';
            }}
        }});

        btn.addEventListener('click', function() {{
            const passcode = input.value.trim();
            if (passcode.length === 4) {{
                window.location.href = `/view/{file_id}/?passcode=${{passcode}}`;
            }} else {{
                if (error) {{
                    error.textContent = '❌ Please enter a 4-digit passcode';
                    error.classList.add('show');
                    error.style.display = 'block';
                }}
                input.value = '';
                input.focus();
            }}
        }});

        input.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter') {{
                btn.click();
            }}
        }});

        input.focus();
    </script>
</body>
</html>
'''

# ========== VIEWS ==========
def index(request):
    return render(request, "index.html")

def upload_view(request):
    message = None
    error = None
    
    if request.method == "POST":
        # Rate limiting
        if not rate_limit(request, 'upload', limit=5, period=300):
            error = "Too many uploads. Please wait 5 minutes."
            return render(request, "upload.html", {"form": UploadForm(), "error": error})
        
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES["file"]
                
                # Security validation
                valid, msg = validate_file_security(file)
                if not valid:
                    error = msg
                    return render(request, "upload.html", {"form": form, "error": error})
                
                ext = os.path.splitext(file.name)[1].lower()
                file_type = sanitize_input(form.cleaned_data.get("file_type", "notes"))
                module = sanitize_input(form.cleaned_data.get("module", ""))
                course = sanitize_input(form.cleaned_data.get("course", ""))
                description = sanitize_input(form.cleaned_data.get("description", ""))
                privacy = sanitize_input(form.cleaned_data.get("privacy", "public"))
                passcode = sanitize_input(form.cleaned_data.get("passcode", ""))
                
                university = sanitize_input(form.cleaned_data.get("university", ""))
                if university == "Other":
                    university = sanitize_input(form.cleaned_data.get("custom_university", ""))
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
                
                # Log the upload
                log_security_event('UPLOAD', f'File: {safe_filename}, Module: {module}', request)
                
                message = f"✅ {file.name} uploaded successfully!"
                form = UploadForm()
                    
            except Exception as e:
                error = f"Upload failed: {str(e)}"
                logger.error(f"Upload error: {error}")
        else:
            error = "Please fill all required fields."
    else:
        form = UploadForm()
    
    return render(request, "upload.html", {"form": form, "message": message, "error": error})

def browse_view(request):
    query = request.GET.get("q", "").strip()
    if query:
        query = sanitize_input(query)
        notes = search_notes(query)
    else:
        notes = get_all_notes()
    
    # Process each note for display
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
        # Rate limiting for passcode attempts
        if not rate_limit(request, f'view_{id}', limit=5, period=300):
            return HttpResponse("Too many attempts. Please wait 5 minutes.", status=429)
        
        result = supabase.table("notes").select("*").eq("id", id).execute()
        
        if not result.data:
            return HttpResponse("File not found", status=404)
        
        note = result.data[0]
        
        # Check if private
        if note.get("privacy") == "private":
            correct_passcode = note.get("passcode", "")
            get_passcode = request.GET.get("passcode", "")
            
            if not get_passcode:
                html = get_passcode_html(id, note.get("original_filename", note.get("filename", "")))
                return HttpResponse(html)
            
            if get_passcode != correct_passcode:
                log_security_event('PASSCODE_FAILURE', f'Failed attempt for file {id}', request)
                html = get_passcode_html(id, note.get("original_filename", note.get("filename", "")), "❌ Incorrect passcode. Please try again.")
                return HttpResponse(html)
            
            # Log successful access
            log_security_event('PASSCODE_SUCCESS', f'Successful access to file {id}', request)
        
        file_url = supabase.storage.from_("notes").get_public_url(note["filename"])
        
        note["can_view_inline"] = can_view_inline(note.get("filename", ""))
        note["is_pdf"] = os.path.splitext(note.get("filename", ""))[1].lower() == '.pdf'
        note["is_image"] = os.path.splitext(note.get("filename", ""))[1].lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
        note["is_text"] = os.path.splitext(note.get("filename", ""))[1].lower() in ['.txt', '.md', '.csv', '.json', '.xml']
        
        note["text_content"] = ""
        if note["is_text"] and file_url:
            try:
                import requests
                response = requests.get(file_url, timeout=10)
                if response.status_code == 200:
                    note["text_content"] = response.text
            except:
                pass
        
        context = {
            "note": note,
            "pdf_url": file_url,
            "admin": ADMIN
        }
        
        return render(request, "view.html", context)
        
    except Exception as e:
        logger.error(f"View error: {e}")
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
                log_security_event('DOWNLOAD_BLOCKED', f'Private file {id} - no passcode', request)
                return HttpResponse("Access Denied. This file is private. Please view it first to unlock.", status=403)
            
            if get_passcode != correct_passcode:
                log_security_event('DOWNLOAD_BLOCKED', f'Private file {id} - wrong passcode', request)
                return HttpResponse("Access Denied. Incorrect passcode.", status=403)
        
        file_data = supabase.storage.from_("notes").download(note["filename"])
        content_type = get_content_type(note["filename"])
        response = HttpResponse(file_data, content_type=content_type)
        response["Content-Disposition"] = f"attachment; filename=\"{note.get('original_filename', note['filename'])}\""
        
        # Log download
        log_security_event('DOWNLOAD', f'File: {note["filename"]}', request)
        
        return response
    except Exception as e:
        logger.error(f"Download error: {e}")
        return HttpResponse(f"Download failed: {str(e)}", status=500)

def delete_file(request, id):
    if not ADMIN:
        log_security_event('DELETE_BLOCKED', f'Unauthorized delete attempt on {id}', request)
        return HttpResponse("Not authorized.", status=403)
    
    try:
        note = supabase.table("notes").select("*").eq("id", id).execute().data[0]
        supabase.storage.from_("notes").remove([note["filename"]])
        supabase.table("notes").delete().eq("id", id).execute()
        
        log_security_event('DELETE', f'File: {note["filename"]}', request)
        return redirect("/admin/")
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return HttpResponse(f"Delete failed: {str(e)}", status=500)

def favicon(request):
    return HttpResponse(status=204)

# ========== ADMIN PASSCODE MANAGEMENT ==========
@csrf_exempt
def update_passcode(request, id):
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        new_passcode = data.get("passcode", "").strip()
        
        if not new_passcode:
            return JsonResponse({"success": False, "error": "Passcode is required"})
        
        if not new_passcode.isdigit():
            return JsonResponse({"success": False, "error": "Passcode must contain only numbers"})
        
        if len(new_passcode) != 4:
            return JsonResponse({"success": False, "error": "Passcode must be exactly 4 digits"})
        
        check_result = supabase.table("notes").select("*").eq("id", id).execute()
        if not check_result.data:
            return JsonResponse({"success": False, "error": "File not found"})
        
        note = check_result.data[0]
        if note.get("privacy") != "private":
            return JsonResponse({"success": False, "error": "File is not private"})
        
        supabase.table("notes").update({"passcode": new_passcode}).eq("id", id).execute()
        
        log_security_event('PASSCODE_UPDATE', f'Updated passcode for file {id}', request)
        
        return JsonResponse({"success": True, "message": "Passcode updated successfully"})
        
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Passcode update error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

# ========== ADMIN DASHBOARD ==========
def admin_dashboard(request):
    if not ADMIN:
        log_security_event('ADMIN_BLOCKED', 'Unauthorized admin access attempt', request)
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

# ========== NEW PAGE VIEWS ==========
def calculator_view(request):
    return render(request, "calculator.html")

def hackathon_view(request):
    return render(request, "hackathon.html")

def free_courses_view(request):
    return render(request, "free_courses.html")

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
    path("calculator/", calculator_view, name="calculator"),
    path("hackathon/", hackathon_view, name="hackathon"),
    path("free-courses/", free_courses_view, name="free_courses"),
    path("favicon.ico", favicon),
]

application = get_wsgi_application()
app = application

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line([__name__, "runserver"])
