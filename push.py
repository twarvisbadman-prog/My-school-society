# push.py — Web Push notifications for Student Hub
# Sends a push + in-app notification to an uploader's followers when they upload a public note.
#
# Needs:  pip install pywebpush
# Env:    VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT (optional)
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

try:
    from pywebpush import webpush, WebPushException
except ImportError:  # app still runs; push just stays off
    webpush = None

    class WebPushException(Exception):
        response = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _public_key():
    return os.environ.get("VAPID_PUBLIC_KEY", "").strip()


def _private_key():
    return os.environ.get("VAPID_PRIVATE_KEY", "").strip()


def _subject():
    return os.environ.get("VAPID_SUBJECT", "").strip() or "mailto:Twarvistech@gmail.com"


def push_ready():
    return bool(webpush and _public_key() and _private_key())


def _sb():
    # Lazy import avoids a circular import with app.py
    import app
    return app.supabase


def _me(request):
    return getattr(request, "current_user", None)


# ============================================================
# API VIEWS
# ============================================================
@csrf_exempt
def api_push_key(request):
    return JsonResponse({"enabled": push_ready(), "public_key": _public_key()})


@csrf_exempt
def api_push_subscribe(request):
    me = _me(request)
    if not me:
        return JsonResponse({"error": "login_required"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        body = json.loads(request.body or "{}")
        sub = body.get("subscription") or {}
        keys = sub.get("keys") or {}
        endpoint = sub.get("endpoint")
        if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
            return JsonResponse({"error": "invalid_subscription"}, status=400)
        _sb().table("push_subscriptions").upsert({
            "user_id": str(me["id"]),
            "endpoint": endpoint,
            "p256dh": keys["p256dh"],
            "auth": keys["auth"],
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
        }, on_conflict="endpoint").execute()
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[push] subscribe failed: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def api_push_unsubscribe(request):
    me = _me(request)
    if not me:
        return JsonResponse({"error": "login_required"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        body = json.loads(request.body or "{}")
        endpoint = body.get("endpoint")
        if endpoint:
            _sb().table("push_subscriptions").delete() \
                .eq("endpoint", endpoint).eq("user_id", str(me["id"])).execute()
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[push] unsubscribe failed: {e}")
        return JsonResponse({"error": str(e)}, status=500)


def sw_view(request):
    """Serve the service worker from the site root so its scope is '/'."""
    path = os.path.join(BASE_DIR, "sw.js")
    if not os.path.exists(path):
        return HttpResponse("sw.js not found", status=404)
    with open(path, "rb") as f:
        data = f.read()
    resp = HttpResponse(data, content_type="application/javascript; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    resp["Service-Worker-Allowed"] = "/"
    return resp


# ============================================================
# SENDING
# ============================================================
def notify_followers_async(uploader_id, uploader_user, title, course, note_id):
    """Fire-and-forget: never blocks or breaks the upload."""
    threading.Thread(
        target=_notify_followers,
        args=(uploader_id, uploader_user, title, course, note_id),
        daemon=True,
    ).start()


def _notify_followers(uploader_id, uploader_user, title, course, note_id):
    try:
        sb = _sb()
        uploader_id = str(uploader_id)
        prof = (uploader_user or {}).get("profile") or {}
        name = prof.get("full_name") or prof.get("username") or "Someone"

        rows = sb.table("follows").select("follower_id") \
            .eq("following_id", uploader_id).execute().data or []
        follower_ids = list({str(r["follower_id"]) for r in rows} - {uploader_id})
        if not follower_ids:
            return

        label = (title or "New notes").strip()
        if course and course != "N/A":
            label = f"{label} ({course})"
        url = f"/view/{note_id}/" if note_id else "/browse/"

        # 1) In-app notifications (shown in the existing bell)
        try:
            sb.table("notifications").insert([{
                "user_id": fid,
                "actor_id": uploader_id,
                "type": "upload",
                "reference_id": str(note_id) if note_id else None,
                "message": f"{name} uploaded new notes: {label}",
                "is_read": False,
            } for fid in follower_ids]).execute()
        except Exception as e:
            print(f"[push] in-app notifications failed: {e}")

        # 2) Browser / phone push
        if not push_ready():
            print("[push] VAPID keys or pywebpush missing — skipped web push")
            return

        subs = sb.table("push_subscriptions").select("*") \
            .in_("user_id", follower_ids).execute().data or []
        if not subs:
            return

        payload = json.dumps({
            "title": f"📚 New notes from {name}",
            "body": label,
            "url": url,
            "tag": f"upload-{note_id or uploader_id}",
        })
        private_key = _private_key()
        subject = _subject()
        dead = []

        def send(s):
            try:
                webpush(
                    subscription_info={
                        "endpoint": s["endpoint"],
                        "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={"sub": subject},  # fresh dict each call (library mutates it)
                    ttl=86400,
                )
            except WebPushException as e:
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):
                    dead.append(s["endpoint"])
                else:
                    print(f"[push] send failed ({code}): {e}")
            except Exception as e:
                print(f"[push] send error: {e}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(send, subs))

        # Clean up expired subscriptions
        for ep in dead:
            try:
                sb.table("push_subscriptions").delete().eq("endpoint", ep).execute()
            except Exception:
                pass

        print(f"[push] ✅ {len(subs) - len(dead)} pushes sent, {len(dead)} expired removed")
    except Exception as e:
        print(f"[push] notify failed: {e}")
