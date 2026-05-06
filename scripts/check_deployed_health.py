"""
Optional production smoke check for Railway FastAPI `/health`.

Usage (PowerShell):
  $env:PUBLIC_API_URL = "https://your-service.up.railway.app"
  python scripts/check_deployed_health.py

The API reports `mvp_env.required` including `GROQ_OR_OPENAI_API_KEY` (true when either
`GROQ_API_KEY` or `OPENAI_API_KEY` is set).

Manual MVP checklist after health is green:
- Supabase Auth: email/password only, confirm email OFF for first testing.
- Vercel: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY.
- Railway CORS_ORIGIN includes your production Vercel origin (comma-separated).
- Signup, login, Tamil RE agent publish, internal test call, CRM row, transfer phrase test.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request


def main() -> int:
    raw = os.environ.get("PUBLIC_API_URL", "").strip().rstrip("/")
    if not raw:
        print(
            "[check_deployed_health] Set PUBLIC_API_URL to your Railway base URL "
            "(e.g. https://xxx.up.railway.app). Skipping.",
        )
        return 0

    url = raw + "/health"
    req = urllib.request.Request(url, method="GET")

    ssl_ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"[check_deployed_health] HTTP {e.code} for {url}")
        return 1
    except OSError as e:
        print(f"[check_deployed_health] request failed for {url}: {e}")
        return 1

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"[check_deployed_health] non-JSON from {url}")
        return 1

    mv = ((data.get("mvp_env") or {}) if isinstance(data.get("mvp_env"), dict) else {})
    req_map = mv.get("required") if isinstance(mv.get("required"), dict) else {}
    top_missing = data.get("missing") if isinstance(data.get("missing"), list) else None
    if top_missing is not None:
        missing_keys = sorted(top_missing)
    else:
        missing_keys = sorted(k for k, v in req_map.items() if not v)
    mvp_ready = data.get("mvp_env_ready")
    if mvp_ready is None:
        mvp_ready = mv.get("ready")
    providers = data.get("providers") if isinstance(data.get("providers"), dict) else {}

    payload = {
        "url": url,
        "status": data.get("status"),
        "ok": bool(data.get("ok")),
        "mvp_env_ready": bool(mvp_ready),
        "providers": providers,
        "missing": missing_keys,
    }
    print(json.dumps(payload, indent=2))
    return 0 if mvp_ready and not missing_keys else 1


if __name__ == "__main__":
    raise SystemExit(main())
