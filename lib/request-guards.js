// Checks shared by the site's Pages Functions (functions/api/*.js).

// The live domains. Requests from the site's own address (including Cloudflare preview
// deployments) are always allowed; the ALLOWED_ORIGINS setting replaces this list.
const DEFAULT_ORIGINS = 'https://auraenergy.ie,https://www.auraenergy.ie';

// The site's pages call these endpoints from the same site, so the browser's Origin header
// matches; ALLOWED_ORIGINS adds other domains (comma-separated). This stops other websites
// using them from a visitor's browser. It is not authentication: rate limiting (below, and a
// Cloudflare rate limiting rule in production) is what limits direct abuse.
export function originAllowed(origin, url, list) {
  if (!origin) return false;
  if (origin === new URL(url).origin) return true;
  return (list || DEFAULT_ORIGINS).split(',').map((s) => s.trim()).includes(origin);
}

// Returns a check that allows `max` requests per key (the visitor's IP) in each window.
// It uses a Cloudflare rate limiting binding when one is passed, otherwise a best-effort
// in-memory count (each isolate keeps its own).
export function rateLimiter({ windowMs, max }) {
  const recent = new Map(); // key -> timestamps of recent requests
  return async function withinLimit(key, binding) {
    if (binding && typeof binding.limit === 'function') {
      const { success } = await binding.limit({ key });
      return success;
    }
    const now = Date.now();
    const times = (recent.get(key) || []).filter((t) => now - t < windowMs);
    if (times.length >= max) {
      recent.set(key, times);
      return false;
    }
    times.push(now);
    recent.set(key, times);
    if (recent.size > 5000) {
      for (const [k, list] of recent) {
        if (!list.length || now - list[list.length - 1] >= windowMs) recent.delete(k);
      }
    }
    return true;
  };
}

export function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
