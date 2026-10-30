# chat.py — General Chat module (24h auto-delete)
# Njia C: lazy import ya app ili kuepuka circular import

import json
import uuid
import html as html_lib
from datetime import datetime, date, timedelta, timezone

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

# ============================================================
# CONSTANTS
# ============================================================
GUEST_DAILY_LIMIT = 3
CHAT_MAX_LENGTH = 1000
CHAT_POLL_LIMIT = 100
ALLOWED_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥", "🎉", "👏"]


def _deps():
    """Lazy import ya app — inaepuka circular import."""
    import app
    return app


# ============================================================
# HELPERS
# ============================================================
def _get_guest_id(request, create=True):
    gid = request.COOKIES.get("chat-guest-id")
    if gid:
        return gid
    if create:
        return str(uuid.uuid4())
    return None


def _now_utc():
    return datetime.now(timezone.utc)


def _cleanup_expired_messages():
    """Futa ujumbe uliopita saa 24."""
    try:
        app = _deps()
        app.supabase.table("chat_messages").delete() \
            .lt("expires_at", _now_utc().isoformat()).execute()
    except Exception as e:
        print(f"[chat cleanup] {e}")


def _get_pinned_message():
    try:
        app = _deps()
        r = app.supabase.table("chat_settings").select("*").eq("id", 1).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def _serialize_message(msg, reactions_map=None):
    reactions = {}
    if reactions_map and str(msg["id"]) in reactions_map:
        reactions = reactions_map[str(msg["id"])]

    reply_preview = None
    if msg.get("reply_to_id"):
        try:
            app = _deps()
            rp = app.supabase.table("chat_messages").select(
                "id, username_snapshot, message, is_deleted, deleted_by_admin"
            ).eq("id", msg["reply_to_id"]).execute()
            if rp.data:
                rm = rp.data[0]
                reply_preview = {
                    "id": str(rm["id"]),
                    "username": rm.get("username_snapshot", ""),
                    "message": "🚫 Deleted by admin" if rm.get("deleted_by_admin")
                               else (rm.get("message", "")[:80]),
                }
        except Exception:
            pass

    is_deleted = msg.get("is_deleted") or msg.get("deleted_by_admin")

    return {
        "id": str(msg["id"]),
        "username": msg.get("username_snapshot", "Unknown"),
        "avatar": msg.get("avatar_snapshot", ""),
        "message": "🚫 Deleted by admin" if msg.get("deleted_by_admin")
                   else (msg.get("message", "") if not is_deleted else "[deleted]"),
        "is_deleted": bool(is_deleted),
        "deleted_by_admin": bool(msg.get("deleted_by_admin")),
        "reply_to": reply_preview,
        "reactions": reactions,
        "created_at": msg.get("created_at"),
        "user_id": str(msg["user_id"]) if msg.get("user_id") else None,
    }


def _build_reactions_map(message_ids, my_user_id=None, my_guest_id=None):
    if not message_ids:
        return {}
    try:
        app = _deps()
        r = app.supabase.table("chat_reactions").select("*") \
            .in_("message_id", message_ids).execute()
        rows = r.data or []
    except Exception as e:
        print(f"[chat reactions] {e}")
        return {}

    result = {}
    for row in rows:
        mid = str(row["message_id"])
        emoji = row.get("emoji", "")
        if mid not in result:
            result[mid] = {}
        if emoji not in result[mid]:
            result[mid][emoji] = {"count": 0, "mine": False}
        result[mid][emoji]["count"] += 1

        if my_user_id and str(row.get("user_id")) == str(my_user_id):
            result[mid][emoji]["mine"] = True
        elif my_guest_id and row.get("guest_id") == my_guest_id:
            result[mid][emoji]["mine"] = True
    return result


# ============================================================
# VIEWS
# ============================================================
@ensure_csrf_cookie
def chat_view(request):
    app = _deps()
    ctx = app.build_view_context(request)
    ctx["guest_id"] = _get_guest_id(request, create=True)
    ctx["guest_limit"] = GUEST_DAILY_LIMIT
    ctx["allowed_emojis"] = ALLOWED_EMOJIS
    ctx["is_admin"] = bool(app.ADMIN)
    return render(request, "chat.html", ctx)


