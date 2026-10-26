# app.py — Student Hub · Full build (v2)
# R2 + Supabase Auth + Gamification + Community + Leaderboard + Notifications + Quiz + Upload Streak + Admin User Mgmt
import os
import uuid
import json
import re
import requests
from datetime import datetime, date, timedelta
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django import forms
from django.urls import path
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.deprecation import MiddlewareMixin
from supabase import create_client, Client
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ── Quiz engine (separate module) ──
import quiz as quiz_engine

# ============================================================
# LOAD .env
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

_csrf = env("CSRF_TRUSTED_ORIGINS", "https://*.onrender.com,https://*.vercel.app,http://localhost:8000")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(",") if o.strip()]

# ============================================================
# SANITY CHECK
# ============================================================
print("=" * 60)
print("🚀 STUDENT HUB — Full Build v2")
print("=" * 60)
print(f"📡 Supabase URL:  {SUPABASE_URL[:50]}")
print(f"🔑 Supabase Key:  {'✅ VALID JWT' if SUPABASE_KEY.startswith('eyJ') else '❌ INVALID'}")
print(f"☁️  R2 Bucket:    {R2_BUCKET_NAME}")
print(f"🔐 Admin URL:     /{SECRET_ADMIN_PATH}/")
print(f"🧠 Quiz bank:     {quiz_engine.total_questions()} questions loaded")
print(f"🐛 Debug:         {DEBUG}")
print("=" * 60)

if not SUPABASE_KEY.startswith("eyJ"):
    raise SystemExit("❌ FATAL: SUPABASE_KEY is invalid!")

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
            "app.SessionMiddleware",
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
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        CSRF_COOKIE_SAMESITE="Lax",
        CSRF_COOKIE_HTTPONLY=False,
    )

# ============================================================
# SUPABASE
# ============================================================
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected!")
except Exception as e:
    print(f"❌ Supabase connection FAILED: {e}")
    raise SystemExit(1)

# ============================================================
# CLOUDFLARE R2
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
# SESSION MIDDLEWARE
# ============================================================
class SessionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.current_user = None
        request._refresh_cookies = None

        token = request.COOKIES.get("sb-access-token") or \
                request.META.get("HTTP_AUTHORIZATION", "").replace("Bearer ", "").strip()
        refresh = request.COOKIES.get("sb-refresh-token")

        if token:
            try:
                resp = supabase.auth.get_user(token)
                if resp and resp.user:
                    request.current_user = self._build_user(resp.user, token)
                    return
            except Exception as e:
                print(f"[session] access token invalid: {e}")

        if refresh:
            try:
                sess = supabase.auth.refresh_session(refresh)
                if sess and sess.session and sess.user:
                    request.current_user = self._build_user(sess.user, sess.session.access_token)
                    request._refresh_cookies = {
                        "access_token": sess.session.access_token,
                        "refresh_token": sess.session.refresh_token,
                    }
            except Exception as e:
                print(f"[session] refresh failed: {e}")

    def process_response(self, request, response):
        try:
            cookies = getattr(request, "_refresh_cookies", None)
            if cookies:
                response.set_cookie("sb-access-token", cookies["access_token"],
                                    httponly=True, max_age=60*60*24*7, samesite="Lax")
                response.set_cookie("sb-refresh-token", cookies["refresh_token"],
                                    httponly=True, max_age=60*60*24*30, samesite="Lax")
        except Exception as e:
            print(f"[session] cookie set failed: {e}")
        return response

    @staticmethod
    def _build_user(user, token):
        profile_data = None
        try:
            p = supabase.table("users").select("*").eq("id", user.id).execute()
            profile_data = p.data[0] if p.data else None

            if not profile_data:
                profile_data = SessionMiddleware._create_profile(user)
                if profile_data:
                    print(f"[session] ✅ Created profile for {user.email}")
                    try:
                        update_streak(user.id)
                        p2 = supabase.table("users").select("*").eq("id", user.id).execute()
                        profile_data = p2.data[0] if p2.data else profile_data
                    except Exception:
                        pass
            else:
                if not profile_data.get("username"):
                    new_username = SessionMiddleware._generate_unique_username(user.email, user.id)
                    try:
                        supabase.table("users").update({"username": new_username}).eq("id", user.id).execute()
                        profile_data["username"] = new_username
                        print(f"[session] ✅ Fixed username for {user.email} → @{new_username}")
                    except Exception as e:
                        print(f"[session] ❌ username fix failed: {e}")

                meta = getattr(user, "user_metadata", None) or {}
                updates = {}
                if not profile_data.get("full_name") and meta.get("name"):
                    updates["full_name"] = meta.get("name")
                if not profile_data.get("avatar_url"):
                    pic = meta.get("avatar_url") or meta.get("picture")
                    if pic:
                        updates["avatar_url"] = pic
                if updates:
                    try:
                        supabase.table("users").update(updates).eq("id", user.id).execute()
                        profile_data.update(updates)
                    except Exception as e:
                        print(f"[session] ⚠️ Failed to update fields: {e}")
        except Exception as e:
            print(f"[session] _build_user error: {e}")

        return {"id": user.id, "email": user.email, "profile": profile_data, "token": token}

    @staticmethod
    def _generate_unique_username(email, user_id):
        base = (email.split("@")[0] if email else "student").lower()
        base = base.replace(".", "_").replace("-", "_")
        base = re.sub(r'[^a-z0-9_]', '', base)[:20] or "student"
        username = base
        try:
            check = supabase.table("users").select("id").eq("username", username).execute()
            if check.data and check.data[0]["id"] != str(user_id):
                username = f"{base}_{str(user_id)[:4]}"
        except Exception:
            pass
        return username

    @staticmethod
    def _create_profile(user):
        try:
            meta = getattr(user, "user_metadata", None) or {}
            email = user.email or ""
            full_name = (meta.get("full_name") or meta.get("name") or meta.get("user_name")
                         or (email.split("@")[0] if email else "Student"))
            avatar_url = meta.get("avatar_url") or meta.get("picture") or ""
            username = SessionMiddleware._generate_unique_username(email, user.id)

            payload = {
                "id": user.id, "email": email, "full_name": full_name, "username": username,
                "points": 0, "current_streak": 0, "longest_streak": 0,
                "uploads_count": 0, "likes_received": 0, "likes_given": 0,
                "quizzes_taken": 0, "quizzes_correct": 0,
            }
            if avatar_url:
                payload["avatar_url"] = avatar_url

            supabase.table("users").insert(payload).execute()
            p = supabase.table("users").select("*").eq("id", user.id).execute()
            return p.data[0] if p.data else None
        except Exception as e:
            print(f"[session] _create_profile error: {e}")
            try:
                p = supabase.table("users").select("*").eq("id", user.id).execute()
                return p.data[0] if p.data else None
            except Exception:
                return None

# ============================================================
# CONSTANTS
# ============================================================
ALLOWED_EXTENSIONS = [
    '.pdf', '.ppt', '.pptx', '.doc', '.docx', '.txt', '.md',
    '.xls', '.xlsx', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar'
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
    "Rukwa Technical College", "Tanga Technical College",
    "Kigoma Technical College", "Lindi Technical College",
    "Mtwara Technical College", "Tabora Technical College",
    "Iringa Technical College", "Morogoro Technical College",
    "Mwanza Technical College", "Kilimanjaro Technical College",
    "Singida Technical College", "Shinyanga Technical College",
    "Katavi Technical College", "Njombe Technical College",
    "Geita Technical College", "Simiyu Technical College",
    "Songwe Technical College", "Manyara Technical College",
]

