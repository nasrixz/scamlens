/**
 * Web Push registration helper.
 *
 * 1. Registers the service worker (public/sw.js).
 * 2. Fetches the VAPID public key from the API.
 * 3. Subscribes the browser's PushManager.
 * 4. Sends the subscription keys to the API so the server can push.
 */
import { API_BASE } from "./api";

let swReg: ServiceWorkerRegistration | null = null;

/** Register SW + subscribe to push if the browser supports it. */
export async function initPush(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    console.warn("[push] not supported");
    return false;
  }

  try {
    swReg = await navigator.serviceWorker.register("/sw.js");
    console.log("[push] sw registered");
  } catch (err) {
    console.error("[push] sw registration failed", err);
    return false;
  }

  // Already subscribed?
  const existing = await swReg.pushManager.getSubscription();
  if (existing) {
    await _sendSubToServer(existing);
    return true;
  }

  return false;
}

/** Ask user permission, then subscribe. Returns true on success. */
export async function subscribePush(): Promise<boolean> {
  if (!swReg) await initPush();
  if (!swReg) return false;

  // Fetch VAPID public key.
  const res = await fetch(`${API_BASE}/push/key`, { credentials: "include" });
  if (!res.ok) {
    console.error("[push] failed to get VAPID key", res.status);
    return false;
  }
  const { public_key } = (await res.json()) as { public_key: string };

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return false;

  try {
    const sub = await swReg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: _urlBase64ToUint8Array(public_key),
    });
    await _sendSubToServer(sub);
    return true;
  } catch (err) {
    console.error("[push] subscribe failed", err);
    return false;
  }
}

/** Unsubscribe from push. */
export async function unsubscribePush(): Promise<void> {
  if (!swReg) return;
  const sub = await swReg.pushManager.getSubscription();
  if (!sub) return;
  await sub.unsubscribe();
  // Tell server to delete.
  const keys = sub.toJSON().keys || {};
  await fetch(`${API_BASE}/me/push/subscribe`, {
    method: "DELETE",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      endpoint: sub.endpoint,
      p256dh: keys.p256dh || "",
      auth: keys.auth || "",
    }),
  });
}

// --- internal helpers -------------------------------------------------------

async function _sendSubToServer(sub: PushSubscription): Promise<void> {
  const keys = sub.toJSON().keys || {};
  await fetch(`${API_BASE}/me/push/subscribe`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      endpoint: sub.endpoint,
      p256dh: keys.p256dh || "",
      auth: keys.auth || "",
      user_agent: navigator.userAgent,
    }),
  });
}

function _urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}
