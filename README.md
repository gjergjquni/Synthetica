## Synthetica Swarm — Multi‑Agent Crisis Blackboard

This repo wraps the upstream `Synthetica` swarm into a Docker‑based, Redis‑backed multi‑agent system (Scout, Architect, Critic, Specialist) orchestrated via Docker Compose.

### Architecture

- **Blackboard (Redis)**: Single source of truth. All tasks live under `blackboard:task:{id}` as strict `BlackboardTask` JSON payloads.
- **Agents (Docker containers)**:
  - `scout` → consumes `TODO`, enriches and moves to `NEEDS_PLAN`.
  - `architect` → turns `NEEDS_PLAN` into `plan_steps`, moves to `REVIEW`.
  - `critic` → validates safety, moves to `VALIDATED` or back to `REVIEW`.
  - `specialist` → runs the Vulture Protocol, adopting missing roles and rescuing `STUCK` tasks.
- **Orchestrator (docker‑compose)**: Boots Redis plus four agents from a shared image built from `Synthetica-upstream/synthetica`.

### Local Python dependencies (host)

If you want to use the helper scripts (`seed_swarm.py`, `test_connection.py`, `inspect_blackboard.py`) on your host:

```bash
pip install -r Synthetica-upstream/synthetica/requirements.txt
```

### Environment configuration

Copy `.env` (or create one) in the project root with at least:

```bash
GOOGLE_API_KEY=your_api_key_here
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
GEMINI_MODEL=gemini-2.5-pro
GEMINI_TIMEOUT_SEC=60
SYNTHETICA_OFFLINE=false
GCP_PROJECT_ID=your_gcp_project_id   # optional (Vertex)
GCP_LOCATION=us-central1             # optional (Vertex)
```

Docker Compose automatically loads `.env` and passes these into each agent container.

### Running the swarm

From the repo root:

```bash
docker compose up --build
```

This will:

- Start Redis (`swarm_blackboard`) on port `6379` (exposed to your Windows host).
- Build a Python 3.11 image, install Synthetica’s requirements, and run `python main.py --role ...` from `Synthetica-upstream/synthetica` for each agent.

### Seeding an emergency task

With the swarm running, in a new terminal:

```bash
python seed_swarm.py
```

This injects a `BlackboardTask` with ID `TASK_001` at key `blackboard:task:TASK_001` on the Redis blackboard with `status="TODO"`, which the **Scout** will pick up first.

### Inspecting the blackboard

To see how tasks move through the workflow:

```bash
python inspect_blackboard.py
```

You’ll see each task’s ID, status, location, assigned agent, risk level, plan steps, critic feedback, and a truncated reasoning snippet.

### Basic connectivity check

To verify Windows ↔ Docker ↔ Redis plumbing:

```bash
python test_connection.py
```

You should see a “Blackboard is LIVE” message if the Redis container is running and port `6379` is mapped correctly.
