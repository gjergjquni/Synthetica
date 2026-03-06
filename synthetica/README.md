# Synthetica — Decentralized Crisis Management Swarm (Google Cloud / Gemini)

Resilient, multi-agent autonomous swarm for flood disaster response (Stockholm Slussen). **Blackboard Architecture** with Redis (Google Memorystore–ready), **Vulture Protocol** with Critical Incident logging and **Role Recovery**, and **Gemini 1.5 Flash** for inference.

## Architecture

- **Redis**: Blackboard (`blackboard:task:*`), heartbeats (`heartbeat:{role}`) TTL 5s, telemetry stream `swarm_telemetry`, incidents list `swarm:incidents`.
- **Agents**: Scout → Architect → Critic; Specialist monitors health, adopts missing roles, logs incidents, and releases when the original agent comes back (Role Recovery).
- **LLM**: Gemini 1.5 Flash via `google-generativeai`; `system_instruction` for personas, `response_mime_type: application/json`; every response includes `reasoning` and `latency_ms`.

## Setup

```bash
cd synthetica
pip install -r requirements.txt
```

### Environment (cloud-native)

- `GOOGLE_API_KEY` — **required** for Gemini.
- `REDIS_HOST` — default `localhost` (use Memorystore endpoint in GCP).
- `REDIS_PORT` — default `6379`.
- `REDIS_PASSWORD` — optional; omit for passwordless VPC (e.g. Memorystore).
- `REDIS_URL` — override full URL if needed (otherwise built from host/port/password).
- `GEMINI_MODEL` — default `gemini-1.5-flash`.
- `GEMINI_TIMEOUT_SEC` — default `60`.
- `SYNTHETICA_SEED` — set to `0` to skip seeding the exemplar task.

## Run

Start Redis (or use Google Memorystore), then:

```bash
python main.py
```

Runs Scout, Architect, Critic, and Specialist concurrently. Each agent writes heartbeats every 2s, logs to the `swarm_telemetry` Redis stream (with `latency_ms` where applicable), and the Specialist runs the Vulture Protocol (takeover + Critical Incident to `swarm:incidents`) and Role Recovery (release when the original agent is back online).

## Exemplar Flow

1. Redis has task `001` (Slussen, rising water, TODO).
2. **Scout** enriches with Stockholm context (Slussenkajen, Gamla Stan Subway, Centralbron) → `NEEDS_PLAN`, `metadata`, `risk_level`.
3. **Architect** produces 3 steps with **T-Bana #1 weight** → `plan_steps`, `REVIEW`.
4. **Critic** validates → `VALIDATED` or `REVIEW`.
5. If Architect is killed, **Specialist** detects missing heartbeat, logs a Critical Incident to `swarm:incidents`, adopts Architect, claims STUCK tasks; when Architect restarts, Specialist sees heartbeat and reverts to Observer (Role Recovery).

## Project Layout

- `config.py` — Cloud-native config: `REDIS_HOST`, `REDIS_PORT`, `GOOGLE_API_KEY`, `build_redis_url()` (Memorystore-ready).
- `models.py` — Pydantic V2: `TaskStatus`, `BlackboardTask` (with `risk_level` 1–10 validator), `Heartbeat`.
- `prompts.py` — System prompts (Scout: Stockholm infrastructure; Architect: T-Bana #1 weight).
- `engine.py` — `BaseAgent`, heartbeats, Vulture Protocol, Role Recovery, telemetry stream, Critical Incidents; fully async.
- `main.py` — Gemini 1.5 Flash, `system_instruction`, JSON mode, `latency_ms`; swarm entry point.

## Observability (for judges)

- **Structured logging** mirrors to Redis stream **`swarm_telemetry`** (role, level, message, timestamp, task_id, latency_ms).
- **Critical Incidents** are appended to Redis list **`swarm:incidents`** on Vulture takeover (event, adopted_role, by_agent, claimed_task_ids, timestamp).
- Every agent response includes **`latency_ms`** (Gemini processing time).

## High Availability

- Heartbeats with short TTL; dead agents detected within seconds.
- Specialist adopts missing core roles and claims STUCK/orphaned tasks; logs incident to `swarm:incidents`.
- **Role Recovery**: when the original agent’s heartbeat reappears, Specialist releases the role and reverts to Observer.
- API timeouts release the task so other agents can retry.
