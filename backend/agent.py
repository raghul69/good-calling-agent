import os
import json
import logging
import certifi
import pytz
import re
import asyncio
import time
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Annotated, Any, AsyncIterable

# Fix for macOS SSL certificate verification
os.environ["SSL_CERT_FILE"] = certifi.where()

# ── Sentry error tracking (#21) ───────────────────────────────────────────────
import sentry_sdk
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1,
        integrations=[AsyncioIntegration()],
        environment=os.environ.get("ENVIRONMENT", "production"),
    )

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv()
logger = logging.getLogger("outbound-agent")
FALLBACK_FIRST_LINE = "ஹலோ sir, MAXR Consultancy ல இருந்து பேசுறேன். Chennai la property பார்க்கிறீங்களா?"
logging.basicConfig(level=logging.INFO)
_PROCESS_STARTED_MONO = time.perf_counter()
_FIRST_LIVEKIT_JOB_SEEN = False

# Duplicate tool call_id grouping bug (livekit-agents) — must run before livekit.agents imports
try:
    from backend.livekit_group_tool_calls_fix import apply_patch as _apply_livekit_group_tool_calls_fix

    _apply_livekit_group_tool_calls_fix()
except Exception as _e:
    logger.warning("[livekit] group_tool_calls patch failed — tool batching may be unreliable: %s", _e)


def _debug_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10] if value else ""


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        entry = {
            "sessionId": "6b88e2",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }
        with open("debug-6b88e2.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        logger.info("[DEBUG-6b88e2] %s %s", message, json.dumps(data, ensure_ascii=True))
    except Exception:
        pass

from livekit import api
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    StopResponse,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import openai, silero

CONFIG_FILE = "config.json"

# ── Rate limiting (#37) ───────────────────────────────────────────────────────
_call_timestamps: dict = defaultdict(list)
RATE_LIMIT_CALLS  = 5
RATE_LIMIT_WINDOW = 3600  # 1 hour

def is_rate_limited(phone: str) -> bool:
    if phone in ("unknown", "demo"):
        return False
    now = time.time()
    _call_timestamps[phone] = [t for t in _call_timestamps[phone] if now - t < RATE_LIMIT_WINDOW]
    if len(_call_timestamps[phone]) >= RATE_LIMIT_CALLS:
        return True
    _call_timestamps[phone].append(now)
    return False


# ── Config loader (#17 partial — per-client path awareness) ───────────────────
def get_live_config(phone_number: str | None = None):
    """Load config — tries per-client file first, then default config.json."""
    config = {}
    paths = []
    if phone_number and phone_number != "unknown":
        clean = phone_number.replace("+", "").replace(" ", "")
        paths.append(f"configs/{clean}.json")
    paths += ["configs/default.json", CONFIG_FILE]

    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    config = json.load(f)
                    logger.info(f"[CONFIG] Loaded: {path}")
                    break
            except Exception as e:
                logger.error(f"[CONFIG] Failed to read {path}: {e}")

    eng = config.get("engine_config") if isinstance(config.get("engine_config"), dict) else {}
    vert = (config.get("vertical") or eng.get("vertical") or "").strip()
    lc_top = config.get("language_config") if isinstance(config.get("language_config"), dict) else {}
    lc_eng = eng.get("language_config") if isinstance(eng.get("language_config"), dict) else {}
    language_config = {**lc_eng, **lc_top}
    return {
        "agent_instructions":       config.get("agent_instructions", ""),
        "stt_min_endpointing_delay":config.get("stt_min_endpointing_delay", 0.05),
        "llm_model":                config.get("llm_model", "gpt-4o-mini"),
        "llm_provider":             config.get("llm_provider", "openai"),
        "tts_voice":                config.get("tts_voice", "kavya"),
        "tts_language":             config.get("tts_language", "en-IN"),
        "tts_model":                config.get("tts_model", "bulbul:v3"),
        "tts_provider":             config.get("tts_provider", "sarvam"),
        "stt_provider":             config.get("stt_provider", "sarvam"),
        "stt_model":                config.get("stt_model", "saaras:v3"),
        "stt_language":             config.get("stt_language", "unknown"),
        "lang_preset":              config.get("lang_preset", "multilingual"),
        "max_turns":                config.get("max_turns", 14),
        "silence_timeout_seconds":  config.get("silence_timeout_seconds", 45),
        "vertical":                 vert,
        "language_config":          language_config,
        **config,
    }


# ── Token counter (#11) ───────────────────────────────────────────────────────
def count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4o")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


_SENTENCE_SPLIT_RE = re.compile(r'(?<=[।.!?])\s+')
_CONFUSION_RE = re.compile(
    r"\b("
    r"hello+|helo+|hallo+|not\s+clear|is\s+not\s+clear|"
    r"speak\s+properly|speak\s+clearly|i\s+don'?t\s+understand|"
    r"i\s+dont\s+understand|can'?t\s+understand|cannot\s+understand|"
    r"puriyala|puri[yia]la|theriyala|clear\s+ah\s+illa|seri[a]?ga\s+pesu"
    r")\b",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(r"[?？]\s*$|\b(sollunga|tell me|can you|will you|shall we|pannalama)\b", re.IGNORECASE)
_TTS_SPEAKABLE_RE = re.compile(r"[A-Za-z0-9\u0900-\u097f\u0b80-\u0bff]")


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]


def _normalize_voice_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\u0b80-\u0bff]+", " ", str(text or "").lower()).strip()


def _looks_placeholder_secret(value: str) -> bool:
    low = str(value or "").strip().lower()
    if not low:
        return True
    return low.startswith(("your_", "sk-your", "replace_", "changeme", "todo"))


def _is_confused_user(text: str) -> bool:
    low = _normalize_voice_text(text)
    if not low:
        return False
    if _CONFUSION_RE.search(str(text or "")):
        return True
    return low in {"hello", "helo", "hallo", "hello hello", "hello sir", "hello madam"}


def _is_question_like(text: str) -> bool:
    return bool(_QUESTION_RE.search(str(text or "").strip()))


def _limit_voice_words(text: str, max_words: int = 12) -> str:
    words = str(text or "").strip().split()
    if len(words) <= max_words:
        return str(text or "").strip()
    trimmed = " ".join(words[:max_words]).strip()
    return trimmed.rstrip(".,!?।") + "."


def _sanitize_tts_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"([.!?।]){2,}", r"\1", cleaned)
    cleaned = re.sub(r"\.\s*\?", "?", cleaned)
    cleaned = cleaned.strip(" \t\r\n,;:")
    if not _TTS_SPEAKABLE_RE.search(cleaned):
        return ""
    return cleaned


def _voice_tts_chunks(text: str, max_words: int = 12) -> tuple[list[str], int]:
    raw = str(text or "").strip()
    sentences = _split_sentences(raw)
    first_sentence = next((s for s in sentences if "?" in s), sentences[0] if sentences else raw)
    chunk = _sanitize_tts_text(_limit_voice_words(first_sentence, max_words=max_words))
    return ([chunk] if chunk else []), len(sentences)


# ── IST time context ──────────────────────────────────────────────────────────
def get_ist_time_context() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    today_str = now.strftime("%A, %B %d, %Y")
    time_str  = now.strftime("%I:%M %p")
    days_lines = []
    for i in range(7):
        day   = now + timedelta(days=i)
        label = "Today" if i == 0 else ("Tomorrow" if i == 1 else day.strftime("%A"))
        days_lines.append(f"  {label}: {day.strftime('%A %d %B %Y')} → ISO {day.strftime('%Y-%m-%d')}")
    days_block = "\n".join(days_lines)
    return (
        f"\n\n[SYSTEM CONTEXT]\n"
        f"Current date & time: {today_str} at {time_str} IST\n"
        f"Resolve ALL relative day references using this table:\n{days_block}\n"
        f"Always use ISO dates when calling save_booking_intent. Appointments in IST (+05:30).]"
    )


def get_compact_ist_time_context() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return (
        "\n\n[SYSTEM CONTEXT]\n"
        f"Current IST: {now.strftime('%A, %B %d, %Y %I:%M %p')}. "
        f"Today ISO {now.strftime('%Y-%m-%d')}; tomorrow ISO {(now + timedelta(days=1)).strftime('%Y-%m-%d')}."
    )


# ── Language presets ──────────────────────────────────────────────────────────
LANGUAGE_PRESETS = {
    "hinglish":    {"label": "Hinglish (Hindi+English)", "tts_language": "hi-IN", "tts_voice": "kavya",  "instruction": "Speak in natural Hinglish — mix Hindi and English like educated Indians do. Default to Hindi but use English words when more natural."},
    "hindi":       {"label": "Hindi",                   "tts_language": "hi-IN", "tts_voice": "ritu",   "instruction": "Speak only in pure Hindi. Avoid English words wherever a Hindi equivalent exists."},
    "english":     {"label": "English (India)",         "tts_language": "en-IN", "tts_voice": "dev",    "instruction": "Speak only in Indian English with a warm, professional tone."},
    "tamil":       {"label": "Tamil",                   "tts_language": "ta-IN", "tts_voice": "priya",  "instruction": "Speak only in Tamil. Use standard spoken Tamil for a professional context."},
    "tamil_tanglish":{"label": "Tamil / Tanglish",       "tts_language": "ta-IN", "tts_voice": "priya",  "instruction": "Speak in natural Tanglish: Tamil sentence flow with common English business words where useful."},
    "telugu":      {"label": "Telugu",                  "tts_language": "te-IN", "tts_voice": "kavya",  "instruction": "Speak only in Telugu. Use clear, polite spoken Telugu."},
    "gujarati":    {"label": "Gujarati",                "tts_language": "gu-IN", "tts_voice": "rohan",  "instruction": "Speak only in Gujarati. Use polite, professional Gujarati."},
    "bengali":     {"label": "Bengali",                 "tts_language": "bn-IN", "tts_voice": "neha",   "instruction": "Speak only in Bengali (Bangla). Use standard, polite spoken Bengali."},
    "marathi":     {"label": "Marathi",                 "tts_language": "mr-IN", "tts_voice": "shubh",  "instruction": "Speak only in Marathi. Use polite, standard spoken Marathi."},
    "kannada":     {"label": "Kannada",                 "tts_language": "kn-IN", "tts_voice": "rahul",  "instruction": "Speak only in Kannada. Use clear, professional spoken Kannada."},
    "malayalam":   {"label": "Malayalam",               "tts_language": "ml-IN", "tts_voice": "ritu",   "instruction": "Speak only in Malayalam. Use polite, professional spoken Malayalam."},
    "multilingual":{"label": "Multilingual (Auto)",     "tts_language": "hi-IN", "tts_voice": "kavya",  "instruction": "Detect the caller's language from their first message and reply in that SAME language for the entire call. Supported: Hindi, Hinglish, English, Tamil, Telugu, Gujarati, Bengali, Marathi, Kannada, Malayalam. Switch if caller switches."},
}

def get_language_instruction(lang_preset: str) -> str:
    preset = LANGUAGE_PRESETS.get(lang_preset, LANGUAGE_PRESETS["multilingual"])
    return f"\n\n[LANGUAGE DIRECTIVE]\n{preset['instruction']}"


