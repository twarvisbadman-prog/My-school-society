# push.py - Web Push for Student Hub
# Notifies followers (push + notification bell) when a PUBLIC note is uploaded.
import os
import sys
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

try:
    from pywebpush import webpush, WebPushException
except ImportError:  # pip install pywebpush
    webpush = None

    class WebPushException(Exception):
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_svc_client = None


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------
def _db():
    """Use SUPABASE_SERVICE_KEY if set (recommended), else the app's client."""
    global _svc_client
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if key:
        if _svc_client is None:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL", "").strip()
            if not url:
                mod = sys.modules.get("app") or sys.modules.get("__main__")
                url = getattr(mod, "SUPABASE_URL")
            _svc_client = create_client(url, key)
        return _svc_client
    mod = sys.modules.get("app") or sys.modules.get("__main__")
    return mod.supabase


def _user(request):
    return getattr(request, "current_user", None)


def _vapid():
    return (
        os.environ.get("VAPID_PUBLIC_KEY", "").strip(),
        os.environ.get("VAPID_PRIVATE_KEY", "").strip(),
        os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com").strip(),
    )


# ------------------------------------------------------------
# views
# ------------------------------------------------------------
def sw_view(request):
    """Serve the service worker from the site root with the right headers."""
    path = os.path.join(BASE_DIR, "sw.js")
    if not os.path.exists(path):
        return HttpResponse("Not found", status=404)
    with open(path, "rb") as f:
        data = f.read()
    resp = HttpResponse(data, content_type="application/javascript; charset=utf-8")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def api_push_key(request):
    pub, _, _ = _vapid()
    return JsonResponse({"key": pub})


@csrf_exempt
def api_push_subscribe(request):
    me = _user(request)
    if not me:
        return JsonResponse({"error": "login_required"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        body = json.loads(request.body or "{}")
        endpoint = (body.get("endpoint") or "").strip()
        keys = body.get("keys") or {}
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")
        if not endpoint.startswith("https://") or not p256dh or not auth:
            return JsonResponse({"error": "invalid_subscription"}, status=400)
        _db().table("push_subscriptions").upsert({
            "user_id": str(me["id"]),
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
        }, on_conflict="endpoint").execute()
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[push] subscribe failed: {e}")
        return JsonResponse({"error": "subscribe_failed"}, status=500)


@csrf_exempt
def api_push_unsubscribe(request):
    me = _user(request)
    if not me:
        return JsonResponse({"error": "login_required"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        body = json.loads(request.body or "{}")
        endpoint = (body.get("endpoint") or "").strip()
        if endpoint:
            _db().table("push_subscriptions").delete() \
                .eq("endpoint", endpoint).eq("user_id", str(me["id"])).execute()
        return JsonResponse({"success": True})
    except Exception as e:
        print(f"[push] unsubscribe failed: {e}")
        return JsonResponse({"error": "unsubscribe_failed"}, status=500)


# ------------------------------------------------------------
# notify followers
# ------------------------------------------------------------
def notify_followers_async(uploader_id, uploader, title, course, note_id):
    """Fire and forget normally. On Vercel (serverless) background threads are
    frozen as soon as the response is sent, so run inline there instead."""
    args = (uploader_id, uploader, title, course, note_id)
    if os.environ.get("VERCEL"):
        _notify(*args)
        return
    threading.Thread(target=_notify, args=args, daemon=True).start()


def _notify(uploader_id, uploader, title, course, note_id):
    try:
        db = _db()
        uploader_id = str(uploader_id)

        rows = db.table("follows").select("follower_id") \
            .eq("following_id", uploader_id).execute().data or []
        follower_ids = list({str(r["follower_id"]) for r in rows} - {uploader_id})
        if not follower_ids:
            return

        profile = (uploader or {}).get("profile") or {}
        name = (profile.get("full_name") or profile.get("username")
                or ((uploader or {}).get("email") or "Someone").split("@")[0])
        title = (title or "a new note").strip()[:80]
        msg = f"{name} uploaded a new note: {title}"
        if course and course != "N/A":
            msg += f" ({course.strip()[:30]})"
        ref = str(note_id) if note_id else None
        url = f"/view/{note_id}/" if note_id else "/browse/"

        # 1) bell entries
        try:
            for i in range(0, len(follower_ids), 200):
                db.table("notifications").insert([{
                    "user_id": uid,
                    "actor_id": uploader_id,
                    "type": "new_note",
                    "reference_id": ref,
                    "message": msg,
                    "is_read": False,
                } for uid in follower_ids[i:i + 200]]).execute()
        except Exception as e:
            print(f"[push] bell insert failed: {e}")

        # 2) push
        _send_push(db, follower_ids, {
            "title": f"📚 New note from {name}",
            "body": title,
            "url": url,
            "tag": f"note-{ref or 'x'}",
        })
    except Exception as e:
        print(f"[push] notify failed: {e}")


def _send_push(db, user_ids, payload):
    if webpush is None:
        print("[push] pywebpush not installed, skipping push")
        return
    _, private, subject = _vapid()
    if not private:
        print("[push] VAPID_PRIVATE_KEY missing, skipping push")
        return

    subs = []
    for i in range(0, len(user_ids), 200):
        r = db.table("push_subscriptions").select("endpoint, p256dh, auth") \
            .in_("user_id", user_ids[i:i + 200]).execute()
        subs.extend(r.data or [])
    if not subs:
        return

    data = json.dumps(payload)

    def send(s):
        try:
            webpush(
                subscription_info={
                    "endpoint": s["endpoint"],
                    "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
                },
                data=data,
                vapid_private_key=private,
                vapid_claims={"sub": subject},
                ttl=86400,
            )
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):  # subscription expired, clean it up
                try:
                    db.table("push_subscriptions").delete() \
                        .eq("endpoint", s["endpoint"]).execute()
                except Exception:
                    pass
            else:
                print(f"[push] send failed ({status}): {e}")
        except Exception as e:
            print(f"[push] send error: {e}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(send, subs))
    print(f"[push] sent to {len(subs)} device(s)")