# ============================================================
# AUTH HELPERS
# ============================================================
def get_current_user(request):
    return getattr(request, "current_user", None)


def build_view_context(request):
    me = get_current_user(request)
    if not me or not me.get("profile"):
        return {"is_authenticated": False, "current_student": None, "profile": None}

    p = me["profile"]
    streak = p.get("current_streak", 0) or 0

    if streak >= 100:
        token = {"emoji": "🐉", "badge_class": "tier-legendary"}
    elif streak >= 30:
        token = {"emoji": "🦁", "badge_class": "tier-epic"}
    elif streak >= 14:
        token = {"emoji": "🐺", "badge_class": "tier-rare"}
    elif streak >= 7:
        token = {"emoji": "🦊", "badge_class": "tier-uncommon"}
    elif streak >= 3:
        token = {"emoji": "🐰", "badge_class": "tier-common"}
    else:
        token = {"emoji": "🐣", "badge_class": "tier-starter"}

    username = p.get("username") or p.get("full_name") or me["email"].split("@")[0]
    initial = (username[0] if username else "S").upper()

    current_student = {
        "id": me["id"],
        "email": me["email"],
        "username": username,
        "full_name": p.get("full_name", ""),
        "avatar_url": p.get("avatar_url", ""),
        "university": p.get("university", ""),
        "initial": initial,
        "streak": streak,
        "longest_streak": p.get("longest_streak", 0) or 0,
        "points": p.get("points", 0) or 0,
        "uploads_count": p.get("uploads_count", 0) or 0,
        "likes_received": p.get("likes_received", 0) or 0,
        "token_details": token,
    }

    return {"is_authenticated": True, "current_student": current_student, "profile": current_student}


def auto_username_from_email(email, user_id):
    base = email.split("@")[0].lower().replace(".", "_").replace("-", "_")[:20]
    base = re.sub(r'[^a-z0-9_]', '', base) or "student"
    try:
        check = supabase.table("users").select("id").eq("username", base).execute()
        if check.data and check.data[0]["id"] != str(user_id):
            base = f"{base}_{str(user_id)[:4]}"
    except Exception:
        pass
    return base

# ============================================================
# STREAK + POINTS
# ============================================================
def award_points(user_id, action, points, reference_id=None):
    try:
        user_id = str(user_id)
        reference_id = str(reference_id) if reference_id else None
        row = supabase.table("users").select("points").eq("id", user_id).execute()
        if not row.data:
            return
        current = row.data[0].get("points", 0) or 0
        supabase.table("users").update({"points": current + points}).eq("id", user_id).execute()
        try:
            supabase.table("activity_log").insert({
                "user_id": user_id, "action": str(action),
                "points": int(points), "reference_id": reference_id,
            }).execute()
        except Exception as log_err:
            print(f"[award_points] log failed: {log_err}")
    except Exception as e:
        print(f"[award_points] {e}")


def update_streak(user_id):
    try:
        user_id = str(user_id)
        row = supabase.table("users").select(
            "current_streak, longest_streak, last_active_date, points"
        ).eq("id", user_id).execute()
        if not row.data:
            return
        u = row.data[0]
        today = date.today()
        last = u.get("last_active_date")
        if last:
            try:
                last = date.fromisoformat(str(last))
            except Exception:
                last = None
        current = u.get("current_streak", 0) or 0
        longest = u.get("longest_streak", 0) or 0

        if last == today:
            return

        points_awarded = 0
        if last == today - timedelta(days=1):
            current += 1
            points_awarded = 5
        else:
            current = 1
            points_awarded = 2

        if current > longest:
            longest = current
        if current in (7, 30, 100, 365):
            points_awarded += current

        supabase.table("users").update({
            "current_streak": current, "longest_streak": longest,
            "last_active_date": today.isoformat(),
            "points": (u.get("points", 0) or 0) + points_awarded,
        }).eq("id", user_id).execute()

        if points_awarded > 0:
            try:
                supabase.table("activity_log").insert({
                    "user_id": user_id, "action": "streak_day",
                    "points": points_awarded, "reference_id": today.isoformat(),
                }).execute()
            except Exception:
                pass
    except Exception as e:
        print(f"[update_streak] {e}")

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
        return None
    try:
        file_obj.seek(0)
        r2_client.upload_fileobj(file_obj, R2_BUCKET_NAME, key,
            ExtraArgs={"ContentType": content_type, "CacheControl": "max-age=86400"})
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
# HELPERS
# ============================================================
def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    types = {
        '.pdf': 'application/pdf', '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain', '.md': 'text/markdown', '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.csv': 'text/csv', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
    }
    return types.get(ext, 'application/octet-stream')


def get_file_icon(filename):
    ext = os.path.splitext(filename)[1].lower()
    icons = {'.pdf': '📄', '.ppt': '📊', '.pptx': '📊', '.doc': '📝', '.docx': '📝',
             '.xls': '📈', '.xlsx': '📈', '.txt': '📃', '.md': '📃',
             '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️',
             '.zip': '📦', '.rar': '📦'}
    return icons.get(ext, '📁')