# ── External imports ──────────────────────────────────────────────────────────
from backend.calendar_tools import get_available_slots, create_booking, cancel_booking
from backend.notify import (
    notify_booking_confirmed,
    notify_booking_cancelled,
    notify_call_no_booking,
    notify_agent_error,
)
from backend.barge_in import BargeInController
from backend.fast_voice_router import FastVoiceRouter
from backend.latency_logger import VoiceLatencyLogger
from backend.llm_streamer import build_voice_llm
from backend.sarvam_streaming_stt import build_sarvam_stt
from backend.sarvam_streaming_tts import build_sarvam_tts


def _function_tool_id(tool_obj: Any) -> str:
    name = getattr(tool_obj, "name", None)
    if isinstance(name, str) and name:
        return name
    fn = getattr(tool_obj, "fn", None) or getattr(tool_obj, "callable", None)
    if fn is not None and callable(fn):
        return getattr(fn, "__name__", "") or ""
    return ""


def _filter_function_tools_for_config(agent_tools: Any, live_config: dict) -> list[Any]:
    all_tools = llm.find_function_tools(agent_tools)
    raw = live_config.get("tools_config")
    if not isinstance(raw, list) or len(raw) == 0:
        return all_tools
    enabled_ids = {str(x.get("id", "")).strip() for x in raw if isinstance(x, dict) and x.get("enabled")}
    if not enabled_ids:
        return all_tools
    out = [t for t in all_tools if _function_tool_id(t) in enabled_ids]
    if not out:
        logger.warning("[TOOLS_CONFIG] No tools matched enabled ids — using full tool set")
        return all_tools
    return out


def _remove_tool_by_id(tools: list[Any], tool_id: str) -> list[Any]:
    return [t for t in tools if _function_tool_id(t) != tool_id]


def _transfer_destination_config_ok(live_config: dict) -> bool:
    cc = live_config.get("call_config") if isinstance(live_config.get("call_config"), dict) else {}
    if (cc.get("transfer_destination_e164") or "").strip():
        return True
    if os.getenv("DEFAULT_TRANSFER_NUMBER", "").strip():
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# TOOL CONTEXT — All AI-callable functions
# ══════════════════════════════════════════════════════════════════════════════

class AgentTools(llm.ToolContext):

    def __init__(self, caller_phone: str, caller_name: str = "", live_config: dict | None = None):
        super().__init__(tools=[])
        self.caller_phone        = caller_phone
        self.caller_name         = caller_name
        self._live_config        = live_config or {}
        self.booking_intent: dict | None = None
        self.sip_domain          = os.getenv("VOBIZ_SIP_DOMAIN")
        self.ctx_api             = None
        self.room_name           = None
        self._sip_identity       = None
        # none | ok | fail — set by transfer_call SIP API path (for CRM summary xfer=)
        self.sip_transfer_outcome = "none"

    # ── Tool: Transfer to Human ───────────────────────────────────────────
    @llm.function_tool(description="Transfer this call to a human agent. Use if: caller asks for human, is angry, or query is outside scope.")
    async def transfer_call(
        self,
        reason: Annotated[str, "Short reason for transferring to a human"] = "human_requested",
    ) -> str:
        logger.info("[TOOL] transfer_call triggered reason=%s", reason)
        cc = self._live_config.get("call_config") if isinstance(self._live_config.get("call_config"), dict) else {}
        destination = (cc.get("transfer_destination_e164") or "").strip() or os.getenv("DEFAULT_TRANSFER_NUMBER", "")
        if destination and self.sip_domain and "@" not in destination:
            clean_dest  = destination.replace("tel:", "").replace("sip:", "")
            destination = f"sip:{clean_dest}@{self.sip_domain}"
        if destination and not destination.startswith("sip:"):
            destination = f"sip:{destination}"
        try:
            if self.ctx_api and self.room_name and destination and self._sip_identity:
                await self.ctx_api.sip.transfer_sip_participant(
                    api.TransferSIPParticipantRequest(
                        room_name=self.room_name,
                        participant_identity=self._sip_identity,
                        transfer_to=destination,
                        play_dialtone=False,
                    )
                )
                self.sip_transfer_outcome = "ok"
                logger.info("[SIP] transfer_sip_participant ok reason=%s", reason)
                return "Transfer initiated successfully."
            self.sip_transfer_outcome = "fail"
            logger.warning("[SIP] transfer_call skipped missing_ctx_api_or_room destination_set=%s", bool(destination))
            return "Unable to transfer right now."
        except Exception as e:
            self.sip_transfer_outcome = "fail"
            logger.error("[SIP] transfer_sip_participant failed reason=%s err=%s", reason, e)
            return "Unable to transfer right now."

    # ── Tool: End Call ────────────────────────────────────────────────────
    @llm.function_tool(description="End the call. Use ONLY when caller says bye/goodbye or after booking is fully confirmed.")
    async def end_call(
        self,
        reason: Annotated[str, "Short reason for ending the call"] = "call_complete",
    ) -> str:
        logger.info("[TOOL] end_call triggered — hanging up. reason=%s", reason)
        try:
            if self.ctx_api and self.room_name and self._sip_identity:
                await self.ctx_api.sip.transfer_sip_participant(
                    api.TransferSIPParticipantRequest(
                        room_name=self.room_name,
                        participant_identity=self._sip_identity,
                        transfer_to="tel:+00000000",
                        play_dialtone=False,
                    )
                )
        except Exception as e:
            logger.warning("[END-CALL] SIP hangup failed: %s", e)
        return "Call ended."

    # ── Tool: Save Booking Intent ─────────────────────────────────────────
    @llm.function_tool(description="Save booking intent after caller confirms appointment. Call this ONCE after you have name, phone, email, date, time.")
    async def save_booking_intent(
        self,
        start_time:  Annotated[str,  "ISO 8601 datetime e.g. '2026-03-01T10:00:00+05:30'"],
        caller_name: Annotated[str,  "Full name of the caller"],
        caller_phone:Annotated[str,  "Phone number of the caller"],
        notes:       Annotated[str,  "Any notes, email, or special requests"] = "",
    ) -> str:
        logger.info(f"[TOOL] save_booking_intent: {caller_name} at {start_time}")
        try:
            self.booking_intent = {
                "start_time":   start_time,
                "caller_name":  caller_name,
                "caller_phone": caller_phone,
                "notes":        notes,
            }
            self.caller_name = caller_name
            return f"Booking intent saved for {caller_name} at {start_time}. I'll confirm after the call."
        except Exception as e:
            logger.error(f"[TOOL] save_booking_intent failed: {e}")
            return "I had trouble saving the booking. Please try again."

    # ── Tool: Check Availability (#13) ────────────────────────────────────
    @llm.function_tool(description="Check available appointment slots for a given date. Call this when user asks about availability.")
    async def check_availability(
        self,
        date: Annotated[str, "Date to check in YYYY-MM-DD format e.g. '2026-03-01'"],
    ) -> str:
        logger.info(f"[TOOL] check_availability: date={date}")
        try:
            slots = await get_available_slots(date)
            if not slots:
                return f"No available slots on {date}. Would you like to check another date?"
            slot_strings = [s.get("start_time", str(s))[-8:][:5] for s in slots[:6]]
            return f"Available slots on {date}: {', '.join(slot_strings)} IST."
        except Exception as e:
            logger.error(f"[TOOL] check_availability failed: {e}")
            return "I'm having trouble checking the calendar right now."

    # ── Tool: Business Hours (#31) ────────────────────────────────────────
    @llm.function_tool(description="Check if the business is currently open and what the operating hours are.")
    async def get_business_hours(
        self,
        request_context: Annotated[str, "Short context for why hours are needed"] = "caller_asked",
    ) -> str:
        logger.info("[TOOL] get_business_hours context=%s", request_context)
        ist  = pytz.timezone("Asia/Kolkata")
        now  = datetime.now(ist)
        hours = {
            0: ("Monday",    "10:00", "19:00"),
            1: ("Tuesday",   "10:00", "19:00"),
            2: ("Wednesday", "10:00", "19:00"),
            3: ("Thursday",  "10:00", "19:00"),
            4: ("Friday",    "10:00", "19:00"),
            5: ("Saturday",  "10:00", "17:00"),
            6: ("Sunday",    None,    None),
        }
        day_name, open_t, close_t = hours[now.weekday()]
        current_time = now.strftime("%H:%M")
        if open_t is None:
            return "We are closed on Sundays. Next opening: Monday 10:00 AM IST."
        if open_t <= current_time <= close_t:
            return f"We are OPEN. Today ({day_name}): {open_t}–{close_t} IST."
        return f"We are CLOSED. Today ({day_name}): {open_t}–{close_t} IST."


# ══════════════════════════════════════════════════════════════════════════════
# AGENT CLASS
# ══════════════════════════════════════════════════════════════════════════════

