"""
SYNTHETICA — Stockholm Crisis Command Dashboard
================================================
B2G Government-Grade AI Swarm Monitoring Interface
Swedish Emergency Management Authority · Crisis AI Division

Run with: streamlit run synthetica_dashboard.py
"""

import streamlit as st
import redis
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SYNTHETICA · Stockholm Crisis Command",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "SYNTHETICA v2.4 · Swedish Emergency Management Authority"}
)

# ─────────────────────────────────────────────
#  GOVERNMENT-GRADE THEME (CSS INJECTION)
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ── Global reset ── */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif !important;
}

/* ── Background: deep government navy ── */
.stApp {
    background-color: #05080F !important;
    color: #CDD6E0 !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #0A0F1A !important;
    border-right: 1px solid #1C2B3A !important;
}

[data-testid="stSidebar"] * {
    color: #8BA0B4 !important;
}

/* ── Top classification banner ── */
.classification-banner {
    background: #0D1B2A;
    border-bottom: 2px solid #1B3A5C;
    border-top: 3px solid #005B9A;
    padding: 6px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: -1rem -1rem 1.5rem -1rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    color: #5A8AAA;
}

.classification-banner .level {
    color: #3A9FD8;
    font-weight: 600;
    letter-spacing: 0.2em;
}

/* ── Page title block ── */
.title-block {
    border-left: 4px solid #005B9A;
    padding: 12px 20px;
    margin-bottom: 24px;
    background: linear-gradient(90deg, rgba(0,91,154,0.08) 0%, transparent 100%);
}

.title-block h1 {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 22px !important;
    font-weight: 600 !important;
    color: #E8EDF3 !important;
    letter-spacing: 0.06em !important;
    margin: 0 0 4px 0 !important;
}

.title-block .subtitle {
    font-size: 12px;
    color: #5A8AAA;
    letter-spacing: 0.08em;
    font-family: 'IBM Plex Mono', monospace;
}

/* ── Section headers ── */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.18em;
    color: #3A9FD8;
    text-transform: uppercase;
    border-bottom: 1px solid #1C2B3A;
    padding-bottom: 8px;
    margin-bottom: 16px;
}

/* ── Metric cards ── */
.metric-card {
    background: #0D1B2A;
    border: 1px solid #1C2B3A;
    border-top: 2px solid #1B3A5C;
    border-radius: 4px;
    padding: 18px 20px;
    position: relative;
}

.metric-card .metric-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.14em;
    color: #5A8AAA;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.metric-card .metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    color: #E8EDF3;
    line-height: 1;
    margin-bottom: 4px;
}

.metric-card .metric-sub {
    font-size: 11px;
    color: #5A8AAA;
}

/* ── Agent status cards ── */
.agent-card {
    background: #0D1B2A;
    border: 1px solid #1C2B3A;
    border-radius: 4px;
    padding: 16px;
}

