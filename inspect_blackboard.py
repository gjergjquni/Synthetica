import json
import os
import sys
from typing import Any


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
UPSTREAM_PATH = os.path.join(PROJECT_ROOT, "Synthetica-upstream", "synthetica")
if UPSTREAM_PATH not in sys.path:
    sys.path.insert(0, UPSTREAM_PATH)

from engine import BLACKBOARD_PREFIX, get_sync_redis  # type: ignore  # noqa: E402
from models import BlackboardTask  # type: ignore  # noqa: E402


def list_tasks() -> list[BlackboardTask]:
    """Return all tasks currently stored on the Synthetica blackboard."""
    r = get_sync_redis()
    if r is None:
        raise RuntimeError("Redis client not available. Install dependencies from requirements.txt.")

    out: list[BlackboardTask] = []
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match=f"{BLACKBOARD_PREFIX}*", count=100)
        for key in keys:
            raw = r.get(key)
            if not raw:
                continue
            try:
                out.append(BlackboardTask.from_redis_value(raw))
            except Exception:
                # If a payload is malformed, show raw JSON for debugging instead of crashing.
                print(f"⚠️ Could not parse task at {key}, raw value:")
                try:
                    print(json.dumps(json.loads(raw), indent=2))
                except Exception:
                    print(raw)
        if cursor == 0:
            break
    return out


def main() -> None:
    tasks = list_tasks()
    if not tasks:
        print("No Synthetica tasks found on the blackboard.")
        return

    print(f"Found {len(tasks)} task(s) on the blackboard:\n")
    for t in tasks:
        print(f"- ID: {t.id}")
        print(f"  Status: {t.status}")
        print(f"  Location: {t.location}")
        print(f"  Assigned Agent: {t.assigned_agent}")
        print(f"  Risk Level: {t.risk_level}")
        if t.plan_steps:
            print("  Plan Steps:")
            for i, step in enumerate(t.plan_steps, start=1):
                print(f"    {i}. {step}")
        if t.critic_feedback:
            print(f"  Critic Feedback: {t.critic_feedback}")
        if t.reasoning:
            print("  Reasoning (truncated):")
            snippet = (t.reasoning or "")[:400]
            ellipsis = "..." if len(t.reasoning or "") > 400 else ""
            print(f"    {snippet}{ellipsis}")
        print()


if __name__ == "__main__":
    main()
