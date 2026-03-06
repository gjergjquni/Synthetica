"""
Synthetica — Blackboard Engine & Vulture Protocol
=================================================
BaseAgent, heartbeat mechanism, autonomous takeover (Vulture Protocol),
Role Recovery, structured logging to Redis stream swarm_telemetry, and
Critical Incident logging to swarm:incidents. Fully asynchronous (asyncio + redis.asyncio).
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

import redis.asyncio as redis

from models import BlackboardTask, Heartbeat, TaskStatus
from prompts import CORE_ROLES, SYSTEM_PROMPTS


def _is_memory_redis_url(redis_url: str) -> bool:
    return redis_url.lower().startswith("memory://") or redis_url.lower().startswith("fakeredis://")


_FAKE_REDIS_SERVER = None


def get_async_redis(redis_url: str) -> Any:
    """
    Build an asyncio Redis client.

    - redis://...      -> real Redis (default)
    - memory://        -> in-process FakeRedis (shared across agents)
    - fakeredis://...  -> alias for memory://
    """
    if _is_memory_redis_url(redis_url):
        global _FAKE_REDIS_SERVER
        try:
            import fakeredis.aioredis  # type: ignore
            import fakeredis  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "In-memory Redis requested but fakeredis is not installed. "
                "Run: pip install -r requirements.txt"
            ) from e

        if _FAKE_REDIS_SERVER is None:
            _FAKE_REDIS_SERVER = fakeredis.FakeServer()
        return fakeredis.aioredis.FakeRedis(server=_FAKE_REDIS_SERVER, decode_responses=True)

    return redis.from_url(redis_url, decode_responses=True)


def _build_redis_client(redis_url: str) -> Any:
    # Backwards-compatible alias for internal callers.
    return get_async_redis(redis_url)


# -----------------------------------------------------------------------------
# Redis key conventions
# -----------------------------------------------------------------------------

BLACKBOARD_PREFIX = "blackboard:task:"
HEARTBEAT_PREFIX = "heartbeat:"
SWARM_TELEMETRY_STREAM = "swarm_telemetry"
SWARM_INCIDENTS_KEY = "swarm:incidents"
HEARTBEAT_TTL_SEC = 5
HEARTBEAT_INTERVAL_SEC = 2.0
TASK_POLL_INTERVAL_SEC = 1.0
GEMINI_TIMEOUT_SEC = 60.0


# -----------------------------------------------------------------------------
# BaseAgent — heartbeat + task polling + role switching
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Structured logging (mirrors to Redis stream swarm_telemetry for judges)
# -----------------------------------------------------------------------------

_logger = logging.getLogger("synthetica")


async def _emit_telemetry(redis_client: redis.Redis, role: str, level: str, message: str, **extra: Any) -> None:
    """Push a structured log entry to Redis stream swarm_telemetry."""
    try:
        entry = {
            "role": role,
            "level": level,
            "message": message,
            "timestamp": time.time(),
            **{k: str(v) for k, v in extra.items()},
        }
        await redis_client.xadd(SWARM_TELEMETRY_STREAM, {"payload": json.dumps(entry)}, maxlen=10000)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# BaseAgent — heartbeat + task polling + role switching + Role Recovery
# -----------------------------------------------------------------------------


class BaseAgent:
    """
    Single agent in the swarm. Maintains heartbeat, polls for tasks matching
    its role (or adopted role), adopts missing core roles (Vulture Protocol),
    logs Critical Incidents to swarm:incidents, and releases adopted role when
    the original agent comes back online (Role Recovery).
    """

    def __init__(
        self,
        role: str,
        redis_url: str = "redis://localhost:6379",
        task_poll_interval: float = TASK_POLL_INTERVAL_SEC,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SEC,
        heartbeat_ttl: int = HEARTBEAT_TTL_SEC,
    ):
        self.role = role.lower()
        self.redis_url = redis_url
        self.task_poll_interval = task_poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_ttl = heartbeat_ttl
        self._redis: Optional[redis.Redis] = None
        # Current effective role (may be adopted when acting as another role)
        self._effective_role = self.role
        self._running = False
        self._started_at = time.time()
        # Allow heartbeats to appear before any takeover decisions.
        self._startup_grace_sec = 3.0

    async def _log(self, level: str, message: str, **extra: Any) -> None:
        """Structured log: Python logging + mirror to Redis stream swarm_telemetry."""
        getattr(_logger, level, _logger.info)(f"[{self.role}] {message}", extra=extra)
        r = await self._get_redis()
        await _emit_telemetry(r, self.role, level, message, **extra)

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = get_async_redis(self.redis_url)
        return self._redis

    # -----------------------------------------
    # Heartbeat
    # -----------------------------------------

    async def _write_heartbeat(self) -> None:
        """Write this agent's heartbeat to heartbeat:{role} with TTL. Run every 2s."""
        r = await self._get_redis()
        # Heartbeats must be keyed by the agent's real role identity.
        # If we key by adopted role, we "lose" the original heartbeat and trigger takeover storms.
        key = f"{HEARTBEAT_PREFIX}{self.role}"
        hb = Heartbeat(
            agent_name=self.role,
            status="alive",
            unix_timestamp=time.time(),
        )
        await r.setex(key, self.heartbeat_ttl, hb.to_redis_value())

    async def _heartbeat_loop(self) -> None:
        """Background loop: emit heartbeat every heartbeat_interval seconds."""
        while self._running:
            try:
                await self._write_heartbeat()
            except Exception as e:
                await self._log("warning", f"Heartbeat error: {e}")
            await asyncio.sleep(self.heartbeat_interval)

    # -----------------------------------------
    # Vulture Protocol — detect missing roles, adopt and claim STUCK
    # -----------------------------------------

    async def _get_missing_core_roles(self) -> list[str]:
        """Check heartbeat:* for CORE_ROLES; return list of roles with no valid heartbeat."""
        r = await self._get_redis()
        missing = []
        for role in CORE_ROLES:
            key = f"{HEARTBEAT_PREFIX}{role}"
            if not await r.exists(key):
                missing.append(role)
        return missing

    async def _claim_stuck_tasks_for_role(self, for_role: str) -> list[str]:
        """
        Find all tasks with status STUCK (or orphaned IN_PROGRESS/NEEDS_PLAN for that role)
        and re-assign to this agent. Returns list of task ids claimed.
        """
        r = await self._get_redis()
        claimed = []
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=f"{BLACKBOARD_PREFIX}*", count=100)
            for key in keys:
                try:
                    raw = await r.get(key)
                    if not raw:
                        continue
                    task = BlackboardTask.from_redis_value(raw)
                    # Claim STUCK, or orphaned IN_PROGRESS/NEEDS_PLAN that belonged to for_role
                    if task.status == TaskStatus.STUCK:
                        pass
                    elif task.assigned_agent == for_role and task.status in (
                        TaskStatus.IN_PROGRESS,
                        TaskStatus.NEEDS_PLAN,
                        TaskStatus.REVIEW,
                    ):
                        pass
                    else:
                        continue
                    task.assigned_agent = self.role
                    if task.status != TaskStatus.STUCK:
                        task.status = TaskStatus.STUCK  # Move to STUCK so adopter can re-process
                    task.timestamp = time.time()
                    await r.set(key, task.to_redis_value())
                    claimed.append(task.id)
                except Exception as e:
                    await self._log("warning", f"Claim task error for key {key}: {e}")
            if cursor == 0:
                break
        return claimed

    async def _log_critical_incident(self, adopted_role: str, claimed_ids: list[str]) -> None:
        """Log a Critical Incident to swarm:incidents (for judges and ops)."""
        r = await self._get_redis()
        incident = {
            "event": "vulture_takeover",
            "adopted_role": adopted_role,
            "by_agent": self.role,
            "claimed_task_ids": claimed_ids,
            "timestamp": time.time(),
        }
        try:
            await r.rpush(SWARM_INCIDENTS_KEY, json.dumps(incident))
        except Exception:
            pass

    async def _try_vulture_takeover(self) -> Optional[str]:
        """
        If any core role is missing, adopt the first missing role, claim its STUCK tasks,
        log a Critical Incident to swarm:incidents, and return the adopted role.
        """
        missing = await self._get_missing_core_roles()
        if not missing:
            return None
        adopt = missing[0]
        claimed = await self._claim_stuck_tasks_for_role(adopt)
        await self._log_critical_incident(adopt, claimed)
        self._effective_role = adopt
        return adopt

    def _release_adopted_role(self) -> None:
        """Revert to Observer state when original agent comes back online (Role Recovery)."""
        self._effective_role = self.role

    async def _is_role_back_online(self, role: str) -> bool:
        """True if the given role has a valid heartbeat (for Role Recovery)."""
        r = await self._get_redis()
        n = await r.exists(f"{HEARTBEAT_PREFIX}{role}")
        return bool(n)

    # -----------------------------------------
    # Task polling — find TODO / NEEDS_PLAN / REVIEW by role
    # -----------------------------------------

    async def _task_matches_role(self, task: BlackboardTask) -> bool:
        """True if this task is appropriate for current effective role."""
        s = task.status
        if self._effective_role == "scout":
            return s == TaskStatus.TODO
        if self._effective_role == "architect":
            return s == TaskStatus.NEEDS_PLAN or s == TaskStatus.STUCK
        if self._effective_role == "critic":
            return s == TaskStatus.REVIEW
        if self._effective_role == "specialist":
            missing = await self._get_missing_core_roles()
            return s in (TaskStatus.STUCK, TaskStatus.REVIEW) or (
                s in (TaskStatus.NEEDS_PLAN, TaskStatus.TODO) and len(missing) > 0
            )
        return False

    async def _fetch_pending_tasks(self) -> list[BlackboardTask]:
        """Scan blackboard for tasks that match this agent's (effective) role."""
        r = await self._get_redis()
        out = []
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=f"{BLACKBOARD_PREFIX}*", count=100)
            for key in keys:
                try:
                    raw = await r.get(key)
                    if not raw:
                        continue
                    task = BlackboardTask.from_redis_value(raw)
                    if await self._task_matches_role(task):
                        out.append(task)
                except Exception:
                    continue
            if cursor == 0:
                break
        return out

    async def _update_task(self, task_id: str, updates: dict[str, Any]) -> None:
        """Read-modify-write task on blackboard with given updates."""
        r = await self._get_redis()
        key = f"{BLACKBOARD_PREFIX}{task_id}"
        raw = await r.get(key)
        if not raw:
            return
        task = BlackboardTask.from_redis_value(raw)
        for k, v in updates.items():
            if hasattr(task, k):
                setattr(task, k, v)
        task.timestamp = time.time()
        task.assigned_agent = self.role
        await r.set(key, task.to_redis_value())

    # -----------------------------------------
    # LLM invocation (override in main.py with Groq)
    # -----------------------------------------

    async def invoke_llm(self, system_prompt: str, user_message: str) -> dict[str, Any]:
        """
        Call Groq with response_format=json_object. Must return dict with at least "reasoning".
        Override or call from main.py where Groq client is configured.
        """
        raise NotImplementedError("Use main.run_agent_loop which injects Groq client")

    # -----------------------------------------
    # Main loop: heartbeat + vulture check + task poll + process
    # -----------------------------------------

    async def run(
        self,
        llm_invoker: Optional[Any] = None,
    ) -> None:
        """
        Run this agent indefinitely: heartbeat loop + poll for tasks, process with LLM,
        and run Vulture Protocol if specialist or if we detect missing core role.
        llm_invoker: async (agent, system_prompt, user_message) -> dict (with reasoning, etc.)
        """
        self._running = True
        asyncio.create_task(self._heartbeat_loop())

        while self._running:
            try:
                # Role Recovery: if we adopted a role and the original agent is back online, release
                if self._effective_role != self.role:
                    if await self._is_role_back_online(self._effective_role):
                        await self._log("info", f"Role Recovery: {self._effective_role} back online; reverting to Observer.")
                        self._release_adopted_role()
                # Specialist only: check for missing roles and adopt if needed.
                # Non-specialists should never trigger takeover logic; otherwise startup can thrash.
                if self.role == "specialist" and (time.time() - self._started_at) >= self._startup_grace_sec:
                    missing = await self._get_missing_core_roles()
                    if missing and self._effective_role == self.role:
                        adopted = await self._try_vulture_takeover()
                        if adopted:
                            await self._log("warning", f"Vulture: adopted role [{adopted}]")

                # Fetch tasks for current (possibly adopted) role
                tasks = await self._fetch_pending_tasks()
                if not tasks:
                    await asyncio.sleep(self.task_poll_interval)
                    continue

                # Process first matching task (one at a time for clarity)
                task = tasks[0]
                system_prompt = SYSTEM_PROMPTS.get(self._effective_role)
                if not system_prompt or not llm_invoker:
                    await asyncio.sleep(self.task_poll_interval)
                    continue

                # Mark IN_PROGRESS
                await self._update_task(
                    task.id,
                    {"status": TaskStatus.IN_PROGRESS, "assigned_agent": self.role},
                )

                user_message = task.model_dump_json()
                try:
                    result = await asyncio.wait_for(
                        llm_invoker(self, system_prompt, user_message),
                        timeout=GEMINI_TIMEOUT_SEC,
                    )
                except asyncio.TimeoutError:
                    await self._update_task(task.id, {"status": task.status, "assigned_agent": None})
                    await self._log("error", f"LLM timeout for task {task.id}")
                    await asyncio.sleep(self.task_poll_interval)
                    continue
                except Exception as e:
                    await self._update_task(task.id, {"status": task.status, "assigned_agent": None})
                    await self._log("error", f"LLM error for task {task.id}: {e}")
                    await asyncio.sleep(self.task_poll_interval)
                    continue

                # Apply result to blackboard (status, plan_steps, metadata, critic_feedback, reasoning, latency_ms)
                updates = {"reasoning": result.get("reasoning"), "assigned_agent": self.role}
                if "status" in result:
                    try:
                        updates["status"] = TaskStatus(result["status"])
                    except ValueError:
                        pass
                if "plan_steps" in result:
                    updates["plan_steps"] = result["plan_steps"]
                if "critic_feedback" in result:
                    updates["critic_feedback"] = result["critic_feedback"]
                # Shared memory / per-task timeline
                base_raw = task.raw_data or {}
                timeline = list(base_raw.get("timeline", []))
                event = {
                    "timestamp": time.time(),
                    "agent": self.role,
                    "effective_role": self._effective_role,
                    "status_after": str(updates.get("status", task.status)),
                    "summary": (result.get("reasoning") or "")[:200],
                }
                timeline.append(event)

                raw_data = {**base_raw, "timeline": timeline}

                if "metadata" in result and isinstance(base_raw, dict):
                    raw_data["metadata"] = result["metadata"]

                if "latency_ms" in result:
                    raw_data["latency_ms"] = result["latency_ms"]

                # Simple shared memory of each agent's latest reasoning
                agent_memory = dict(base_raw.get("agent_memory", {}))
                if result.get("reasoning"):
                    agent_memory[self.role] = result["reasoning"]
                raw_data["agent_memory"] = agent_memory

                updates["raw_data"] = raw_data

                await self._update_task(task.id, updates)
                latency_ms = result.get("latency_ms")
                await self._log(
                    "info",
                    f"Processed task {task.id} -> {updates.get('status', task.status)}",
                    task_id=task.id,
                    status=str(updates.get("status", task.status)),
                    latency_ms=str(latency_ms) if latency_ms is not None else "",
                )

            except Exception as e:
                await self._log("error", f"Loop error: {e}")
            await asyncio.sleep(self.task_poll_interval)

    def stop(self) -> None:
        self._running = False


# -----------------------------------------
# Sync helper for non-async callers (e.g. seeding blackboard)
# -----------------------------------------

def get_sync_redis(redis_url: str = "redis://localhost:6379"):
    """Synchronous Redis for scripting; use redis.asyncio in agents."""
    try:
        import redis as redis_sync
        return redis_sync.from_url(redis_url, decode_responses=True)
    except ImportError:
        return None
