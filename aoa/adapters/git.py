"""Git adapter — scan git log for recent commits."""

import subprocess


def scan_git(repo_path, days=5):
    """Scan git log for commits within `days`.

    Returns list of dicts: {hash, message, author, date, files}
    """
    try:
        since = f"{days} days ago"
        result = subprocess.run(
            ["git", "-C", repo_path, "log", f"--since={since}",
             "--pretty=format:%h|%s|%an|%ai", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", timeout=10
        )
        commits = []
        current = None
        for line in result.stdout.strip().split("\n"):
            if "|" in line and not line.startswith(" "):
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    current = {
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3][:10],
                        "files": 0,
                    }
                    commits.append(current)
            elif line.strip() and current:
                current["files"] += 1
        return commits
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
