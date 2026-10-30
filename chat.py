# chat.py — General Chat module for Student Hub (24h auto-delete)
# Lives next to app.py. Imports `app` lazily to avoid a circular import.
#
# Needs these from app.py:
#   app.supabase, app.get_current_user, app.build_view_context, app.is_chat_admin
#
# Tables (see chat_schema.sql): chat_messages, chat_reactions, chat_settings, guest_chat_limits

import json
import time
import uuid
from datetime import datetime, date, timedelta, timezone

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

# ============================================================
# CONSTANTS
# ============================================================
GUEST_DAILY_LIMIT = 3
CHAT_MAX_LENGTH = 1000
CHAT_POLL_LIMIT = 100
CHAT_TTL_HOURS = 24
FLOOD_SECONDS = 1.0           # min gap between messages from the same sender
CLEANUP_EVERY_SECONDS = 60    # throttle expired-message cleanup
GUEST_COOKIE = "chat-guest-id"
ALLOWED_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥", "🎉", "👏"]

_last_cleanup = 0.0


def _deps():
    """Lazy import of app (avoids circular import)."""
    import app
    return app


# ============================================================
# HELPERS
# ============================================================
def _now_utc():
    return datetime.now(timezone.utc)


def _json_body(request):
    try:
        data = json.loads(request.body or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return None


def _get_guest_id(request):
    gid = request.COOKIES.get(GUEST_COOKIE, "").strip()
    # only accept well-formed UUIDs so the cookie can't be abused
    try:
        return str(uuid.UUID(gid)) if gid else None
    except Exception:
        return None


def _set_guest_cookie(response, guest_id):
    response.set_cookie(GUEST_COOKIE, guest_id, max_age=60 * 60 * 24 * 365,
                        samesite="Lax", httponly=True)


def _cleanup_expired_messages():
    """Delete messages older than 24h. Throttled to once per minute per process."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < CLEANUP_EVERY_SECONDS:
        return
    _last_cleanup = now
    try:
        app = _deps()
        expired = app.supabase.table("chat_messages").select("id") \
            .lt("expires_at", _now_utc().isoformat()).execute().data or []
        ids = [r["id"] for r in expired]
        if ids:
            # remove reactions first (in case there is no ON DELETE CASCADE)
            app.supabase.table("chat_reactions").delete().in_("message_id", ids).execute()
            app.supabase.table("chat_messages").delete().in_("id", ids).execute()
    except Exception as e:
        print(f"[chat cleanup] {e}")


def _get_pinned():
    try:
        app = _deps()
        r = app.supabase.table("chat_settings").select("*").eq("id", 1).execute()
        row = r.data[0] if r.data else None
        if row and row.get("pinned_message"):
            return {"message": row["pinned_message"], "pinned_at": row.get("pinned_at")}
    except Exception as e:
        print(f"[chat pinned] {e}")
    return None


def _build_reactions_map(message_ids, my_user_id=None, my_guest_id=None):
    """{message_id: {emoji: {count, mine}}}"""
    if not message_ids:
        return {}
    try:
        app = _deps()
        rows = app.supabase.table("chat_reactions").select("*") \
            .in_("message_id", message_ids).execute().data or []
    except Exception as e:
        print(f"[chat reactions] {e}")
        return {}

    result = {}
    for row in rows:
        mid = str(row["message_id"])
        emoji = row.get("emoji", "")
        slot = result.setdefault(mid, {}).setdefault(emoji, {"count": 0, "mine": False})
        slot["count"] += 1
        if my_user_id and row.get("user_id") and str(row["user_id"]) == my_user_id:
            slot["mine"] = True
        elif my_guest_id and row.get("guest_id") and row["guest_id"] == my_guest_id:
            slot["mine"] = True
    return result


def _build_reply_map(rows):
    """Batch-fetch the messages being replied to: {id: preview}"""
    reply_ids = list({str(r["reply_to_id"]) for r in rows if r.get("reply_to_id")})
    if not reply_ids:
        return {}
    try:
        app = _deps()
        data = app.supabase.table("chat_messages").select(
            "id, username_snapshot, message, is_deleted, deleted_by_admin"
        ).in_("id", reply_ids).execute().data or []
    except Exception as e:
        print(f"[chat replies] {e}")
        return {}
    out = {}
    for rm in data:
        gone = rm.get("is_deleted") or rm.get("deleted_by_admin")
        out[str(rm["id"])] = {
            "id": str(rm["id"]),
            "username": rm.get("username_snapshot", ""),
            "message": "🚫 Deleted" if gone else (rm.get("message", "") or "")[:80],
        }
    return out


def _serialize(msg, reactions_map, reply_map):
    deleted_by_admin = bool(msg.get("deleted_by_admin"))
    is_deleted = bool(msg.get("is_deleted")) or deleted_by_admin
    if deleted_by_admin:
        text = "🚫 Deleted by admin"
    elif is_deleted:
        text = "[deleted]"
    else:
        text = msg.get("message", "")
    rid = str(msg["reply_to_id"]) if msg.get("reply_to_id") else None
    return {
        "id": str(msg["id"]),
        "username": msg.get("username_snapshot") or "Unknown",
        "avatar": msg.get("avatar_snapshot") or "",
        "message": text,
        "is_deleted": is_deleted,
        "deleted_by_admin": deleted_by_admin,
        "reply_to": reply_map.get(rid) if rid else None,
        "reactions": reactions_map.get(str(msg["id"]), {}),
        "created_at": msg.get("created_at"),
        "user_id": str(msg["user_id"]) if msg.get("user_id") else None,
    }


# ============================================================
# VIEW — chat page
# ============================================================
@ensure_csrf_cookie
def chat_view(request):
    app = _deps()
    ctx = app.build_view_context(request)
    ctx["guest_limit"] = GUEST_DAILY_LIMIT
    ctx["allowed_emojis"] = ALLOWED_EMOJIS
    ctx["is_admin"] = bool(app.is_chat_admin(request))
    response = render(request, "chat.html", ctx)
    if not app.get_current_user(request) and not _get_guest_id(request):
        _set_guest_cookie(response, str(uuid.uuid4()))
    return response


# ============================================================
# API — messages (polling)
# ============================================================
def api_chat_messages(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    app = _deps()
    _cleanup_expired_messages()

    me = app.get_current_user(request)
    my_uid = str(me["id"]) if me else None
    my_gid = None if me else _get_guest_id(request)
    after_id = request.GET.get("after", "").strip()
    now_iso = _now_utc().isoformat()

    try:
        after_ts = None
        if after_id:
            try:
                r = app.supabase.table("chat_messages").select("created_at") \
                    .eq("id", after_id).execute()
                if r.data:
                    after_ts = r.data[0]["created_at"]
            except Exception:
                after_ts = None

        q = app.supabase.table("chat_messages").select("*").gte("expires_at", now_iso)
        if after_ts:
            # new messages since the cursor, oldest first
            rows = q.gt("created_at", after_ts).order("created_at", desc=False) \
                .limit(CHAT_POLL_LIMIT).execute().data or []
        else:
            # first load: the LATEST N messages, returned oldest-first
            rows = q.order("created_at", desc=True).limit(CHAT_POLL_LIMIT).execute().data or []
            rows.reverse()
    except Exception as e:
        print(f"[chat messages] {e}")
        return JsonResponse({"error": "fetch_failed", "message": str(e)}, status=500)

    reactions_map = _build_reactions_map([str(r["id"]) for r in rows], my_uid, my_gid)
    reply_map = _build_reply_map(rows)
    messages = [_serialize(r, reactions_map, reply_map) for r in rows]

    return JsonResponse({
        "messages": messages,
        "pinned": _get_pinned(),
        "is_admin": bool(app.is_chat_admin(request)),
    })


# ============================================================
# API — send
# ============================================================
def api_chat_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    app = _deps()
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    # Stored RAW: chat.html escapes on render, so escaping here would double-escape.
    text = str(body.get("message") or "").strip()
    reply_to_id = body.get("reply_to_id") or None

    if not text:
        return JsonResponse({"error": "empty_message", "message": "Ujumbe hauwezi kuwa tupu."}, status=400)
    if len(text) > CHAT_MAX_LENGTH:
        return JsonResponse({"error": "too_long",
                             "message": f"Ujumbe usizidi {CHAT_MAX_LENGTH} herufi."}, status=400)

    if reply_to_id:
        try:
            reply_to_id = str(uuid.UUID(str(reply_to_id)))
        except Exception:
            reply_to_id = None

    me = app.get_current_user(request)
    new_guest_cookie = None
    now = _now_utc()

    if me:
        profile = me.get("profile") or {}
        username = profile.get("username") or profile.get("full_name") or me["email"].split("@")[0]
        avatar = profile.get("avatar_url") or ""
        user_id = str(me["id"])
        guest_id = None
        sender_filter = ("user_id", user_id)
    else:
        guest_id = _get_guest_id(request)
        if not guest_id:
            guest_id = str(uuid.uuid4())
            new_guest_cookie = guest_id
        user_id = None
        avatar = ""
        username = f"Guest-{guest_id[:4]}"
        sender_filter = ("guest_id", guest_id)

    # --- flood control ---
    try:
        last = app.supabase.table("chat_messages").select("created_at") \
            .eq(*sender_filter).order("created_at", desc=True).limit(1).execute().data
        if last:
            last_ts = datetime.fromisoformat(last[0]["created_at"].replace("Z", "+00:00"))
            if (now - last_ts).total_seconds() < FLOOD_SECONDS:
                return JsonResponse({"error": "too_fast",
                                     "message": "Polepole kidogo, subiri sekunde moja."}, status=429)
    except Exception as e:
        print(f"[chat flood] {e}")

    # --- guest daily limit ---
    if not me:
        today = date.today().isoformat()
        try:
            r = app.supabase.table("guest_chat_limits").select("*") \
                .eq("guest_id", guest_id).eq("day", today).execute()
            if r.data:
                count = r.data[0].get("message_count", 0) or 0
                if count >= GUEST_DAILY_LIMIT:
                    resp = JsonResponse({
                        "error": "guest_limit_reached",
                        "message": f"Umetumia ujumbe {GUEST_DAILY_LIMIT} leo. Tafadhali ingia kuchat bila kikomo.",
                        "login_required": True,
                    }, status=429)
                    if new_guest_cookie:
                        _set_guest_cookie(resp, new_guest_cookie)
                    return resp
                app.supabase.table("guest_chat_limits").update({"message_count": count + 1}) \
                    .eq("id", r.data[0]["id"]).execute()
            else:
                app.supabase.table("guest_chat_limits").insert({
                    "guest_id": guest_id, "day": today, "message_count": 1,
                }).execute()
        except Exception as e:
            print(f"[chat guest limit] {e}")
            return JsonResponse({"error": "limit_check_failed",
                                 "message": "Imeshindikana kuthibitisha kikomo, jaribu tena."}, status=500)

    payload = {
        "user_id": user_id,
        "guest_id": guest_id,
        "username_snapshot": username,
        "avatar_snapshot": avatar,
        "message": text,
        "reply_to_id": reply_to_id,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=CHAT_TTL_HOURS)).isoformat(),
    }

    try:
        ins = app.supabase.table("chat_messages").insert(payload).execute()
        new_id = ins.data[0]["id"] if ins.data else None
    except Exception as e:
        print(f"[chat send] {e}")
        return JsonResponse({"error": "insert_failed", "message": "Imeshindikana kutuma ujumbe."}, status=500)

    resp = JsonResponse({"success": True, "id": str(new_id) if new_id else None})
    if new_guest_cookie:
        _set_guest_cookie(resp, new_guest_cookie)
    return resp


# ============================================================
# API — react (toggle)
# ============================================================
def api_chat_react(request, message_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    app = _deps()
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    emoji = str(body.get("emoji") or "").strip()
    if emoji not in ALLOWED_EMOJIS:
        return JsonResponse({"error": "invalid_emoji"}, status=400)

    try:
        message_id = str(uuid.UUID(str(message_id)))
    except Exception:
        return JsonResponse({"error": "invalid_message_id"}, status=400)

    me = app.get_current_user(request)
    user_id = str(me["id"]) if me else None
    guest_id = None if me else _get_guest_id(request)
    if not user_id and not guest_id:
        return JsonResponse({"error": "identify_required"}, status=400)

    try:
        exists = app.supabase.table("chat_messages").select("id, is_deleted") \
            .eq("id", message_id).execute().data
        if not exists or exists[0].get("is_deleted"):
            return JsonResponse({"error": "message_not_found"}, status=404)

        q = app.supabase.table("chat_reactions").select("id") \
            .eq("message_id", message_id).eq("emoji", emoji)
        q = q.eq("user_id", user_id) if user_id else q.eq("guest_id", guest_id)
        existing = q.execute().data

        if existing:
            app.supabase.table("chat_reactions").delete().eq("id", existing[0]["id"]).execute()
            action = "removed"
        else:
            app.supabase.table("chat_reactions").insert({
                "message_id": message_id, "user_id": user_id,
                "guest_id": guest_id, "emoji": emoji,
            }).execute()
            action = "added"
        return JsonResponse({"success": True, "action": action})
    except Exception as e:
        print(f"[chat react] {e}")
        return JsonResponse({"error": "react_failed"}, status=500)


# ============================================================
# API — admin: delete message
# ============================================================
def api_chat_admin_delete(request, message_id):
    app = _deps()
    if not app.is_chat_admin(request):
        return JsonResponse({"error": "not_authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        message_id = str(uuid.UUID(str(message_id)))
    except Exception:
        return JsonResponse({"error": "invalid_message_id"}, status=400)
    try:
        app.supabase.table("chat_messages").update({
            "is_deleted": True,
            "deleted_by_admin": True,
            "message": "🚫 Deleted by admin",
        }).eq("id", message_id).execute()
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[chat admin delete] {e}")
        return JsonResponse({"error": "delete_failed"}, status=500)


# ============================================================
# API — admin: pin / unpin
# ============================================================
def api_chat_admin_pin(request):
    app = _deps()
    if not app.is_chat_admin(request):
        return JsonResponse({"error": "not_authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    new_pin = str(body.get("pinned_message") or "").strip()[:500]
    me = app.get_current_user(request)

    if new_pin:
        values = {"id": 1, "pinned_message": new_pin,
                  "pinned_by": str(me["id"]) if me else None,
                  "pinned_at": _now_utc().isoformat()}
    else:
        values = {"id": 1, "pinned_message": None, "pinned_by": None, "pinned_at": None}

    try:
        app.supabase.table("chat_settings").upsert(values).execute()  # creates row 1 if missing
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[chat admin pin] {e}")
        return JsonResponse({"error": "pin_failed"}, status=500)


# ============================================================
# API — guest status
# ============================================================
def api_chat_guest_status(request):
    app = _deps()
    if app.get_current_user(request):
        return JsonResponse({"logged_in": True, "remaining": None})

    guest_id = _get_guest_id(request)
    if not guest_id:
        return JsonResponse({"logged_in": False, "remaining": GUEST_DAILY_LIMIT})

    try:
        r = app.supabase.table("guest_chat_limits").select("message_count") \
            .eq("guest_id", guest_id).eq("day", date.today().isoformat()).execute()
        used = (r.data[0].get("message_count", 0) or 0) if r.data else 0
        return JsonResponse({"logged_in": False, "remaining": max(0, GUEST_DAILY_LIMIT - used)})
    except Exception as e:
        print(f"[chat guest status] {e}")
        return JsonResponse({"logged_in": False, "remaining": GUEST_DAILY_LIMIT})
