"""v0.8 — Asset Registry: classify what was PRODUCED, not just what was DONE.

Artifact = observable output with a type and a weight.
Weight is the baseline value multiplier for this type of output.
The org's value model applies on top.
"""

from collections import Counter

# ── Artifact type registry ──
# type_key -> (category, weight)
# Weight reflects baseline "how valuable is one unit of this output"
ARTIFACT_TYPES = {
    # Code
    ".py": ("code", 1.0),
    ".ts": ("code", 1.0),
    ".js": ("code", 1.0),
    ".rs": ("code", 1.2),
    ".go": ("code", 1.0),
    ".java": ("code", 1.0),
    ".c": ("code", 1.2),
    ".cpp": ("code", 1.2),
    ".h": ("code", 0.8),
    # Documents
    ".md": ("document", 0.6),
    ".txt": ("document", 0.3),
    ".rst": ("document", 0.6),
    # Config
    ".json": ("config", 0.3),
    ".yaml": ("config", 0.3),
    ".toml": ("config", 0.3),
    ".ini": ("config", 0.2),
    ".cfg": ("config", 0.2),
    # Scripts
    ".bat": ("script", 0.4),
    ".ps1": ("script", 0.5),
    ".sh": ("script", 0.5),
    # Images / assets
    ".png": ("asset", 0.2),
    ".jpg": ("asset", 0.2),
    ".svg": ("asset", 0.3),
    # Git operations
    "git_commit": ("commit", 2.0),
    "git_push": ("delivery", 3.0),
    "git_pr": ("delivery", 5.0),
    # Quality
    "test_result": ("quality", 3.0),
    "benchmark_result": ("benchmark", 8.0),
    # Knowledge
    "dataset": ("dataset", 10.0),
    "sop_document": ("sop", 5.0),
    "skill_file": ("skill", 4.0),
    # Infrastructure
    "plugin": ("plugin", 6.0),
    "extension": ("extension", 6.0),
    "repo": ("repo", 20.0),
    "deploy": ("deploy", 4.0),
    "install": ("install", 1.0),
}

CATEGORY_LABELS = {
    "code": "代码",
    "document": "文档",
    "config": "配置",
    "script": "脚本",
    "asset": "资源",
    "commit": "提交",
    "delivery": "交付",
    "quality": "质量保障",
    "benchmark": "基准测试",
    "dataset": "数据集",
    "sop": "SOP",
    "skill": "技能文件",
    "plugin": "插件",
    "extension": "扩展",
    "repo": "仓库",
    "deploy": "部署",
    "install": "安装",
}


def classify_file(filepath):
    """Classify a file path into an artifact type and weight."""
    import os
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ARTIFACT_TYPES:
        return ARTIFACT_TYPES[ext]
    # Check for special filenames
    basename = os.path.basename(filepath).lower()
    if "sop" in basename or "standard" in basename:
        return ("sop", ARTIFACT_TYPES["sop_document"][1])
    if "skill" in basename or "prompt" in basename:
        return ("skill", ARTIFACT_TYPES["skill_file"][1])
    if "benchmark" in basename or "bench" in basename:
        return ("benchmark", ARTIFACT_TYPES["benchmark_result"][1])
    return ("other", 0.1)


def classify_git_op(op_type):
    """Classify a git operation."""
    mapping = {
        "commit": ("commit", ARTIFACT_TYPES["git_commit"][1]),
        "push": ("delivery", ARTIFACT_TYPES["git_push"][1]),
        "pr": ("delivery", ARTIFACT_TYPES["git_pr"][1]),
    }
    return mapping.get(op_type, ("other", 0.1))


def aggregate_asset_value(artifacts_by_category):
    """Compute weighted asset value from category distribution.

    Args:
        artifacts_by_category: {category: count}

    Returns:
        {category_label: {count, weight, weighted_value}}
    """
    result = {}
    total_weighted = 0.0
    for cat, count in artifacts_by_category.items():
        # Find the weight for this category
        weight = 0.1
        for _, (c, w) in ARTIFACT_TYPES.items():
            if c == cat:
                weight = w
                break
        weighted = count * weight
        result[cat] = {
            "count": count,
            "weight": weight,
            "weighted": round(weighted, 1),
        }
        total_weighted += weighted

    return result, round(total_weighted, 1)
