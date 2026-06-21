"""v0.3.3 — Causal Memory Kernel

memory ≠ log
memory = causal graph of state transitions

Every policy change is attributable: which force drove it, by how much,
and what would have happened if a force were different.
"""

import os
import json
import time

FILE = "trace_history/causal_memory.json"


def load():
    if not os.path.exists(FILE):
        return []
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save(memory):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(memory[-80:], f, ensure_ascii=False, indent=2)


def build_event(prev_policy, force_fields):
    """Build a causal event from v0.3.2 force fields.

    Maps bias / attractor / friction to three causal weights that
    answer: 'which force contributed most to this decision?'
    """
    bias = abs(force_fields.get("bias", 0))
    attr = abs(force_fields.get("attractor", 0))
    fric = force_fields.get("friction", 1.0)
    fric_gap = 1.0 - fric  # how much friction dampened

    # Normalize to [0,1] so weights sum to 1.0
    total = bias + attr + fric_gap
    if total < 1e-6:
        total = 1.0

    causes = [
        {
            "factor": "memory_bias",
            "weight": round(bias / total, 3),
            "raw_value": round(force_fields.get("bias", 0), 4),
        },
        {
            "factor": "identity_attractor",
            "weight": round(attr / total, 3),
            "raw_value": round(force_fields.get("attractor", 0), 4),
        },
        {
            "factor": "friction",
            "weight": round(fric_gap / total, 3),
            "raw_value": round(fric, 4),
        },
    ]

    # Dominant cause
    dominant = max(causes, key=lambda c: c["weight"])

    # Counterfactual: what if the dominant cause were halved?
    effective = force_fields.get("effective", 0)
    cf_effective = None
    if dominant["factor"] == "memory_bias" and bias > 0.1:
        cf_effective = round(effective * (1 - dominant["weight"] * 0.5), 4)
    elif dominant["factor"] == "identity_attractor" and attr > 0.01:
        cf_effective = round(effective * (1 - dominant["weight"] * 0.5), 4)

    return {
        "ts": time.time(),
        "from_state": prev_policy if prev_policy else "init",
        "to_decision": (
            "converging" if effective > 0.4
            else "diverging" if effective < -0.4
            else "stabilizing"
        ),
        "effective": round(effective, 4),
        "causes": causes,
        "dominant_cause": dominant["factor"],
        "counterfactual": {
            "scenario": f"halve {dominant['factor']}",
            "would_be_effective": cf_effective,
        } if cf_effective is not None else None,
    }


def update(memory, event):
    memory.append(event)
    return memory[-80:]


def summary(memory):
    """Extract macro-level causal explanation from recent history."""
    if not memory:
        return {"status": "no_causal_data"}

    recent = memory[-10:]

    # Aggregate
    avg_effective = sum(e["effective"] for e in recent) / len(recent)
    avg_bias = sum(
        c["raw_value"]
        for e in recent
        for c in e["causes"]
        if c["factor"] == "memory_bias"
    ) / len(recent)

    # Dominant cause across window
    cause_totals = {"memory_bias": 0.0, "identity_attractor": 0.0, "friction": 0.0}
    for e in recent:
        for c in e["causes"]:
            cause_totals[c["factor"]] += c["weight"]
    dominant = max(cause_totals, key=cause_totals.get)

    # Determine macro interpretation
    if dominant == "friction" and cause_totals["friction"] / len(recent) > 0.4:
        interpretation = "系统主要由摩擦阻尼主导——人格已稳定，变化缓慢"
    elif dominant == "identity_attractor" and cause_totals["identity_attractor"] / len(recent) > 0.3:
        interpretation = "系统主要由自我一致性吸引子主导——在回归历史均值"
    elif dominant == "memory_bias" and cause_totals["memory_bias"] / len(recent) > 0.5:
        interpretation = "系统主要由近期行为偏置主导——短期趋势驱动变化"
    else:
        interpretation = "三力均衡——系统处于混合驱动状态"

    return {
        "avg_effective": round(avg_effective, 4),
        "avg_bias": round(avg_bias, 4),
        "dominant_cause": dominant,
        "cause_distribution": {
            k: round(v / len(recent), 3) for k, v in cause_totals.items()
        },
        "events_analyzed": len(recent),
        "interpretation": interpretation,
    }
