import json
import time

import redis


BLACKBOARD_PREFIX = "blackboard:task:"


def build_initial_task() -> dict:
    """
    Build a payload that matches the Synthetica BlackboardTask schema.

    Agents expect:
    - key pattern: blackboard:task:{id}
    - fields: id, status, location, raw_data, plan_steps, critic_feedback,
      reasoning, assigned_agent, timestamp, risk_level
    """
    now = time.time()
    return {
        "id": "TASK_001",
        "status": "TODO",  # This triggers the SCOUT
        "location": "Slussen/Gamla Stan",
        "raw_data": {
            "source": "Stockholm City Sensors",
            "timestamp": now,
            "description": (
                "CRITICAL: Water levels rising rapidly at Slussenkajen. "
                "Gamla Stan T-Bana station reporting seepage on platform level. "
                "Approximately 300 people currently in the station area."
            ),
        },
        "plan_steps": [],
        "critic_feedback": None,
        "reasoning": None,
        "assigned_agent": None,
        "timestamp": now,
        "risk_level": 8,
    }


def main() -> None:
    # Connect to the Blackboard on your host machine
    # (Docker maps container port 6379 -> localhost:6379)
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    task = build_initial_task()
    key = f"{BLACKBOARD_PREFIX}{task['id']}"
    r.set(key, json.dumps(task))

    # Avoid emoji here so Windows console encodings don't explode.
    print("Emergency Task Injected into Synthetica Blackboard!")
    print(f"Task ID: {task['id']}")
    print(f"Redis Key: {key}")
    print("Check your Docker agent logs to watch the swarm react.")


if __name__ == "__main__":
    main()