class OutboundAssistant(Agent):

    def __init__(
        self,
        agent_tools: AgentTools,
        first_line: str = "",
        live_config: dict | None = None,
        function_tools: list[Any] | None = None,
        orchestrator: Any | None = None,
        tool_executor: Any | None = None,
        latency_tracker: Any | None = None,
    ):
        tools_list = function_tools if function_tools is not None else llm.find_function_tools(agent_tools)
        self._first_line = first_line
        self._live_config = live_config or {}
        self._agent_tools = agent_tools
        self._orchestrator = orchestrator
        self._tool_executor = tool_executor
        self._latency_tracker = latency_tracker
        self._last_assistant_norm = ""
        self._last_question_norm = ""
        self._recent_question_norms: list[str] = []
        self._confusion_count = 0
        live_config_loaded = self._live_config
        self._response_timeout_s = float(live_config_loaded.get("response_timeout_seconds") or 1.2)
        self._fast_pipeline_enabled = (
            str(live_config_loaded.get("vertical") or "").strip().lower() == "tamil_real_estate"
            or str(live_config_loaded.get("response_latency_mode") or "").strip().lower() == "fast"
        )
        self._fast_router = FastVoiceRouter()
        self._active_response_task: asyncio.Task[Any] | None = None
        self._barge_in = BargeInController()
        self._voice_latency = VoiceLatencyLogger(call_id=str(live_config_loaded.get("call_id") or ""))

        base_instructions = live_config_loaded.get("agent_instructions", "")
        latency_mode = str(live_config_loaded.get("response_latency_mode") or "normal").lower()
        ist_context = get_compact_ist_time_context() if latency_mode == "fast" else get_ist_time_context()
        lang_preset = live_config_loaded.get("lang_preset", "multilingual")
        lang_instruction = get_language_instruction(lang_preset)
        cost_guardrail = (
            "\n\n[VOICE STYLE]\n"
            "Reply in one short sentence only. "
            "Use at most 9 Tamil/Tanglish words in fast mode; otherwise at most 12. "
            "Use simple Tanglish, not formal Tamil. "
            "Ask one question at a time. Do not repeat the same question twice. "
            "If the caller says hello/not clear/speak properly/I don't understand/puriyala, apologize briefly, switch simpler English/Tanglish, and continue."
        )
        final_instructions = base_instructions + ist_context + lang_instruction + cost_guardrail

        # Token counter (#11)
        token_count = count_tokens(final_instructions)
        logger.info(f"[PROMPT] System prompt: {token_count} tokens")
        if token_count > 600:
            logger.warning(f"[PROMPT] Prompt exceeds 600 tokens — consider trimming for latency")

        super().__init__(instructions=final_instructions, tools=tools_list)

    def _fallback_recovery_line(self, user_text: str = "") -> str:
        self._confusion_count += 1
        if self._confusion_count <= 1:
            return "Sorry sir, simple-ah sollren. Site visit interest irukka?"
        if self._confusion_count == 2:
            return "Sorry, clear-ah pesaren. Which area prefer panreenga?"
        return "No problem sir. English-la sollren, property options venuma?"

    def _dedupe_reply(self, line: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(line or "")).strip()
        norm = _normalize_voice_text(cleaned)
        if not norm:
            return ""
        duplicate_response = norm == self._last_assistant_norm
        duplicate_question = _is_question_like(cleaned) and norm in self._recent_question_norms
        if duplicate_response or duplicate_question:
            logger.info("[DUPLICATE_RESPONSE_GUARD] duplicate_response=%s duplicate_question=%s text=%s", duplicate_response, duplicate_question, cleaned[:120])
            cleaned = "Seri sir, vera simple-ah: area preference irukka?"
            norm = _normalize_voice_text(cleaned)
        self._last_assistant_norm = norm
        if _is_question_like(cleaned):
            self._last_question_norm = norm
            self._recent_question_norms = (self._recent_question_norms + [norm])[-5:]
        return cleaned

    async def _say_guarded(
        self,
        line: str,
        *,
        allow_interruptions: bool = True,
        wait: bool = False,
        lifecycle: str = "",
    ) -> None:
        text = _sanitize_tts_text(self._dedupe_reply(line))
        if not text:
            logger.info("[TTS_CHUNK_SKIPPED] reason=no_speakable_text")
            return
        speak_start = time.perf_counter()
        handle = self.session.say(text, allow_interruptions=allow_interruptions)
        publish_ms = _ms_since(speak_start)
        if lifecycle == "greeting":
            logger.info("[FIRST_AUDIO_SENT] stage=greeting publish_ms=%s chars=%s", publish_ms, len(text))
        logger.info("[VOICE_LATENCY] stage=%s livekit_publish_ms=%s chars=%s", self._fast_router.state.stage, publish_ms, len(text))
        self._voice_latency.log(stage=self._fast_router.state.stage, livekit_publish_ms=publish_ms)
        self._fast_router.mark_agent_reply(text)
        if wait:
            await handle.wait_for_playout()

    def handle_partial_transcript(self, text: str) -> None:
        if not self._fast_pipeline_enabled:
            return
        result = self._fast_router.note_partial(text)
        if result.handled and agent_is_speaking:
            self._barge_in.note_user_speech(text)
            self._barge_in.interrupt(self.session, self._active_response_task, reason=f"early_intent:{result.intent}")

    async def on_enter(self):
        greeting = self._live_config.get("first_line") or self._first_line or FALLBACK_FIRST_LINE
        try:
            logger.info(
                "[GREETING_TRIGGERED] agent_id=%s first_line=%s",
                str(self._live_config.get("agent_id") or "").strip() or "-",
                str(greeting or "").strip(),
            )
            greeting_chunks, _raw_sentence_count = _voice_tts_chunks(greeting, max_words=12)
            greeting = greeting_chunks[0] if greeting_chunks else greeting
            if not str(greeting or "").strip():
                greeting = FALLBACK_FIRST_LINE
            logger.info("[GREETING_TTS_STARTED] chars=%s direct_tts=true", len(greeting or ""))
            logger.info("[WELCOME_TTS_START] chars=%s direct_tts=true", len(greeting or ""))
            await self._say_guarded(greeting, allow_interruptions=True, wait=True, lifecycle="greeting")
        except Exception as e:
            logger.exception("[GREETING_FAILED] exception=%s first_line=%s", e, str(greeting or "").strip())
            raise

    def tts_node(self, text: AsyncIterable[str], model_settings: Any) -> Any:
        async def _short_chunk_stream():
            tts_start = time.perf_counter()
            chunk_count = 0
            first_logged = False
            buffer = ""
            raw_total_len = 0

            def _ready_to_speak(value: str) -> bool:
                stripped = value.strip()
                if not stripped:
                    return False
                if re.search(r"[।.!?]\s*$", stripped):
                    return True
                return len(stripped.split()) >= 7

            async for raw_chunk in text:
                raw_text = str(raw_chunk or "")
                if not raw_text:
                    continue
                raw_len = len(raw_text)
                raw_total_len += raw_len
                logger.info("[TTS_TEXT_LENGTH] chars=%s", raw_len)
                buffer = re.sub(r"\s+", " ", f"{buffer}{raw_text}").strip()
                if not _ready_to_speak(buffer):
                    continue

                chunks, raw_sentence_count = _voice_tts_chunks(buffer, max_words=9)
                if raw_sentence_count > 1:
                    logger.info("[TTS_CHUNK_COUNT] raw_sentences=%s enforced_chunks=%s", raw_sentence_count, len(chunks))
                for chunk in chunks[:1]:
                    chunk = _sanitize_tts_text(chunk)
                    if not chunk:
                        logger.info("[TTS_CHUNK_SKIPPED] reason=no_speakable_text")
                        continue
                    chunk_count += 1
                    if not first_logged:
                        first_logged = True
                        logger.info("[TTS_FIRST_CHUNK_MS] ms=%s chars=%s", _ms_since(tts_start), len(chunk))
                    logger.info("[TTS_TEXT_LENGTH] chunk=%s chars=%s words=%s", chunk_count, len(chunk), len(chunk.split()))
                    if len(chunk) > 120:
                        logger.warning("[TTS_TOO_LONG] chunk=%s chars=%s", chunk_count, len(chunk))
                    yield chunk
                buffer = ""

            if buffer.strip():
                chunks, raw_sentence_count = _voice_tts_chunks(buffer, max_words=9)
                if raw_sentence_count > 1:
                    logger.info("[TTS_CHUNK_COUNT] raw_sentences=%s enforced_chunks=%s", raw_sentence_count, len(chunks))
                for chunk in chunks[:1]:
                    chunk = _sanitize_tts_text(chunk)
                    if not chunk:
                        logger.info("[TTS_CHUNK_SKIPPED] reason=no_speakable_text")
                        continue
                    chunk_count += 1
                    if not first_logged:
                        first_logged = True
                        logger.info("[TTS_FIRST_CHUNK_MS] ms=%s chars=%s", _ms_since(tts_start), len(chunk))
                    logger.info("[TTS_TEXT_LENGTH] chunk=%s chars=%s words=%s", chunk_count, len(chunk), len(chunk.split()))
                    if len(chunk) > 120:
                        logger.warning("[TTS_TOO_LONG] chunk=%s chars=%s", chunk_count, len(chunk))
                    yield chunk
            if raw_total_len > 120:
                logger.warning("[TTS_TOO_LONG] chars=%s", raw_total_len)
            logger.info("[TTS_CHUNK_COUNT] chunks=%s", chunk_count)

        return Agent.default.tts_node(self, _short_chunk_stream(), model_settings)

    async def _orch_run_tool(self, action: Any) -> None:
        """Run calendar tools on AgentTools or placeholder tools from ToolExecutor."""
        from backend.orchestration.schemas import AgentAction

        assert isinstance(action, AgentAction)
        name = (action.tool_name or "").strip()
        pl = action.payload or {}
        sess = self.session
        at = self._agent_tools
        if name == "check_availability":
            msg = await at.check_availability(pl.get("date") or "")
        elif name == "get_business_hours":
            msg = await at.get_business_hours()
        elif name == "save_booking_intent":
            h = sess.say(
                "Sure sir, preferred date and time sollunga.",
                allow_interruptions=True,
            )
            await h.wait_for_playout()
            return
        else:
            execr = self._tool_executor
            if execr is None:
                msg = "This action isn't available yet."
            else:
                res = await execr.execute(name, pl)
                msg = "Done." if res.get("ok") else "Sorry, that didn't work."
        text = (msg if isinstance(msg, str) else str(msg))[:1200]
        h = sess.say(_limit_voice_words(text, max_words=10), allow_interruptions=True)
        await h.wait_for_playout()

    async def on_user_turn_completed(
        self,
        turn_ctx: llm.ChatContext,
        new_message: llm.ChatMessage,
    ) -> None:
        orch = self._orchestrator
        if orch is None:
            return
        text = (new_message.text_content or "").strip()
        if not text:
            return
        if self._fast_pipeline_enabled:
            self._fast_router.start_turn()
            fast_action = self._fast_router.route_final(text)
            if fast_action.handled and fast_action.message:
                logger.info("[FAST_PIPELINE] llm_skipped intent=%s stage=%s", fast_action.intent, fast_action.stage)
                self._voice_latency.log(
                    stage=self._fast_router.state.stage,
                    stt_partial_ms=self._fast_router.last_partial_ms,
                    router_ms=self._fast_router.last_router_ms,
                )
                await self._say_guarded(fast_action.message, allow_interruptions=True)
                raise StopResponse()
            if fast_action.needs_llm:
                logger.info("[FAST_PIPELINE] llm_path=streaming_agent reason=%s", fast_action.intent or "complex")
                return
        if _is_confused_user(text):
            logger.info("[CONFUSION_DETECTED] text=%s", text[:120])
            await self._say_guarded(self._fallback_recovery_line(text), allow_interruptions=True)
            raise StopResponse()
        orch_start = time.perf_counter()
        try:
            action = await asyncio.wait_for(
                orch.handle_user_message(text),
                timeout=max(0.6, self._response_timeout_s),
            )
        except asyncio.TimeoutError:
            logger.warning("[RESPONSE_TIMEOUT] orchestrator exceeded %.2fs text=%s", self._response_timeout_s, text[:120])
            await self._say_guarded("One sec sir, simple-ah ketkaren. Area preference irukka?", allow_interruptions=True)
            raise StopResponse()
        except Exception as e:
            logger.exception("[ORCHESTRATOR] failed; using recovery prompt: %s", e)
            await self._say_guarded("Sorry sir, repeat panren. Which area looking?", allow_interruptions=True)
            raise StopResponse()
        if self._latency_tracker is not None:
            self._latency_tracker.note_orchestrator_llm(_ms_since(orch_start))
        if action.type == "speak":
            line = (action.orchestration_message or action.next_question or "").strip()
            if line:
                await self._say_guarded(line, allow_interruptions=True)
            raise StopResponse()
        if action.type == "noop":
            raise StopResponse()

        sess = self.session
        at = self._agent_tools

        if action.type == "transfer":
            await at.transfer_call(reason=action.reason or "orchestrator_brain")
            raise StopResponse()

        if action.type == "end_call":
            await at.end_call(reason=action.reason or "orchestrator_brain")
            raise StopResponse()

        if action.type == "schedule_callback":
            line = (action.orchestration_message or action.next_question or "").strip()
            if line:
                await self._say_guarded(line, allow_interruptions=True, wait=True)
            if self._tool_executor is not None:
                await self._tool_executor.execute(
                    "schedule_callback",
                    {"snippet": text[:800], **(action.payload or {})},
                )
            raise StopResponse()

        if action.type == "send_whatsapp":
            line = (action.orchestration_message or action.next_question or "").strip()
            if line:
                await self._say_guarded(line, allow_interruptions=True, wait=True)
            if self._tool_executor is not None:
                await self._tool_executor.execute(
                    "send_whatsapp",
                    {"snippet": text[:800], **(action.payload or {})},
                )
            raise StopResponse()

        if action.type == "tool_call":
            await self._orch_run_tool(action)
            raise StopResponse()

        if action.type == "save_data":
            if self._tool_executor is not None:
                await self._tool_executor.execute(
                    "save_lead",
                    {"snippet": text[:800], **(action.payload or {})},
                )
            ack = (action.orchestration_message or "").strip() or "Thanks — I've noted that."
            try:
                await self._say_guarded(ack, allow_interruptions=True, wait=True)
            except Exception as e:
                logger.warning("[ORCHESTRATOR] save_data say failed: %s", e)
            raise StopResponse()

        raise StopResponse()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

