"""Filesystem adapter — scan directories for recently modified files."""

import os
import time


def scan_files(dirs, days, ignore=None):
    """Scan directories for files modified within `days`.

    Returns list of dicts: {path, root, time, ext}
    """
    if ignore is None:
        ignore = {".git", "node_modules", "__pycache__", ".obsidian", ".trash", ".cache"}
    cutoff = time.time() - days * 86400
    files = []
    for root_dir in dirs:
        if not os.path.exists(root_dir):
            continue
        for dirpath, dirs_list, filenames in os.walk(root_dir):
            dirs_list[:] = [d for d in dirs_list if d not in ignore and not d.startswith(".")]
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    mtime = os.path.getmtime(fp)
                    if mtime > cutoff:
                        files.append({
                            "path": fp.replace(root_dir, "").lstrip("\\").lstrip("/"),
                            "root": root_dir,
                            "time": mtime,
                            "ext": os.path.splitext(f)[1] or "(none)",
                        })
                except OSError:
                    pass
    files.sort(key=lambda x: x["time"], reverse=True)
    return files
