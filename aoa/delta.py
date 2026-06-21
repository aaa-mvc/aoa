"""Delta computation, drift detection, and semantic interpretation."""

import math


def compute_focus_dispersion(files):
    """Ratio of unique top-level directories to total files. Lower = more focused."""
    if not files:
        return 0.0
    dirs = set()
    for f in files:
        p = f["path"].replace("\\", "/")
        top = p.split("/")[0] if "/" in p else "(root)"
        dirs.add(top)
    return len(dirs) / len(files)


def compute_raw_delta(current_state, previous_trace):
    """Compute numerical delta between current state snapshot and previous trace."""
    if previous_trace is None:
        return None

    curr_files = current_state["files_scanned"]
    prev_files = previous_trace["state"]["files_scanned"]
    curr_value = current_state.get("_value", 0)
    prev_value = previous_trace["value"]["total_usd"]

    delta = {
        "files_scanned": {
            "from": prev_files,
            "to": curr_files,
            "delta": curr_files - prev_files,
            "pct": round((curr_files - prev_files) / prev_files * 100, 1)
            if prev_files > 0 else 0,
        },
        "total_value_usd": {
            "from": prev_value,
            "to": curr_value,
            "delta": curr_value - prev_value,
        },
        "previous_run_id": previous_trace["run_id"],
    }
    return delta


def detect_drift(current_state, history_traces, drift_config):
    """Compare current focus_dispersion against historical baseline.

    Returns dict with: signal, interpretation, confidence, evidence, baseline stats.
    """
    min_history = drift_config.get("min_history", 3)

    if len(history_traces) < min_history:
        return {
            "signal": "insufficient_data",
            "interpretation": (
                f"⏳ 历史数据不足（{len(history_traces)} 次，需 ≥{min_history} 次），暂无法判断趋势"
            ),
            "confidence": "low",
            "evidence": f"当前历史记录数: {len(history_traces)}",
        }

    # Gather historical dispersion values
    historical_disp = []
    for t in history_traces:
        disp = t.get("state", {}).get("_focus_dispersion")
        if disp is None:
            continue
        historical_disp.append(disp)

    if len(historical_disp) < min_history:
        return {
            "signal": "insufficient_data",
            "interpretation": (
                f"⏳ 有效历史数据不足（{len(historical_disp)} 条），暂无法判断趋势"
            ),
            "confidence": "low",
            "evidence": f"有效 dispersion 记录: {len(historical_disp)}",
        }

    current_disp = current_state.get("_focus_dispersion", 0)

    # Baseline: mean and std
    mean = sum(historical_disp) / len(historical_disp)
    variance = sum((d - mean) ** 2 for d in historical_disp) / len(historical_disp)
    std = math.sqrt(variance) if variance > 0 else 0.001

    threshold = 0.5 * std

    files_count = current_state.get("files_scanned", 0)

    if current_disp < mean - threshold:
        signal = "converging"
        interpretation = (
            f"📈 相比历史基线，当前更收敛（分散度 {current_disp:.3f} < 基线 {mean:.3f}），"
            f"注意力在集中——修改集中在更少的顶层目录中。"
        )
    elif current_disp > mean + threshold:
        signal = "diverging"
        interpretation = (
            f"📉 相比历史基线，当前更分散（分散度 {current_disp:.3f} > 基线 {mean:.3f}），"
            f"文件修改跨约 {current_disp * files_count:.0f} 个顶层目录"
            f"（历史均值约 {mean * files_count:.0f} 个），"
            f"可能表明注意力在多个上下文之间切换。"
        )
    else:
        signal = "stable"
        interpretation = (
            f"➡️ 聚焦度与历史基线一致（当前 {current_disp:.3f}，"
            f"基线 {mean:.3f} ± {threshold:.3f}），行为模式稳定。"
        )

    confidence = "high" if abs(current_disp - mean) > std else "medium"

    return {
        "signal": signal,
        "interpretation": interpretation,
        "confidence": confidence,
        "baseline_mean": round(mean, 4),
        "baseline_std": round(std, 4),
        "current_dispersion": round(current_disp, 4),
        "evidence": (
            f"历史 dispersion: mean={mean:.4f}, σ={std:.4f}; "
            f"当前: {current_disp:.4f}; "
            f"阈值: ±{threshold:.4f} (0.5σ)"
        ),
    }


def interpret_delta(raw_delta, drift_result):
    """Convert raw numerical delta + drift into semantic claims with evidence."""
    claims = []

    if raw_delta is not None:
        fd = raw_delta["files_scanned"]
        abs_pct = abs(fd["pct"])

        if abs_pct < 5:
            claims.append({
                "claim": "文件修改数基本稳定",
                "evidence": (
                    f"文件修改数 {fd['from']} → {fd['to']}"
                    f"（{fd['delta']:+d}，{fd['pct']:+.1f}%）"
                ),
                "confidence": "high",
                "rule": "abs(file_pct_change) < 5%",
            })
        elif fd["delta"] > 0:
            claims.append({
                "claim": "活跃度上升",
                "evidence": (
                    f"文件修改数 {fd['from']} → {fd['to']}"
                    f"（{fd['delta']:+d}，{fd['pct']:+.1f}%）"
                ),
                "confidence": "high" if abs_pct > 10 else "medium",
                "rule": "file_count_delta > 0",
            })
        else:
            claims.append({
                "claim": "活跃度下降",
                "evidence": (
                    f"文件修改数 {fd['from']} → {fd['to']}"
                    f"（{fd['delta']:+d}，{fd['pct']:+.1f}%）"
                ),
                "confidence": "high" if abs_pct > 10 else "medium",
                "rule": "file_count_delta < 0",
            })

    if drift_result and drift_result["signal"] != "insufficient_data":
        label_map = {
            "converging": "注意力正在收敛",
            "diverging": "注意力可能分散",
            "stable": "行为模式稳定",
        }
        claims.append({
            "claim": label_map.get(drift_result["signal"], "趋势未知"),
            "evidence": drift_result["evidence"],
            "confidence": drift_result["confidence"],
            "rule": f"focus_dispersion vs baseline (mean={drift_result.get('baseline_mean', 'N/A')})",
        })

    return claims
