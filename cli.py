"""AOA CLI — unified entry point for all profiles.

Usage:
  python cli.py run desktop     # Personal work review
  python cli.py run code        # Code activity review
  python cli.py run brain       # Knowledge base review
  python cli.py run git         # Git activity review
"""

import os
import sys
import json
import time
from datetime import datetime

from aoa.adapters.filesystem import scan_files
from aoa.adapters.git import scan_git
from aoa.adapters.agent_trace import scan_agent_logs
from aoa.engine import make_report
from aoa.trace import save as save_trace
from aoa.trace import load_last, load_all
from aoa.delta import compute_focus_dispersion
import aoa.memory as memory_mod
import aoa.causal as causal_mod


def load_profile_config(profile_name):
    """Load config.json from profiles/<profile_name>/"""
    config_path = os.path.join("profiles", profile_name, "config.json")
    if not os.path.exists(config_path):
        print(f"  ✗ Profile not found: {profile_name}")
        print(f"    Expected config at: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_user_info(profile_name):
    """Load user.json from profiles/<profile_name>/"""
    user_path = os.path.join("profiles", profile_name, "user.json")
    if not os.path.exists(user_path):
        return None
    with open(user_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_profile_config(profile_name, config):
    """Save modified config back to the profile's config.json."""
    config_path = os.path.join("profiles", profile_name, "config.json")
    # Strip internal fields before saving
    clean = {k: v for k, v in config.items() if not k.startswith("_")}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def apply_policy_influence(config, drift_result, memory_bias=None, mem=None):
    """v0.3.2: Unified force = (bias + attractor) * friction drives policy.

    effective > +0.4 → converging action
    effective < -0.4 → diverging action
    else           → stabilize
    """
    if drift_result is None or drift_result["signal"] == "insufficient_data":
        return config

    old_days = config.get("look_back_days", 5)
    new_config = config.copy()

    # ── v0.3.2: unified effective force ──
    force = None
    if mem and len(mem) >= 3:
        force = memory_mod.effective_force(mem)

    if force is None:
        # Fallback: use signal directly (no memory yet)
        signal = drift_result["signal"]
        base = 0.2
        if signal == "converging":
            new_config["look_back_days"] = max(1, int(old_days * (1 - base)))
            new_config["_focus_mode"] = "deep_scan"
            new_config["_policy_applied"] = f"converging → {old_days}→{new_config['look_back_days']}"
        elif signal == "diverging":
            new_config["look_back_days"] = min(14, int(old_days * (1 + base)))
            new_config["_focus_mode"] = "broad_scan"
            new_config["_policy_applied"] = f"diverging → {old_days}→{new_config['look_back_days']}"
        else:
            new_config["_focus_mode"] = "stable_scan"
            new_config["_policy_applied"] = "stable → no change"
        return new_config

    effective = force["effective"]
    base = 0.2

    if effective > 0.4:
        new_config["look_back_days"] = max(1, int(old_days * (1 - base)))
        new_config["_focus_mode"] = "deep_scan"
        new_config["_policy_applied"] = (
            f"effective {effective:+.3f} → look_back {old_days}→{new_config['look_back_days']}"
        )
    elif effective < -0.4:
        new_config["look_back_days"] = min(14, int(old_days * (1 + base)))
        new_config["_focus_mode"] = "broad_scan"
        new_config["_policy_applied"] = (
            f"effective {effective:+.3f} → look_back {old_days}→{new_config['look_back_days']}"
        )
    else:
        # Stabilize: gradual contraction toward floor
        new_lb = max(2, old_days - 1)
        new_config["look_back_days"] = new_lb
        new_config["_focus_mode"] = "stable_scan"
        new_config["_policy_applied"] = (
            f"stabilizing (eff {effective:+.3f}) → {old_days}→{new_lb}"
        )

    return new_config


# ═══════════════════════════════════════════════════════════════
# v0.2.1 Stability Kernel
# ═══════════════════════════════════════════════════════════════

POLICY_STATE_FILE = "trace_history/policy_state.json"


def _load_policy_state():
    """Load policy signal history for oscillation detection."""
    if not os.path.exists(POLICY_STATE_FILE):
        return {"signals": [], "equilibrium": False}
    with open(POLICY_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_policy_state(state):
    os.makedirs(os.path.dirname(POLICY_STATE_FILE), exist_ok=True)
    with open(POLICY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def apply_stability(config, drift_result):
    """v0.2.1: dampen runaway and detect equilibrium.

    Three guards:
      1. Oscillation lock — if signal flips within 4 runs, force stable
      2. Runaway brake — 3+ consecutive same signal → halve influence
      3. Hard floor — look_back_days never below 2
    """
    state = _load_policy_state()
    signal = drift_result.get("signal", "stable") if drift_result else "insufficient_data"

    if signal == "insufficient_data":
        return config

    # Append current signal
    state["signals"].append(signal)
    # Keep only last 8
    state["signals"] = state["signals"][-8:]

    new_config = config.copy()
    signals = state["signals"]
    n = len(signals)
    old_days = config.get("look_back_days", 5)

    # Guard 1: Oscillation detection (flip within 4 runs)
    if n >= 4:
        recent4 = signals[-4:]
        flips = sum(1 for i in range(1, len(recent4)) if recent4[i] != recent4[i - 1])
        if flips >= 2:
            new_config["look_back_days"] = old_days  # revert to original
            new_config["_stability_action"] = f"oscillation locked → holding at {old_days}"
            state["equilibrium"] = False
            _save_policy_state(state)
            return new_config

    # Guard 2: Runaway brake (3+ same signal)
    if n >= 3 and len(set(signals[-3:])) == 1:
        same_signal = signals[-1]
        if same_signal in ("converging", "diverging"):
            new_config["look_back_days"] = old_days  # halt further change
            new_config["_stability_action"] = (
                f"runaway brake → {same_signal} x{len([s for s in signals if s == same_signal])}, "
                f"holding at {old_days}"
            )
            state["equilibrium"] = False
            _save_policy_state(state)
            return new_config

    # Guard 3: Hard floor
    if new_config.get("look_back_days", 5) < 2:
        new_config["look_back_days"] = 2
        new_config["_stability_action"] = "hard floor → look_back clipped to 2"

    # Equilibrium: 5+ consecutive stable
    if n >= 5 and all(s == "stable" for s in signals[-5:]):
        state["equilibrium"] = True
        new_config["_stability_action"] = "equilibrium → system stable"

    _save_policy_state(state)
    return new_config


def run_desktop(cfg):
    """Run filesystem scan profile."""
    audience = cfg.get("_audience", "self")
    user_info = cfg.get("_user_info")
    visibility = cfg.get("visibility", {})
    visible = set(visibility.get(audience, visibility.get("self", [])))

    print(f"\n  AOA — Action-Oriented Audit · {cfg['name']}")
    if audience != "self":
        print(f"  视角：{audience}（可见字段：{', '.join(sorted(visible))}）")
    print(f"  扫描中...")

    start_ms = time.time() * 1000
    files = scan_files(cfg.get("scan_dirs", ["."]), cfg.get("look_back_days", 5))
    duration_ms = int(time.time() * 1000 - start_ms)

    # Value
    import aoa.value as value_mod
    total_value = value_mod.compute(files, cfg.get("value", {}))

    # Dispersion
    dispersion = compute_focus_dispersion(files)

    # Run ID
    run_id = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Build current state snapshot
    current_state = {
        "files_scanned": len(files),
        "dirs_covered": list({f["root"] for f in files}),
        "_focus_dispersion": dispersion,
        "_value": total_value,
    }

    # Load history
    previous_trace = load_last(cfg.get("name", "aoa"))
    history_traces = load_all(cfg.get("name", "aoa"))

    # Persist trace
    value_config_for_trace = {
        "model": cfg.get("value", {}).get("model", "hourly_linear"),
        "params": cfg.get("value", {}).get("params", {}),
        "_window_days": cfg.get("look_back_days", 5),
    }
    save_trace(run_id, cfg.get("name", "aoa"), files,
               value_config_for_trace, total_value, duration_ms, dispersion)

    # Re-read history to include current run
    all_history = load_all(cfg.get("name", "aoa"))

    # Generate report
    report, _, drift_result = make_report(cfg, files, previous_trace, all_history,
                                          current_state, user_info, visible)

    # ── v0.3: Load memory + compute bias ──
    mem = memory_mod.load()
    memory_bias = memory_mod.compute_bias(mem)

    # ── v0.3.2: Policy Influence (unified force: bias + attractor + friction) ──
    new_cfg = apply_policy_influence(cfg, drift_result, memory_bias, mem)

    # ── v0.2.1: Stability Kernel ──
    new_cfg = apply_stability(new_cfg, drift_result)
    stability_note = new_cfg.pop("_stability_action", None)

    if new_cfg.get("_policy_applied"):
        policy_note = new_cfg.pop("_policy_applied")
        # Persist modified config for next run
        _save_profile_config(cfg.get("_profile", "desktop"), new_cfg)
        msg = f"  Policy: {policy_note}"
        if stability_note:
            msg += f" | Stability: {stability_note}"
        if memory_bias and abs(memory_bias.get("bias", 0.0)) > 0.1:
            force = memory_mod.effective_force(mem) if mem and len(mem) >= 3 else None
            if force:
                msg += (
                    f" | Force: eff={force['effective']:+.3f}"
                    f" (bias={force['bias']:+.2f} id={force['identity']:+.2f}"
                    f" attr={force['attractor']:+.3f} fric={force['friction']:.2f})"
                )
            else:
                msg += f" | Personality: {memory_bias['trend']} (bias {memory_bias['bias']:+.2f})"
        print(msg)

    # ── v0.3: Update memory with this run's signal ──
    signal = drift_result.get("signal", "stable") if drift_result else "stable"
    mem = memory_mod.update(mem, {
        "look_back": cfg.get("look_back_days", 5),
        "policy": signal,
        "drift": drift_result.get("current_dispersion", 0) if drift_result else 0,
        "ts": run_id,
    })
    memory_mod.save(mem)

    # ── v0.3.3: Causal memory — why did the system change? ──
    force_fields = memory_mod.effective_force(mem) if mem and len(mem) >= 3 else None
    if force_fields:
        prev_policy = mem[-2].get("policy", "init") if len(mem) >= 2 else "init"
        causal_event = causal_mod.build_event(prev_policy, force_fields)
        causal_mem = causal_mod.load()
        causal_mem = causal_mod.update(causal_mem, causal_event)
        causal_mod.save(causal_mem)

    # Output
    output_path = cfg.get("output", "report.md")
    # Resolve relative to profile directory
    if not os.path.isabs(output_path):
        output_path = os.path.join("profiles", cfg.get("_profile", "desktop"), output_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    # ── v0.4: Feedback ──
    feedback_text = cfg.get("_feedback", "")
    if feedback_text:
        _append_feedback(output_path, feedback_text, cfg.get("name", "AOA"))

    safe_id = run_id.replace(":", "-")

    # Print report directly to terminal — no need to open another file
    # GBK-safe: strip characters that Windows console can't encode
    console_report = report.encode("gbk", errors="ignore").decode("gbk")
    print("")
    print("  " + "=" * 56)
    print(console_report)
    print("")
    print(f"  [报告已保存: {output_path}]")
    print(f"  [Trace: trace_history/{safe_id}.json]")

    # Keep terminal open
    if cfg.get("_interactive"):
        input("  按 Enter 退出...")


def run_agent_audit(cfg):
    """Run agent log audit profile."""
    audience = cfg.get("_audience", "self")
    user_info = cfg.get("_user_info")
    visibility = cfg.get("visibility", {})
    visible = set(visibility.get(audience, visibility.get("self", [])))
    def _show(key):
        return key in visible

    print(f"\n  AOA — Agent Audit · {cfg['name']}")
    print(f"  扫描 Agent 日志...")

    log_dir = cfg.get("log_dir", ".")
    days = cfg.get("look_back_days", 7)
    sessions = scan_agent_logs(log_dir, days)

    # ── Build report ──
    lines = []
    lines.append(f"# {cfg['name']}")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"监控周期：{days} 天")
    lines.append(f"数据源：{log_dir}")
    lines.append("")

    total_main = [s for s in sessions if not s["is_subagent"]]
    total_sub = [s for s in sessions if s["is_subagent"]]
    total_tools = sum(s["tool_calls"] for s in sessions)
    total_users = sum(s["user_msgs"] for s in sessions)
    total_assistant = sum(s["assistant_msgs"] for s in sessions)

    # ── Agent info ──
    if _show("agent_info") and user_info:
        lines.append("## [Agent] 身份")
        lines.append("")
        for key, label in [("id", "ID"), ("name", "名称"), ("type", "类型"),
                           ("provider", "提供商"), ("host", "运行位置")]:
            val = user_info.get(key, "-")
            lines.append(f"- {label}：{val}")
        lines.append("")

    # ── Exec summary ──
    if _show("exec_summary"):
        lines.append("## [Summary] 执行摘要")
        lines.append("")
        lines.append(f"- 主会话：**{len(total_main)}** 次")
        lines.append(f"- 子 Agent：**{len(total_sub)}** 个")
        lines.append(f"- 用户请求：**{total_users}** 条")
        lines.append(f"- Agent 响应：**{total_assistant}** 条")
        lines.append(f"- 工具调用：**{total_tools}** 次")
        if total_main:
            avg_tools = total_tools / max(len(total_main), 1)
            lines.append(f"- 平均每会话工具调用：**{avg_tools:.1f}** 次")
        lines.append("")

    # ── Detail ──
    if _show("detail") and sessions:
        lines.append("## [Detail] 最近会话")
        lines.append("")
        for s in sessions[:12]:
            tag = "[Sub]" if s["is_subagent"] else "[Main]"
            dur_min = s["duration_sec"] / 60
            title = s.get("title", "")
            title_str = f" — {title[:60]}" if title else ""
            lines.append(
                f"- `{s['timestamp'][:10]}` {tag} {s['id']} | "
                f"用户{s['user_msgs']}条 工具{s['tool_calls']}次 "
                f"{dur_min:.0f}分钟{title_str}"
            )
        lines.append("")

    # ── Trends ──
    if _show("trends") and len(total_main) >= 3:
        lines.append("## [Trend] 行为趋势")
        lines.append("")
        # Daily session count
        by_day = {}
        for s in sessions:
            day = s["timestamp"][:10] if s["timestamp"] else "?"
            by_day[day] = by_day.get(day, 0) + 1
        for day in sorted(by_day.keys())[-7:]:
            n = by_day[day]
            bar = "|" * min(n, 30)
            lines.append(f"- **{day[5:]}** {bar} {n} 会话")
        lines.append("")

    # ── Cost/value ──
    if _show("cost_value"):
        value_model = cfg.get("value", {})
        params = value_model.get("params", {})
        cost_per = params.get("cost_per_session", 3.0)
        human_hours = params.get("human_hours_per_session", 2.0)
        human_rate = params.get("human_rate_per_hour", 50)

        total_cost = len(total_main) * cost_per
        human_equiv = len(total_main) * human_hours * human_rate

        lines.append("## [Value] 成本-价值估算")
        lines.append("")
        lines.append(f"- 模型：`{value_model.get('model', 'agent_roi')}`")
        lines.append(f"- 估算 API 成本：**${total_cost:.2f}**")
        lines.append(f"- 等效人工价值：**${human_equiv:,.0f}**")
        if total_cost > 0:
            lines.append(f"- 投入产出比：**1:{human_equiv/total_cost:.0f}**")
        lines.append("")

    # ── Verdict ──
    if _show("verdict"):
        lines.append("## [Verdict] 审计结论")
        lines.append("")
        if not total_main:
            lines.append("- ⚠️ 此周期内无Agent会话记录")
        elif total_tools == 0:
            lines.append("- ⚠️ Agent 运行但未执行任何工具操作")
        else:
            lines.append(f"- ✅ 该 Agent 正常运行，{days}天内执行 {len(total_main)} 次会话、{total_tools} 次操作")
            if total_sub:
                lines.append(f"- ℹ️ 调度了 {len(total_sub)} 个子 Agent")
        lines.append("")

    lines.append("---")
    lines.append(
        f"*由 AOA (Action-Oriented Audit) Agent 审计模块生成 · "
        f"{datetime.now().strftime('%Y-%m-%d')}*"
    )

    report = "\n".join(lines)
    output_path = cfg.get("output", "report.md")
    if not os.path.isabs(output_path):
        output_path = os.path.join("profiles", cfg.get("_profile", "agent"), output_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  报告已保存：{output_path}")

    # Print to terminal (GBK-safe)
    console_report = report.encode("gbk", errors="ignore").decode("gbk")
    print("")
    print("  " + "=" * 56)
    print(console_report)
    print("")
    print(f"  [报告已保存: {output_path}]")

    if cfg.get("_interactive"):
        input("  按 Enter 退出...")


def run_git(cfg):
    """Run git log scan profile."""
    print(f"\n  AOA — Action-Oriented Audit · {cfg['name']}")
    print(f"  扫描 git log...")

    repo_path = cfg.get("repo_path", ".")
    days = cfg.get("look_back_days", 5)

    commits = scan_git(repo_path, days)

    # Build a simple markdown report
    lines = [
        f"# {cfg['name']} — Git Activity",
        f"Repo: {repo_path} | Last {days} days",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if not commits:
        lines.append("> No commits in this period.")
    else:
        by_author = {}
        for c in commits:
            by_author.setdefault(c["author"], []).append(c)

        lines.append("## By Author")
        for author, cs in sorted(by_author.items(), key=lambda x: -len(x[1])):
            lines.append(
                f"- **{author}**: {len(cs)} commits, "
                f"{sum(c['files'] for c in cs)} files"
            )

        lines.append("")
        lines.append("## Recent Commits")
        for c in commits[:15]:
            lines.append(
                f"- `{c['date']}` [{c['hash']}] "
                f"{c['message'][:70]} ({c['files']} files) — {c['author']}"
            )

        total = len(commits)
        lines.append("")
        lines.append("## Value Estimate")
        lines.append(f"- {total} commits × 30 min = **{total * 0.5:.0f} hours**")
        lines.append(f"- At $100/hr = **${total * 50:,.0f}**")

    lines.append("")
    lines.append("---")
    lines.append(
        f"*由 AOA (Action-Oriented Audit) 自动生成 · "
        f"{datetime.now().strftime('%Y-%m-%d')}*"
    )

    report = "\n".join(lines)
    output_path = cfg.get("output", "git_report.md")
    if not os.path.isabs(output_path):
        output_path = os.path.join("profiles", cfg.get("_profile", "git"), output_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  报告已保存：{output_path}")
    try:
        os.startfile(output_path)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("AOA — Action-Oriented Audit v0.6")
        print("")
        print("Usage:")
        print("  python cli.py interactive          (推荐：双击即用，数字选单）")
        print("  python cli.py discover agents      (自动发现本机所有 Agent）")
        print("  python cli.py run <profile> [--audience self|manager|hr|boss] [--feedback \"text\"]")
        print("  python cli.py aggregate feedback")
        print("")
        print("Available profiles:")
        _list_profiles()
        sys.exit(0)

    command = sys.argv[1]

    # ── Interactive mode ──
    if command == "interactive" or command == "i":
        _interactive()
        return

    # ── v0.4: Aggregate feedback ──
    if command == "aggregate":
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        if subcmd == "feedback":
            _aggregate_feedback()
        else:
            print("Usage: python cli.py aggregate feedback")
        return

    # ── v0.6: Discover agents ──
    if command == "discover":
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        if subcmd == "agents":
            _discover_agents()
        else:
            print("Usage: python cli.py discover agents")
        return

    profile_name = sys.argv[2] if len(sys.argv) > 2 else ""
    if not profile_name:
        print("Usage: python cli.py run <profile>")
        _list_profiles()
        sys.exit(1)

    # Parse --feedback flag
    feedback_text = None
    if "--feedback" in sys.argv:
        idx = sys.argv.index("--feedback")
        if idx + 1 < len(sys.argv):
            feedback_text = sys.argv[idx + 1]

    # Parse --audience flag
    audience = "self"
    if "--audience" in sys.argv:
        idx = sys.argv.index("--audience")
        if idx + 1 < len(sys.argv):
            audience = sys.argv[idx + 1]

    if command != "run":
        print(f"Unknown command: {command}")
        print("Usage: python cli.py run <profile>")
        sys.exit(1)

    cfg = load_profile_config(profile_name)
    cfg["_profile"] = profile_name
    cfg["_feedback"] = feedback_text
    cfg["_audience"] = audience
    cfg["_user_info"] = load_user_info(profile_name)

    # Dispatch by profile type
    source = cfg.get("source", "filesystem")

    if source == "git":
        run_git(cfg)
    elif source == "agent_log":
        run_agent_audit(cfg)
    else:
        run_desktop(cfg)


def _interactive():
    """Interactive menu — no commands to remember. Pick from numbered lists."""
    print("")
    print("  ========================================")
    print("    AOA - Action-Oriented Audit")
    print("  ========================================")
    print("")

    # Step 1: Pick profile
    profiles_dir = "profiles"
    profiles = []
    if os.path.exists(profiles_dir):
        for name in sorted(os.listdir(profiles_dir)):
            config_path = os.path.join(profiles_dir, name, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                profiles.append((name, cfg.get("name", name)))

    if not profiles:
        print("  (无可用 profile)")
        return

    print("  选择场景：")
    for i, (key, label) in enumerate(profiles, 1):
        print(f"    [{i}] {label}")
    print("")
    choice = input("  输入数字 (1-{0}): ".format(len(profiles))).strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(profiles):
            print("  无效选择，退出。")
            return
    except ValueError:
        print("  无效输入，退出。")
        return
    profile_name = profiles[idx][0]

    # Step 2: Pick audience
    print("")
    print("  选择视角（谁看这份报告）：")
    audiences = [
        ("self",    "我自己"),
        ("manager", "主管"),
        ("hr",      "HR"),
        ("boss",    "老板/管理员"),
    ]
    for i, (key, label) in enumerate(audiences, 1):
        print(f"    [{i}] {label}")
    print("")
    aud_choice = input("  输入数字 (1-{0}, 默认1): ".format(len(audiences))).strip()
    audience = "self"
    try:
        if aud_choice:
            aud_idx = int(aud_choice) - 1
            if 0 <= aud_idx < len(audiences):
                audience = audiences[aud_idx][0]
    except ValueError:
        pass

    # Step 3: Feedback (optional)
    print("")
    feedback = input("  今日反馈（直接回车跳过）: ").strip()

    # Step 4: Run
    print("")
    print(f"  场景: {profiles[idx][1]}")
    print(f"  视角: {audience}")
    if feedback:
        print(f"  反馈: {feedback[:50]}{'...' if len(feedback) > 50 else ''}")

    cfg = load_profile_config(profile_name)
    cfg["_profile"] = profile_name
    cfg["_audience"] = audience
    cfg["_feedback"] = feedback if feedback else None
    cfg["_user_info"] = load_user_info(profile_name)
    cfg["_interactive"] = True

    source = cfg.get("source", "filesystem")
    if source == "git":
        run_git(cfg)
    elif source == "agent_log":
        run_agent_audit(cfg)
    else:
        run_desktop(cfg)


def _discover_agents():
    """Auto-detect all agents on this machine and present a summary."""
    print("")
    print("  ========================================")
    print("    AOA - Agent Discovery")
    print("  ========================================")
    print(f"  扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("")

    # Known agent log locations
    known_locations = [
        ("Claude Code", "C:/Users/Hi/.claude/projects"),
    ]

    # Also check existing agent profiles
    profiles_dir = "profiles"
    if os.path.exists(profiles_dir):
        for name in os.listdir(profiles_dir):
            config_path = os.path.join(profiles_dir, name, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("source") == "agent_log":
                    known_locations.append((cfg.get("name", name), cfg.get("log_dir", "")))

    # Dedupe by log_dir
    seen = set()
    unique = []
    for name, path in known_locations:
        if path not in seen:
            seen.add(path)
            unique.append((name, path))

    if not unique:
        print("  (未发现 Agent 日志目录)")
        print("")
        print("  配置方法：")
        print("    在 profiles/<agent-name>/config.json 中设置：")
        print('    {"source": "agent_log", "log_dir": "/path/to/agent/logs"}')
        return

    print(f"  发现 {len(unique)} 个 Agent 日志源：")
    print("")

    total_sessions = 0
    total_tools = 0
    total_cost = 0.0

    for i, (name, log_dir) in enumerate(unique, 1):
        exists = os.path.exists(log_dir)
        if not exists:
            print(f"  [{i}] {name}")
            print(f"      路径：{log_dir}")
            print(f"      状态：目录不存在")
            print("")
            continue

        # Quick scan — last 7 days
        sessions = scan_agent_logs(log_dir, days=7)
        main_sessions = [s for s in sessions if not s["is_subagent"]]
        sub_sessions = [s for s in sessions if s["is_subagent"]]
        tools = sum(s["tool_calls"] for s in sessions)
        users = sum(s["user_msgs"] for s in sessions)

        # Rough cost estimate
        est_cost = len(main_sessions) * 3.0

        last_active = ""
        if main_sessions:
            last_active = main_sessions[0]["timestamp"][:10]

        # Collect titles & keywords
        all_titles = []
        for s in main_sessions:
            title = s.get("title", "")
            if title:
                all_titles.append(title)

        print(f"  [{i}] {name}")
        print(f"      路径：{log_dir}")
        print(f"      近 7 天：{len(main_sessions)} 主会话 | {len(sub_sessions)} 子 Agent")
        print(f"      交互：{users} 请求 | {tools} 工具调用")
        print(f"      估算成本：${est_cost:.0f}")
        if last_active:
            print(f"      最近活跃：{last_active}")

        # Show recent session titles
        if all_titles:
            print(f"      最近会话主题：")
            for t in all_titles[-8:]:
                print(f"        - {t[:70]}")

        # Sub-agent names with types
        if sub_sessions:
            sub_list = []
            for s in sub_sessions:
                atype = s.get("agent_type", "")
                adesc = s.get("agent_desc", s.get("title", ""))
                label = f"{atype}: {adesc}" if atype else (adesc or s["id"][:20])
                sub_list.append(label)
            unique_subs = list(set(sub_list))
            print(f"      子 Agent：{len(unique_subs)} 个")
            for sn in unique_subs[:5]:
                print(f"        - {sn[:80]}")
            if len(unique_subs) > 5:
                print(f"        ... 等 {len(unique_subs)} 个")

        # Keyword extraction from titles + descriptions (no chopping)
        if all_titles or sub_sessions:
            kw = {}
            stop_en = {"the", "a", "an", "and", "or", "of", "in", "to", "for", "is",
                       "with", "on", "at", "by", "from", "this", "that", "it", "be"}

            def extract_phrases(text):
                """Extract whole meaningful units: English words + full title text."""
                # English whole words (3+ chars)
                import re
                en_words = re.findall(r'[a-zA-Z]{3,}', text)
                for w in en_words:
                    wl = w.lower()
                    if wl not in stop_en:
                        kw[wl] = kw.get(wl, 0) + 1
                # Full title as phrase (keep Chinese intact)
                clean = text.strip()
                if len(clean) >= 4:
                    kw[clean] = kw.get(clean, 0) + 1

            for t in all_titles:
                if t:
                    extract_phrases(t)
            for s in sub_sessions:
                desc = s.get("agent_desc", "")
                if desc:
                    extract_phrases(desc)

            # Show top phrases (whole titles/descriptions, not fragments)
            # First show English keywords that repeat
            en_kw = {k: v for k, v in kw.items() if k.isascii() and v >= 2}
            # Then show full Chinese phrases that repeat
            cn_kw = {k: v for k, v in kw.items() if not k.isascii() and v >= 2}

            if en_kw or cn_kw:
                print(f"      高频主题：")
                # English keywords
                en_top = sorted(en_kw.items(), key=lambda x: -x[1])[:8]
                for w, c in en_top:
                    print(f"        [{c}x] {w}")
                # Full repeating Chinese titles
                cn_top = sorted(cn_kw.items(), key=lambda x: -x[1])[:5]
                for w, c in cn_top:
                    print(f"        [{c}x] {w[:70]}")
        print("")

        total_sessions += len(main_sessions)
        total_tools += tools
        total_cost += est_cost

    print("  ---")
    print(f"  Agent 总计：{total_sessions} 会话 | {total_tools} 工具调用 | 估算总成本 ${total_cost:.0f}")
    print("")

    # ── Also show AOA's own human profiles ──
    if os.path.exists(profiles_dir):
        human_profiles = []
        for name in os.listdir(profiles_dir):
            config_path = os.path.join(profiles_dir, name, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("source") != "agent_log":
                    human_profiles.append((name, cfg))
        if human_profiles:
            print(f"  AOA 追踪的 {len(human_profiles)} 个工作区：")
            for pname, pcfg in human_profiles:
                dirs = pcfg.get("scan_dirs", [])
                print(f"    [{pname}] {pcfg.get('name', pname)} → {', '.join(dirs[:2])}")
            print("")

    print("  审计命令：")
    # Find matching profile names
    for _, log_dir in unique:
        matched = None
        if os.path.exists(profiles_dir):
            for pname in os.listdir(profiles_dir):
                cpath = os.path.join(profiles_dir, pname, "config.json")
                if os.path.exists(cpath):
                    with open(cpath, "r", encoding="utf-8") as f:
                        pcfg = json.load(f)
                    if pcfg.get("log_dir") == log_dir:
                        matched = pname
                        break
        if matched:
            print(f"    python cli.py run {matched}")
        else:
            print(f"    (未找到对应 profile，日志目录: {log_dir})")
    print("")


def _list_profiles():
    """List all available profile directories."""
    profiles_dir = "profiles"
    if os.path.exists(profiles_dir):
        for name in os.listdir(profiles_dir):
            config_path = os.path.join(profiles_dir, name, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                print(f"  {name:12s} — {cfg.get('name', '(unnamed)')}")
    else:
        print("  (no profiles found)")


# ═══════════════════════════════════════════════════════════════
# v0.4: Feedback — complaint/assistance window + aggregation
# ═══════════════════════════════════════════════════════════════

def _append_feedback(report_path, text, profile_name):
    """Append user feedback to an existing report file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    section = [
        "",
        "## \U0001f4ac 今日反馈",
        f"- 时间：{ts}",
        f"- 来源：{profile_name}",
        f"- 内容：{text}",
        "",
    ]
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n".join(section))


def _append_feedback_template(report_path):
    """Append an empty feedback template to the report."""
    template = [
        "",
        "## \U0001f4ac 今日反馈",
        "- 最大阻力：___",
        "- 需要协助：___",
        "- 想吐槽的：___",
        "",
    ]
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n".join(template))


def _aggregate_feedback():
    """Scan all profile reports and aggregate feedback sections.

    Usage: python cli.py aggregate feedback
    """
    print("\n  AOA — 反馈汇总")
    print(f"  扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("")

    profiles_dir = "profiles"
    if not os.path.exists(profiles_dir):
        print("  (无 profile 目录)")
        return

    all_feedback = []
    for name in os.listdir(profiles_dir):
        report_path = os.path.join(profiles_dir, name, "report.md")
        if not os.path.exists(report_path):
            continue

        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract feedback section
        marker = "## \U0001f4ac 今日反馈"
        if marker not in content:
            continue

        idx = content.index(marker)
        section = content[idx:].split("\n## ")[0]  # until next section
        section = section.strip()

        # Extract report date
        date_line = ""
        for line in content.split("\n")[:5]:
            if "生成时间" in line:
                date_line = line.replace("生成时间：", "").strip()
                break

        all_feedback.append({
            "profile": name,
            "date": date_line,
            "section": section,
        })

    if not all_feedback:
        print("  > 暂无反馈数据。")
        print("")
        print("  使用方法：")
        print('    python cli.py run <profile> --feedback "你的反馈内容"')
        return

    # Output aggregated
    total = len(all_feedback)
    print(f"  共 {total} 条反馈：")
    print("")

    # Group and sort
    for i, fb in enumerate(all_feedback, 1):
        print(f"--- {i}. {fb['profile']} ({fb['date']}) ---")
        # Skip the marker line, show content
        lines = fb["section"].split("\n")[1:]  # skip "## 💬 今日反馈"
        for line in lines:
            if line.startswith("- "):
                print(f"  {line}")
        print("")

    # Simple frequency analysis
    print("---")
    print("  [关键词频次]")
    keywords = {}
    for fb in all_feedback:
        text = fb["section"].lower()
        for kw in ["协助", "阻力", "慢", "卡", "阻塞", "部署", "文档", "工具", "沟通", "流程"]:
            if kw in text:
                keywords[kw] = keywords.get(kw, 0) + 1

    if keywords:
        for kw, count in sorted(keywords.items(), key=lambda x: -x[1]):
            bar = "█" * count
            print(f"  {kw:6s} {bar} {count}")
    print("")


if __name__ == "__main__":
    main()
