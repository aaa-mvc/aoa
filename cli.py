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
from aoa.engine import make_report
from aoa.trace import save as save_trace
from aoa.trace import load_last, load_all
from aoa.delta import compute_focus_dispersion


def load_profile_config(profile_name):
    """Load config.json from profiles/<profile_name>/"""
    config_path = os.path.join("profiles", profile_name, "config.json")
    if not os.path.exists(config_path):
        print(f"  ✗ Profile not found: {profile_name}")
        print(f"    Expected config at: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_profile_config(profile_name, config):
    """Save modified config back to the profile's config.json."""
    config_path = os.path.join("profiles", profile_name, "config.json")
    # Strip internal fields before saving
    clean = {k: v for k, v in config.items() if not k.startswith("_")}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def apply_policy_influence(config, drift_result):
    """v0.2-final: drift signal → behavioral bias on next run's config.

    converge → shrink look_back (deeper focus)
    diverge  → expand look_back (broader awareness)
    stable   → no change
    """
    if drift_result is None or drift_result["signal"] == "insufficient_data":
        return config

    signal = drift_result["signal"]
    strength = 0.2
    old_days = config.get("look_back_days", 5)

    new_config = config.copy()

    if signal == "converging":
        new_config["look_back_days"] = max(1, int(old_days * (1 - strength)))
        new_config["_focus_mode"] = "deep_scan"
        new_config["_policy_applied"] = (
            f"converging → look_back {old_days}→{new_config['look_back_days']}"
        )
    elif signal == "diverging":
        new_config["look_back_days"] = min(14, int(old_days * (1 + strength)))
        new_config["_focus_mode"] = "broad_scan"
        new_config["_policy_applied"] = (
            f"diverging → look_back {old_days}→{new_config['look_back_days']}"
        )
    else:
        new_config["_focus_mode"] = "stable_scan"
        new_config["_policy_applied"] = "stable → no change"

    return new_config


def run_desktop(cfg):
    """Run filesystem scan profile."""
    print(f"\n  AOA — Action-Oriented Audit · {cfg['name']}")
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
    report, _, drift_result = make_report(cfg, files, previous_trace, all_history, current_state)

    # ── v0.2-final: Policy Influence Layer ──
    new_cfg = apply_policy_influence(cfg, drift_result)
    if new_cfg.get("_policy_applied"):
        policy_note = new_cfg.pop("_policy_applied")
        # Persist modified config for next run
        _save_profile_config(cfg.get("_profile", "desktop"), new_cfg)
        print(f"  Policy: {policy_note}")

    # Output
    output_path = cfg.get("output", "report.md")
    # Resolve relative to profile directory
    if not os.path.isabs(output_path):
        output_path = os.path.join("profiles", cfg.get("_profile", "desktop"), output_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  报告已保存：{output_path}")
    safe_id = run_id.replace(":", "-")
    print(f"  Trace 已保存：trace_history/{safe_id}.json")

    # Open report
    try:
        os.startfile(output_path)
    except Exception:
        pass


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
    if len(sys.argv) < 3:
        print("AOA — Action-Oriented Audit v0.2")
        print("")
        print("Usage:")
        print("  python cli.py run <profile>")
        print("")
        print("Available profiles:")
        _list_profiles()
        sys.exit(0)

    command = sys.argv[1]
    profile_name = sys.argv[2]

    if command != "run":
        print(f"Unknown command: {command}")
        print("Usage: python cli.py run <profile>")
        sys.exit(1)

    cfg = load_profile_config(profile_name)
    cfg["_profile"] = profile_name

    # Dispatch by profile type
    source = cfg.get("source", "filesystem")

    if source == "git":
        run_git(cfg)
    else:
        run_desktop(cfg)


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


if __name__ == "__main__":
    main()
