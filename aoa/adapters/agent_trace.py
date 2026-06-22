"""Agent trace adapter — scan Claude Code / agent transcript logs.

Reads JSONL transcript files and extracts:
  - Session count
  - User requests (tasks given)
  - Assistant responses (work done)
  - Tool calls (actions executed)
  - Session duration
  - Sub-agent spawns
"""

import os
import json
import time


def scan_agent_logs(log_dir, days=7):
    """Scan agent transcript directory for recent sessions.

    Args:
        log_dir: path to directory containing .jsonl transcript files
        days: look-back window

    Returns list of session dicts:
        {id, timestamp, user_msgs, assistant_msgs, tool_calls, subagents, duration_sec}
    """
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
    """Parse one JSONL transcript into a session summary."""
    stats = {
        "user_msgs": 0,
        "assistant_msgs": 0,
        "tool_calls": 0,
        "subagents": 0,
        "errors": 0,
        "first_ts": None,
        "last_ts": None,
        "titles": [],
        "subagent_names": [],
    }

    # Check if this is a sub-agent session
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
                                    # Detect sub-agent spawns
                                    tool_name = block.get("name", "")
                                    if "agent" in tool_name.lower() or "task" in tool_name.lower():
                                        stats["subagents"] += 1

                ts = event.get("timestamp", "")
                if ts:
                    if stats["first_ts"] is None:
                        stats["first_ts"] = ts
                    stats["last_ts"] = ts

    except (IOError, OSError):
        return None

    # Compute duration
    duration_sec = 0
    if stats["first_ts"] and stats["last_ts"]:
        try:
            t1 = _parse_iso(stats["first_ts"])
            t2 = _parse_iso(stats["last_ts"])
            duration_sec = max(0, t2 - t1)
        except (ValueError, IndexError):
            pass

    session_id = fname.replace(".jsonl", "")

    # Sub-agent names from directory
    if is_subagent:
        sub_name = os.path.basename(fname.replace(".jsonl", ""))
        stats["subagent_names"].append(sub_name)

    # Best title
    best_title = stats["titles"][-1] if stats["titles"] else ""

    return {
        "id": session_id[:12],
        "full_id": session_id,
        "is_subagent": is_subagent,
        "title": best_title,
        "titles": stats["titles"],
        "timestamp": stats["first_ts"] or "",
        "user_msgs": stats["user_msgs"],
        "assistant_msgs": stats["assistant_msgs"],
        "tool_calls": stats["tool_calls"],
        "subagent_count": stats["subagents"],
        "duration_sec": round(duration_sec, 1),
        "errors": stats["errors"],
    }


def _parse_iso(ts):
    """Parse ISO timestamp like '2026-06-16T08:14:36.502Z' to epoch seconds."""
    # Strip Z and parse
    ts = ts.replace("Z", "").replace("T", " ")
    parts = ts.split(".")
    dt_part = parts[0]
    struct = time.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
    return time.mktime(struct)
