"""
Configuration Manager for Outbound Caller Agent

Handles loading and saving configuration from config.json with environment variable fallback.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("config-manager")

CONFIG_FILE = "config.json"
CONFIG_SCHEMA = {
    "agent": {
        "llm_provider": "groq",  # groq, openai, openai-realtime
        "llm_model": "gpt-4o-mini",
        "openai_realtime_model": "gpt-4o-mini-realtime-preview-2024-12-17",
        "tts_provider": "elevenlabs",
        "elevenlabs_voice_id": "6AUOG2nbfr0yFEeI0784",
        "tts_speed": 1.0,
        "stt_provider": "deepgram",  # deepgram, openai-realtime
    },
    "call_behavior": {
        "initial_greeting_delay": 1.0,
        "min_endpointing_delay": 0.5,
        "max_endpointing_delay": 15.0,
        "no_response_timeout": 7.0,
        "initial_silence_wait": 5.0,
        "max_call_duration": 300,
    },
    "call_dispatch": {
        "call_delay_seconds": 5,
        "wait_for_call_completion": True,
        "call_completion_check_interval": 10,
        "max_wait_time": 600,
        "max_retries": 3,
        "retry_no_answer": True,
    },
    "integrations": {
        "livekit_url": "",
        "livekit_api_key": "",
        "livekit_api_secret": "",
        "sip_outbound_trunk_id": "",
        "google_sheet_id": "",
        "google_sheet_name": "Sheet1",
        "aws_bucket_name": "",
        "aws_region": "us-east-1",
        "aws_access_key_id": "",
        "aws_secret_access_key": "",
        "gcp_bucket_name": "",
        "gcp_credentials": "",
        "twilio_account_sid": "",
        "twilio_auth_token": "",
        "twilio_from_number": "",
    },
    "observability": {
        "langfuse_public_key": "",
        "langfuse_secret_key": "",
        "langfuse_base_url": "https://cloud.langfuse.com",
    },
    "system_prompt": "",  # Will be loaded from agent.py default or config
}


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json, falling back to defaults and env vars."""
    config = CONFIG_SCHEMA.copy()
    
    # Try to load from config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # Deep merge with defaults
                config = _deep_merge(config, file_config)
                logger.info(f"✅ Loaded configuration from {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load {CONFIG_FILE}: {e}. Using defaults and env vars.")
    else:
        logger.info(f"ℹ️  {CONFIG_FILE} not found. Using defaults and env vars.")
    
    # Override with environment variables (env vars take precedence)
    config = _apply_env_overrides(config)
    
    return config


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to config.json."""
    try:
        # Don't save sensitive fields - keep them in env vars
        safe_config = _sanitize_config(config.copy())
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(safe_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save configuration: {e}")
        return False


def get_config_value(path: str, default: Any = None) -> Any:
    """
    Get a config value by dot-separated path (e.g., 'agent.llm_provider').
    Falls back to environment variables, then default.
    """
    config = load_config()
    keys = path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            # Try environment variable
            env_key = path.upper().replace('.', '_')
            env_value = os.getenv(env_key)
            if env_value:
                return env_value
            return default
    
    return value if value != "" else default


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config."""
    # Agent settings
    if os.getenv("LLM_PROVIDER"):
        config["agent"]["llm_provider"] = os.getenv("LLM_PROVIDER", "").lower()
    if os.getenv("OPENAI_MODEL"):
        config["agent"]["llm_model"] = os.getenv("OPENAI_MODEL")
    if os.getenv("OPENAI_REALTIME_MODEL"):
        config["agent"]["openai_realtime_model"] = os.getenv("OPENAI_REALTIME_MODEL")
    if os.getenv("ELEVENLABS_VOICE_ID"):
        config["agent"]["elevenlabs_voice_id"] = os.getenv("ELEVENLABS_VOICE_ID")
    if os.getenv("TTS_SPEED"):
        try:
            config["agent"]["tts_speed"] = float(os.getenv("TTS_SPEED"))
        except (ValueError, TypeError):
            pass
    
    # Call behavior
    for key, env_key in [
        ("initial_greeting_delay", "INITIAL_GREETING_DELAY"),
        ("min_endpointing_delay", "MIN_ENDPOINTING_DELAY"),
        ("max_endpointing_delay", "MAX_ENDPOINTING_DELAY"),
        ("no_response_timeout", "NO_RESPONSE_TIMEOUT"),
        ("initial_silence_wait", "INITIAL_SILENCE_WAIT"),
        ("max_call_duration", "MAX_CALL_DURATION"),
    ]:
        if os.getenv(env_key):
            try:
                config["call_behavior"][key] = float(os.getenv(env_key))
            except (ValueError, TypeError):
                pass
    
    # Call dispatch
    for key, env_key in [
        ("call_delay_seconds", "CALL_DELAY_SECONDS"),
        ("max_wait_time", "MAX_WAIT_TIME"),
        ("max_retries", "MAX_RETRIES"),
        ("call_completion_check_interval", "CALL_COMPLETION_CHECK_INTERVAL"),
    ]:
        if os.getenv(env_key):
            try:
                config["call_dispatch"][key] = int(os.getenv(env_key))
            except (ValueError, TypeError):
                pass
    
    if os.getenv("WAIT_FOR_CALL_COMPLETION"):
        config["call_dispatch"]["wait_for_call_completion"] = os.getenv("WAIT_FOR_CALL_COMPLETION", "").lower() == "true"
    if os.getenv("RETRY_NO_ANSWER"):
        config["call_dispatch"]["retry_no_answer"] = os.getenv("RETRY_NO_ANSWER", "").lower() == "true"
    
    # Integrations (only non-sensitive values)
    if os.getenv("LIVEKIT_URL"):
        config["integrations"]["livekit_url"] = os.getenv("LIVEKIT_URL")
    if os.getenv("GOOGLE_SHEET_ID"):
        config["integrations"]["google_sheet_id"] = os.getenv("GOOGLE_SHEET_ID")
    if os.getenv("GOOGLE_SHEET_NAME"):
        config["integrations"]["google_sheet_name"] = os.getenv("GOOGLE_SHEET_NAME")
    if os.getenv("AWS_BUCKET_NAME"):
        config["integrations"]["aws_bucket_name"] = os.getenv("AWS_BUCKET_NAME")
    if os.getenv("AWS_REGION"):
        config["integrations"]["aws_region"] = os.getenv("AWS_REGION")
    
    # Observability
    if os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST"):
        config["observability"]["langfuse_base_url"] = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
    
    return config


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from config before saving."""
    safe_config = config.copy()
    
    # Remove API keys and secrets
    sensitive_paths = [
        "integrations.livekit_api_key",
        "integrations.livekit_api_secret",
        "integrations.aws_access_key_id",
        "integrations.aws_secret_access_key",
        "integrations.gcp_credentials",
        "integrations.twilio_account_sid",
        "integrations.twilio_auth_token",
        "observability.langfuse_public_key",
        "observability.langfuse_secret_key",
    ]
    
    for path in sensitive_paths:
        keys = path.split('.')
        d = safe_config
        for key in keys[:-1]:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                break
        else:
            if isinstance(d, dict) and keys[-1] in d:
                d[keys[-1]] = ""  # Clear but keep structure
    
    return safe_config


def load_system_prompt() -> str:
    """Load system prompt from config.json or return default."""
    config = load_config()
    prompt = config.get("system_prompt", "")
    
    if not prompt:
        # Return empty - agent.py will use its default
        return ""
    
    return prompt
