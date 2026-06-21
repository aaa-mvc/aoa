"""Trace persistence — save, load, and index structured execution traces.

Each profile's traces are isolated: load_last() and load_all() filter by profile name.
"""

import os
import json
from collections import Counter

TRACE_DIR = "trace_history"


def _ensure_trace_dir():
    os.makedirs(TRACE_DIR, exist_ok=True)


def save(run_id, profile, files, value_config, value_result, duration_ms, dispersion):
    """Save structured trace JSON to trace_history/<run_id>.json"""
    _ensure_trace_dir()

    by_ext = Counter(f["ext"] for f in files)
    top_dirs = Counter(
        f["path"].split("/")[0] if "/" in f["path"]
        else f["path"].split("\\")[0]
        for f in files
    )

    trace = {
        "run_id": run_id,
        "profile": profile,
        "source": "filesystem_mtime",
        "state": {
            "files_scanned": len(files),
            "dirs_covered": list({f["root"] for f in files}),
            "window_days": value_config.get("_window_days", 5),
            "top_extensions": dict(by_ext.most_common(10)),
            "top_directories": dict(top_dirs.most_common(10)),
            "_focus_dispersion": dispersion,
        },
        "value": {
            "model": value_config.get("model", "hourly_linear"),
            "params": value_config.get("params", {}),
            "total_usd": value_result,
        },
        "duration_ms": duration_ms,
    }

    safe_id = run_id.replace(":", "-")
    path = os.path.join(TRACE_DIR, f"{safe_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)

    _update_index(safe_id, trace)
    return trace


def _update_index(safe_id, trace):
    """Maintain index.json with all run summaries, keyed by profile."""
    index_path = os.path.join(TRACE_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {}

    profile_name = trace["profile"]
    if profile_name not in index:
        index[profile_name] = {"runs": []}

    index[profile_name]["runs"].append({
        "id": safe_id,
        "files": trace["state"]["files_scanned"],
        "value": trace["value"]["total_usd"],
        "dispersion": trace["state"].get("_focus_dispersion", 0.0),
        "duration_ms": trace["duration_ms"],
    })

    # Trend for this profile
    runs = index[profile_name]["runs"]
    if len(runs) >= 2:
        recent = runs[-3:]
        files_trend = [r["files"] for r in recent]
        index[profile_name]["trend"] = {
            "files": "up" if files_trend[-1] > files_trend[0]
            else ("down" if files_trend[-1] < files_trend[0] else "stable"),
            "runs_count": len(runs),
        }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return index


def load_last(profile):
    """Load the most recent trace for a given profile, or None."""
    index_path = os.path.join(TRACE_DIR, "index.json")
    if not os.path.exists(index_path):
        return None
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    profile_data = index.get(profile)
    if not profile_data:
        return None
    runs = profile_data.get("runs", [])
    if not runs:
        return None

    latest_id = runs[-1]["id"]
    trace_path = os.path.join(TRACE_DIR, f"{latest_id}.json")
    if os.path.exists(trace_path):
        with open(trace_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_all(profile):
    """Load all historical traces for a given profile (baseline calculation)."""
    index_path = os.path.join(TRACE_DIR, "index.json")
    if not os.path.exists(index_path):
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    profile_data = index.get(profile)
    if not profile_data:
        return []

    traces = []
    for run in profile_data.get("runs", []):
        trace_path = os.path.join(TRACE_DIR, f"{run['id']}.json")
        if os.path.exists(trace_path):
            with open(trace_path, "r", encoding="utf-8") as f:
                traces.append(json.load(f))
    return traces
