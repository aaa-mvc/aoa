"""v0.8 — Artifact Extractor: scan sessions for produced artifacts.

Classifies each file by extension → artifact type → value weight.
Extracts project name from file path.

Usage:
    from aoa.artifact_extractor import extract_artifacts, summarize_assets
    assets = extract_artifacts(sessions)
    summary = summarize_assets(assets)
"""

import os
from collections import Counter

# ── File extension → (artifact type, value weight) ──
EXT_MAP = {
    # Code
    ".py": ("code", 1.0),
    ".ts": ("code", 1.0),
    ".tsx": ("code", 1.0),
    ".js": ("code", 1.0),
    ".jsx": ("code", 1.0),
    ".rs": ("code", 1.2),
    ".go": ("code", 1.0),
    ".java": ("code", 1.0),
    ".c": ("code", 1.2),
    ".cpp": ("code", 1.2),
    ".h": ("code", 0.8),
    ".hpp": ("code", 0.8),
    # Documents
    ".md": ("document", 0.6),
    ".txt": ("document", 0.3),
    ".rst": ("document", 0.6),
    ".pdf": ("document", 2.0),
    # Config
    ".json": ("config", 0.3),
    ".yaml": ("config", 0.3),
    ".yml": ("config", 0.3),
    ".toml": ("config", 0.3),
    ".ini": ("config", 0.2),
    ".cfg": ("config", 0.2),
    ".lock": ("config", 0.2),
    # Scripts
    ".bat": ("script", 0.4),
    ".ps1": ("script", 0.5),
    ".sh": ("script", 0.5),
    # Images / assets
    ".png": ("asset", 0.2),
    ".jpg": ("asset", 0.2),
    ".jpeg": ("asset", 0.2),
    ".svg": ("asset", 0.3),
    ".gif": ("asset", 0.1),
    # Web
    ".html": ("web", 0.4),
    ".css": ("web", 0.5),
    ".scss": ("web", 0.5),
    # Data
    ".csv": ("data", 0.4),
    ".sql": ("data", 0.6),
    ".db": ("data", 2.0),
    # Notebooks
    ".ipynb": ("notebook", 1.5),
}

# Git ops
GIT_WEIGHTS = {
    "commit": 2.0,
    "push": 3.0,
    "pr": 5.0,
}

# Other ops
OP_WEIGHTS = {
    "test_run": 3.0,
    "install": 1.0,
    "deploy": 4.0,
}

CATEGORY_LABELS = {
    "code": "代码",
    "document": "文档",
    "config": "配置",
    "script": "脚本",
    "asset": "资源",
    "web": "前端",
    "data": "数据",
    "notebook": "笔记本",
    "commit": "提交",
    "delivery": "交付",
    "test": "测试",
    "deploy": "部署",
    "install": "安装",
    "other": "其他",
}


def classify_file(filepath):
    """Classify a single file path → (artifact_type, weight)."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in EXT_MAP:
        return EXT_MAP[ext]
    basename = os.path.basename(filepath).lower()
    if "readme" in basename or "changelog" in basename:
        return ("document", 0.8)
    if "license" in basename:
        return ("document", 1.0)
    return ("other", 0.1)


def extract_project(filepath):
    """Extract short project name from a full path.

    D:/Brain/AOA/cli.py         → AOA
    D:/Brain/AFA/desktop_review → AFA
    C:/Users/Hi/.claude/projects → claude
    """
    path = filepath.replace(chr(92), "/")
    # Remove drive letter
    if ":/" in path:
        path = path.split(":/", 1)[1]
    parts = [p for p in path.split("/") if p and not p.startswith(".")]
    # Skip common prefix dirs
    skip = {"Users", "Hi", "Brain", "home", "projects", "src"}
    meaningful = [p for p in parts if p not in skip]
    if meaningful:
        return meaningful[0]
    elif parts:
        return parts[0]
    return "unknown"


def extract_artifacts(sessions):
    """Extract all artifacts from agent sessions.

    Returns list of dicts:
        {type, path, project, weight, category}
    """
    artifacts = []

    for s in sessions:
        project = "unknown"
        # Derive project from the session's most-hit project dir
        projs = s.get("projects", {})
        if projs:
            top = max(projs, key=projs.get)
            project = top.split("/")[-1] if "/" in top else top

        # New files
        art = s.get("artifacts", {})
        # We can't get individual file paths from aggregated artifacts,
        # but we can infer from the session's _file_paths

    return artifacts


def summarize_from_aggregates(sessions):
    """Summarize assets from already-aggregated session data.

    Uses the artifact counts already collected during parsing.
    """
    # Count artifacts by type
    total_new = 0
    total_modified = 0
    ops = Counter()

    for s in sessions:
        art = s.get("artifacts", {})
        total_new += art.get("new_files", 0)
        total_modified += art.get("modified_files", 0)
        ops["commit"] += art.get("git_commits", 0)
        ops["delivery"] += art.get("git_pushes", 0)
        ops["test"] += art.get("test_runs", 0)
        ops["install"] += art.get("installs", 0)

    assets = []
    if total_new:
        assets.append(("code", total_new, 1.0, total_new * 1.0))
    if total_modified:
        assets.append(("document", total_modified, 0.6, total_modified * 0.6))
    for op_type, count in ops.items():
        if count:
            w = OP_WEIGHTS.get(op_type, GIT_WEIGHTS.get(op_type, 1.0))
            assets.append((op_type, count, w, count * w))

    return assets


def format_asset_summary(sessions):
    """Generate a human-readable asset summary from sessions."""
    assets = summarize_from_aggregates(sessions)
    lines = []
    total_weighted = 0.0

    label_map = {
        "code": ("新建文件", "个"),
        "document": ("修改文件", "个"),
        "commit": ("Git 提交", "次"),
        "delivery": ("Git 推送", "次"),
        "test": ("测试运行", "次"),
        "install": ("依赖安装", "次"),
    }

    for atype, count, weight, weighted_val in assets:
        label, unit = label_map.get(atype, (atype, ""))
        lines.append(f"- {label}：{count} {unit} × 权重 {weight} = **{weighted_val:.0f}**")
        total_weighted += weighted_val

    lines.append(f"- **加权资产总分：{total_weighted:.0f}**")
    return lines, total_weighted
