"""
Synthetica — Entry Point & Execution Logic (Google Cloud / Gemini)
==================================================================
Gemini 1.5 Flash via google-generativeai: system_instruction for personas,
generation_config.response_mime_type = application/json, latency_ms on every response.
Cloud-native config (REDIS_HOST, GOOGLE_API_KEY); telemetry to swarm_telemetry.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Optional

# Add project root for imports when run as script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redis.asyncio import Redis

from config import GEMINI_MODEL, GEMINI_TIMEOUT_SEC, GOOGLE_API_KEY, REDIS_URL, SYNTHETICA_SEED
from engine import BLACKBOARD_PREFIX, BaseAgent, get_async_redis
from models import BlackboardTask, TaskStatus


# -----------------------------------------------------------------------------
# Gemini 1.5 Flash — system_instruction, JSON mode, latency_ms
# -----------------------------------------------------------------------------

def _get_genai():
    import google.generativeai as genai
    return genai


async def invoke_gemini(
    agent: BaseAgent,
    system_instruction: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Call Gemini 1.5 Flash with system_instruction and response_mime_type=application/json.
    Returns dict with at least "reasoning" and "latency_ms" for judges.
    """
    genai = _get_genai()
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY environment variable is required")
    genai.configure(api_key=GOOGLE_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_instruction,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.3,
        },
    )

    start = time.perf_counter()
    try:
        # SDK is sync; run in thread to keep event loop non-blocking
        response = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: model.generate_content(user_message),
            ),
            timeout=GEMINI_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        raise
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    latency_ms = round((time.perf_counter() - start) * 1000)
    content = response.text if response and response.text else ""

    if not content:
        return {
            "reasoning": "No content returned from model.",
            "status": "REVIEW",
            "latency_ms": latency_ms,
        }

    try:
        out = json.loads(content)
    except json.JSONDecodeError as e:
        return {
            "reasoning": f"Model returned non-JSON; parse error: {e}",
            "status": "REVIEW",
            "latency_ms": latency_ms,
        }

    if "reasoning" not in out:
        out["reasoning"] = "No reasoning field in model output; audit trail missing."
    out["latency_ms"] = latency_ms
    return out


