import json
import os
import logging
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
logger = logging.getLogger("config_manager")

CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.json")

def read_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Error reading config: {e}")

    def get_val(key, env_key, default=""):
        return os.getenv(env_key) or config.get(key) or default

    values = {
        "first_line": get_val("first_line", "FIRST_LINE", "Namaste! This is Aryan from RapidX AI — we help businesses automate with AI. Hmm, may I ask what kind of business you run?"),
        "agent_instructions": get_val("agent_instructions", "AGENT_INSTRUCTIONS", ""),
        "stt_min_endpointing_delay": float(get_val("stt_min_endpointing_delay", "STT_MIN_ENDPOINTING_DELAY", 0.6)),
        "llm_model": get_val("llm_model", "LLM_MODEL", "gpt-4o-mini"),
        "tts_voice": get_val("tts_voice", "TTS_VOICE", "kavya"),
        "tts_language": get_val("tts_language", "TTS_LANGUAGE", "hi-IN"),
        "livekit_url": get_val("livekit_url", "LIVEKIT_URL", ""),
        "sip_trunk_id": get_val("sip_trunk_id", "SIP_TRUNK_ID", ""),
        "livekit_api_key": get_val("livekit_api_key", "LIVEKIT_API_KEY", ""),
        "livekit_api_secret": get_val("livekit_api_secret", "LIVEKIT_API_SECRET", ""),
        "openai_api_key": get_val("openai_api_key", "OPENAI_API_KEY", ""),
        "sarvam_api_key": get_val("sarvam_api_key", "SARVAM_API_KEY", ""),
        "cal_api_key": get_val("cal_api_key", "CAL_API_KEY", ""),
        "cal_event_type_id": get_val("cal_event_type_id", "CAL_EVENT_TYPE_ID", ""),
        "telegram_bot_token": get_val("telegram_bot_token", "TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": get_val("telegram_chat_id", "TELEGRAM_CHAT_ID", ""),
        "supabase_url": get_val("supabase_url", "SUPABASE_URL", ""),
        "supabase_key": os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or config.get("supabase_key") or "",
        "supabase_service_role_key": get_val("supabase_service_role_key", "SUPABASE_SERVICE_ROLE_KEY", ""),
    }
    for key, value in config.items():
        if key not in values:
            values[key] = value
    return values

def write_config(data):
    config = read_config()
    config.update(data)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
