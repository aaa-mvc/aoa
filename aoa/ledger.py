"""v0.8.2 — Artifact Ledger: unified asset registry with grouping and scoring.

The Ledger is the single source of truth for "what was produced."
It stores typed, weighted artifact records and supports:
  - category grouping
  - project filtering
  - weighted scoring
  - export to dict/JSON
"""

from collections import Counter, defaultdict

# ── Weight table (single source of truth) ──
WEIGHTS = {
    # Code
    ".py": ("code", 1.0), ".ts": ("code", 1.0), ".js": ("code", 1.0),
    ".rs": ("code", 1.2), ".go": ("code", 1.0), ".java": ("code", 1.0),
    ".c": ("code", 1.2), ".cpp": ("code", 1.2), ".h": ("code", 0.8),
    # Documents
    ".md": ("document", 0.6), ".txt": ("document", 0.3), ".rst": ("document", 0.6),
    # Config
    ".json": ("config", 0.3), ".yaml": ("config", 0.3), ".yml": ("config", 0.3),
    ".toml": ("config", 0.3), ".ini": ("config", 0.2),
    # Scripts
    ".bat": ("script", 0.4), ".ps1": ("script", 0.5), ".sh": ("script", 0.5),
    # Assets
    ".png": ("asset", 0.2), ".jpg": ("asset", 0.2), ".svg": ("asset", 0.3),
    # Data
    ".csv": ("data", 0.4), ".sql": ("data", 0.6), ".ipynb": ("notebook", 1.5),
    # Ops (non-file artifacts)
    "git_commit": ("commit", 2.0),
    "git_push": ("delivery", 3.0),
    "test_run": ("test", 3.0),
    "install": ("install", 1.0),
    "deploy": ("deploy", 4.0),
    "benchmark": ("benchmark", 8.0),
    "dataset": ("dataset", 10.0),
    "sop": ("sop", 5.0),
    "plugin": ("plugin", 6.0),
    "repo": ("repo", 20.0),
}

CATEGORY_LABELS = {
    "code": "Code Files", "document": "Documents", "config": "Config Files",
    "script": "Scripts", "asset": "Assets", "data": "Data Files",
    "notebook": "Notebooks", "commit": "Commits", "delivery": "Deliveries",
    "test": "Test Runs", "install": "Installs", "deploy": "Deploys",
    "benchmark": "Benchmarks", "dataset": "Datasets", "sop": "SOP Docs",
    "plugin": "Plugins", "repo": "Repos", "other": "Other",
}


def classify(path_or_op):
    """Classify a file path or operation name → (category, weight)."""
    import os
    if not path_or_op:
        return ("other", 0.1)
    # Direct op match
    if path_or_op in WEIGHTS:
        return WEIGHTS[path_or_op]
    # File extension match
    ext = os.path.splitext(path_or_op)[1].lower()
    if ext in WEIGHTS:
        return WEIGHTS[ext]
    # Heuristic
    basename = os.path.basename(path_or_op).lower()
    if "readme" in basename or "changelog" in basename:
        return ("document", 0.8)
    if "license" in basename:
        return ("document", 1.0)
    return ("other", 0.1)


def extract_project(filepath):
    """D:/Brain/AOA/cli.py → AOA"""
    path = filepath.replace(chr(92), "/")
    if ":/" in path:
        path = path.split(":/", 1)[1]
    parts = [p for p in path.split("/") if p and not p.startswith(".")]
    skip = {"Users", "Hi", "Brain", "home", "projects", "src", "tmp"}
    meaningful = [p for p in parts if p not in skip]
    return meaningful[0] if meaningful else (parts[0] if parts else "unknown")


class ArtifactLedger:
    """Registry of produced artifacts with weighted scoring."""

    def __init__(self):
        self.rows = []

    def add(self, artifact_type, path="", project="", weight=None):
        """Add one artifact record.

        Args:
            artifact_type: op name ('git_commit') or file path ('D:/Brain/AOA/cli.py')
            path: original file path (if applicable)
            project: project name override (auto-detected if empty)
            weight: override weight (auto-detected if None)
        """
        cat, w = classify(artifact_type)
        if weight is not None:
            w = weight
        proj = project or extract_project(path or artifact_type)
        self.rows.append({
            "type": cat,
            "path": path or artifact_type,
            "project": proj,
            "weight": w,
        })

    def add_batch(self, artifact_type, count, project="", weight=None):
        """Add N artifacts of the same type at once."""
        for _ in range(count):
            self.add(artifact_type, path="", project=project, weight=weight)

    def by_category(self):
        """Group artifacts by category with counts and weighted scores."""
        groups = defaultdict(lambda: {"count": 0, "weight": 0.0, "weighted": 0.0})
        for r in self.rows:
            cat = r["type"]
            groups[cat]["count"] += 1
            groups[cat]["weight"] = r["weight"]
            groups[cat]["weighted"] += r["weight"]
        return dict(groups)

    def by_project(self):
        """Group artifacts by project with weighted scores."""
        groups = defaultdict(lambda: {"count": 0, "score": 0.0})
        for r in self.rows:
            proj = r["project"]
            groups[proj]["count"] += 1
            groups[proj]["score"] += r["weight"]
        return dict(groups)

    def score(self):
        """Total weighted score across all artifacts."""
        return round(sum(r["weight"] for r in self.rows), 1)

    def total_count(self):
        return len(self.rows)

    def summary(self):
        """Human-readable multi-line summary."""
        lines = []
        by_cat = self.by_category()
        # Sort by weighted score descending
        sorted_cats = sorted(by_cat.items(), key=lambda x: -x[1]["weighted"])
        for cat, info in sorted_cats:
            label = CATEGORY_LABELS.get(cat, cat)
            count = info["count"]
            wscore = info["weighted"]
            lines.append(f"- {label:20s} {count:4d}  × 权重 {info['weight']:.1f}  = {wscore:.0f}")
        lines.append(f"- {'─' * 45}")
        lines.append(f"  {'Artifact Score':20s} {self.total_count():4d}          = {self.score():.0f}")
        return lines

    def to_dict(self):
        """Export ledger as a dict (JSON-serializable)."""
        return {
            "total_count": self.total_count(),
            "total_score": self.score(),
            "by_category": {
                CATEGORY_LABELS.get(k, k): {"count": v["count"], "score": v["weighted"]}
                for k, v in self.by_category().items()
            },
            "by_project": {
                k: {"count": v["count"], "score": v["score"]}
                for k, v in self.by_project().items()
            },
        }


def build_ledger_from_sessions(sessions):
    """Build an ArtifactLedger from agent session data."""
    ledger = ArtifactLedger()

    for s in sessions:
        art = s.get("artifacts", {})
        proj = "unknown"
        projs = s.get("projects", {})
        if projs:
            top = max(projs, key=projs.get)
            proj = top.split("/")[-1] if "/" in top else top

        # File artifacts
        ledger.add_batch("write", art.get("new_files", 0), project=proj, weight=1.0)
        ledger.add_batch("edit", art.get("modified_files", 0), project=proj, weight=0.6)

        # Ops artifacts
        for op, weight_key in [("git_commits", "git_commit"),
                                ("git_pushes", "git_push"),
                                ("test_runs", "test_run"),
                                ("installs", "install")]:
            count = art.get(op, 0)
            if count:
                cat, w = classify(weight_key)
                ledger.add_batch(weight_key, count, project=proj, weight=w)

    return ledger
