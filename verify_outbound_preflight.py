from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXACT_FIRST_LINE = "Hello, this is your AI assistant. Can you hear me?"
TARGET_PHONE = "+916384189687"
APP_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = APP_ROOT / "config.json"

REQUIRED_ENV_VARS = [
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "GROQ_API_KEY",
    "SARVAM_API_KEY",
]

TRUNK_ENV_VARS = [
    "LIVEKIT_SIP_TRUNK_ID",
    "OUTBOUND_TRUNK_ID",
    "SIP_TRUNK_ID",
]

SUCCESS_LOG_PATTERNS = [
    "[SIP] Participant connected",
    "[AGENT] Session live",
    "[LLM] Using Groq",
    "[TTS] Using Sarvam Bulbul v3",
    "[TTS] Pre-warmed successfully",
    "[AUDIO] Track published",
]

SILENT_CALL_DIAGNOSTIC_PATTERNS = [
    "Traceback",
    "TTS",
    "audio",
    "publish",
    "subscription",
    "track",
    "Sarvam",
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def mask_bool(value: str | None) -> str:
    return "present" if value else "missing"


def config_key_for_env(env_key: str) -> str:
    return env_key.lower()


def credential_source(env_key: str, config: dict[str, Any], railway_vars: set[str]) -> str:
    config_key = config_key_for_env(env_key)
    if config.get(config_key):
        return "config fallback"
    if os.environ.get(env_key):
        return "env vars"
    if env_key in railway_vars:
        return "env vars (Railway)"
    return "missing"


def normalized_base_url(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.strip().rstrip("/")
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def discover_base_url(cli_arg: str | None) -> str:
    for candidate in (
        cli_arg,
        os.environ.get("RAILWAY_PUBLIC_DOMAIN"),
        os.environ.get("NEXT_PUBLIC_API_URL"),
        os.environ.get("API_BASE_URL"),
        os.environ.get("PUBLIC_BASE_URL"),
        os.environ.get("RAILWAY_STATIC_URL"),
    ):
        base_url = normalized_base_url(candidate)
        if base_url:
            return base_url
    return ""


def run_command(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            args,
            cwd=APP_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, f"{args[0]} not found"
    except subprocess.TimeoutExpired:
        return False, f"{' '.join(args)} timed out after {timeout}s"


def railway_variable_names() -> tuple[set[str], bool]:
    names: set[str] = set()
    cli_seen = False
    for command in (["railway", "variables", "--kv"], ["railway", "variables"]):
        ok, output = run_command(command, timeout=20)
        if "railway not found" not in output.lower():
            cli_seen = True
        if not ok:
            continue
        for line in output.splitlines():
            key = line.split("=", 1)[0].strip()
            if key and key.replace("_", "").isalnum():
                names.add(key)
        if names:
            break
    return names, cli_seen


def fetch_json(base_url: str, path: str, timeout: int = 15) -> tuple[bool, dict[str, Any] | str]:
    url = f"{base_url}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, json.loads(body)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def post_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 30,
) -> tuple[bool, dict[str, Any] | str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return True, json.loads(response_body)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def print_status(label: str, ok: bool | None | str, detail: str = "") -> None:
    if ok is True:
        prefix = "PASS"
    elif ok is False:
        prefix = "FAIL"
    elif ok == "WARN":
        prefix = "WARN"
    elif ok == "SKIP":
        prefix = "SKIP"
    else:
        prefix = "INFO"
    suffix = f" - {detail}" if detail else ""
    print(f"[{prefix}] {label}{suffix}")


def _provider_flag(payload: dict[str, Any], key: str) -> bool:
    providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
    return bool(providers.get(key))


def production_health_check(base_url: str) -> tuple[bool, dict[str, Any]]:
    """Check production runtime env through public health endpoints.

    Local env can be intentionally empty; this is the authoritative readiness
    check for a Railway-hosted outbound call worker/API.
    """
    result: dict[str, Any] = {
        "base_url": base_url,
        "livekit_configured": False,
        "sip_trunk_configured": False,
        "groq_or_openai_configured": False,
        "api_health": None,
        "livekit_health": None,
        "sip_health": None,
    }

    ok, api_health = fetch_json(base_url, "/health")
    if ok and isinstance(api_health, dict):
        result["api_health"] = api_health
        result["livekit_configured"] = bool(api_health.get("livekit_configured")) or _provider_flag(api_health, "livekit")
        result["sip_trunk_configured"] = bool(api_health.get("sip_trunk_configured")) or _provider_flag(api_health, "sip")
        result["groq_or_openai_configured"] = bool(api_health.get("groq_or_openai_configured")) or _provider_flag(api_health, "llm") or bool(
            ((api_health.get("mvp_env") or {}).get("required") or {}).get("GROQ_OR_OPENAI_API_KEY")
        )
    else:
        result["api_health"] = str(api_health)

    ok, livekit_health = fetch_json(base_url, "/api/livekit/health")
    if ok and isinstance(livekit_health, dict):
        result["livekit_health"] = livekit_health
        result["livekit_configured"] = result["livekit_configured"] or bool(
            livekit_health.get("ok") is True
            and livekit_health.get("api_reachable") is True
        )
    else:
        result["livekit_health"] = str(livekit_health)

    ok, sip_health = fetch_json(base_url, "/api/sip/health")
    if ok and isinstance(sip_health, dict):
        result["sip_health"] = sip_health
        result["sip_trunk_configured"] = result["sip_trunk_configured"] or bool(sip_health.get("trunk_configured"))
        result["livekit_configured"] = result["livekit_configured"] or bool(sip_health.get("livekit_configured"))
    else:
        result["sip_health"] = str(sip_health)

    ready = bool(
        result["livekit_configured"]
        and result["sip_trunk_configured"]
        and result["groq_or_openai_configured"]
    )
    return ready, result


def summarize_logs(log_output: str) -> None:
    if not log_output:
        print_status("Railway deploy logs", None, "no logs returned")
        return
    for pattern in SUCCESS_LOG_PATTERNS:
        print_status(f"log pattern {pattern}", pattern in log_output, "present" if pattern in log_output else "not seen")
    if "[AUDIO] Track published" not in log_output:
        print_status("audio publish instrumentation", None, "[AUDIO] Track published not found; inspect room tracks during live call")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight outbound LiveKit/Railway call readiness without placing a call by default.")
    parser.add_argument("--base-url", help="Public API base URL, for example https://example.up.railway.app")
    parser.add_argument("--phone", default=TARGET_PHONE)
    parser.add_argument("--first-line", default=EXACT_FIRST_LINE)
    parser.add_argument("--place-call", action="store_true", help="Actually POST to /api/calls/outbound-test. Requires confirmation.")
    parser.add_argument("--confirm-phone", default="", help="Must equal --phone when --place-call is used.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when critical preflight checks fail.")
    args = parser.parse_args()

    load_dotenv(APP_ROOT / ".env")
    config = load_config()
    base_url = discover_base_url(args.base_url)
    railway_vars, railway_cli_vars_available = railway_variable_names()

    production_ready = False
    production_health: dict[str, Any] = {}

    print("Outbound AI call preflight")
    print(f"target_phone={args.phone}")
    print(f"first_line={args.first_line!r}")
    print_status("place call mode", None, "disabled" if not args.place_call else "enabled")

    print("\nRAILWAY_CLI_CHECK")
    ok, railway_status = run_command(["railway", "status"], timeout=20)
    railway_cli_available = ok or railway_cli_vars_available or "railway not found" not in railway_status.lower()
    if not railway_cli_available:
        print_status("RAILWAY_CLI_CHECK", "SKIP", "railway CLI not found locally; production env will be checked over HTTP if base URL is available")
        logs = ""
    else:
        print_status("Railway status command", ok, railway_status.splitlines()[0] if railway_status else "")

        ok, deployments = run_command(["railway", "deployments", "--json"], timeout=25)
        if ok:
            print_status("Railway deployments", True, "latest deployment metadata available")
        else:
            print_status("Railway deployments", None, deployments[:180])

        ok, logs = run_command(["railway", "logs", "--lines", "300"], timeout=30)
        print_status("Railway logs", ok, "latest logs available" if ok else logs[:180])
        if ok:
            worker_started = "[AGENT] Session live" in logs or "outbound-caller" in logs or "Worker" in logs
            print_status("worker started evidence", worker_started, "found in logs" if worker_started else "not found in recent logs")
            summarize_logs(logs)
        else:
            print_status("worker started evidence", None, "logs unavailable")

    print("\nLOCAL_ENV_CHECK")
    for env_key in REQUIRED_ENV_VARS:
        source = credential_source(env_key, config, railway_vars)
        present = source != "missing"
        print_status(f"{env_key}", True if present else "WARN", f"source={source}" if present else "missing locally; production HTTP check is authoritative")

    print("runtime credential source:")
    livekit_sources = {
        key: credential_source(key, config, railway_vars)
        for key in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    }
    for key, source in livekit_sources.items():
        print(f"  {key}: {source}")

    trunk_found = False
    config_trunk_present = bool(config.get("sip_trunk_id"))
    for env_key in TRUNK_ENV_VARS:
        source_present = bool(os.environ.get(env_key)) or env_key in railway_vars
        trunk_found = trunk_found or source_present
        print_status(f"{env_key}", True if source_present else "WARN", "env vars" if source_present else "missing locally")
    trunk_found = trunk_found or config_trunk_present
    print_status("SIP_TRUNK_ID fallback config", True if config_trunk_present else "WARN", "config fallback" if config_trunk_present else "missing locally")
    print_status("any SIP trunk env accepted", True if trunk_found else "WARN", "one of LIVEKIT_SIP_TRUNK_ID / OUTBOUND_TRUNK_ID / SIP_TRUNK_ID" if trunk_found else "none found locally; production HTTP check is authoritative")

    print("\nPRODUCTION_HTTP_CHECK")
    if base_url:
        print_status("base URL", True, base_url)
        production_ready, production_health = production_health_check(base_url)
        print_status(
            "production livekit_configured",
            bool(production_health.get("livekit_configured")),
            "from /health + /api/livekit/health + /api/sip/health",
        )
        print_status(
            "production sip_trunk_configured",
            bool(production_health.get("sip_trunk_configured")),
            "accepts LIVEKIT_SIP_TRUNK_ID or OUTBOUND_TRUNK_ID or SIP_TRUNK_ID",
        )
        print_status(
            "production groq_or_openai_configured",
            bool(production_health.get("groq_or_openai_configured")),
            "from /health providers.llm",
        )
        print_status("PRODUCTION_HTTP_CHECK", production_ready, "production health green" if production_ready else "production health incomplete")
    else:
        print_status("base URL", "SKIP", "not provided; read from --base-url, RAILWAY_PUBLIC_DOMAIN, NEXT_PUBLIC_API_URL, or API_BASE_URL")
        print_status("PRODUCTION_HTTP_CHECK", "SKIP", "no production base URL available")

    print("silent-call diagnostics to collect if needed:")
    for pattern in SILENT_CALL_DIAGNOSTIC_PATTERNS:
        print(f"  - Railway/LiveKit logs containing: {pattern}")
    print("  - LiveKit room participants and track publications/subscriptions")
    print("  - Sarvam TTS/STT errors and response metadata")

    if args.place_call:
        if args.confirm_phone != args.phone:
            print_status("call confirmation", False, "--confirm-phone must exactly match --phone")
            return 2
        if not base_url:
            print_status("call request", False, "missing base URL")
            return 2
        secret = os.environ.get("INTERNAL_TEST_CALL_SECRET", "")
        if not secret:
            print_status("call request", False, "INTERNAL_TEST_CALL_SECRET missing locally")
            return 2
        payload = {"phone_number": args.phone, "first_line": args.first_line}
        ok, result = post_json(
            base_url,
            "/api/calls/outbound-test",
            payload,
            {"X-Internal-Test-Secret": secret},
        )
        print_status("outbound call request", ok, json.dumps(result)[:500] if isinstance(result, dict) else str(result))
        return 0 if ok else 2

    print_status("outbound call request", None, "not sent; preflight-only mode")
    print(f"READY_FOR_LIVE_CALL={'true' if production_ready else 'false'}")
    if args.strict and not production_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