async def invoke_mock_llm(
    agent: BaseAgent,
    system_instruction: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Local demo LLM used when GOOGLE_API_KEY isn't set.
    Returns strict-JSON-shaped outputs that move tasks through the pipeline.
    """
    start = time.perf_counter()
    try:
        task = json.loads(user_message)
    except Exception:
        task = {}

    role = getattr(agent, "_effective_role", agent.role)
    location = task.get("location") or "Unknown"
    issue = None
    if isinstance(task.get("raw_data"), dict):
        issue = task["raw_data"].get("issue")

    if role == "scout":
        out: dict[str, Any] = {
            "status": "NEEDS_PLAN",
            "metadata": {
                "severity": "High",
                "type": "Flood",
                "critical_infrastructure": [
                    "Slussen Slussenkajen",
                    "Gamla Stan Subway",
                    "Centralbron",
                ],
                "summary": f"{location}: {issue or 'Situation report received'}",
            },
            "risk_level": 8,
            "reasoning": "Mock Scout: synthesized a minimal, safe enrichment to drive the demo pipeline.",
        }
    elif role == "architect":
        out = {
            "plan_steps": [
                "Coordinate with SL/Trafikverket to close and assess nearby T-Bana entrances; deploy pumps/barriers for underground ingress points.",
                "Secure Centralbron and primary evacuation corridors; redirect traffic and stage rescue/medical resources upstream.",
                "Protect Slussenkajen waterfront assets; set exclusion zones, monitor water level, and hand off an action log to incident command.",
            ],
            "status": "REVIEW",
            "reasoning": "Mock Architect: prioritized T-Bana life safety first, then bridge routing, then waterfront stabilization.",
        }
    elif role == "critic":
        out = {
            "flaw_1": "Access points for underground ingress may be incomplete without a rapid survey of secondary entrances.",
            "flaw_2": "Traffic diversion could bottleneck emergency vehicles if not coordinated with police dispatch in real time.",
            "alternative_1": "Run a 15-minute entrance sweep using station staff + CCTV, then update closure list before pumping operations.",
            "alternative_2": "Establish a dedicated emergency lane and dynamic signal plan on diversion routes with police traffic control.",
            "verdict": "APPROVE",
            "critic_feedback": "Plan is sound; ensure a rapid sweep of all T-Bana entrances and coordinate live traffic control to prevent EMS delays.",
            "status": "VALIDATED",
            "reasoning": "Mock Critic: provided two concrete risks plus mitigations; approved with conditions for safety.",
        }
    else:
        # Specialist (or unknown): nudge STUCK/REVIEW forward safely.
        out = {
            "status": "REVIEW",
            "reasoning": "Mock Specialist: advancing the task to keep the demo swarm moving without external dependencies.",
        }

    out["latency_ms"] = round((time.perf_counter() - start) * 1000)
    return out


# -----------------------------------------------------------------------------
# Seed blackboard with exemplar task (optional)
# -----------------------------------------------------------------------------

async def seed_exemplar_task(redis_url: str) -> None:
    """Insert the exemplar task: Slussen rising water (TODO)."""
    r = get_async_redis(redis_url)
    task = BlackboardTask(
        id="001",
        status=TaskStatus.TODO,
        location="Slussen",
        raw_data={"issue": "Rising water", "source": "exemplar"},
        timestamp=time.time(),
    )
    await r.set(f"{BLACKBOARD_PREFIX}{task.id}", task.to_redis_value())
    await r.aclose()


# -----------------------------------------------------------------------------
# Run full swarm: Scout, Architect, Critic, Specialist
# -----------------------------------------------------------------------------

async def run_swarm(redis_url: str, seed: bool = True) -> None:
    """Start all four agents concurrently; each polls Redis and runs until interrupted."""
    if seed:
        await seed_exemplar_task(redis_url)

    agents = [
        BaseAgent("scout", redis_url=redis_url),
        BaseAgent("architect", redis_url=redis_url),
        BaseAgent("critic", redis_url=redis_url),
        BaseAgent("specialist", redis_url=redis_url),
    ]

    async def llm_invoker(agent: BaseAgent, system_prompt: str, user_message: str) -> dict[str, Any]:
        if os.getenv("SYNTHETICA_OFFLINE", "").lower() in ("1", "true", "yes") or not GOOGLE_API_KEY:
            return await invoke_mock_llm(agent, system_prompt, user_message)
        return await invoke_gemini(agent, system_prompt, user_message)

    tasks = [asyncio.create_task(agent.run(llm_invoker=llm_invoker)) for agent in agents]
    try:
        run_seconds = float(os.getenv("SYNTHETICA_RUN_SECONDS", "0") or "0")
        if run_seconds > 0:
            await asyncio.sleep(run_seconds)
            for a in agents:
                a.stop()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            if os.getenv("SYNTHETICA_PRINT_FINAL", "1").lower() in ("1", "true", "yes"):
                r = get_async_redis(redis_url)
                try:
                    raw = await r.get(f"{BLACKBOARD_PREFIX}001")
                finally:
                    await r.aclose()
                if raw:
                    try:
                        obj = json.loads(raw)
                        safe = json.dumps(obj, ensure_ascii=True)
                    except Exception:
                        safe = raw.encode("utf-8", errors="backslashreplace").decode("utf-8")
                    print("FINAL_TASK_001=", safe)
            return

        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for a in agents:
            a.stop()
        raise


def main() -> None:
    # Auto-fallback to local demo mode if Gemini key isn't set.
    if not GOOGLE_API_KEY and not os.getenv("SYNTHETICA_OFFLINE"):
        os.environ["SYNTHETICA_OFFLINE"] = "1"

    # Auto-fallback to in-memory Redis if Redis isn't available.
    redis_url = REDIS_URL
    if not redis_url.lower().startswith(("memory://", "fakeredis://")):
        try:
            async def _probe() -> None:
                r = Redis.from_url(redis_url, decode_responses=True)
                try:
                    await r.ping()
                finally:
                    await r.aclose()

            asyncio.run(_probe())
        except Exception:
            redis_url = "memory://"

    asyncio.run(run_swarm(redis_url, seed=SYNTHETICA_SEED))


if __name__ == "__main__":
    main()
