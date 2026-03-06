import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Third-party imports
from redis.asyncio import Redis
import google.generativeai as genai

# Try to import Vertex AI (Enterprise version)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig as VertexConfig
    HAS_VERTEX = True
except ImportError:
    HAS_VERTEX = False

# Local Synthetica imports
from config import GEMINI_MODEL, GEMINI_TIMEOUT_SEC, GOOGLE_API_KEY, REDIS_URL
from engine import BLACKBOARD_PREFIX, BaseAgent, get_async_redis
from models import BlackboardTask, TaskStatus
from prompts import SYSTEM_PROMPTS

# -----------------------------------------------------------------------------
# UNIVERSAL LLM INVOKER (Vertex AI or Google AI Studio)
# -----------------------------------------------------------------------------

async def invoke_gemini(
    agent: BaseAgent,
    system_instruction: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Connects to Google. 
    It checks for GCP_PROJECT_ID first (Vertex AI).
    If not found, it uses GOOGLE_API_KEY (AI Studio).
    """
    start_time = time.perf_counter()
    project_id = os.getenv("GCP_PROJECT_ID")
    
    try:
        # PATH 1: VERTEX AI (Enterprise)
        if HAS_VERTEX and project_id:
            vertexai.init(project=project_id, location=os.getenv("GCP_LOCATION", "us-central1"))
            model = GenerativeModel(
                os.getenv("GEMINI_MODEL", "gemini-1.5-flash"), 
                system_instruction=[system_instruction]
            )
            
            # Run in thread to keep the swarm heartbeats moving
            response = await asyncio.to_thread(
                lambda: model.generate_content(
                    user_message,
                    generation_config=VertexConfig(
                        response_mime_type="application/json",
                        temperature=0.3
                    )
                )
            )
            raw_text = response.text

        # PATH 2: GOOGLE AI STUDIO (Standard API Key)
        elif GOOGLE_API_KEY:
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                system_instruction=system_instruction
            )
            
            response = await asyncio.to_thread(
                lambda: model.generate_content(
                    user_message,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.3}
                )
            )
            raw_text = response.text
        
        else:
            raise RuntimeError("ERROR: No API Key or GCP Project ID found in .env")

        # Calculate latency for the judges
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Parse the JSON and add the latency metric
        res_dict = json.loads(raw_text)
        res_dict["latency_ms"] = latency_ms
        return res_dict

    except Exception as e:
        print(f"--- API ERROR in {agent.role.upper()}: {e} ---")
        return {
            "error": str(e),
            "reasoning": "Fallback due to connection error.",
            "latency_ms": 0,
        }


async def invoke_gemini_offline(
    agent: BaseAgent,
    system_instruction: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Offline / mock LLM path.

    This lets the swarm run end‑to‑end without calling external APIs.
    It fabricates deterministic JSON responses that respect the expected
    contract for each role (status transitions, plan_steps, critic_feedback,
    metadata, reasoning, latency_ms).
    """
    try:
        task = BlackboardTask.model_validate_json(user_message)
    except Exception:
        # If we somehow can't parse, just return a generic reasoning blob.
        return {
            "status": "TODO",
            "reasoning": "Offline mock: unable to parse task payload.",
            "latency_ms": 1,
        }

    role = agent.role.lower()

    if role == "scout":
        return {
            "status": "NEEDS_PLAN",
            "metadata": {
                "severity": "High",
                "type": "Flood",
                "critical_infrastructure": [
                    "Slussenkajen",
                    "Gamla Stan T-Bana",
                    "Centralbron",
                ],
                "observed_trend": "Rising",
                "summary": f"Synthetic flood intelligence for {task.location or 'unknown location'}.",
            },
            "risk_level": task.risk_level or 8,
            "reasoning": "Offline mock: SCOUT normalized the raw report and assessed a high‑risk flood scenario.",
            "latency_ms": 5,
        }

    if role == "architect":
        return {
            "status": "REVIEW",
            "plan_steps": [
                "Conduct rapid assessment and evacuate Gamla Stan T-Bana platforms.",
                "Establish controlled access and emergency lanes across Centralbron.",
                "Stabilize Slussenkajen waterfront and coordinate ferry/shoreline safety.",
            ],
            "reasoning": "Offline mock: ARCHITECT produced a 3‑step tactical plan prioritizing life safety, mobility, and stabilization.",
            "latency_ms": 5,
        }

    if role == "critic":
        return {
            "status": "VALIDATED",
            "critic_feedback": (
                "Offline mock: Plan checked for electrical hazards, flood progression, and crowd crush risk. "
                "No blocking flaws identified; proceed with heightened monitoring."
            ),
            "reasoning": "Offline mock: CRITIC adversarially reviewed the plan and approved it for execution.",
            "latency_ms": 5,
        }

    if role == "specialist":
        # Specialist mainly coordinates takeovers; keep status as‑is but provide reasoning.
        return {
            "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
            "reasoning": "Offline mock: SPECIALIST is monitoring heartbeats and stands ready to adopt missing roles.",
            "latency_ms": 2,
        }

    # Fallback for unknown roles
    return {
        "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
        "reasoning": f"Offline mock: generic handler for role '{role}'.",
        "latency_ms": 1,
    }

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------

def main() -> None:
    # 1. Parse which role this container is playing
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", type=str, default="scout", help="scout, architect, critic, or specialist")
    args = parser.parse_args()

    # 2. Check if we should run in Mock/Offline mode
    is_offline = os.getenv("SYNTHETICA_OFFLINE", "").lower() in ("1", "true", "yes")
    
    # 3. Create the Agent Node
    # Every node uses BaseAgent (Vulture Protocol is built-in there)
    agent = BaseAgent(args.role, redis_url=REDIS_URL)
    
    print(f"🚀 SYNTHETICA SWARM NODE: {args.role.upper()} ACTIVATED")
    
    # Check connection type for logs
    if is_offline:
        print("📝 MODE: OFFLINE (Using Mock Responses)")
    elif os.getenv("GCP_PROJECT_ID"):
        print(f"🌐 MODE: VERTEX AI ({os.getenv('GCP_PROJECT_ID')})")
    else:
        print("🌐 MODE: GOOGLE AI STUDIO (Standard API)")

    # 4. Start the autonomous loop
    llm_invoker = invoke_gemini_offline if is_offline else invoke_gemini

    try:
        asyncio.run(agent.run(llm_invoker=llm_invoker))
    except KeyboardInterrupt:
        print(f"Stopping {args.role}...")
        agent.stop()
    except Exception as e:
        print(f"FATAL SWARM ERROR: {e}")

if __name__ == "__main__":
    main()