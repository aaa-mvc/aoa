"""Agent trace adapter — scan Claude Code / agent transcript logs.

v0.7: Capability Trace — classifies tool calls into capability categories.
"""

import os
import json
import time
from collections import Counter

# ── Capability classification ──
# Actual tool names from Claude Code transcripts (case-sensitive)
CAPABILITY_MAP = {
    # Code generation
    "Write": "code_gen",
    "Edit": "code_gen",
    "NotebookEdit": "code_gen",
    # Project analysis
    "Read": "analysis",
    "Grep": "analysis",
    "Glob": "analysis",
    # Search & research
    "WebSearch": "research",
    "WebFetch": "research",
    # Execution
    "Bash": "execution",
    "PowerShell": "execution",
    "Skill": "execution",
    "Monitor": "execution",
    # Task delegation
    "Agent": "delegation",
    "TaskOutput": "delegation",
    "TaskStop": "delegation",
    # Planning
    "TodoWrite": "planning",
    "EnterPlanMode": "planning",
    "ExitPlanMode": "planning",
    # Interaction
    "AskUserQuestion": "interaction",
}

CAPABILITY_LABELS = {
    "code_gen": "代码生成",
    "analysis": "项目分析",
    "research": "搜索研究",
    "execution": "命令执行",
    "delegation": "任务委派",
    "planning": "任务规划",
    "interaction": "交互提问",
    "other": "其他",
}


def classify_tool(tool_name, tool_input=None):
    """Classify a tool call into a capability category."""
    # Direct match
    if tool_name in CAPABILITY_MAP:
        return CAPABILITY_MAP[tool_name]
    # Partial match
    for key, cap in CAPABILITY_MAP.items():
        if key in tool_name:
            return cap
    return "other"


def scan_agent_logs(log_dir, days=7):
    cutoff = time.time() - days * 86400
    sessions = []

    if not os.path.exists(log_dir):
        return sessions

    for root, dirs, files in os.walk(log_dir):
        for fname in files:
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(root, fname)
            try:
                mtime = os.path.getmtime(fpath)
                if mtime < cutoff:
                    continue
            except OSError:
                continue

            session = _parse_session(fpath, fname)
            if session:
                sessions.append(session)

    sessions.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
    return sessions


def _parse_session(fpath, fname):
    stats = {
        "user_msgs": 0,
        "assistant_msgs": 0,
        "tool_calls": 0,
        "subagents": 0,
        "errors": 0,
        "first_ts": None,
        "last_ts": None,
        "titles": [],
        "capabilities": Counter(),
    }

    is_subagent = "/subagents/" in fpath.replace("\\", "/")

    try:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    stats["errors"] += 1
                    continue

                etype = event.get("type", "")

                if etype == "user":
                    stats["user_msgs"] += 1
                elif etype == "ai-title":
                    title = event.get("aiTitle", "")
                    if title and title not in stats["titles"]:
                        stats["titles"].append(title)
                elif etype == "assistant":
                    stats["assistant_msgs"] += 1
                    content = event.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "tool_use":
                                    stats["tool_calls"] += 1
                                    tool_name = block.get("name", "")
                                    tool_input = block.get("input", {})
                                    cap = classify_tool(tool_name, tool_input)
                                    stats["capabilities"][cap] += 1
                                    # Detect sub-agent spawns
                                    if "agent" in tool_name.lower() or "task" in tool_name.lower():
                                        stats["subagents"] += 1

                ts = event.get("timestamp", "")
                if ts:
                    if stats["first_ts"] is None:
                        stats["first_ts"] = ts
                    stats["last_ts"] = ts

    except (IOError, OSError):
        return None

    duration_sec = 0
    if stats["first_ts"] and stats["last_ts"]:
        try:
            t1 = _parse_iso(stats["first_ts"])
            t2 = _parse_iso(stats["last_ts"])
            duration_sec = max(0, t2 - t1)
        except (ValueError, IndexError):
            pass

    session_id = fname.replace(".jsonl", "")

    if is_subagent:
        meta_path = fpath.replace(".jsonl", ".meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta = json.load(mf)
                stats["agent_type"] = meta.get("agentType", "")
                stats["agent_desc"] = meta.get("description", "")
            except (json.JSONDecodeError, IOError):
                pass

    best_title = stats["titles"][-1] if stats["titles"] else ""

    return {
        "id": session_id[:12],
        "full_id": session_id,
        "is_subagent": is_subagent,
        "title": best_title,
        "titles": stats["titles"],
        "agent_type": stats.get("agent_type", ""),
        "agent_desc": stats.get("agent_desc", ""),
        "timestamp": stats["first_ts"] or "",
        "user_msgs": stats["user_msgs"],
        "assistant_msgs": stats["assistant_msgs"],
        "tool_calls": stats["tool_calls"],
        "capabilities": dict(stats["capabilities"]),
        "subagent_count": stats["subagents"],
        "duration_sec": round(duration_sec, 1),
        "errors": stats["errors"],
    }


def _parse_iso(ts):
    ts = ts.replace("Z", "").replace("T", " ")
    parts = ts.split(".")
    dt_part = parts[0]
    struct = time.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
    return time.mktime(struct)


def aggregate_capabilities(sessions):
    """Aggregate capability distribution across all sessions."""
    total = Counter()
    for s in sessions:
        for cap, count in s.get("capabilities", {}).items():
            total[cap] += count
    return dict(total)