def can_view_inline(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.txt', '.md', '.csv']


def get_all_notes(current_user_id=None):
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
            try:
                lk = supabase.table("note_likes").select("*", count="exact").eq("note_id", note["id"]).execute()
                note["like_count"] = lk.count if hasattr(lk, "count") and lk.count is not None else len(lk.data or [])
            except Exception:
                note["like_count"] = 0
            note["user_liked"] = False
            if current_user_id:
                try:
                    ul = supabase.table("note_likes").select("id") \
                        .eq("user_id", str(current_user_id)).eq("note_id", note["id"]).execute()
                    note["user_liked"] = bool(ul.data)
                except Exception:
                    pass
        return notes
    except Exception as e:
        print(f"[get_all_notes] {e}")
        return []


def search_notes(query, current_user_id=None):
    try:
        response = supabase.table("notes").select("*").or_(
            f"module.ilike.%{query}%,course.ilike.%{query}%,description.ilike.%{query}%"
        ).order("uploaded_at", desc=True).execute()
        notes = response.data if response.data else []
        for note in notes:
            try:
                lk = supabase.table("note_likes").select("*", count="exact").eq("note_id", note["id"]).execute()
                note["like_count"] = lk.count if hasattr(lk, "count") and lk.count is not None else len(lk.data or [])
            except Exception:
                note["like_count"] = 0
            note["user_liked"] = False
            if current_user_id:
                try:
                    ul = supabase.table("note_likes").select("id") \
                        .eq("user_id", str(current_user_id)).eq("note_id", note["id"]).execute()
                    note["user_liked"] = bool(ul.data)
                except Exception:
                    pass
        return notes
    except Exception as e:
        print(f"[search_notes] {e}")
        return get_all_notes(current_user_id)

# ============================================================
# PASSCODE HTML
# ============================================================
def get_passcode_html(file_id, filename, error=None):
    error_html = f'<div style="color:#ff4444;font-size:0.85rem;margin-top:12px;background:rgba(255,68,68,0.05);padding:10px;border-radius:10px;border:1px solid rgba(255,68,68,0.1);">{error}</div>' if error else '<div id="passcodeError" style="color:#ff4444;font-size:0.85rem;margin-top:12px;display:none;background:rgba(255,68,68,0.05);padding:10px;border-radius:10px;border:1px solid rgba(255,68,68,0.1);">❌ Incorrect passcode. Please try again.</div>'

    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Passcode Required | Student Hub</title>
    <link rel="icon" type="image/png" href="/apple-touch-icon.png">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:'Inter',sans-serif; background:#fafaf9; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; }}
        .container {{ max-width:450px; width:100%; }}
        .card {{ background:#fff; border:1px solid #e7e5e4; border-radius:28px; padding:40px 35px; box-shadow:0 28px 64px -20px rgba(28,25,23,.22); text-align:center; }}
        .lock-icon {{ display:inline-flex; align-items:center; justify-content:center; width:82px; height:82px; margin-bottom:18px; border-radius:50%; background:#fef3c7; color:#b45309; font-size:2rem; }}
        .card h1 {{ font-size:1.6rem; font-weight:800; color:#1c1917; margin-bottom:8px; }}
        .sub-text {{ color:#57534e; font-size:0.88rem; margin-bottom:16px; }}
        .filename {{ color:#44403c; font-size:0.85rem; margin-bottom:20px; padding:12px; background:#f5f5f4; border-radius:12px; border:1px solid #e7e5e4; word-break:break-all; }}
        .passcode-hint {{ color:#78716c; font-size:0.72rem; margin-bottom:12px; }}
        input {{ width:100%; padding:16px 18px; background:#fafaf9; border:1px solid #e7e5e4; border-radius:16px; color:#1c1917; font-size:1.4rem; font-family:'Courier New',monospace; letter-spacing:12px; text-align:center; outline:none; }}
        input:focus {{ border-color:#ea580c; background:#fff; box-shadow:0 0 0 4px rgba(234,88,12,.12); }}
        button {{ width:100%; padding:15px; margin-top:16px; background:linear-gradient(120deg,#c2410c,#be185d); border:none; border-radius:999px; color:#fff; font-weight:800; font-size:1rem; cursor:pointer; box-shadow:0 8px 22px -8px rgba(219,39,119,.5); }}
        .back-link {{ display:inline-block; margin-top:16px; color:#57534e; text-decoration:none; font-size:0.85rem; }}
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
            <div style="margin-top:12px;"><a href="/browse/" class="back-link"><i class="fas fa-arrow-left"></i> Back to Browse</a></div>
        </div>
    </div>
    <script>
        const input = document.getElementById('passcodeInput');
        const btn = document.getElementById('unlockBtn');
        const error = document.getElementById('passcodeError');
        if (error) error.style.display = 'none';
        input.addEventListener('input', function() {{
            this.value = this.value.replace(/\\D/g, '').slice(0, 4);
        }});
        btn.addEventListener('click', function() {{
            const passcode = input.value.trim();
            if (passcode.length === 4) {{
                window.location.href = `/view/{file_id}/?passcode=${{passcode}}`;
            }} else {{
                if (error) {{ error.textContent = '❌ Please enter a 4-digit passcode'; error.style.display = 'block'; }}
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
# SERVE FILES
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
        ".png": "image/png", 
        ".jpg": "image/jpeg", 
        ".jpeg": "image/jpeg",
        ".gif": "image/gif", 
        ".svg": "image/svg+xml", 
        ".webp": "image/webp",
        ".ico": "image/x-icon", 
        ".css": "text/css", 
        ".js": "application/javascript",
        ".json": "application/json", 
        ".txt": "text/plain", 
        ".xml": "application/xml",
        ".pdf": "application/pdf", 
        ".woff": "font/woff", 
        ".woff2": "font/woff2",
        ".mp4": "video/mp4"
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


def serve_subfolder_file(request, subpath):
    safe_subpath = os.path.normpath(subpath).replace("\\", "/")
    if safe_subpath.startswith("..") or safe_subpath.startswith("/") or ".." in safe_subpath.split("/"):
        return HttpResponse("Not found", status=404)
    file_path = os.path.join(BASE_DIR, safe_subpath)
    real_path = os.path.realpath(file_path)
    real_base = os.path.realpath(BASE_DIR)
    if not real_path.startswith(real_base):
        return HttpResponse("Not found", status=404)
    if not os.path.exists(real_path) or os.path.isdir(real_path):
        return HttpResponse("Not found", status=404)
    ext = os.path.splitext(real_path)[1].lower()
    content_types = {".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
                     ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
                     ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
                     ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml",
                     ".webp": "image/webp", ".ico": "image/x-icon", ".woff": "font/woff",
                     ".woff2": "font/woff2", ".ttf": "font/ttf", ".otf": "font/otf",
                     ".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8",
                     ".md": "text/markdown; charset=utf-8", ".mp4": "video/mp4",
                     ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav"}
    content_type = content_types.get(ext, "application/octet-stream")
    try:
        with open(real_path, "rb") as f:
            data = f.read()
        response = HttpResponse(data, content_type=content_type)
        response["Cache-Control"] = "public, max-age=300" if ext in (".html", ".htm") else "public, max-age=2592000"
        return response
    except Exception as e:
        print(f"Error serving {safe_subpath}: {e}")
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
# AUTH VIEWS
# ============================================================
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("username", "").strip().lower() or request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user = resp.user
            session = resp.session
            existing = supabase.table("users").select("*").eq("id", user.id).execute()
            if not existing.data:
                SessionMiddleware._create_profile(user)
            else:
                prof = existing.data[0]
                if not prof.get("username"):
                    auto_username = auto_username_from_email(user.email, user.id)
                    supabase.table("users").update({"username": auto_username}).eq("id", user.id).execute()
            update_streak(user.id)
            next_url = request.GET.get("next", "/dashboard/")
            response = redirect(next_url)
            response.set_cookie("sb-access-token", session.access_token,
                                httponly=True, max_age=60*60*24*7, samesite="Lax")
            response.set_cookie("sb-refresh-token", session.refresh_token,
                                httponly=True, max_age=60*60*24*30, samesite="Lax")
            return response
        except Exception as e:
            print(f"[login] {e}")
            return render(request, "login.html", {
                "error": "Invalid email or password.",
                "supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY,
            })
    return render(request, "login.html", {"supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY})


def signup_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        full_name = request.POST.get("full_name", "").strip()
        confirm = request.POST.get("confirm_password", "")
        if password != confirm:
            return render(request, "signup.html", {
                "error": "Passwords do not match.",
                "supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY,
            })
        if len(password) < 6:
            return render(request, "signup.html", {
                "error": "Password must be at least 6 characters.",
                "supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY,
            })
        try:
            supabase.auth.sign_up({
                "email": email, "password": password,
                "options": {"data": {"full_name": full_name}},
            })
            return render(request, "signup.html", {
                "message": "Account created! Check your email to verify, then log in.",
                "supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY,
            })
        except Exception as e:
            err = str(e)
            if "already registered" in err.lower() or "already exists" in err.lower():
                err = "This email is already registered. Try logging in."
            return render(request, "signup.html", {
                "error": err,
                "supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY,
            })
    return render(request, "signup.html", {"supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY})


def logout_view(request):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    response = redirect("/")
    response.delete_cookie("sb-access-token")
    response.delete_cookie("sb-refresh-token")
    return response


def oauth_callback(request):
    return render(request, "auth_callback.html", {"supabase_url": SUPABASE_URL, "supabase_anon": SUPABASE_KEY})


def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if not email:
            return render(request, "forgot_password.html", {"error": "Please enter your email."})
        try:
            supabase.auth.reset_password_email(
                email, {"redirect_to": f"{request.scheme}://{request.get_host()}/reset-password/"})
        except Exception as e:
            print(f"[forgot_password] {e}")
        return render(request, "forgot_password.html", {
            "message": "If that email is registered, we've sent a reset link. Check your inbox.",
        })
    return render(request, "forgot_password.html")


def reset_password_view(request):
    return render(request, "reset_password.html")


def dashboard_view(request):
    me = get_current_user(request)
    if not me:
        return redirect(f"/login/?next=/dashboard/")
    try:
        uploads = supabase.table("notes").select("*").eq("uploader_id", str(me["id"])) \
            .order("uploaded_at", desc=True).execute().data or []
    except Exception:
        uploads = []
    today = date.today().isoformat()
    try:
        quiz = supabase.table("quiz_attempts").select("*") \
            .eq("user_id", str(me["id"])).eq("quiz_date", today).execute().data
        quiz_today = quiz[0] if quiz else None
    except Exception:
        quiz_today = None
    ctx = build_view_context(request)
    ctx.update({"me": me["profile"], "uploads": uploads, "quiz_today": quiz_today})
    return render(request, "dashboard.html", ctx)


@ensure_csrf_cookie
def profile_view(request, username):
    try:
        row = supabase.table("users").select("*").eq("username", username).execute()
        if not row.data:
            return HttpResponse("User not found", status=404)
        profile = row.data[0]

        try:
            uploads = supabase.table("notes").select("*").eq("uploader_id", str(profile["id"])) \
                .order("uploaded_at", desc=True).limit(20).execute().data or []
        except Exception:
            uploads = []

        try:
            followers = supabase.table("follows").select("*", count="exact") \
                .eq("following_id", str(profile["id"])).execute()
            following = supabase.table("follows").select("*", count="exact") \
                .eq("follower_id", str(profile["id"])).execute()
            followers_count = followers.count if hasattr(followers, "count") and followers.count is not None else len(followers.data or [])
            following_count = following.count if hasattr(following, "count") and following.count is not None else len(following.data or [])
        except Exception:
            followers_count = 0
            following_count = 0

        me = get_current_user(request)
        is_following = False
        is_friend = False
        is_me = False
        if me:
            is_me = str(me["id"]) == str(profile["id"])
            if not is_me:
                try:
                    f1 = supabase.table("follows").select("id") \
                        .eq("follower_id", str(me["id"])).eq("following_id", str(profile["id"])).execute()
                    f2 = supabase.table("follows").select("id") \
                        .eq("follower_id", str(profile["id"])).eq("following_id", str(me["id"])).execute()
                    is_following = bool(f1.data)
                    is_friend = bool(f1.data and f2.data)
                except Exception:
                    pass

        try:
            activity = supabase.table("activity_log").select("*") \
                .eq("user_id", str(profile["id"])).order("created_at", desc=True).limit(10).execute().data or []
        except Exception:
            activity = []

        ctx = build_view_context(request)
        ctx.update({
            "profile": profile, "uploads": uploads,
            "followers_count": followers_count, "following_count": following_count,
            "is_following": is_following, "is_friend": is_friend,
            "activity": activity, "is_me": is_me,
        })
        return render(request, "profile.html", ctx)
    except Exception as e:
        return HttpResponse(f"Error: {e}", status=500)


def leaderboard_view(request):
    leaders = []
    try:
        rows = supabase.table("leaderboard").select("*").limit(100).execute()
        leaders = rows.data or []
        for i, l in enumerate(leaders, start=1):
            l["rank"] = i
        if leaders and ("followers_count" not in leaders[0] or leaders[0].get("followers_count") is None):
            try:
                followers_resp = supabase.table("follows").select("following_id").execute()
                counts = {}
                for f in (followers_resp.data or []):
                    fid = str(f.get("following_id"))
                    counts[fid] = counts.get(fid, 0) + 1
                for l in leaders:
                    l["followers_count"] = counts.get(str(l["id"]), 0)
            except Exception as fe:
                print(f"[leaderboard] followers fallback failed: {fe}")
                for l in leaders:
                    l.setdefault("followers_count", 0)
        for l in leaders:
            l.setdefault("likes_received", 0)
            l.setdefault("uploads_count", 0)
            l.setdefault("current_streak", 0)
            l.setdefault("followers_count", 0)
            l.setdefault("points", 0)
    except Exception as e:
        print(f"[leaderboard] view failed: {e}")
        try:
            rows = supabase.table("users").select(
                "id, username, full_name, avatar_url, university, points, current_streak, "
                "longest_streak, uploads_count, likes_received"
            ).not_.is_("username", "null").order("points", desc=True).limit(100).execute()
            raw = rows.data or []
            try:
                fr = supabase.table("follows").select("following_id").execute()
                counts = {}
                for f in (fr.data or []):
                    fid = str(f.get("following_id"))
                    counts[fid] = counts.get(fid, 0) + 1
            except Exception:
                counts = {}
            for i, u in enumerate(raw):
                u["rank"] = i + 1
                u["followers_count"] = counts.get(str(u["id"]), 0)
                u.setdefault("likes_received", 0)
                u.setdefault("uploads_count", 0)
                u.setdefault("current_streak", 0)
                leaders.append(u)
        except Exception as e2:
            print(f"[leaderboard] fallback failed: {e2}")
            leaders = []
    ctx = build_view_context(request)
    ctx["leaders"] = leaders
    return render(request, "leaderboard.html", ctx)


def community_view(request):
    try:
        rows = supabase.table("users").select(
            "id, username, full_name, avatar_url, university, points, current_streak, uploads_count"
        ).not_.is_("username", "null").order("points", desc=True).limit(200).execute()
        users = rows.data or []
    except Exception as e:
        print(f"[community] {e}")
        users = []
    me = get_current_user(request)
    if me:
        try:
            following_resp = supabase.table("follows").select("following_id") \
                .eq("follower_id", str(me["id"])).execute()
            following_ids = {str(f["following_id"]) for f in (following_resp.data or [])}
            for u in users:
                u["is_following"] = str(u["id"]) in following_ids
        except Exception:
            for u in users:
                u["is_following"] = False
    else:
        for u in users:
            u["is_following"] = False
    ctx = build_view_context(request)
    ctx["users"] = users
    return render(request, "community.html", ctx)

# ============================================================
# MAIN VIEWS
# ============================================================
def index(request):
    return render(request, "index.html", build_view_context(request))


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
                        current_user = get_current_user(request)
                        uploader_id = str(current_user["id"]) if current_user else None

                        insert_payload = {
                            "filename": safe_filename,
                            "original_filename": file.name,
                            "module": module, "course": course, "description": description,
                            "file_type": file_type, "privacy": privacy,
                            "passcode": passcode if privacy == "private" else "",
                            "university": university, "uploader": "user",
                            "uploaded_at": datetime.now().isoformat(),
                            "file_size": file_size,
                        }
                        if uploader_id:
                            insert_payload["uploader_id"] = uploader_id
                            insert_payload["uploader"] = current_user["email"]
                            print(f"[upload] 🔗 Note linked to {current_user['email']} ({uploader_id})")

                        try:
                            supabase.table("notes").insert(insert_payload).execute()
                        except Exception as e:
                            print(f"[upload] ❌ Insert failed: {e}")
                            error = f"Upload failed: {str(e)}"

                        if not error:
                            if uploader_id:
                                award_points(uploader_id, "upload", 15, safe_filename)
                                try:
                                    u = supabase.table("users").select("uploads_count").eq("id", uploader_id).execute()
                                    if u.data:
                                        supabase.table("users").update({
                                            "uploads_count": (u.data[0].get("uploads_count", 0) or 0) + 1
                                        }).eq("id", uploader_id).execute()
                                except Exception:
                                    pass
                                update_streak(uploader_id)

                                # ═══════════════════════════════════════════
                                # 🎁 3-NOTE UPLOAD STREAK BONUS
                                # ═══════════════════════════════════════════
                                try:
                                    count_resp = supabase.table("notes").select("id", count="exact") \
                                        .eq("uploader_id", uploader_id).execute()
                                    total_uploads = (count_resp.count if hasattr(count_resp, "count")
                                                     and count_resp.count is not None
                                                     else len(count_resp.data or []))

                                    if total_uploads > 0 and total_uploads % 3 == 0:
                                        sequence_pts = 50
                                        admin_pts = 200
                                        app_pts = 200
                                        total_bonus = sequence_pts + admin_pts + app_pts

                                        award_points(uploader_id, "upload_streak_3", sequence_pts, safe_filename)
                                        award_points(uploader_id, "admin_bonus", admin_pts, safe_filename)
                                        award_points(uploader_id, "app_bonus", app_pts, safe_filename)

                                        try:
                                            supabase.table("notifications").insert({
                                                "user_id": uploader_id,
                                                "actor_id": uploader_id,
                                                "type": "bonus",
                                                "reference_id": safe_filename,
                                                "message": (
                                                    f"🎉 3-upload streak! "
                                                    f"+{sequence_pts} sequence · "
                                                    f"+{admin_pts} admin reward · "
                                                    f"+{app_pts} app bonus = "
                                                    f"{total_bonus} pts total!"
                                                ),
                                                "is_read": False,
                                            }).execute()
                                        except Exception as ne:
                                            print(f"[upload] bonus notification failed: {ne}")

                                        message = (
                                            f"✅ Uploaded! 🎉 3-note streak hit — "
                                            f"you earned {total_bonus} bonus points! "
                                            f"Check your notifications."
                                        )
                                        request._bonus_token = {
                                            "show": True,
                                            "sequence": sequence_pts,
                                            "admin": admin_pts,
                                            "app": app_pts,
                                            "total": total_bonus,
                                            "emoji": "🏅",
                                        }
                                        print(f"[upload] 🎁 3-streak bonus → {uploader_id} (+{total_bonus} pts)")
                                except Exception as e:
                                    print(f"[upload] streak check failed: {e}")

                            if not message:
                                message = f"✅ {file.name} uploaded successfully!"
                            form = UploadForm()
            except Exception as e:
                error = f"Upload failed: {str(e)}"
                print(f"❌ ERROR: {error}")
        else:
            error = "Please fill all required fields."
    else:
        form = UploadForm()

    ctx = build_view_context(request)
    ctx.update({"form": form, "message": message, "error": error})
    ctx["bonus_token"] = getattr(request, "_bonus_token", None)
    return render(request, "upload.html", ctx)


def browse_view(request):
    me = get_current_user(request)
    current_user_id = str(me["id"]) if me else None
    query = request.GET.get("q", "").strip()
    notes = search_notes(query, current_user_id) if query else get_all_notes(current_user_id)
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
    ctx = build_view_context(request)
    ctx.update({"notes": notes, "query": query})
    return render(request, "browse.html", ctx)


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
        ctx = {"note": note, "pdf_url": file_url, "admin": ADMIN}
        ctx.update(build_view_context(request))
        return render(request, "view.html", ctx)
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
                return HttpResponse("Access Denied. File is private.", status=403)
            if get_passcode != correct_passcode:
                return HttpResponse("Access Denied. Incorrect passcode.", status=403)
        r2_key = f"notes/{note['filename']}"
        file_data = get_r2_file_bytes(r2_key)
        if file_data is None:
            return HttpResponse("File not found in storage", status=404)
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
        delete_from_r2(f"notes/{note['filename']}")
        supabase.table("notes").delete().eq("id", id).execute()
        return redirect(f"/{SECRET_ADMIN_PATH}/")
    except Exception as e:
        return HttpResponse(f"Delete failed: {str(e)}", status=500)


def favicon(request):
    return HttpResponse(status=204)


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
        return JsonResponse({"success": True, "message": "Passcode updated"})
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
        update_data = {f: str(data[f]).strip() for f in allowed_fields if f in data}
        if not update_data:
            return JsonResponse({"success": False, "error": "No valid fields"})
        if "file_type" in update_data and update_data["file_type"] not in ["notes", "pastpaper"]:
            return JsonResponse({"success": False, "error": "Invalid file_type"})
        supabase.table("notes").update(update_data).eq("id", id).execute()
        return JsonResponse({"success": True, "updated": update_data})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def admin_edit(request, id):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    try:
        result = supabase.table("notes").select("*").eq("id", id).execute()
        if not result.data:
            return HttpResponse("File not found", status=404)
        note = result.data[0]
        error_message = None
        if request.method == "POST":
            module = request.POST.get("module", "").strip()
            course = request.POST.get("course", "").strip()
            if not module or not course:
                error_message = "Module and Course are required."
            else:
                supabase.table("notes").update({
                    "module": module,
                    "course": course,
                    "description": request.POST.get("description", "").strip(),
                    "university": request.POST.get("university", "").strip() or "Not specified",
                    "file_type": request.POST.get("file_type", "notes").strip(),
                }).eq("id", id).execute()
                return redirect(f"/{SECRET_ADMIN_PATH}/")
        form = EditForm(initial={
            "module": note.get("module", ""), "course": note.get("course", ""),
            "description": note.get("description", ""), "university": note.get("university", ""),
            "file_type": note.get("file_type", "notes"),
        })
        return render(request, "admin_edit.html", {"note": note, "form": form, "error": error_message})
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


def admin_dashboard(request):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    all_notes = get_all_notes()
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
        "total_files": len(all_notes),
        "file_types": file_types,
        "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:5]),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "private_count": private_count,
        "public_count": public_count,
    }
    return render(request, "admin.html", {
        "notes": all_notes, "stats": stats, "admin": ADMIN,
        "secret_admin_path": SECRET_ADMIN_PATH,
    })


def admin_settings(request):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    return render(request, "admin_settings.html", {"secret_admin_path": SECRET_ADMIN_PATH})

# ============================================================
# ADMIN — USER MANAGEMENT ✨
# ============================================================
def admin_users(request):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    try:
        users = supabase.table("users").select(
            "id, email, username, full_name, avatar_url, university, points, "
            "current_streak, longest_streak, uploads_count, likes_received, "
            "quizzes_taken, quizzes_correct, created_at"
        ).order("points", desc=True).execute().data or []
    except Exception as e:
        print(f"[admin_users] {e}")
        users = []
    for u in users:
        try:
            c = supabase.table("notes").select("id", count="exact").eq("uploader_id", str(u["id"])).execute()
            u["note_count"] = c.count if hasattr(c, "count") and c.count is not None else len(c.data or [])
        except Exception:
            u["note_count"] = 0
    return render(request, "admin_users.html", {
        "users": users, "admin": ADMIN, "secret_admin_path": SECRET_ADMIN_PATH,
    })


@csrf_exempt
def admin_user_delete(request, user_id):
    if not ADMIN:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST only"}, status=405)
    try:
        uid = str(user_id)
        try:
            notes = supabase.table("notes").select("id, filename").eq("uploader_id", uid).execute().data or []
            for n in notes:
                try:
                    delete_from_r2(f"notes/{n['filename']}")
                except Exception:
                    pass
            supabase.table("notes").delete().eq("uploader_id", uid).execute()
        except Exception as e:
            print(f"[admin_user_delete] notes cleanup failed: {e}")
        for table in ["note_likes", "follows", "notifications", "activity_log", "quiz_attempts"]:
            try:
                if table == "follows":
                    supabase.table(table).delete().eq("follower_id", uid).execute()
                    supabase.table(table).delete().eq("following_id", uid).execute()
                else:
                    supabase.table(table).delete().eq("user_id", uid).execute()
            except Exception as e:
                print(f"[admin_user_delete] cleanup {table} failed: {e}")
        supabase.table("users").delete().eq("id", uid).execute()
        print(f"[admin_user_delete] ✅ Deleted user {uid}")
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[admin_user_delete] FATAL: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def admin_notes_by_owner(request):
    if not ADMIN:
        return HttpResponse("Access Denied.", status=403)
    try:
        notes = supabase.table("notes").select(
            "id, filename, original_filename, module, course, university, "
            "uploader_id, uploader, uploaded_at, file_size, privacy"
        ).order("uploaded_at", desc=True).execute().data or []
    except Exception as e:
        print(f"[admin_notes_by_owner] {e}")
        notes = []
    for n in notes:
        n["owner"] = None
        oid = n.get("uploader_id")
        if oid:
            try:
                r = supabase.table("users").select(
                    "id, username, full_name, email, avatar_url"
                ).eq("id", str(oid)).execute()
                if r.data:
                    n["owner"] = r.data[0]
            except Exception:
                pass
        n.setdefault("original_filename", n.get("filename", ""))
        n.setdefault("privacy", "public")
    return render(request, "admin_notes.html", {
        "notes": notes, "admin": ADMIN, "secret_admin_path": SECRET_ADMIN_PATH,
    })

# ============================================================
# STATIC PAGES
# ============================================================
def about_view(request):
    try:
        return render(request, "about.html", build_view_context(request))
    except Exception as e:
        return HttpResponse(f"About page error: {e}", status=500)


def aboutcreator_view(request):
    try:
        return render(request, "aboutcreator.html", build_view_context(request))
    except Exception as e:
        return HttpResponse(f"About Creator page error: {e}", status=500)


def calculator_view(request):
    return render(request, "calculator.html", build_view_context(request))


def hackathon_view(request):
    try:
        return render(request, "hackerthon.html", build_view_context(request))
    except Exception as e:
        return HttpResponse(f"Hackathon page error: {e}", status=500)


def free_courses_view(request):
    try:
        return render(request, "free_course.html", build_view_context(request))
    except Exception as e:
        return HttpResponse(f"Free courses error: {e}", status=500)


def _serve_course_index(course_slug):
    path = os.path.join(BASE_DIR, "free_course", course_slug, "index.html")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Cache-Control"] = "public, max-age=300"
        return response
    except Exception as e:
        return HttpResponse(f"Course '{course_slug}' error: {e}", status=500)


def free_course_detail_view(request, course_slug):
    if not course_slug or not re.match(r"^[a-z0-9\-]+$", course_slug):
        return free_courses_view(request)
    response = _serve_course_index(course_slug)
    return response if response is not None else free_courses_view(request)


def scanner_view(request):
    try:
        return render(request, "scanner.html", build_view_context(request))
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


def quiz_view(request):
    ctx = build_view_context(request)
    ctx["today"] = date.today().strftime("%B %d, %Y")
    return render(request, "quiz.html", ctx)

# ============================================================
# GAMIFICATION APIs
# ============================================================
@csrf_exempt
def api_me(request):
    user = get_current_user(request)
    if not user:
        return JsonResponse({"logged_in": False})
    return JsonResponse({"logged_in": True, "profile": user["profile"]})


@csrf_exempt
def api_like_note(request, note_id):
    """
    LIKE API:
      +1 point to LIKER (like_given)
      +2 points to OWNER (like_received)  ← UPDATED
      +1 likes_received counter for OWNER
      + Notification to owner
    Unlike: -1 likes_received counter (points stay).
    """
    user = get_current_user(request)
    if not user:
        return JsonResponse({"error": "login_required", "login_required": True}, status=401)

    my_id = str(user["id"])
    note_id_str = str(note_id)

    try:
        owner_id = None
        try:
            note_resp = supabase.table("notes").select("uploader_id, uploader, filename") \
                .eq("id", note_id_str).execute()
            if note_resp.data:
                note = note_resp.data[0]
                owner_id = note.get("uploader_id")
                if not owner_id:
                    uploader_email = note.get("uploader")
                    if uploader_email and "@" in uploader_email:
                        try:
                            u_lookup = supabase.table("users").select("id") \
                                .eq("email", uploader_email.lower()).execute()
                            if u_lookup.data:
                                owner_id = u_lookup.data[0]["id"]
                                try:
                                    supabase.table("notes").update({"uploader_id": str(owner_id)}) \
                                        .eq("id", note_id_str).execute()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                if owner_id:
                    owner_id = str(owner_id)
        except Exception as e:
            print(f"[like] note fetch failed: {e}")

        existing = supabase.table("note_likes").select("id") \
            .eq("user_id", my_id).eq("note_id", note_id_str).execute()

        if existing.data:
            # UNLIKE
            supabase.table("note_likes").delete() \
                .eq("user_id", my_id).eq("note_id", note_id_str).execute()
            liked = False
            if owner_id and owner_id != my_id:
                try:
                    o = supabase.table("users").select("likes_received").eq("id", owner_id).execute()
                    if o.data:
                        cur = o.data[0].get("likes_received", 0) or 0
                        supabase.table("users").update({
                            "likes_received": max(0, cur - 1)
                        }).eq("id", owner_id).execute()
                except Exception as e:
                    print(f"[like] decrement failed: {e}")
        else:
            # LIKE
            supabase.table("note_likes").insert({
                "user_id": my_id, "note_id": note_id_str,
            }).execute()
            liked = True

            if owner_id and owner_id != my_id:
                try:
                    o = supabase.table("users").select("likes_received, points").eq("id", owner_id).execute()
                    if o.data:
                        cur_likes = o.data[0].get("likes_received", 0) or 0
                        cur_points = o.data[0].get("points", 0) or 0
                        new_likes = cur_likes + 1
                        new_points = cur_points + 2   # 👈 +2 per like

                        supabase.table("users").update({
                            "likes_received": new_likes,
                            "points": new_points,
                        }).eq("id", owner_id).execute()

                        try:
                            supabase.table("activity_log").insert({
                                "user_id": owner_id, "action": "like_received",
                                "points": 2, "reference_id": note_id_str,
                            }).execute()
                        except Exception:
                            pass

                        # Notification
                        try:
                            liker_name = user.get("profile", {}).get("full_name") or \
                                         user.get("profile", {}).get("username") or \
                                         user.get("email", "Someone")
                            supabase.table("notifications").insert({
                                "user_id": owner_id, "actor_id": my_id,
                                "type": "like", "reference_id": note_id_str,
                                "message": f"{liker_name} liked your note (+2 pts)",
                                "is_read": False,
                            }).execute()
                        except Exception as ne:
                            print(f"[like] notification failed: {ne}")

                        print(f"[like] ⭐ Owner {owner_id} +2 pts ({cur_points}→{new_points}), likes {cur_likes}→{new_likes}")
                except Exception as e:
                    print(f"[like] owner credit failed: {e}")

            award_points(my_id, "like_given", 1, note_id_str)

        try:
            count_resp = supabase.table("note_likes").select("*", count="exact") \
                .eq("note_id", note_id_str).execute()
            count = count_resp.count if hasattr(count_resp, "count") and count_resp.count is not None else len(count_resp.data or [])
        except Exception:
            count = 0

        update_streak(my_id)
        updated = supabase.table("users").select("points").eq("id", my_id).execute()
        points = updated.data[0]["points"] if updated.data else 0

        return JsonResponse({
            "liked": bool(liked),
            "count": int(count),
            "points": int(points) if points is not None else 0,
            "owner_credited": bool(owner_id and owner_id != my_id),
        })
    except Exception as e:
        print(f"[api_like_note] FATAL: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def api_follow_user(request, user_id):
    me = get_current_user(request)
    if not me:
        return JsonResponse({"error": "login_required", "login_required": True}, status=401)
    target_user_id = str(user_id)
    my_id = str(me["id"])
    if my_id == target_user_id:
        return JsonResponse({"error": "cannot_follow_self"}, status=400)
    try:
        existing = supabase.table("follows").select("id") \
            .eq("follower_id", my_id).eq("following_id", target_user_id).execute()
        if existing.data:
            supabase.table("follows").delete() \
                .eq("follower_id", my_id).eq("following_id", target_user_id).execute()
            following = False
            try:
                supabase.table("notifications").delete() \
                    .eq("user_id", target_user_id).eq("actor_id", my_id) \
                    .eq("type", "follow").execute()
            except Exception:
                pass
        else:
            supabase.table("follows").insert({
                "follower_id": my_id, "following_id": target_user_id,
            }).execute()
            following = True
            try:
                award_points(target_user_id, "new_follower", 2, my_id)
            except Exception:
                pass
            try:
                follower_name = me.get("profile", {}).get("full_name") or \
                                me.get("profile", {}).get("username") or \
                                me.get("email", "Someone")
                supabase.table("notifications").insert({
                    "user_id": target_user_id, "actor_id": my_id,
                    "type": "follow", "reference_id": my_id,
                    "message": f"{follower_name} started following you",
                    "is_read": False,
                }).execute()
            except Exception as ne:
                print(f"[follow] notification failed: {ne}")
        try:
            update_streak(my_id)
        except Exception:
            pass
        return JsonResponse({"following": bool(following)})
    except Exception as e:
        print(f"[api_follow_user] FATAL: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================
# UPDATE PROFILE — username / full_name / university ✨
# ============================================================
@csrf_exempt
def api_update_profile(request):
    me = get_current_user(request)
    if not me:
        return JsonResponse({"error": "login_required", "message": "Please log in first."}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed", "message": "Use POST."}, status=405)
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "invalid_json", "message": "Malformed request body."}, status=400)

    my_id = str(me["id"])
    updates = {}

    new_username = (body.get("username") or "").strip().lower()
    if new_username:
        if not re.match(r"^[a-z0-9_]{3,20}$", new_username):
            return JsonResponse({
                "error": "invalid_username",
                "message": "Username must be 3–20 chars: lowercase letters, numbers, underscore only."
            }, status=400)
        try:
            exists = supabase.table("users").select("id").eq("username", new_username).execute()
            if exists.data and str(exists.data[0]["id"]) != my_id:
                return JsonResponse({
                    "error": "username_taken",
                    "message": f"@{new_username} is already taken."
                }, status=400)
        except Exception as e:
            print(f"[api_update_profile] uniqueness check failed: {e}")
        updates["username"] = new_username

    new_full_name = (body.get("full_name") or "").strip()
    if new_full_name:
        if len(new_full_name) > 80:
            return JsonResponse({
                "error": "invalid_full_name",
                "message": "Display name must be 80 characters or fewer."
            }, status=400)
        updates["full_name"] = new_full_name

    new_university = (body.get("university") or "").strip()
    if new_university:
        if len(new_university) > 200:
            return JsonResponse({
                "error": "invalid_university",
                "message": "University must be 200 characters or fewer."
            }, status=400)
        updates["university"] = new_university

    if not updates:
        return JsonResponse({
            "error": "nothing_to_update",
            "message": "No changes were provided."
        }, status=400)

    try:
        supabase.table("users").update(updates).eq("id", my_id).execute()
        print(f"[api_update_profile] ✅ Updated {my_id}: {updates}")
        return JsonResponse({"success": True, "updated": updates})
    except Exception as e:
        print(f"[api_update_profile] update failed: {e}")
        return JsonResponse({
            "error": "update_failed",
            "message": f"Database error: {str(e)}"
        }, status=500)


# ============================================================
# DAILY QUIZ API
# ============================================================
@csrf_exempt
def api_daily_quiz(request):
    user = get_current_user(request)
    today = date.today()
    today_q = quiz_engine.get_daily_question(today=today, shuffle_options=True)

    if request.method == "GET":
        already = None
        if user:
            try:
                r = supabase.table("quiz_attempts").select("*") \
                    .eq("user_id", str(user["id"])).eq("quiz_date", today.isoformat()).execute()
                already = r.data[0] if r.data else None
            except Exception:
                already = None
        payload = {
            "question": today_q["q"], "options": today_q["options"],
            "subject": today_q["subject"], "already_answered": bool(already),
            "login_required": user is None,
        }
        if already:
            payload["your_answer"] = already.get("user_answer")
            payload["correct_answer"] = already.get("correct_answer")
            payload["is_correct"] = already.get("is_correct")
            payload["points_earned"] = already.get("points_earned", 0)
        return JsonResponse(payload)

    if not user:
        return JsonResponse({"error": "login_required", "login_required": True}, status=401)

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}
    answer = (body.get("answer") or "").strip()

    try:
        my_id = str(user["id"])
        existing = supabase.table("quiz_attempts").select("id") \
            .eq("user_id", my_id).eq("quiz_date", today.isoformat()).execute()
        if existing.data:
            return JsonResponse({"error": "already_answered_today"}, status=400)

        is_correct = quiz_engine.is_correct_answer(today_q, answer)
        points = 10 if is_correct else 0

        supabase.table("quiz_attempts").insert({
            "user_id": my_id, "quiz_date": today.isoformat(),
            "question": today_q["q"], "user_answer": answer,
            "correct_answer": today_q["a"], "is_correct": is_correct,
            "points_earned": points,
        }).execute()

        ur = supabase.table("users").select("quizzes_taken, quizzes_correct").eq("id", my_id).execute()
        if ur.data:
            taken = (ur.data[0].get("quizzes_taken", 0) or 0) + 1
            correct = (ur.data[0].get("quizzes_correct", 0) or 0) + (1 if is_correct else 0)
            supabase.table("users").update({
                "quizzes_taken": taken, "quizzes_correct": correct,
            }).eq("id", my_id).execute()

        if points:
            award_points(my_id, "quiz_correct", points, today.isoformat())
        update_streak(my_id)

        return JsonResponse({
            "correct": is_correct, "correct_answer": today_q["a"],
            "your_answer": answer, "points_earned": points,
            "subject": today_q["subject"],
        })
    except Exception as e:
        print(f"[api_daily_quiz] {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================
# NOTIFICATIONS + FOLLOW LISTS API
# ============================================================
@csrf_exempt
def api_notifications(request):
    me = get_current_user(request)
    if not me:
        return JsonResponse({"error": "login_required"}, status=401)
    my_id = str(me["id"])
    try:
        r = supabase.table("notifications").select("*").eq("user_id", my_id) \
            .order("created_at", desc=True).limit(30).execute()
        rows = r.data or []
    except Exception as e:
        print(f"[api_notifications] {e}")
        return JsonResponse({"notifications": [], "unread_count": 0})

    notifications = []
    for n in rows:
        actor_id = n.get("actor_id")
        actor = None
        try:
            if actor_id:
                a = supabase.table("users").select("id, username, full_name, avatar_url") \
                    .eq("id", str(actor_id)).execute()
                actor = a.data[0] if a.data else None
        except Exception:
            pass
        notifications.append({
            "id": n.get("id"), "type": n.get("type"),
            "message": n.get("message"), "is_read": bool(n.get("is_read")),
            "created_at": n.get("created_at"),
            "actor": {
                "id": str(actor.get("id")) if actor else "",
                "username": actor.get("username", "") if actor else "",
                "full_name": actor.get("full_name", "") if actor else "",
                "avatar_url": actor.get("avatar_url", "") if actor else "",
            } if actor else None,
            "reference_id": str(n.get("reference_id")) if n.get("reference_id") else "",
        })
    unread = sum(1 for n in notifications if not n["is_read"])
    return JsonResponse({"notifications": notifications, "unread_count": unread})


@csrf_exempt
def api_mark_notifications_read(request):
    me = get_current_user(request)
    if not me:
        return JsonResponse({"error": "login_required"}, status=401)
    my_id = str(me["id"])
    try:
        supabase.table("notifications").update({"is_read": True}).eq("user_id", my_id).execute()
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[api_mark_notifications_read] {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def api_list_followers(request, username):
    return _api_follow_list(request, username, mode="followers")


@csrf_exempt
def api_list_following(request, username):
    return _api_follow_list(request, username, mode="following")


def _api_follow_list(request, username, mode="followers"):
    try:
        row = supabase.table("users").select("id, username, full_name, avatar_url") \
            .eq("username", username).execute()
        if not row.data:
            return JsonResponse({"users": []})
        target_id = str(row.data[0]["id"])
    except Exception as e:
        print(f"[follow_list] user lookup failed: {e}")
        return JsonResponse({"users": []})

    try:
        if mode == "followers":
            r = supabase.table("follows").select("follower_id").eq("following_id", target_id).execute()
            user_ids = [str(x["follower_id"]) for x in (r.data or [])]
        else:
            r = supabase.table("follows").select("following_id").eq("follower_id", target_id).execute()
            user_ids = [str(x["following_id"]) for x in (r.data or [])]
    except Exception as e:
        print(f"[follow_list] follows fetch failed: {e}")
        return JsonResponse({"users": []})

    if not user_ids:
        return JsonResponse({"users": []})

    try:
        rows = supabase.table("users").select(
            "id, username, full_name, avatar_url, university, points, current_streak"
        ).in_("id", user_ids).execute()
        users = rows.data or []
    except Exception as e:
        print(f"[follow_list] profiles fetch failed: {e}")
        return JsonResponse({"users": []})

    me = get_current_user(request)
    my_following_ids = set()
    if me:
        try:
            fr = supabase.table("follows").select("following_id").eq("follower_id", str(me["id"])).execute()
            my_following_ids = {str(x["following_id"]) for x in (fr.data or [])}
        except Exception:
            pass
    my_id = str(me["id"]) if me else ""

    users_out = []
    for u in users:
        uid = str(u["id"])
        users_out.append({
            "id": uid,
            "username": u.get("username", ""),
            "full_name": u.get("full_name", ""),
            "avatar_url": u.get("avatar_url", ""),
            "university": u.get("university", ""),
            "points": u.get("points", 0) or 0,
            "current_streak": u.get("current_streak", 0) or 0,
            "is_following": uid in my_following_ids,
            "is_me": uid == my_id,
        })
    return JsonResponse({"users": users_out})


# ============================================================
# URLS
# ============================================================
urlpatterns = [
    path("", index),

    # AUTH
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),
    path("auth/callback/", oauth_callback, name="oauth_callback"),

    # PASSWORD RESET
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("reset-password/", reset_password_view, name="reset_password"),

    # USER
    path("dashboard/", dashboard_view, name="dashboard"),
    path("leaderboard/", leaderboard_view, name="leaderboard"),
    path("community/", community_view, name="community"),
    path("profile/<str:username>/", profile_view, name="profile"),

    # QUIZ
    path("quiz/", quiz_view, name="quiz"),
    path("daily-quiz/", quiz_view, name="daily_quiz_alt"),

    # APIs
    path("api/me/", api_me, name="api_me"),
    path("api/quiz/daily/", api_daily_quiz, name="api_daily_quiz"),
    path("api/like/<int:note_id>/", api_like_note, name="api_like_note"),
    path("api/follow/<str:user_id>/", api_follow_user, name="api_follow_user"),
    path("api/profile/update/", api_update_profile, name="api_update_profile"),

    # NOTIFICATIONS + FOLLOW LISTS
    path("api/notifications/", api_notifications, name="api_notifications"),
    path("api/notifications/read/", api_mark_notifications_read, name="api_mark_notifications_read"),
    path("api/followers/<str:username>/", api_list_followers, name="api_list_followers"),
    path("api/following/<str:username>/", api_list_following, name="api_list_following"),

    # ADMIN
    path(f"{SECRET_ADMIN_PATH}/", admin_dashboard, name="admin_dashboard"),
    path(f"{SECRET_ADMIN_PATH}/settings/", admin_settings, name="admin_settings"),
    path(f"{SECRET_ADMIN_PATH}/users/", admin_users, name="admin_users"),
    path(f"{SECRET_ADMIN_PATH}/users/delete/<str:user_id>/", admin_user_delete, name="admin_user_delete"),
    path(f"{SECRET_ADMIN_PATH}/notes/", admin_notes_by_owner, name="admin_notes_by_owner"),
    path("admin_edit/<int:id>/", admin_edit, name="admin_edit"),

    # ICONS
    path("apple-touch-icon.png", serve_root_file, {"filename": "apple-touch-icon.png"}, name="apple_icon"),
    path("apple-touch-icon-precomposed.png", serve_root_file, {"filename": "apple-touch-icon.png"}),
    path("favicon.ico", favicon_view, name="favicon"),
    path("favicon.png", favicon_view, name="favicon_png"),

    # MAIN
    path("upload/", upload_view),
    path("browse/", browse_view),
    path("view/<int:id>/", view_file),
    path("download/<int:id>/", download_file),
    path("delete/<int:id>/", delete_file),
    path("update-passcode/<int:id>/", update_passcode, name="update_passcode"),
    path("update-metadata/<int:id>/", update_metadata, name="update_metadata"),

    # ABOUT
    path("about.html", about_view, name="about"),
    path("about/", about_view, name="about_alt"),

    # CALCULATOR
    path("calculator.html", calculator_view),
    path("calculator/", calculator_view, name="calculator"),

    # HACKERTHON
    path("hackerthon.html", hackathon_view),
    path("hackerthon/", hackathon_view, name="hackerthon"),
    path("hackathon.html", hackathon_view),
    path("hackathon/", hackathon_view, name="hackathon"),

    # FREE COURSES
    path("free_course.html", free_courses_view),
    path("free_course/", free_courses_view, name="free_course"),
    path("free_courses.html", free_courses_view),
    path("free-courses/", free_courses_view, name="free_courses"),
    path("free_course/<slug:course_slug>/", free_course_detail_view, name="free_course_detail"),
    path("free_course/<slug:course_slug>/index.html", free_course_detail_view, name="free_course_detail_index"),
    path("free_course/<path:subpath>", serve_subfolder_file, name="free_course_assets"),

    # AUTOQUIZ
    path("autoquiz.html", autoquiz_view, name="autoquiz"),
    path("autoquiz/", autoquiz_view, name="autoquiz_alt"),

    # SCANNER
    path("scanner.html", scanner_view, name="scanner"),
    path("scanner/", scanner_view, name="scanner_alt"),

    # ABOUT CREATOR (MUST be above the catch-all root file server)
    path("aboutcreator.html", aboutcreator_view, name="aboutcreator"),
    path("aboutcreator/", aboutcreator_view, name="aboutcreator_alt"),

    # ROOT FILE SERVER (must be LAST)
    path("<str:filename>", serve_root_file, name="root_file"),
]

application = get_wsgi_application()
app = application