# ============================================================
# API — GET MESSAGES (polling)
# ============================================================
@csrf_exempt
def api_chat_messages(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    app = _deps()
    _cleanup_expired_messages()

    after_id = request.GET.get("after", "").strip()
    me = app.get_current_user(request)
    my_uid = str(me["id"]) if me else None
    my_gid = _get_guest_id(request, create=False)

    try:
        q = app.supabase.table("chat_messages").select("*") \
            .gte("expires_at", _now_utc().isoformat()) \
            .order("created_at", desc=False).limit(CHAT_POLL_LIMIT)
        if after_id:
            try:
                r = app.supabase.table("chat_messages").select("created_at") \
                    .eq("id", after_id).execute()
                if r.data:
                    q = q.gt("created_at", r.data[0]["created_at"])
            except Exception:
                pass
        rows = q.execute().data or []
    except Exception as e:
        print(f"[chat messages] {e}")
        return JsonResponse({"error": str(e)}, status=500)

    msg_ids = [str(r["id"]) for r in rows]
    reactions_map = _build_reactions_map(msg_ids, my_uid, my_gid)
    messages = [_serialize_message(r, reactions_map) for r in rows]

    pinned = _get_pinned_message()
    pinned_payload = None
    if pinned and pinned.get("pinned_message"):
        pinned_payload = {
            "message": pinned["pinned_message"],
            "pinned_at": pinned.get("pinned_at"),
        }

    return JsonResponse({
        "messages": messages,
        "pinned": pinned_payload,
        "is_admin": bool(app.ADMIN),
    })


# ============================================================
# API — SEND MESSAGE
# ============================================================
@csrf_exempt
def api_chat_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    app = _deps()
    _cleanup_expired_messages()

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    raw = (body.get("message") or "").strip()
    reply_to_id = body.get("reply_to_id") or None

    if not raw:
        return JsonResponse(
            {"error": "empty_message", "message": "Ujumbe hauwezi kuwa tupu."},
            status=400)
    if len(raw) > CHAT_MAX_LENGTH:
        return JsonResponse(
            {"error": "too_long", "message": f"Ujumbe usizidi {CHAT_MAX_LENGTH} herufi."},
            status=400)

    safe_msg = html_lib.escape(raw)

    me = app.get_current_user(request)
    now = _now_utc()
    guest_id = None
    set_cookies = {}

    if me:
        profile = me.get("profile") or {}
        username = (profile.get("username") or profile.get("full_name")
                    or me["email"].split("@")[0])
        avatar = profile.get("avatar_url", "")
        user_id = str(me["id"])
    else:
        guest_id = _get_guest_id(request, create=False)
        if not guest_id:
            guest_id = str(uuid.uuid4())
            set_cookies["chat-guest-id"] = guest_id

        today = date.today().isoformat()
        try:
            r = app.supabase.table("guest_chat_limits").select("*") \
                .eq("guest_id", guest_id).eq("day", today).execute()
            if r.data:
                count = r.data[0].get("message_count", 0) or 0
                if count >= GUEST_DAILY_LIMIT:
                    return JsonResponse({
                        "error": "guest_limit_reached",
                        "message": (f"Umetumia ujumbe {GUEST_DAILY_LIMIT} leo. "
                                    "Tafadhali ingia (login) kuchat bila kikomo."),
                        "login_required": True,
                    }, status=429)
                app.supabase.table("guest_chat_limits").update({
                    "message_count": count + 1,
                }).eq("id", r.data[0]["id"]).execute()
            else:
                app.supabase.table("guest_chat_limits").insert({
                    "guest_id": guest_id, "day": today, "message_count": 1,
                }).execute()
        except Exception as e:
            print(f"[chat guest limit] {e}")

        username = "Guest"
        avatar = ""
        user_id = None

    payload = {
        "user_id": user_id,
        "guest_id": guest_id,
        "username_snapshot": username,
        "avatar_snapshot": avatar,
        "message": safe_msg,
        "reply_to_id": reply_to_id,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
    }

    try:
        ins = app.supabase.table("chat_messages").insert(payload).execute()
        new_id = ins.data[0]["id"] if ins.data else None
    except Exception as e:
        print(f"[chat send] {e}")
        return JsonResponse({"error": "insert_failed", "message": str(e)}, status=500)

    resp = JsonResponse({"success": True, "id": str(new_id) if new_id else None})
    for k, v in set_cookies.items():
        resp.set_cookie(k, v, max_age=60*60*24*365, samesite="Lax")
    return resp


# ============================================================
# API — REACT
# ============================================================
@csrf_exempt
def api_chat_react(request, message_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    app = _deps()

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    emoji = (body.get("emoji") or "").strip()
    if emoji not in ALLOWED_EMOJIS:
        return JsonResponse({"error": "invalid_emoji"}, status=400)

    me = app.get_current_user(request)
    user_id = str(me["id"]) if me else None
    guest_id = None if me else _get_guest_id(request, create=False)

    if not user_id and not guest_id:
        return JsonResponse({"error": "identify_required"}, status=400)

    try:
        q = app.supabase.table("chat_reactions").select("id") \
            .eq("message_id", message_id).eq("emoji", emoji)
        if user_id:
            q = q.eq("user_id", user_id)
        else:
            q = q.eq("guest_id", guest_id)
        existing = q.execute()

        if existing.data:
            app.supabase.table("chat_reactions").delete() \
                .eq("id", existing.data[0]["id"]).execute()
            action = "removed"
        else:
            app.supabase.table("chat_reactions").insert({
                "message_id": message_id,
                "user_id": user_id,
                "guest_id": guest_id,
                "emoji": emoji,
            }).execute()
            action = "added"

        return JsonResponse({"success": True, "action": action})
    except Exception as e:
        print(f"[chat react] {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================
# API — ADMIN DELETE
# ============================================================
@csrf_exempt
def api_chat_admin_delete(request, message_id):
    app = _deps()
    if not app.ADMIN:
        return JsonResponse({"error": "not_authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        app.supabase.table("chat_messages").update({
            "is_deleted": True,
            "deleted_by_admin": True,
            "message": "🚫 Deleted by admin",
        }).eq("id", message_id).execute()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================
# API — ADMIN PIN
# ============================================================
@csrf_exempt
def api_chat_admin_pin(request):
    app = _deps()
    if not app.ADMIN:
        return JsonResponse({"error": "not_authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    new_pin = (body.get("pinned_message") or "").strip()
    me = app.get_current_user(request)
    pinned_by = str(me["id"]) if me else None

    try:
        if new_pin:
            app.supabase.table("chat_settings").update({
                "pinned_message": new_pin[:500],
                "pinned_by": pinned_by,
                "pinned_at": _now_utc().isoformat(),
            }).eq("id", 1).execute()
        else:
            app.supabase.table("chat_settings").update({
                "pinned_message": None,
                "pinned_by": None,
                "pinned_at": None,
            }).eq("id", 1).execute()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================
# API — GUEST STATUS
# ============================================================
@csrf_exempt
def api_chat_guest_status(request):
    app = _deps()
    me = app.get_current_user(request)
    if me:
        return JsonResponse({"logged_in": True, "remaining": None})

    guest_id = _get_guest_id(request, create=False)
    if not guest_id:
        return JsonResponse({"logged_in": False, "remaining": GUEST_DAILY_LIMIT})

    today = date.today().isoformat()
    try:
        r = app.supabase.table("guest_chat_limits").select("*") \
            .eq("guest_id", guest_id).eq("day", today).execute()
        used = r.data[0].get("message_count", 0) if r.data else 0
        return JsonResponse({
            "logged_in": False,
            "remaining": max(0, GUEST_DAILY_LIMIT - used),
        })
    except Exception:
        return JsonResponse({"logged_in": False, "remaining": GUEST_DAILY_LIMIT})
