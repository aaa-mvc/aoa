"""AOA engine — report generation from scan results + trace history."""

import json
from datetime import datetime
from collections import Counter

from aoa.delta import compute_raw_delta, detect_drift, interpret_delta


def make_report(cfg, files, previous_trace, history_traces, current_state,
                user_info=None, visible=None):
    """Generate a Markdown report with optional visibility filter.

    Args:
        user_info: dict from user.json (employee identity)
        visible: set of section keys to include. None = show all.
    """
    if visible is None:
        visible = {"user_info", "delta", "semantic", "drift", "policy",
                   "rhythm", "types", "recent", "value", "feedback"}

    def _show(key):
        return key in visible

    lines = []
    lines.append(f"# {cfg['name']}")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"回溯天数：{cfg['look_back_days']} 天")
    lines.append("")

    # ── User info ──
    if _show("user_info") and user_info:
        lines.append("## \U0001f464 员工信息")
        lines.append("")
        for key, label in [("id", "工号"), ("name", "姓名"), ("role", "岗位"),
                           ("department", "部门"), ("level", "职级"),
                           ("joined", "入职"), ("manager", "主管")]:
            val = user_info.get(key, "-")
            lines.append(f"- {label}：{val}")
        if user_info.get("responsibilities"):
            lines.append(f"- 职责：{', '.join(user_info['responsibilities'])}")
        lines.append("")

    # ── Delta + Drift section ──
    drift_result = None
    if previous_trace is not None and (_show("delta") or _show("semantic") or _show("drift")):
        raw_delta = compute_raw_delta(current_state, previous_trace)
        drift_config = cfg.get("drift", {})
        drift_result = detect_drift(current_state, history_traces[:-1], drift_config)
        semantic = interpret_delta(raw_delta, drift_result)

        if _show("delta"):
            lines.append("## \U0001f4ca 相比上次")
            lines.append("")
            lines.append(f"上次评估时间：{previous_trace['run_id'][:16]}")
            lines.append("")

        if raw_delta and _show("delta"):
            fd = raw_delta["files_scanned"]
            lines.append(
                f"- 文件修改数：{fd['from']} → {fd['to']}"
                f"（**{fd['delta']:+d}，{fd['pct']:+.1f}%**）"
            )
            vd = raw_delta["total_value_usd"]
            lines.append(
                f"- 估算价值：${vd['from']:,.0f} → ${vd['to']:,.0f}"
                f"（**${vd['delta']:+,.0f}**）"
            )
            lines.append("")

        if semantic and _show("semantic"):
            lines.append("### 变化解读")
            lines.append("")
            for s in semantic:
                conf_label = {"high": "高", "medium": "中", "low": "低"}.get(
                    s["confidence"], s["confidence"]
                )
                lines.append(f"- **{s['claim']}**（置信度：{conf_label}）")
                lines.append(f"  - 证据：{s['evidence']}")
            lines.append("")

        if drift_result and drift_result["signal"] != "insufficient_data" and _show("drift"):
            lines.append("### 趋势判断")
            lines.append("")
            lines.append(f"{drift_result['interpretation']}")
            lines.append("")

    # ── Insufficient data ──
    elif previous_trace is None and (_show("delta") or _show("drift")):
        min_hist = cfg.get("drift", {}).get("min_history", 3)
        hist_count = len(history_traces) if history_traces else 0
        lines.append(
            f"> ⏳ 历史数据不足（{hist_count} 次运行），"
            f"暂无法判断趋势。连续运行 {min_hist} 次后自动开启。"
        )
        lines.append("")

    # ── Policy ──
    if drift_result and drift_result["signal"] != "insufficient_data" and _show("policy"):
        lines.append("## \U0001f3af 下次建议")
        lines.append("")
        look_back = cfg.get("look_back_days", 5)

        if drift_result["signal"] == "diverging":
            top_dirs_list = []
            if files:
                top_counts = Counter(
                    f["path"].split("/")[0] if "/" in f["path"]
                    else f["path"].split("\\")[0]
                    for f in files
                )
                top_dirs_list = [d for d, _ in top_counts.most_common(5)]
            lines.append("- 当前趋势：**注意力正在分散**")
            lines.append("- 建议：聚焦扫描核心目录")
            if top_dirs_list:
                lines.append(f"- 核心目录：`{', '.join(top_dirs_list[:5])}`")
            lines.append("- 原因：文件修改跨多个顶层目录，可能被碎片化干扰")
            lines.append(f"- 操作：可手动缩减 `scan_dirs` 或缩小 `look_back_days`（当前 {look_back} 天）")
        elif drift_result["signal"] == "converging":
            lines.append("- 当前趋势：**注意力正在收敛**")
            lines.append("- 建议：保持当前扫描策略")
            lines.append("- 原因：修改集中在更少的目录中，聚焦度良好")
            lines.append(f"- 操作：无需调整（`look_back_days`={look_back}，`scan_dirs` 不变）")
        else:
            lines.append("- 当前趋势：**行为模式稳定**")
            lines.append("- 建议：保持当前扫描策略")
            lines.append("- 原因：聚焦度与历史基线一致")
            lines.append("- 操作：无需调整")
        lines.append("")

    # ── Empty result ──
    if not files:
        lines.append("> 此期间无活动记录。")
        return "\n".join(lines), 0, drift_result

    # ── Daily rhythm ──
    if _show("rhythm"):
        by_day = Counter()
        for f in files:
            day = datetime.fromtimestamp(f["time"]).strftime("%m/%d")
            by_day[day] += 1

        lines.append("## 每日节奏")
        lines.append("")
        for day in sorted(by_day.keys()):
            n = by_day[day]
            bar = "█" * min(n // 3, 30)
            lines.append(f"- **{day}** {bar} {n}")
        lines.append("")

    # ── File type distribution ──
    if _show("types"):
        by_type = Counter(f["ext"] for f in files)
        lines.append("## 文件类型分布")
        lines.append("")
        for ext, n in by_type.most_common(8):
            lines.append(f"- `{ext}` — {n}")
        lines.append("")

    # ── Recent changes ──
    if _show("recent"):
        lines.append("## 最近修改")
        lines.append("")
        for f in files[:12]:
            ts = datetime.fromtimestamp(f["time"]).strftime("%m/%d %H:%M")
            name = f["path"].replace("\\", "/")
            if len(name) > 70:
                name = "..." + name[-67:]
            lines.append(f"- `{ts}` {name}")
        lines.append("")

    # ── Value estimation ──
    if _show("value"):
        value_model = cfg.get("value", {})
        params = value_model.get("params", {})
        mpa = params.get("minutes_per_action", 10)
        rate = params.get("rate_per_hour", cfg.get("value_per_action", 50))
        label = cfg.get("action_label", "次修改")
        currency = params.get("currency", "USD")

        hours = len(files) * mpa / 60
        total_value = hours * rate

        lines.append("## 价值估算")
        lines.append("")
        lines.append(f"- 模型：`{value_model.get('model', 'hourly_linear')}`")
        lines.append(f"- 共 **{len(files)}** {label}")
        lines.append(f"- 估算耗时 **{hours:.1f}** 小时（每{label}约 {mpa} 分钟）")
        lines.append(f"- 时薪假设 **{currency} {rate}**")
        lines.append(f"- **估算价值：{currency} {total_value:,.0f}**")
        lines.append("")

    lines.append("---")
    lines.append(
        f"*由 AOA (Action-Oriented Audit) 自动生成 · "
        f"{datetime.now().strftime('%Y-%m-%d')}*"
    )

    return "\n".join(lines), total_value if _show("value") else 0, drift_result
