"""v0.3 Memory Kernel — accumulated behavioral history biases future policy.

Memory is no longer storage — it becomes bias.
"""

import os
import json
import math

MEMORY_FILE = "trace_history/memory.json"


def load():
    """Load memory buffer. Returns list of {look_back, policy, drift, ts}."""
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save(memory):
    """Persist memory buffer (bounded to last 50 entries)."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory[-50:], f, ensure_ascii=False, indent=2)


def update(memory, entry):
    """Append a new memory entry and return bounded buffer."""
    memory.append(entry)
    return memory[-50:]


def compute_bias(memory):
    """Compute behavioral preference vector from memory history.

    Uses exponential decay weighting (recent runs matter more).
    Returns {bias, trend, strength} where:
      bias > 0  → system prefers converging
      bias < 0  → system prefers diverging
      bias ~ 0  → neutral
    """
    if not memory:
        return {"bias": 0.0, "trend": "neutral", "strength": 0.0}

    total_weight = 0.0
    weighted_score = 0.0
    recent = memory[-15:]  # last 15 runs max

    for i, m in enumerate(reversed(recent)):
        age = i  # 0 = most recent
        weight = math.exp(-0.3 * age)

        signal = m.get("policy", "stable")
        if signal == "converging":
            score = 1.0
        elif signal == "diverging":
            score = -1.0
        else:
            score = 0.3  # stable is mildly positive

        weighted_score += score * weight
        total_weight += weight

    bias = weighted_score / max(total_weight, 1e-6)

    # Classify trend
    if bias > 0.3:
        trend = "converging-biased"
    elif bias < -0.3:
        trend = "diverging-biased"
    else:
        trend = "neutral"

    return {
        "bias": round(bias, 4),
        "trend": trend,
        "strength": round(abs(bias), 4),
    }


def friction(bias_value):
    """v0.3.1: Personality friction — stronger bias resists change more.

    Returns 0.0-1.0 multiplier:
      1.0 = no resistance (neutral, flexible)
      0.3 = strong resistance (personality locked in, hard to change)
    """
    return 1.0 - min(abs(bias_value), 0.7)


def phase(memory):
    """v0.3.1: Classify the system's behavioral phase state.

    warmup           — not enough history
    stable           — bias within neutral band, system balanced
    converging-biased — system strongly prefers converging
    diverging-biased  — system strongly prefers diverging
    """
    if len(memory) < 5:
        return "warmup"
    b = compute_bias(memory)["bias"]
    if abs(b) < 0.25:
        return "stable"
    return "converging-biased" if b > 0 else "diverging-biased"