agent_is_speaking = False


def _ms_since(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


class CallLatencyTracker:
    """Collect per-turn voice latency from LiveKit metrics without blocking audio."""

    def __init__(self, room_name: str):
        self.room_name = room_name
        self._voice_latency = VoiceLatencyLogger(call_id=room_name)
        self.turn_index = 0
        self.current_turn: dict[str, Any] | None = None
        self._last_user_speaking_end_wall: float | None = None

    def mark_user_speaking_end(self, created_at: float | None = None) -> None:
        self._last_user_speaking_end_wall = float(created_at or time.time())

    def mark_final_transcript(self, transcript: str, created_at: float | None = None) -> None:
        self.turn_index += 1
        final_at = float(created_at or time.time())
        self.current_turn = {
            "turn": self.turn_index,
            "room": self.room_name,
            "final_transcript_wall": final_at,
            "final_transcript_mono": time.perf_counter(),
            "stt_ms": None,
            "llm_first_token_ms": None,
            "llm_total_ms": None,
            "tts_first_audio_ms": None,
            "tts_total_ms": None,
            "db_save_ms": None,
        }
        if self._last_user_speaking_end_wall:
            stt_ms = max(0, int((final_at - self._last_user_speaking_end_wall) * 1000))
            self.current_turn["stt_ms"] = stt_ms
            logger.info("[STT_LATENCY_MS] room=%s turn=%s ms=%s source=user_state_to_final_transcript", self.room_name, self.turn_index, stt_ms)
            self._voice_latency.log(stage="stt_final", stt_final_ms=stt_ms)
        logger.info("[TURN_START] room=%s turn=%s transcript_chars=%s", self.room_name, self.turn_index, len(transcript or ""))

    def note_db_save(self, ms: int, *, source: str = "transcript") -> None:
        turn = self.current_turn
        turn_id = turn.get("turn") if turn else ""
        if turn is not None:
            turn["db_save_ms"] = ms
        logger.info("[DB_SAVE_MS] room=%s turn=%s ms=%s source=%s", self.room_name, turn_id, ms, source)

    def note_orchestrator_llm(self, ms: int) -> None:
        turn = self.current_turn
        turn_id = turn.get("turn") if turn else ""
        if turn is not None:
            turn["llm_first_token_ms"] = ms
            turn["llm_total_ms"] = ms
        logger.info("[LLM_FIRST_TOKEN_MS] room=%s turn=%s ms=%s source=orchestrator_non_streaming", self.room_name, turn_id, ms)
        self._voice_latency.log(stage="llm", llm_first_token_ms=ms)
        logger.info("[LLM_TOTAL_MS] room=%s turn=%s ms=%s source=orchestrator", self.room_name, turn_id, ms)

    def note_agent_state(self, old_state: str, new_state: str, created_at: float | None = None) -> None:
        global agent_is_speaking
        if new_state == "speaking":
            agent_is_speaking = True
            self._log_total_response(created_at=float(created_at or time.time()), source="agent_state_speaking")
        elif old_state == "speaking" and new_state != "speaking":
            agent_is_speaking = False

    def note_metric(self, metric: Any) -> None:
        mtype = getattr(metric, "type", "")
        turn = self.current_turn
        turn_id = turn.get("turn") if turn else ""
        if mtype == "eou_metrics":
            stt_ms = int(float(getattr(metric, "transcription_delay", 0.0) or 0.0) * 1000)
            if turn is not None:
                turn["stt_ms"] = stt_ms
            logger.info(
                "[STT_LATENCY_MS] room=%s turn=%s ms=%s eou_delay_ms=%s source=eou_metrics",
                self.room_name,
                turn_id,
                stt_ms,
                int(float(getattr(metric, "end_of_utterance_delay", 0.0) or 0.0) * 1000),
            )
            return
        if mtype == "stt_metrics":
            stt_ms = int(float(getattr(metric, "duration", 0.0) or 0.0) * 1000)
            logger.info(
                "[STT_LATENCY_MS] room=%s turn=%s ms=%s audio_ms=%s streamed=%s source=stt_metrics",
                self.room_name,
                turn_id,
                stt_ms,
                int(float(getattr(metric, "audio_duration", 0.0) or 0.0) * 1000),
                bool(getattr(metric, "streamed", False)),
            )
            return
        if mtype == "llm_metrics":
            first_ms = int(float(getattr(metric, "ttft", 0.0) or 0.0) * 1000)
            total_ms = int(float(getattr(metric, "duration", 0.0) or 0.0) * 1000)
            if turn is not None:
                turn["llm_first_token_ms"] = first_ms
                turn["llm_total_ms"] = total_ms
            logger.info("[LLM_FIRST_TOKEN_MS] room=%s turn=%s ms=%s speech_id=%s", self.room_name, turn_id, first_ms, getattr(metric, "speech_id", None) or "")
            self._voice_latency.log(stage="llm", llm_first_token_ms=first_ms)
            logger.info("[LLM_TOTAL_MS] room=%s turn=%s ms=%s tokens=%s", self.room_name, turn_id, total_ms, getattr(metric, "total_tokens", 0))
            return
        if mtype == "tts_metrics":
            first_ms = int(float(getattr(metric, "ttfb", 0.0) or 0.0) * 1000)
            total_ms = int(float(getattr(metric, "duration", 0.0) or 0.0) * 1000)
            if turn is not None:
                turn["tts_first_audio_ms"] = first_ms
                turn["tts_total_ms"] = total_ms
            logger.info("[TTS_FIRST_AUDIO_MS] room=%s turn=%s ms=%s streamed=%s", self.room_name, turn_id, first_ms, bool(getattr(metric, "streamed", False)))
            self._voice_latency.log(stage="tts", tts_first_audio_ms=first_ms)
            logger.info("[TTS_TOTAL_MS] room=%s turn=%s ms=%s audio_ms=%s chars=%s", self.room_name, turn_id, total_ms, int(float(getattr(metric, "audio_duration", 0.0) or 0.0) * 1000), getattr(metric, "characters_count", 0))
            metric_start = float(getattr(metric, "timestamp", 0.0) or 0.0)
            first_audio_at = metric_start + float(getattr(metric, "ttfb", 0.0) or 0.0) if metric_start else None
            self._log_total_response(created_at=first_audio_at, source="tts_first_audio")

    def _log_total_response(self, *, created_at: float | None, source: str) -> None:
        turn = self.current_turn
        if not turn:
            return
        start_wall = float(turn.get("final_transcript_wall") or 0.0)
        if created_at and start_wall:
            total_ms = max(0, int((created_at - start_wall) * 1000))
        else:
            total_ms = _ms_since(float(turn.get("final_transcript_mono") or time.perf_counter()))
        components = {
            "stt": turn.get("stt_ms") or 0,
            "llm_first_token": turn.get("llm_first_token_ms") or 0,
            "llm_total": turn.get("llm_total_ms") or 0,
            "tts_first_audio": turn.get("tts_first_audio_ms") or 0,
            "tts_total": turn.get("tts_total_ms") or 0,
            "db_save": turn.get("db_save_ms") or 0,
        }
        slowest = max(components.items(), key=lambda kv: kv[1])[0] if components else "unknown"
        logger.info(
            "[TOTAL_RESPONSE_MS] room=%s turn=%s ms=%s source=%s slowest=%s breakdown=%s",
            self.room_name,
            turn.get("turn"),
            total_ms,
            source,
            slowest,
            json.dumps(components, ensure_ascii=True, separators=(",", ":")),
        )
        logger.info(
            "[LATENCY_ANALYSIS] room=%s turn=%s total_ms=%s slowest_component=%s threshold_ms=1500",
            self.room_name,
            turn.get("turn"),
            total_ms,
            slowest,
        )
        self._voice_latency.log(
            stage=source,
            stt_final_ms=int(components.get("stt") or 0),
            llm_first_token_ms=int(components.get("llm_first_token") or 0),
            tts_first_audio_ms=int(components.get("tts_first_audio") or 0),
            total_response_ms=total_ms,
        )
        if total_ms > 1500:
            logger.warning(
                "[LATENCY_ANALYSIS] room=%s turn=%s over_threshold_ms=%s slowest_component=%s breakdown=%s",
                self.room_name,
                turn.get("turn"),
                total_ms,
                slowest,
                json.dumps(components, ensure_ascii=True, separators=(",", ":")),
            )

async def entrypoint(ctx: JobContext):
    global agent_is_speaking, _FIRST_LIVEKIT_JOB_SEEN

    # ── Connect ───────────────────────────────────────────────────────────
    await ctx.connect()
    _job_id = getattr(ctx.job, "id", "") or ""
    _process_uptime_ms = int((time.perf_counter() - _PROCESS_STARTED_MONO) * 1000)
    _is_cold_start = not _FIRST_LIVEKIT_JOB_SEEN
    _FIRST_LIVEKIT_JOB_SEEN = True
    logger.info(
        "[RAILWAY_COLD_START] room=%s job_id=%s cold_start=%s process_uptime_ms=%s",
        ctx.room.name,
        _job_id,
        _is_cold_start,
        _process_uptime_ms,
    )
    logger.info("[LIVEKIT] room_connected name=%s job_id=%s", ctx.room.name, _job_id)
    logger.info(f"[ROOM] Connected: {ctx.room.name}")
    latency_tracker = CallLatencyTracker(ctx.room.name)

    # ── Extract caller info ───────────────────────────────────────────────
    phone_number = None
    caller_name  = ""
    caller_phone = "unknown"
    owner_user_id = None
    owner_workspace_id = None
    call_record_id = None
    metadata_agent_id = None
    metadata_agent_version_id = None
    metadata_published_agent_uuid = None
    metadata_agent_config = {}
    metadata_first_line = ""
    retry_count = 0
    max_retries = int(os.getenv("MAX_CALL_RETRIES", "3") or 3)

    # Try metadata first (outbound dispatch)
    metadata = ctx.job.metadata or ""
    skip_sip_dial = False
    logger.info("[DISPATCH] Raw metadata: %s", metadata or "<empty>")
    if metadata:
        try:
            meta = json.loads(metadata)
            if not isinstance(meta, dict):
                raise ValueError("metadata JSON is not an object")
            phone_number = meta.get("phone_number") or meta.get("to") or meta.get("phone")
            owner_user_id = meta.get("user_id")
            owner_workspace_id = meta.get("workspace_id")
            call_record_id = meta.get("db_call_id")
            metadata_agent_id = meta.get("agent_id")
            metadata_agent_version_id = meta.get("agent_version_id")
            metadata_published_agent_uuid = meta.get("published_agent_uuid") or (
                metadata_agent_id if metadata_agent_id and metadata_agent_version_id else None
            )
            if isinstance(meta.get("agent_config"), dict):
                metadata_agent_config = meta.get("agent_config") or {}
            metadata_first_line = str(meta.get("first_line") or "").strip()
            retry_count = int(meta.get("retry_count") or 0)
            max_retries = int(meta.get("max_retries") or max_retries)
            skip_sip_dial = bool(meta.get("skip_sip_dial"))
        except Exception as e:
            logger.warning("[DISPATCH] Failed to parse metadata: %s", e)

    # Extract from SIP participants
    for identity, participant in ctx.room.remote_participants.items():
        # Name from caller ID (#32)
        if participant.name and participant.name not in ("", "Caller", "Unknown"):
            caller_name = participant.name
            logger.info(f"[CALLER-ID] Name from SIP: {caller_name}")
        if not phone_number:
            attr = participant.attributes or {}
            phone_number = attr.get("sip.phoneNumber") or attr.get("phoneNumber")
        if not phone_number and "+" in identity:
            import re as _re
            m = _re.search(r"\+\d{7,15}", identity)
            if m:
                phone_number = m.group()

    caller_phone = phone_number or "unknown"

    # ── Rate limiting (#37) ───────────────────────────────────────────────
    if is_rate_limited(caller_phone):
        logger.warning(f"[RATE-LIMIT] Blocked {caller_phone} — too many calls in 1h")
        return

    # ── Load config ───────────────────────────────────────────────────────
    live_config   = get_live_config(caller_phone)
    if metadata_agent_config:
        live_config.update({k: v for k, v in metadata_agent_config.items() if v is not None})
    if metadata_first_line:
        live_config["first_line"] = metadata_first_line
        logger.info("[DISPATCH] Using first_line from dispatch metadata")
    if not str(live_config.get("first_line") or "").strip():
        live_config["first_line"] = FALLBACK_FIRST_LINE
        logger.warning("[FIRST_LINE_FALLBACK] agent_id=%s", metadata_agent_id or "-")

    engine_cfg = live_config.get("engine_config") if isinstance(live_config.get("engine_config"), dict) else {}
    vertical = str(live_config.get("vertical") or engine_cfg.get("vertical") or "").strip()
    latency_mode = str(live_config.get("response_latency_mode") or engine_cfg.get("response_latency_mode") or "").strip().lower()
    if vertical == "tamil_real_estate":
        live_config["response_latency_mode"] = "fast"
        live_config["stt_min_endpointing_delay"] = min(float(live_config.get("stt_min_endpointing_delay") or 0.18), 0.18)
        live_config["max_turns"] = 8
        live_config["silence_timeout_seconds"] = 6
        live_config["response_timeout_seconds"] = float(live_config.get("response_timeout_seconds") or 1.2)
        live_config["llm_temperature"] = float(live_config.get("llm_temperature") or 0.2)
        if str(live_config.get("llm_provider") or "").lower() == "groq" and str(live_config.get("llm_model") or "").strip() in {"", "llama-3.3-70b-versatile"}:
            live_config["llm_model"] = "llama-3.1-8b-instant"
        live_config["llm_max_tokens"] = min(int(live_config.get("llm_max_tokens") or 36), 36)
        logger.info(
            "[LATENCY_OPTIMIZED_CONFIG] vertical=tamil_real_estate saved_mode=%s mode=fast stt_endpointing=%s max_turns=8 silence_reference=6 llm_model=%s",
            latency_mode or "-",
            live_config.get("stt_min_endpointing_delay"),
            live_config.get("llm_model"),
        )

    call_cfg = live_config.get("call_config") if isinstance(live_config.get("call_config"), dict) else {}
    analytics_cfg = live_config.get("analytics_config") if isinstance(live_config.get("analytics_config"), dict) else {}
    logger.info(
        "[AGENT_CONFIG] loaded full config agent_id=%s agent_version_id=%s",
        str(live_config.get("agent_id") or metadata_agent_id or "").strip() or "-",
        str(live_config.get("agent_version_id") or metadata_agent_version_id or "").strip() or "-",
    )
    logger.info(
        "[ENGINE_CONFIG] loaded stt_min_endpointing_delay=%s max_turns=%s base_silence_s=%s response_latency_mode=%s",
        live_config.get("stt_min_endpointing_delay"),
        live_config.get("max_turns"),
        live_config.get("silence_timeout_seconds"),
        live_config.get("response_latency_mode"),
    )
    logger.info("[CALL_CONFIG] loaded %s", json.dumps(call_cfg, default=str)[:1600])
    logger.info("[TOOLS_CONFIG] loaded %s", json.dumps(live_config.get("tools_config"), default=str)[:1600])
    if analytics_cfg:
        logger.info("[ANALYTICS_CONFIG] loaded %s", json.dumps(analytics_cfg, default=str)[:800])

    delay_setting = live_config.get("stt_min_endpointing_delay", 0.05)
    llm_model     = live_config.get("llm_model", "gpt-4o-mini")
    llm_provider  = str(live_config.get("llm_provider", "openai") or "openai").lower()
    tts_voice     = live_config.get("tts_voice", "kavya")
    tts_language  = live_config.get("tts_language", "en-IN")
    tts_provider  = str(live_config.get("tts_provider", "sarvam") or "sarvam").lower()
    stt_provider  = str(live_config.get("stt_provider", "sarvam") or "sarvam").lower()
    stt_language  = live_config.get("stt_language", "unknown")  # auto-detect (#20)
    tts_model     = str(live_config.get("tts_model") or "bulbul:v3").strip() or "bulbul:v3"
    stt_model     = str(live_config.get("stt_model") or "").strip()
    live_openai_key = str(live_config.get("openai_api_key") or "").strip()
    env_openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    live_groq_key = str(live_config.get("groq_api_key") or "").strip()
    env_groq_key = str(os.getenv("GROQ_API_KEY") or "").strip()
    openai_ready = not _looks_placeholder_secret(live_openai_key or env_openai_key)
    groq_ready = not _looks_placeholder_secret(live_groq_key or env_groq_key)
    if llm_provider == "openai" and not openai_ready and groq_ready:
        llm_provider = "groq"
        live_config["llm_provider"] = "groq"
        if not str(live_config.get("llm_model") or "").strip() or str(live_config.get("llm_model")).startswith("gpt-"):
            live_config["llm_model"] = "llama-3.1-8b-instant"
            llm_model = live_config["llm_model"]
        logger.warning("[LLM_PROVIDER_FALLBACK] from=openai to=groq reason=openai_key_missing_or_placeholder")
    if stt_provider == "deepgram" and not os.getenv("DEEPGRAM_API_KEY", "").strip():
        logger.warning("[STT] Deepgram selected but DEEPGRAM_API_KEY is not set — falling back to Sarvam")
        stt_provider = "sarvam"
        stt_model = ""
    if not stt_model:
        stt_model = "nova-2-general" if stt_provider == "deepgram" else "saaras:v3"
    logger.info(
        "[AGENT_CONFIG_LOADED] agent_id=%s first_line=%s voice_pipeline=%s stt_provider=%s tts_provider=%s llm_provider=%s",
        str(live_config.get("agent_id") or metadata_agent_id or metadata_published_agent_uuid or "").strip() or "-",
        str(live_config.get("first_line") or "").strip(),
        str(live_config.get("voice_pipeline") or os.getenv("VOICE_PIPELINE") or "livekit_agents").strip(),
        stt_provider,
        tts_provider,
        llm_provider,
    )

    logger.info(
        "[AUDIO_CONFIG] loaded agent_id=%s version_id=%s tts_provider=%s tts_model=%s tts_voice=%s tts_language=%s "
        "stt_provider=%s stt_model=%s stt_language=%s llm_provider=%s",
        str(metadata_agent_id or metadata_agent_config.get("agent_id") or "").strip() or "-",
        str(metadata_agent_version_id or metadata_agent_config.get("agent_version_id") or "").strip() or "-",
        tts_provider,
        tts_model,
        tts_voice,
        tts_language,
        stt_provider,
        stt_model,
        stt_language,
        str(live_config.get("llm_provider") or "").strip() or "-",
    )
    max_turns = int(live_config.get("max_turns", 14) or 14)
    base_silence = int(live_config.get("silence_timeout_seconds", 45) or 45)
    if call_cfg.get("silence_hangup_enabled", True):
        silence_timeout_seconds = int(call_cfg.get("silence_hangup_seconds") or base_silence)
    else:
        silence_timeout_seconds = base_silence

    # Override OS env vars from UI config
    for key in ["LIVEKIT_URL","LIVEKIT_API_KEY","LIVEKIT_API_SECRET","OPENAI_API_KEY",
                "GROQ_API_KEY","SARVAM_API_KEY","CAL_API_KEY","TELEGRAM_BOT_TOKEN","SUPABASE_URL",
                "SUPABASE_KEY","SUPABASE_SERVICE_ROLE_KEY"]:
        val = live_config.get(key.lower(), "")
        if val:
            if key.endswith("_KEY") and _looks_placeholder_secret(str(val)):
                logger.warning("[ENV_OVERRIDE_SKIPPED] key=%s reason=placeholder", key)
                continue
            os.environ[key] = val

    # ── Caller memory (#15) ───────────────────────────────────────────────
    async def get_caller_history(phone: str) -> str:
        if phone == "unknown":
            return ""
        try:
            import backend.db as db
            sb = db.get_supabase(service_role=True)
            if not sb:
                return ""
            query = (sb.table("call_logs")
                       .select("summary, created_at")
                       .eq("phone", phone)
                       .order("created_at", desc=True)
                       .limit(1))
            if owner_workspace_id:
                query = query.eq("workspace_id", owner_workspace_id)
            elif owner_user_id:
                query = query.eq("user_id", owner_user_id)
            result = query.execute()
            if result.data:
                last = result.data[0]
                return f"\n\n[CALLER HISTORY: Last call {last['created_at'][:10]}. Summary: {last['summary']}]"
        except Exception as e:
            logger.warning(f"[MEMORY] Could not load history: {e}")
        return ""

    caller_history = await get_caller_history(caller_phone)
    if caller_history:
        logger.info(f"[MEMORY] Loaded caller history for {caller_phone}")
        # Append to live_config instructions
        live_config["agent_instructions"] = (live_config.get("agent_instructions","") + caller_history)

    # ── Instantiate tools ─────────────────────────────────────────────────
    agent_tools = AgentTools(caller_phone=caller_phone, caller_name=caller_name, live_config=live_config)
    agent_tools._sip_identity = (
        f"sip_{caller_phone.replace('+','')}" if phone_number else "inbound_caller"
    )
    agent_tools.ctx_api   = ctx.api
    agent_tools.room_name = ctx.room.name

    function_tools_filtered = _filter_function_tools_for_config(agent_tools, live_config)
    _tcfg = live_config.get("tools_config")
    _enabled_tool_ids = {
        str(x.get("id", "")).strip()
        for x in (_tcfg if isinstance(_tcfg, list) else [])
        if isinstance(x, dict) and x.get("enabled")
    }
    if "transfer_call" in _enabled_tool_ids and not _transfer_destination_config_ok(live_config):
        logger.warning("[TOOLS_CONFIG] transfer_call enabled but no transfer destination — removing tool")
        function_tools_filtered = _remove_tool_by_id(function_tools_filtered, "transfer_call")

    # ── Orchestration brain (policy layer; same STT/LLM/TTS pipeline) ─────────
    from backend.orchestration import AgentOrchestrator, OrchestrationStateStore
    from backend.orchestration.tool_executor import (
        ToolExecutor,
        caller_name_from_orchestration_lead,
        format_summary_with_orchestration_lead,
    )
    from backend.orchestration.transfer_manager import TransferManager

    _call_cfg_orch = live_config.get("call_config") if isinstance(live_config.get("call_config"), dict) else {}
    _tools_cfg_list = live_config.get("tools_config") if isinstance(live_config.get("tools_config"), list) else []
    _orch_id = str(call_record_id or ctx.room.name)
    orch_state_store = OrchestrationStateStore(
        call_id=_orch_id,
        agent_id=str(metadata_agent_id or "").strip() or None,
        org_id=str(owner_workspace_id or ""),
        user_id=str(owner_user_id or ""),
        room_name=ctx.room.name,
    )
    _orch_transfer = TransferManager(_call_cfg_orch)
    _orch_exec = ToolExecutor()
    orchestrator = AgentOrchestrator(
        agent_config=dict(live_config),
        call_config=_call_cfg_orch,
        tools_config=_tools_cfg_list,
        call_id=_orch_id,
        room_name=ctx.room.name,
        user_id=str(owner_user_id or ""),
        org_id=str(owner_workspace_id or ""),
        transfer_manager=_orch_transfer,
        state_store=orch_state_store,
        tool_executor=_orch_exec,
    )

    # ── Outbound SIP dial ────────────────────────────────────────────────
    if not skip_sip_dial and phone_number and caller_phone not in ("unknown", "demo"):
        outbound_trunk_id = (
            os.getenv("OUTBOUND_TRUNK_ID", "")
            or os.getenv("LIVEKIT_SIP_TRUNK_ID", "")
            or os.getenv("SIP_TRUNK_ID", "")
        ).strip()
        # region agent log
        _debug_log(
            "livekit-auth",
            "H3,H4",
            "backend/agent.py:entrypoint",
            "Worker preparing SIP dial with sanitized LiveKit env",
            {
                "livekit_host": os.getenv("LIVEKIT_URL", "").replace("wss://", "").replace("https://", ""),
                "key_present": bool(os.getenv("LIVEKIT_API_KEY", "").strip()),
                "secret_present": bool(os.getenv("LIVEKIT_API_SECRET", "").strip()),
                "key_fingerprint": _debug_fingerprint(os.getenv("LIVEKIT_API_KEY", "").strip()),
                "outbound_trunk_id": outbound_trunk_id,
            },
        )
        # endregion
        if not outbound_trunk_id:
            logger.error(
                "[SIP] SIP trunk misconfigured — set OUTBOUND_TRUNK_ID or LIVEKIT_SIP_TRUNK_ID or SIP_TRUNK_ID on worker; cannot dial %s",
                caller_phone,
            )
            if call_record_id:
                import backend.db as db
                db.mark_call_failed(call_record_id, "sip_failure", retry_count=retry_count, max_retries=max_retries)
            return
        else:
            logger.info("[SIP] Dialing %s in room %s using trunk %s", caller_phone, ctx.room.name, outbound_trunk_id)
            try:
                await ctx.api.sip.create_sip_participant(
                    api.CreateSIPParticipantRequest(
                        sip_trunk_id=outbound_trunk_id,
                        sip_call_to=caller_phone,
                        room_name=ctx.room.name,
                        participant_identity=agent_tools._sip_identity,
                        participant_name=caller_name or caller_phone,
                        wait_until_answered=True,
                    )
                )
                logger.info("[SIP] Participant connected: %s", agent_tools._sip_identity)
                if call_record_id:
                    import backend.db as db
                    db.mark_call_answered(call_record_id, room_name=ctx.room.name)
            except Exception as e:
                logger.exception("[SIP] create_sip_participant failed for %s: %s", caller_phone, e)
                failure_text = str(e).lower()
                if "busy" in failure_text:
                    reason = "busy"
                elif "timeout" in failure_text or "timed out" in failure_text:
                    reason = "timeout"
                elif "no answer" in failure_text or "no_answer" in failure_text:
                    reason = "no_answer"
                else:
                    reason = "sip_failure"
                if call_record_id:
                    import backend.db as db
                    db.mark_call_failed(call_record_id, reason, retry_count=retry_count, max_retries=max_retries)
                return
    else:
        logger.info("[SIP] No outbound phone number — running inbound/browser session without SIP dial.")

    _sk = (os.getenv("SARVAM_API_KEY") or "").strip()
    if llm_provider == "groq" and not (os.getenv("GROQ_API_KEY") or "").strip():
        logger.error("[ERROR] GROQ_API_KEY missing — cannot run voice worker with Groq provider")
        if call_record_id:
            import backend.db as db
            db.mark_call_failed(call_record_id, "sip_failure", retry_count=retry_count, max_retries=max_retries)
        return
    if stt_provider == "sarvam" and not _sk:
        logger.error("[ERROR] SARVAM_API_KEY missing — Sarvam STT cannot run")
        if call_record_id:
            import backend.db as db
            db.mark_call_failed(call_record_id, "sip_failure", retry_count=retry_count, max_retries=max_retries)
        return
    if tts_provider == "sarvam" and not _sk:
        logger.error("[ERROR] SARVAM_API_KEY missing — Sarvam TTS cannot run")
        if call_record_id:
            import backend.db as db
            db.mark_call_failed(call_record_id, "sip_failure", retry_count=retry_count, max_retries=max_retries)
        return

    # ── Build LLM (#8 Groq support) ───────────────────────────────────────
    llm_max_tokens = int(live_config.get("llm_max_tokens") or os.getenv("VOICE_MAX_COMPLETION_TOKENS", "64") or 64)
    llm_temperature = float(live_config.get("llm_temperature") or 0.3)
    _latency_mode = str(live_config.get("response_latency_mode") or "normal").lower()
    if _latency_mode == "fast":
        llm_max_tokens = min(llm_max_tokens, 36)
    elif _latency_mode == "quality":
        llm_max_tokens = max(llm_max_tokens, 96)
    agent_llm = build_voice_llm(
        provider=llm_provider,
        model=llm_model,
        max_completion_tokens=llm_max_tokens,
        temperature=llm_temperature,
    )

    # ── Build STT (#1 16kHz, #20 auto-detect, #9 Deepgram) ──────────────
    if stt_provider == "deepgram":
        try:
            from livekit.plugins import deepgram
            dg_model = stt_model or "nova-2-general"
            agent_stt = deepgram.STT(
                model=dg_model,
                language="multi",        # multilingual mode
                interim_results=True,
            )
            logger.info("[STT] Using deepgram %s", dg_model)
        except ImportError:
            logger.warning("[STT] deepgram plugin not installed — falling back to Sarvam")
            agent_stt = build_sarvam_stt(
                language=stt_language,
                model="saaras:v3",
                sample_rate=16000,
            )
            logger.info("[STT] Using sarvam saaras:v3 (deepgram plugin unavailable)")
    else:
        sm = stt_model or "saaras:v3"
        agent_stt = build_sarvam_stt(
            language=stt_language,      # "unknown" = auto-detect (#20)
            model=sm,
            sample_rate=16000,          # force 16kHz (#1)
        )
        logger.info("[STT] Using Sarvam %s", sm)

    # ── Build TTS (#2 24kHz, #10 ElevenLabs) ────────────────────────────
    if tts_provider == "elevenlabs":
        try:
            from livekit.plugins import elevenlabs
            _el_voice_id = live_config.get("elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
            agent_tts = elevenlabs.TTS(
                model="eleven_turbo_v2_5",
                voice_id=_el_voice_id,
            )
            logger.info(f"[TTS] Using ElevenLabs Turbo v2.5 — voice: {_el_voice_id}")
        except ImportError:
            logger.warning("[TTS] elevenlabs plugin not installed — falling back to Sarvam")
            agent_tts = build_sarvam_tts(
                language=tts_language,
                model=tts_model or "bulbul:v3",
                speaker=tts_voice,
                sample_rate=24000,
                pace=float(live_config.get("tts_pace") or 1.12),
            )
    else:
        tm = tts_model or "bulbul:v3"
        agent_tts = build_sarvam_tts(
            language=tts_language,
            model=tm,
            speaker=tts_voice,
            sample_rate=24000,          # force 24kHz (#2)
            pace=float(live_config.get("tts_pace") or 1.12),
        )
        logger.info(
            "[TTS] Using Sarvam Bulbul v3 voice=%s language=%s model=%s",
            tts_voice,
            tts_language,
            tm,
        )

    # ── Sentence chunker (keep responses short for voice) ─────────────────
    def before_tts_cb(agent_response: str) -> str:
        sentences = re.split(r'(?<=[।.!?])\s+', agent_response.strip())
        return sentences[0] if sentences else agent_response

    # ── Turn counter + auto-close (#29) ──────────────────────────────────
    turn_count    = 0
    interrupt_count = 0  # (#30)

    # ── Build agent ───────────────────────────────────────────────────────
    agent = OutboundAssistant(
        agent_tools=agent_tools,
        first_line=live_config.get("first_line", ""),
        live_config=live_config,
        function_tools=function_tools_filtered,
        orchestrator=orchestrator,
        tool_executor=_orch_exec,
        latency_tracker=latency_tracker,
    )

    # ── Build session (#3 noise cancellation attempted) ───────────────────
    try:
        from livekit.agents import noise_cancellation as nc
        _noise_cancel = nc.BVC()
        logger.info("[AUDIO] BVC noise cancellation enabled")
    except Exception:
        _noise_cancel = None
        logger.info("[AUDIO] BVC not available — running without noise cancellation")

    room_input = RoomInputOptions(
        close_on_disconnect=False,
        audio_sample_rate=16000,
        audio_num_channels=1,
        audio_frame_size_ms=20,
        pre_connect_audio=True,
    )
    if _noise_cancel:
        try:
            room_input = RoomInputOptions(
                close_on_disconnect=False,
                audio_sample_rate=16000,
                audio_num_channels=1,
                audio_frame_size_ms=20,
                pre_connect_audio=True,
                noise_cancellation=_noise_cancel,
            )
        except Exception:
            room_input = RoomInputOptions(close_on_disconnect=False, audio_sample_rate=16000, audio_frame_size_ms=20)

    session = AgentSession(
        stt=agent_stt,
        llm=agent_llm,
        tts=agent_tts,
        turn_detection="stt",
        min_endpointing_delay=float(delay_setting),  # 0.05 default (#6)
        max_endpointing_delay=float(live_config.get("stt_max_endpointing_delay") or 0.8),
        allow_interruptions=True,
        min_interruption_duration=float(live_config.get("min_interruption_duration") or 0.15),
        min_interruption_words=int(live_config.get("min_interruption_words") or 0),
        false_interruption_timeout=float(live_config.get("false_interruption_timeout") or 0.6),
        resume_false_interruption=False,
        discard_audio_if_uninterruptible=True,
        preemptive_generation=True,
        user_away_timeout=None,
    )

    await session.start(room=ctx.room, agent=agent, room_input_options=room_input)
    logger.info("[AUDIO] Track published")

    # ── TTS pre-warm (#12) ────────────────────────────────────────────────
    try:
        await session.tts.prewarm()
        logger.info("[TTS] Pre-warmed successfully")
    except Exception as e:
        logger.debug(f"[TTS] Pre-warm skipped: {e}")

    logger.info("[AGENT] Session live — waiting for caller audio.")
    orchestrator.start_session()
    call_start_time = datetime.now()
    logger.info(
        "[USAGE] call_start room=%s workspace_id=%s user_id=%s phone=%s",
        ctx.room.name,
        owner_workspace_id or "",
        owner_user_id or "",
        caller_phone,
    )
    logger.info("[CALL_START] room=%s call_log_id=%s", ctx.room.name, call_record_id if call_record_id is not None else "")

    # ── Recording → Supabase Storage ─────────────────────────────────────
    egress_id = None
    _rec_scope = owner_workspace_id or owner_user_id or "unassigned"
    recording_object_path = f"recordings/{_rec_scope}/{ctx.room.name}.ogg"
    try:
        rec_api = api.LiveKitAPI(
            url=os.environ["LIVEKIT_URL"],
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        )
        egress_resp = await rec_api.egress.start_room_composite_egress(
            api.RoomCompositeEgressRequest(
                room_name=ctx.room.name,
                audio_only=True,
                file_outputs=[api.EncodedFileOutput(
                    file_type=api.EncodedFileType.OGG,
                    filepath=recording_object_path,
                    s3=api.S3Upload(
                        access_key=os.environ["SUPABASE_S3_ACCESS_KEY"],
                        secret=os.environ["SUPABASE_S3_SECRET_KEY"],
                        bucket="call-recordings",
                        region=os.environ.get("SUPABASE_S3_REGION", "ap-south-1"),
                        endpoint=os.environ["SUPABASE_S3_ENDPOINT"],
                        force_path_style=True,
                    )
                )]
            )
        )
        egress_id = egress_resp.egress_id
        await rec_api.aclose()
        logger.info(f"[RECORDING] Started egress: {egress_id}")
    except Exception as e:
        logger.warning(f"[RECORDING] Failed to start recording: {e}")

    # ── Upsert active_calls (#38) ─────────────────────────────────────────
    async def upsert_active_call(status: str):
        try:
            import backend.db as db
            sb = db.get_supabase(service_role=True)
            if sb:
                row = {
                    "room_id":     ctx.room.name,
                    "user_id":     owner_user_id,
                    "phone":       caller_phone,
                    "caller_name": caller_name,
                    "status":      status,
                    "last_updated": datetime.utcnow().isoformat(),
                }
                if owner_workspace_id:
                    row["workspace_id"] = owner_workspace_id
                sb.table("active_calls").upsert(row).execute()
        except Exception as e:
            logger.debug(f"[ACTIVE-CALL] {e}")

    await upsert_active_call("active")

    # ── Real-time transcript streaming (#33) ─────────────────────────────
    async def _log_transcript(role: str, content: str):
        _db_start = time.perf_counter()
        try:
            import backend.db as db
            def _insert_transcript() -> None:
                sb = db.get_supabase(service_role=True)
                if sb:
                    tr = {
                        "call_room_id": ctx.room.name,
                        "user_id":      owner_user_id,
                        "phone":        caller_phone,
                        "role":         role,
                        "content":      content,
                    }
                    if owner_workspace_id:
                        tr["workspace_id"] = owner_workspace_id
                    sb.table("call_transcripts").insert(tr).execute()

            await asyncio.to_thread(_insert_transcript)
            latency_tracker.note_db_save(_ms_since(_db_start), source=f"transcript_{role}")
        except Exception as e:
            latency_tracker.note_db_save(_ms_since(_db_start), source=f"transcript_{role}_failed")
            logger.debug(f"[TRANSCRIPT-STREAM] {e}")

    shutdown_requested = False
    shutdown_completed = False
    last_user_activity = time.time()
    last_partial_transcript = ""

    iw_raw = live_config.get("interruption_words") or []
    if isinstance(iw_raw, str):
        iw_list = [x.strip().lower() for x in re.split(r"[,;\n]+", iw_raw) if x.strip()]
    elif isinstance(iw_raw, list):
        iw_list = [str(x).strip().lower() for x in iw_raw if str(x).strip()]
    else:
        iw_list = []
    filler_word_set = {
        "okay.", "okay", "ok", "uh", "hmm", "hm", "yeah", "yes",
        "no", "um", "ah", "oh", "right", "sure", "fine", "good",
        "haan", "han", "theek", "theek hai", "accha", "ji", "ha",
    }
    filler_word_set.update(iw_list)

    _fc_msg = (call_cfg.get("final_call_message") or "").strip()
    if _fc_msg:
        inactivity_instructions = (
            f"Briefly convey this closing message to the caller, then end the call: '{_fc_msg}'"
        )
    else:
        inactivity_instructions = "Briefly say you are ending the call due to inactivity and thank the caller."

    async def _inactive_call_watchdog():
        nonlocal shutdown_requested
        while not shutdown_requested:
            await asyncio.sleep(5)
            if turn_count == 0:
                continue
            if time.time() - last_user_activity >= silence_timeout_seconds:
                logger.info("[INACTIVITY] No caller speech for %ss; ending call.", silence_timeout_seconds)
                shutdown_requested = True
                try:
                    await session.generate_reply(instructions=inactivity_instructions)
                except Exception:
                    pass
                try:
                    session.shutdown(drain=True)
                except Exception as e:
                    logger.warning(f"[INACTIVITY] Session shutdown failed: {e}")
                return

    asyncio.create_task(_inactive_call_watchdog())

    max_dur = int(call_cfg.get("total_call_timeout_seconds") or 0)
    if max_dur > 0:

        async def _max_call_duration_watchdog():
            nonlocal shutdown_requested
            await asyncio.sleep(float(max_dur))
            if shutdown_requested:
                return
            logger.info("[CALL_CONFIG] total_call_timeout_seconds reached (%s)", max_dur)
            shutdown_requested = True
            try:
                await session.generate_reply(
                    instructions="Politely tell the caller the maximum call time has been reached and say goodbye.",
                )
            except Exception:
                pass
            try:
                session.shutdown(drain=True)
            except Exception as e:
                logger.warning(f"[CALL_LIMIT] Session shutdown failed: {e}")

        asyncio.create_task(_max_call_duration_watchdog())

    # ── Session event handlers ────────────────────────────────────────────
    @session.on("user_state_changed")
    def _user_state_changed(ev):
        if getattr(ev, "old_state", None) == "speaking" and getattr(ev, "new_state", None) != "speaking":
            latency_tracker.mark_user_speaking_end(getattr(ev, "created_at", None))

    @session.on("agent_state_changed")
    def _agent_state_changed(ev):
        latency_tracker.note_agent_state(
            str(getattr(ev, "old_state", "")),
            str(getattr(ev, "new_state", "")),
            getattr(ev, "created_at", None),
        )

    @session.on("user_input_transcribed")
    def _user_input_transcribed(ev):
        nonlocal last_partial_transcript
        transcript = str(getattr(ev, "transcript", "") or "").strip()
        if not bool(getattr(ev, "is_final", False)):
            if transcript:
                last_partial_transcript = transcript
                agent.handle_partial_transcript(transcript)
                if agent_is_speaking and _is_confused_user(transcript):
                    logger.info("[PARTIAL_CONFUSION_BARGE_IN] text=%s", transcript[:120])
                    try:
                        session.interrupt(force=True)
                    except Exception as e:
                        logger.debug("[BARGE_IN] interrupt failed: %s", e)
            return
        if transcript:
            last_partial_transcript = ""
            latency_tracker.mark_final_transcript(transcript, getattr(ev, "created_at", None))

    @session.on("metrics_collected")
    def _metrics_collected(ev):
        latency_tracker.note_metric(getattr(ev, "metrics", None))

    @session.on("conversation_item_added")
    def _conversation_item_added(ev):
        item = getattr(ev, "item", None)
        role = str(getattr(item, "role", "") or "").strip()
        if role != "assistant":
            return
        content = getattr(item, "content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content if isinstance(c, str))
        text = str(content or "").strip()
        if text:
            asyncio.create_task(_log_transcript("assistant", text))

    @session.on("agent_speech_started")
    def _agent_speech_started(ev):
        global agent_is_speaking
        agent_is_speaking = True
        latency_tracker._log_total_response(created_at=time.time(), source="legacy_agent_speech_started")

    @session.on("agent_speech_finished")
    def _agent_speech_finished(ev):
        global agent_is_speaking
        agent_is_speaking = False

    # Interrupt logging (#30)
    @session.on("agent_speech_interrupted")
    def _on_interrupted(ev):
        nonlocal interrupt_count
        interrupt_count += 1
        orchestrator.handle_interruption()
        logger.info(f"[INTERRUPT] Agent interrupted. Total: {interrupt_count}")

    @session.on("user_speech_committed")
    def on_user_speech_committed(ev):
        nonlocal turn_count, last_user_activity
        global agent_is_speaking

        transcript = ev.user_transcript.strip()
        transcript_lower = transcript.lower().rstrip(".")

        if agent_is_speaking and transcript_lower in filler_word_set and not _is_confused_user(transcript):
            logger.debug(f"[FILTER-ECHO] Dropped: '{transcript}'")
            return
        if not transcript or len(transcript) < 3:
            return
        if transcript_lower in filler_word_set:
            logger.debug(f"[FILTER-FILLER] Dropped: '{transcript}'")
            return

        # Real-time transcript stream
        last_user_activity = time.time()
        asyncio.create_task(_log_transcript("user", transcript))

        # Turn counter + auto-close (#29)
        turn_count += 1
        logger.info(f"[TRANSCRIPT] Turn {turn_count}/{max_turns}: '{transcript}'")
        if turn_count >= max_turns:
            logger.info(f"[LIMIT] Reached {max_turns} turns — wrapping up")
            asyncio.create_task(
                session.generate_reply(
                    instructions="Politely wrap up: thank the caller, say they can call back anytime, and say a warm goodbye."
                )
            )

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        nonlocal shutdown_requested
        global agent_is_speaking
        logger.info(f"[HANGUP] Participant disconnected: {participant.identity}")
        agent_is_speaking = False
        if shutdown_requested:
            return
        shutdown_requested = True
        try:
            # Let the session terminate gracefully; cleanup runs via shutdown callback.
            session.shutdown(drain=True)
        except Exception as e:
            logger.warning(f"[HANGUP] Session shutdown request failed: {e}")

    # ══════════════════════════════════════════════════════════════════════
    # POST-CALL SHUTDOWN HOOK
    # ══════════════════════════════════════════════════════════════════════

    async def unified_shutdown_hook(shutdown_ctx: JobContext):
        nonlocal shutdown_requested, shutdown_completed
        if shutdown_completed:
            logger.info("[SHUTDOWN] Hook already executed; skipping duplicate run.")
            return
        shutdown_requested = True
        shutdown_completed = True
        logger.info("[SHUTDOWN] Sequence started.")
        try:
            try:
                orchestrator.end_session()
            except Exception as e:
                logger.debug("[ORCHESTRATOR] end_session: %s", e)
            shutdown_deadline = datetime.now() + timedelta(minutes=2)
    
            def _ensure_time(stage: str) -> bool:
                if datetime.now() >= shutdown_deadline:
                    logger.warning(f"[SHUTDOWN] Timeout reached at stage: {stage}. Skipping remaining cleanup.")
                    return False
                return True
    
            duration = int((datetime.now() - call_start_time).total_seconds())
    
            # Booking
            booking_status_msg = "No booking"
            summary_for_log = booking_status_msg
    
            if agent_tools.booking_intent:
                if not _ensure_time("booking"):
                    return
                from backend.calendar_tools import async_create_booking
                intent = agent_tools.booking_intent
                result = await async_create_booking(
                    start_time=intent["start_time"],
                    caller_name=intent["caller_name"] or "Unknown Caller",
                    caller_phone=intent["caller_phone"],
                    notes=intent["notes"],
                )
                if result.get("success"):
                    notify_booking_confirmed(
                        caller_name=intent["caller_name"],
                        caller_phone=intent["caller_phone"],
                        booking_time_iso=intent["start_time"],
                        booking_id=result.get("booking_id"),
                        notes=intent["notes"],
                        tts_voice=tts_voice,
                        ai_summary="",
                    )
                    booking_status_msg = f"Booking Confirmed: {result.get('booking_id')}"
                else:
                    booking_status_msg = f"Booking Failed: {result.get('message')}"
            else:
                notify_call_no_booking(
                    caller_name=agent_tools.caller_name,
                    caller_phone=agent_tools.caller_phone,
                    call_summary="Caller did not schedule during this call.",
                    tts_voice=tts_voice,
                    duration_seconds=duration,
                )
    
            _lead_snapshot = getattr(_orch_exec, "latest_lead", None) if _orch_exec is not None else None
            _lead_dict = dict(_lead_snapshot) if isinstance(_lead_snapshot, dict) and _lead_snapshot else None
            if _lead_dict:
                _cn = caller_name_from_orchestration_lead(_lead_dict)
                if _cn and not (agent_tools.caller_name or "").strip():
                    agent_tools.caller_name = _cn
            summary_for_log = format_summary_with_orchestration_lead(booking_status_msg, _lead_dict)
            _xreq = bool(getattr(getattr(orchestrator, "_state", None), "transfer_requested", False))
            _xout = str(getattr(agent_tools, "sip_transfer_outcome", "none"))
            if _xout == "ok":
                _xfer = "ok"
            elif _xout == "fail":
                _xfer = "fail"
            elif _xreq:
                _xfer = "requested"
            else:
                _xfer = "none"
            if "Booking Confirmed" in booking_status_msg:
                _disp = "booking_confirmed"
            elif "Booking Failed" in booking_status_msg:
                _disp = "booking_failed"
            else:
                _disp = "completed"
            summary_for_log = f"{summary_for_log} | disp={_disp} | xfer={_xfer}"
            _sum_cap = int(os.getenv("MAX_CALL_SUMMARY_CHARS", "8000") or 8000)
            if len(summary_for_log) > _sum_cap:
                summary_for_log = summary_for_log[: max(0, _sum_cap - 12)] + "…[truncated]"
                logger.warning("[CRM] summary_truncated cap=%s", _sum_cap)

            # Build transcript
            transcript_text = ""
            try:
                messages = agent.chat_ctx.messages
                if callable(messages):
                    messages = messages()
                lines = []
                for msg in messages:
                    if getattr(msg, "role", None) in ("user", "assistant"):
                        content = getattr(msg, "content", "")
                        if isinstance(content, list):
                            content = " ".join(str(c) for c in content if isinstance(c, str))
                        lines.append(f"[{msg.role.upper()}] {content}")
                transcript_text = "\n".join(lines)
            except Exception as e:
                logger.error(f"[SHUTDOWN] Transcript read failed: {e}")
                transcript_text = "unavailable"

            _max_tx = int(os.getenv("MAX_CALL_TRANSCRIPT_CHARS", "196608") or 196608)
            if transcript_text != "unavailable" and len(transcript_text) > _max_tx:
                _tx_before = len(transcript_text)
                transcript_text = transcript_text[:_max_tx] + "\n…[truncated]"
                logger.warning("[CRM] transcript_truncated chars_before=%s cap=%s", _tx_before, _max_tx)

            # Sentiment analysis (#14)
            sentiment = "unknown"
            if transcript_text and transcript_text != "unavailable":
                if not _ensure_time("sentiment"):
                    return
                try:
                    import openai as _oai
                    _oai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
                    if _looks_placeholder_secret(_oai_key):
                        logger.debug("[SENTIMENT] skipped OPENAI_API_KEY missing_or_placeholder")
                    else:
                        _client = _oai.AsyncOpenAI(api_key=_oai_key)
                        resp = await _client.chat.completions.create(
                            model="gpt-4o-mini",
                            max_tokens=5,
                            messages=[
                                {
                                    "role": "user",
                                    "content": (
                                        "Classify this call as one word: positive, neutral, negative, or frustrated.\n\n"
                                        f"{transcript_text[:800]}"
                                    ),
                                }
                            ],
                        )
                        _raw_s = getattr(resp.choices[0].message, "content", None) if resp and resp.choices else None
                        sentiment = (_raw_s or "").strip().lower() if isinstance(_raw_s, str) else "unknown"
                        logger.info(f"[SENTIMENT] {sentiment}")
                except Exception as e:
                    logger.warning(f"[SENTIMENT] Failed: {e}")
    
            # Cost estimation (#34)
            def estimate_cost(dur: int, chars: int) -> float:
                return round(
                    (dur / 60) * 0.002 +
                    (dur / 60) * 0.006 +
                    (chars / 1000) * 0.003 +
                    (chars / 4000) * 0.0001,
                    5
                )
            estimated_cost = estimate_cost(duration, len(transcript_text))
            logger.info(f"[COST] Estimated: ${estimated_cost}")
            logger.info(
                "[USAGE] call_end room=%s workspace_id=%s user_id=%s duration_sec=%s cost_usd=%s",
                ctx.room.name,
                owner_workspace_id or "",
                owner_user_id or "",
                duration,
                estimated_cost,
            )
            logger.info(
                "[CALL_END] room=%s call_log_id=%s duration_sec=%s transcript_chars=%s",
                ctx.room.name,
                call_record_id if call_record_id is not None else "",
                duration,
                len(transcript_text),
            )
            try:
                import backend.db as db
                db.record_provider_usage_event(
                    workspace_id=owner_workspace_id,
                    user_id=owner_user_id,
                    agent_id=metadata_agent_id,
                    agent_version_id=metadata_agent_version_id,
                    call_log_id=call_record_id,
                    provider_type="llm_tts_stt",
                    provider_name=f"{llm_provider}+{tts_provider}+{stt_provider}",
                    model=str(llm_model or ""),
                    metric="estimated_call_cost",
                    quantity=duration,
                    estimated_cost_usd=estimated_cost,
                    metadata={"room_name": ctx.room.name, "phone": caller_phone},
                )
            except Exception as e:
                logger.debug(f"[USAGE] Provider usage event skipped: {e}")
    
            # Analytics timestamps (#19)
            ist = pytz.timezone("Asia/Kolkata")
            call_dt = call_start_time.astimezone(ist)
    
            # Stop recording
            recording_url = ""
            if egress_id:
                if not _ensure_time("recording_stop"):
                    return
                try:
                    _lk_url = (os.getenv("LIVEKIT_URL") or "").strip()
                    _lk_key = (os.getenv("LIVEKIT_API_KEY") or "").strip()
                    _lk_sec = (os.getenv("LIVEKIT_API_SECRET") or "").strip()
                    if not (_lk_url and _lk_key and _lk_sec):
                        logger.error("[ERROR] recording_stop skipped — LiveKit URL/key/secret incomplete")
                    else:
                        stop_api = api.LiveKitAPI(url=_lk_url, api_key=_lk_key, api_secret=_lk_sec)
                        await stop_api.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
                        await stop_api.aclose()
                        recording_url = recording_object_path
                        logger.info(f"[RECORDING] Stopped. Object path: {recording_url}")
                except Exception as e:
                    logger.warning(f"[RECORDING] Stop failed: {e}")
    
            # Update active_calls to completed (#38)
            if not _ensure_time("active_calls_update"):
                return
            await upsert_active_call("completed")
    
            # n8n webhook (#39)
            _n8n_url = os.getenv("N8N_WEBHOOK_URL")
            if _n8n_url:
                if not _ensure_time("n8n_webhook"):
                    return
                try:
                    import httpx
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: httpx.post(_n8n_url, json={
                            "event":        "call_completed",
                            "phone":        caller_phone,
                            "caller_name":  agent_tools.caller_name,
                            "duration":     duration,
                            "booked":       bool(agent_tools.booking_intent),
                            "sentiment":    sentiment,
                            "summary":      summary_for_log,
                            "recording_url":recording_url,
                            "interrupt_count": interrupt_count,
                            "workspace_id": owner_workspace_id,
                            "user_id":      owner_user_id,
                        }, timeout=5.0)
                    )
                    logger.info("[N8N] Webhook triggered")
                except Exception as e:
                    logger.warning(f"[N8N] Webhook failed: {e}")
    
            # Save to Supabase
            if not _ensure_time("save_call_log"):
                return
            from backend.db import mark_call_completed, save_call_log
            call_fields = {
                "phone": caller_phone,
                "duration": duration,
                "transcript": transcript_text,
                "summary": summary_for_log,
                "recording_url": recording_url,
                "caller_name": agent_tools.caller_name or "",
                "sentiment": sentiment,
                "estimated_cost_usd": estimated_cost,
                "call_date": call_dt.date().isoformat(),
                "call_hour": call_dt.hour,
                "call_day_of_week": call_dt.strftime("%A"),
                "was_booked": bool(agent_tools.booking_intent),
                "interrupt_count": interrupt_count,
                "owner_user_id": owner_user_id,
                "workspace_id": owner_workspace_id,
                "agent_id": metadata_agent_id,
                "agent_version_id": metadata_agent_version_id,
                "published_agent_uuid": metadata_published_agent_uuid,
            }
            if call_record_id:
                _db_save_start = time.perf_counter()
                crm_res = mark_call_completed(
                    call_record_id,
                    **{k: v for k, v in call_fields.items() if k not in {"owner_user_id", "workspace_id"}},
                )
                latency_tracker.note_db_save(_ms_since(_db_save_start), source="call_log_mark_completed")
                if not crm_res.get("success"):
                    logger.error(
                        "[ERROR] CRM mark_call_completed failed id=%s detail=%s",
                        call_record_id,
                        crm_res.get("message"),
                    )
                else:
                    logger.info("[CRM] mark_call_completed ok id=%s", call_record_id)
            else:
                _db_save_start = time.perf_counter()
                crm_res = save_call_log(**call_fields)
                latency_tracker.note_db_save(_ms_since(_db_save_start), source="call_log_save")
                if not crm_res.get("success"):
                    logger.error("[ERROR] CRM save_call_log failed detail=%s", crm_res.get("message"))
                else:
                    logger.info("[CRM] save_call_log ok id=%s", crm_res.get("id"))
    
        except Exception as _ush:
            logger.exception("[ERROR] unified_shutdown_hook fatal: %s", _ush)
    ctx.add_shutdown_callback(unified_shutdown_hook)


# ══════════════════════════════════════════════════════════════════════════════
# WORKER ENTRY
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="outbound-caller",
    ))
