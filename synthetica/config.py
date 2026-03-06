"""
Synthetica — Environment-Ready, Cloud-Native Configuration
===========================================================
Uses REDIS_HOST, REDIS_PORT (Google Memorystore–ready; passwordless VPC when no REDIS_PASSWORD).
GOOGLE_API_KEY for Gemini. All values from os.getenv with safe defaults.
"""

import os


# -----------------------------------------------------------------------------
# Redis (Memorystore-compatible)
# -----------------------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")  # Empty = passwordless (VPC / local)
REDIS_DB = int(os.getenv("REDIS_DB", "0"))


def build_redis_url() -> str:
    """
    Build Redis URL for redis-py. Supports passwordless connections for
    Google Memorystore (VPC) when REDIS_PASSWORD is not set.
    """
    if REDIS_PASSWORD:
        return f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"


REDIS_URL = os.getenv("REDIS_URL") or build_redis_url()


# -----------------------------------------------------------------------------
# Google / Gemini
# -----------------------------------------------------------------------------

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_TIMEOUT_SEC = float(os.getenv("GEMINI_TIMEOUT_SEC", "60"))


# -----------------------------------------------------------------------------
# Swarm behaviour
# -----------------------------------------------------------------------------

SYNTHETICA_SEED = os.getenv("SYNTHETICA_SEED", "1").lower() in ("1", "true", "yes")
