// push-client.js — add to any page:  <script src="/push-client.js" defer></script>
// Logged-in users who haven't decided yet see a small "Enable notifications" pill.
(function () {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;

  var DISMISS_KEY = 'sh_push_dismissed';

  function b64ToUint8(b64) {
    var pad = '='.repeat((4 - b64.length % 4) % 4);
    var raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function getJSON(url) {
    return fetch(url, { credentials: 'same-origin' }).then(function (r) { return r.json(); });
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }

  function subscribe(reg, publicKey) {
    return reg.pushManager.getSubscription().then(function (existing) {
      return existing || reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: b64ToUint8(publicKey)
      });
    }).then(function (sub) {
      return postJSON('/api/push/subscribe/', { subscription: sub.toJSON() });
    });
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#14162b;color:#fff;padding:12px 18px;border-radius:12px;font:600 14px system-ui,sans-serif;z-index:99999;box-shadow:0 8px 24px rgba(0,0,0,.3)';
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3200);
  }

  function showPill(onEnable) {
    var pill = document.createElement('div');
    pill.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:99998;display:flex;align-items:center;gap:6px;background:#4f46e5;color:#fff;border-radius:999px;padding:6px 6px 6px 14px;font:600 13px system-ui,sans-serif;box-shadow:0 8px 24px rgba(79,70,229,.4)';
    var btn = document.createElement('button');
    btn.textContent = '🔔 Get notified of new notes';
    btn.style.cssText = 'background:none;border:none;color:#fff;font:inherit;cursor:pointer;padding:6px 4px';
    var x = document.createElement('button');
    x.textContent = '✕';
    x.setAttribute('aria-label', 'Dismiss');
    x.style.cssText = 'background:rgba(255,255,255,.2);border:none;color:#fff;width:28px;height:28px;border-radius:50%;cursor:pointer';
    pill.appendChild(btn); pill.appendChild(x);
    document.body.appendChild(pill);
    btn.onclick = function () { pill.remove(); onEnable(); };
    x.onclick = function () {
      pill.remove();
      try { localStorage.setItem(DISMISS_KEY, '1'); } catch (e) {}
    };
  }

  function init() {
    Promise.all([getJSON('/api/me/'), getJSON('/api/push/key/')]).then(function (res) {
      var me = res[0], cfg = res[1];
      if (!me.logged_in || !cfg.enabled) return;

      navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function () {
        return navigator.serviceWorker.ready;
      }).then(function (reg) {
        function enable() {
          Notification.requestPermission().then(function (perm) {
            if (perm === 'granted') {
              subscribe(reg, cfg.public_key).then(function () {
                toast('🔔 Notifications on!');
              });
            }
          });
        }

        window.StudentHubPush = {
          enable: enable,
          disable: function () {
            return reg.pushManager.getSubscription().then(function (sub) {
              if (!sub) return;
              return postJSON('/api/push/unsubscribe/', { endpoint: sub.endpoint })
                .then(function () { return sub.unsubscribe(); });
            });
          }
        };

        if (Notification.permission === 'granted') {
          subscribe(reg, cfg.public_key);          // keep subscription fresh silently
        } else if (Notification.permission === 'default') {
          var dismissed = false;
          try { dismissed = localStorage.getItem(DISMISS_KEY) === '1'; } catch (e) {}
          if (!dismissed) showPill(enable);
        }
      });
    }).catch(function () {});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
