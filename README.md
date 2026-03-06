## Synthetica Swarm  Multi‑Agent Crisis Blackboard

Synthetica is a **multi‑agent crisis decision system** powered by Gemini, running on a **Redis blackboard** and orchestrated with **Docker Compose**.  
This repo wraps the upstream `Synthetica` swarm and adds a clean, batteries‑included way to run, seed, and inspect emergencies from your local machine.

---

### High‑level architecture

- **Blackboard (Redis)**  
  - Single source of truth for incidents.  
  - Tasks live under keys like `blackboard:task:{id}` as strict `BlackboardTask` JSON payloads.

- **Agents (Docker containers, see `prompts.py`)**  
  - **`scout`**: Normalizes raw reports, adds metadata, and moves tasks from `TODO` → `NEEDS_PLAN`.  
  - **`architect`**: Designs a 3‑step operational plan and moves tasks to `REVIEW`.  
  - **`critic`**: Performs adversarial safety review and moves tasks to `VALIDATED` (or back to `REVIEW`).  
  - **`specialist`**: Swarm guardian (Vulture Protocol) that watches for `STUCK` tasks and adopts missing roles.

- **Orchestration (`docker-compose.yml`)**  
  - Boots Redis + all four agents from a shared image built from `Synthetica-upstream/synthetica`.  
  - Wires environment variables from `.env` through to the containers.

---

### Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Python 3.11+** on your host if you want to run helper scripts like `seed_swarm.py` and `inspect_blackboard.py`

---

### Local Python dependencies (host)

To use the helper scripts (`seed_swarm.py`, `test_connection.py`, `inspect_blackboard.py`) from your host:

```bash
pip install -r Synthetica-upstream/synthetica/requirements.txt