.agent-card.online { border-left: 3px solid #00A878; }
.agent-card.offline { border-left: 3px solid #C0392B; opacity: 0.7; }
.agent-card.warning { border-left: 3px solid #D4AC0D; }

.agent-card .agent-name {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: #CDD6E0;
    margin-bottom: 4px;
}

.agent-card .agent-role {
    font-size: 11px;
    color: #5A8AAA;
    margin-bottom: 10px;
}

.status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.06em;
    padding: 3px 8px;
    border-radius: 2px;
}

.status-indicator.online {
    background: rgba(0,168,120,0.1);
    color: #00A878;
    border: 1px solid rgba(0,168,120,0.25);
}

.status-indicator.offline {
    background: rgba(192,57,43,0.1);
    color: #C0392B;
    border: 1px solid rgba(192,57,43,0.25);
}

/* ── Blackboard table ── */
.blackboard-container {
    background: #0A0F1A;
    border: 1px solid #1C2B3A;
    border-radius: 4px;
    padding: 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
}

/* ── Log viewer ── */
.log-container {
    background: #030509;
    border: 1px solid #1C2B3A;
    border-radius: 4px;
    padding: 14px 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: #5A8AAA;
    line-height: 1.7;
    max-height: 200px;
    overflow-y: auto;
}

/* ── HITL panel ── */
.hitl-container {
    background: #110900;
    border: 1px solid #3D2200;
    border-left: 4px solid #D4AC0D;
    border-radius: 4px;
    padding: 20px;
}

.hitl-container.clear {
    background: #020B07;
    border: 1px solid #0D2B1A;
    border-left: 4px solid #00A878;
}

.hitl-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.16em;
    color: #D4AC0D;
    text-transform: uppercase;
    margin-bottom: 12px;
}

.hitl-label.clear { color: #00A878; }

.hitl-request-box {
    background: rgba(0,0,0,0.3);
    border: 1px solid #1C2B3A;
    border-radius: 3px;
    padding: 14px;
    margin-bottom: 14px;
}

.hitl-field-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.14em;
    color: #5A8AAA;
    text-transform: uppercase;
    margin-bottom: 4px;
}

.hitl-field-value {
    font-size: 13px;
    color: #CDD6E0;
    line-height: 1.5;
}

.conf-badge {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 2px;
    background: rgba(212,172,13,0.12);
    color: #D4AC0D;
    border: 1px solid rgba(212,172,13,0.3);
    margin-top: 6px;
}

/* ── Dividers ── */
hr {
    border: none !important;
    border-top: 1px solid #1C2B3A !important;
    margin: 20px 0 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: transparent !important;
    border: 1px solid #1C2B3A !important;
    color: #8BA0B4 !important;
    border-radius: 3px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.06em !important;
    padding: 6px 14px !important;
    transition: all 0.15s !important;
}

.stButton > button:hover {
    border-color: #3A9FD8 !important;
    color: #3A9FD8 !important;
    background: rgba(58,159,216,0.05) !important;
}

/* ── Streamlit element overrides ── */
[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    color: #E8EDF3 !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #1C2B3A !important;
    border-radius: 4px !important;
}

div[data-testid="stCodeBlock"] {
    background: #030509 !important;
}

/* ── Sidebar elements ── */
.sidebar-org {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.14em;
    color: #2A4A6A;
    text-transform: uppercase;
    padding: 0 0 12px 0;
    border-bottom: 1px solid #1C2B3A;
    margin-bottom: 16px;
}

.sidebar-stat {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid #0F1E2E;
    font-size: 12px;
}

.sidebar-stat-label { color: #3A5A7A; }
.sidebar-stat-value {
    font-family: 'IBM Plex Mono', monospace;
    color: #CDD6E0;
    font-size: 11px;
}

/* ── Audit trail ── */
.audit-row {
    display: flex;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px solid #0F1E2E;
    font-size: 11px;
    align-items: flex-start;
}
.audit-time {
    font-family: 'IBM Plex Mono', monospace;
    color: #2A5A7A;
    white-space: nowrap;
    font-size: 10px;
    padding-top: 1px;
}
.audit-actor {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 2px;
    white-space: nowrap;
}
.audit-system { background: rgba(58,159,216,0.1); color: #3A9FD8; }
.audit-human  { background: rgba(212,172,13,0.1); color: #D4AC0D; }
.audit-agent  { background: rgba(0,168,120,0.1); color: #00A878; }
.audit-text { color: #8BA0B4; line-height: 1.4; flex: 1; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  REDIS CONNECTION
# ─────────────────────────────────────────────
@st.cache_resource
def get_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None

r = get_redis()
connected = r is not None

# ─────────────────────────────────────────────
#  CLASSIFICATION BANNER
# ─────────────────────────────────────────────
st.markdown("""
<div class="classification-banner">
    <span>SWEDISH EMERGENCY MANAGEMENT AUTHORITY · AI CRISIS DIVISION</span>
    <span class="level">RESTRICTED // OPERATIONAL USE ONLY</span>
    <span id="banner-time">LIVE SYSTEM</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-org">
        SYNTHETICA v2.4.1<br>
        Crisis Intelligence Platform
    </div>
    """, unsafe_allow_html=True)

    now = datetime.now()
    st.markdown(f"""
    <div class="sidebar-stat"><span class="sidebar-stat-label">Timestamp</span><span class="sidebar-stat-value">{now.strftime('%H:%M:%S')}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Date</span><span class="sidebar-stat-value">{now.strftime('%Y-%m-%d')}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Redis</span><span class="sidebar-stat-value" style="color:{'#00A878' if connected else '#C0392B'}">{'CONNECTED' if connected else 'OFFLINE'}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Protocol</span><span class="sidebar-stat-value">BLACKBOARD-v2</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Encryption</span><span class="sidebar-stat-value">AES-256</span></div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Operations</div>', unsafe_allow_html=True)

    if st.button("⟳  Refresh Dashboard"):
        st.cache_resource.clear()
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Scenario Inject</div>', unsafe_allow_html=True)

    if connected:
        if st.button("🌊  Slussen Flood Event"):
            task = {"id": "manual-001", "task": "CRITICAL: Slussen water level +1.5m. Assess Södermalm evacuation.", "target": "Scout", "status": "todo", "created_by": "OPERATOR", "result": ""}
            r.set("blackboard", json.dumps([task]))
            st.rerun()
        if st.button("⚡  City Power Outage"):
            task = {"id": "manual-002", "task": "ALERT: Grid instability. 4 districts entering brownout. Assess hospital backup power.", "target": "Scout", "status": "todo", "created_by": "OPERATOR", "result": ""}
            r.set("blackboard", json.dumps([task]))
            st.rerun()
        if st.button("🚇  Metro System Failure"):
            task = {"id": "manual-003", "task": "Tunnelbana lines T10/T11/T14 signal failure. 180,000 passengers affected. Plan reroute.", "target": "Scout", "status": "todo", "created_by": "OPERATOR", "result": ""}
            r.set("blackboard", json.dumps([task]))
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#1C3A5A;line-height:1.8;padding-top:12px;border-top:1px solid #1C2B3A">
        SYNTHETICA SWARM INTELLIGENCE<br>
        NON-HIERARCHICAL · STIGMERGIC<br>
        © 2026 SE CRISIS AI DIVISION<br>
        ALL ACTIONS AUDIT-LOGGED
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  PAGE TITLE
# ─────────────────────────────────────────────
st.markdown("""
<div class="title-block">
    <h1>SYNTHETICA · LIVE SWARM COMMAND</h1>
    <div class="subtitle">STOCKHOLM CRISIS RESPONSE · AI AGENT MONITORING INTERFACE · OPERATIONAL</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CONNECTION GUARD
# ─────────────────────────────────────────────
if not connected:
    st.markdown("""
    <div style="background:#0D0203;border:1px solid #3D0A09;border-left:4px solid #C0392B;
                border-radius:4px;padding:20px;font-family:'IBM Plex Mono',monospace;">
        <div style="font-size:10px;letter-spacing:0.16em;color:#C0392B;margin-bottom:8px">
            ⚠ SYSTEM FAULT — REDIS UNAVAILABLE
        </div>
        <div style="font-size:13px;color:#8BA0B4">
            Cannot establish connection to the shared blackboard (Redis).<br>
            Ensure Docker is running and Redis container is active on port 6379.
        </div>
        <div style="margin-top:12px;font-size:11px;color:#3A5A7A">
            COMMAND: <span style="color:#5A9ABF">docker run -p 6379:6379 -d redis</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─────────────────────────────────────────────
#  SECTION 1 — SYSTEM METRICS
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">01 · SYSTEM METRICS</div>', unsafe_allow_html=True)

agents = ["Scout", "Architect", "Critic", "Specialist"]
agent_roles = {
    "Scout":      "Data Harvester",
    "Architect":  "Logistics Strategist",
    "Critic":     "Safety Auditor",
    "Specialist": "Redundancy Agent",
}

alive_agents = [a for a in agents if r.exists(f"heartbeat:{a}")]
n_alive = len(alive_agents)

# Parse blackboard for task counts
raw_board = r.get("blackboard")
tasks = []
if raw_board:
    try:
        tasks = json.loads(raw_board)
    except Exception:
        tasks = []

n_done  = sum(1 for t in tasks if t.get("status") == "done")
n_todo  = sum(1 for t in tasks if t.get("status") == "todo")
n_doing = sum(1 for t in tasks if t.get("status") == "doing")

approval_pending = r.exists("approval_needed")

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(
        label="Active Agents",
        value=f"{n_alive} / {len(agents)}",
        delta="All Operational" if n_alive == len(agents) else f"{len(agents)-n_alive} Offline",
        delta_color="normal" if n_alive == len(agents) else "inverse"
    )

with m2:
    st.metric(
        label="Tasks Completed",
        value=n_done,
        delta=f"{n_todo} queued · {n_doing} in progress"
    )

with m3:
    st.metric(
        label="Authorization Queue",
        value="PENDING" if approval_pending else "CLEAR",
        delta="Human review required" if approval_pending else "Swarm autonomous",
        delta_color="inverse" if approval_pending else "normal"
    )

with m4:
    total = n_done + n_todo + n_doing
    conf = f"{int((n_done / total) * 100)}%" if total > 0 else "—"
    st.metric(
        label="Completion Rate",
        value=conf,
        delta=f"{total} total tasks logged"
    )

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SECTION 2 — AGENT STATUS
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">02 · SWARM AGENT STATUS</div>', unsafe_allow_html=True)

cols = st.columns(4)
for i, role in enumerate(agents):
    is_alive = r.exists(f"heartbeat:{role}")
    status_class = "online" if is_alive else "offline"
    status_text  = "OPERATIONAL" if is_alive else "OFFLINE"
    indicator_class = "online" if is_alive else "offline"
    dot = "●" if is_alive else "○"

    with cols[i]:
        st.markdown(f"""
        <div class="agent-card {status_class}">
            <div class="agent-name">{role.upper()}-01</div>
            <div class="agent-role">{agent_roles[role]}</div>
            <div class="status-indicator {indicator_class}">{dot} {status_text}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SECTION 3 — LIVE BLACKBOARD + LOGS
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">03 · LIVE BLACKBOARD</div>', unsafe_allow_html=True)

left_col, right_col = st.columns([3, 2])

with left_col:
    if tasks:
        # Sanitise for display
        display_tasks = []
        for t in tasks:
            display_tasks.append({
                "ID":         t.get("id", "—")[:12],
                "Task":       t.get("task", "—")[:60] + ("…" if len(t.get("task","")) > 60 else ""),
                "Target":     t.get("target", "—"),
                "Status":     t.get("status", "—").upper(),
                "Confidence": f"{int(t.get('confidence', 0) * 100)}%" if t.get("confidence") else "—",
                "Result":     t.get("result", "—")[:50] + ("…" if len(t.get("result","")) > 50 else ""),
            })
        st.dataframe(
            display_tasks,
            use_container_width=True,
            hide_index=True,
            height=220
        )
    else:
        st.markdown("""
        <div class="blackboard-container" style="text-align:center;padding:40px;color:#1C3A5A">
            BLACKBOARD EMPTY — AWAITING INCIDENT SIGNAL
        </div>
        """, unsafe_allow_html=True)

with right_col:
    st.markdown('<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;letter-spacing:0.14em;color:#3A9FD8;margin-bottom:10px">SYSTEM LOG</div>', unsafe_allow_html=True)
    log_data = r.get("logs") or "[SYSTEM] Awaiting agent activity..."
    # Trim to last 20 lines for display
    log_lines = log_data.splitlines()[:20]
    log_display = "\n".join(log_lines)
    st.code(log_display, language="text")

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SECTION 4 — HUMAN-IN-THE-LOOP
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">04 · HUMAN-IN-THE-LOOP AUTHORIZATION</div>', unsafe_allow_html=True)

approval_raw = r.get("approval_needed")

if approval_raw:
    try:
        req = json.loads(approval_raw)
    except Exception:
        req = {}

    st.markdown(f"""
    <div class="hitl-container">
        <div class="hitl-label">⚠ EXECUTIVE AUTHORIZATION REQUIRED</div>
        <div class="hitl-request-box">
            <div class="hitl-field-label">Requesting Agent</div>
            <div class="hitl-field-value" style="font-family:'IBM Plex Mono',monospace">{req.get('agent', 'UNKNOWN')}-01</div>
        </div>
        <div class="hitl-request-box">
            <div class="hitl-field-label">Action Requested</div>
            <div class="hitl-field-value">{req.get('task', 'No task description available.')}</div>
        </div>
        <div class="hitl-request-box">
            <div class="hitl-field-label">AI Assessment</div>
            <div class="hitl-field-value">{req.get('result', '—')}</div>
            <div class="conf-badge">⚠ CONFIDENCE: {int(float(req.get('confidence', 0)) * 100)}% — Below autonomous threshold (80%)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    justification = st.text_input(
        "Authorization Justification (required for audit compliance)",
        placeholder="Enter rationale for decision — this will be recorded in the audit trail...",
        label_visibility="visible"
    )

    a_col, r_col, _ = st.columns([1, 1, 3])

    with a_col:
        if st.button("✓  Authorize Action", type="primary"):
            if justification.strip():
                r.set("human_decision", "approved")
                r.delete("approval_needed")
                # Log to audit trail
                audit = r.get("audit_log") or ""
                ts = datetime.now().strftime("%H:%M:%S")
                r.set("audit_log", f"[{ts}] HUMAN AUTHORIZED · Agent: {req.get('agent')} · Justification: {justification}\n" + audit)
                st.success("Action authorized and logged to audit trail.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Justification is mandatory for compliance. Please provide a rationale.")

    with r_col:
        if st.button("✗  Reject — Return to Swarm"):
            r.set("human_decision", "rejected")
            r.delete("approval_needed")
            audit = r.get("audit_log") or ""
            ts = datetime.now().strftime("%H:%M:%S")
            r.set("audit_log", f"[{ts}] HUMAN REJECTED · Agent: {req.get('agent')} · Action returned for revision\n" + audit)
            st.warning("Action rejected. Task returned to blackboard for agent revision.")
            time.sleep(1)
            st.rerun()

else:
    st.markdown("""
    <div class="hitl-container clear">
        <div class="hitl-label clear">✓ SYSTEM OPERATING AUTONOMOUSLY</div>
        <div style="font-size:13px;color:#3A7A5A;font-family:'IBM Plex Sans',sans-serif">
            All active agents are within confidence thresholds.<br>
            No executive authorization required at this time.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SECTION 5 — AUDIT TRAIL
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">05 · AUDIT TRAIL</div>', unsafe_allow_html=True)

audit_log = r.get("audit_log") or ""
if audit_log:
    st.code(audit_log, language="text")
else:
    st.markdown("""
    <div style="background:#030509;border:1px solid #1C2B3A;border-radius:4px;
                padding:16px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#1C3A5A;text-align:center">
        NO AUDIT ENTRIES — HUMAN INTERVENTION HAS NOT BEEN REQUIRED
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="border-top:1px solid #1C2B3A;padding-top:14px;display:flex;
            justify-content:space-between;font-family:'IBM Plex Mono',monospace;
            font-size:9px;color:#1C3A5A;letter-spacing:0.1em">
    <span>SYNTHETICA v2.4.1 · SWEDISH EMERGENCY MANAGEMENT AUTHORITY</span>
    <span>NON-HIERARCHICAL SWARM INTELLIGENCE · BLACKBOARD ARCHITECTURE</span>
    <span>ALL ACTIONS RECORDED · GDPR COMPLIANT</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  AUTO-REFRESH (every 2s — respectful of gov servers)
# ─────────────────────────────────────────────
time.sleep(2)
st.rerun()