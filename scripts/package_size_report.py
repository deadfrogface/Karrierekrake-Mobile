"""Where the space of a built package goes: total, largest folders and largest files.

Printed into the job log and written as JSON, so a size change can be traced to a file
without downloading the package.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def size_report(root: Path, *, top: int = 40) -> dict:
    root = Path(root)
    files: list[tuple[str, int]] = []
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            files.append((path.relative_to(root).as_posix(), path.stat().st_size))
    folders: Counter[str] = Counter()
    for rel, size in files:
        parts = rel.split("/")
        # One level below the program's own library folder, otherwise the first folder.
        depth = 2 if parts[0] in {"_internal", "Frameworks", "Resources"} and len(parts) > 2 else 1
        folders["/".join(parts[:depth]) if len(parts) > depth else "(top level)"] += size
    files.sort(key=lambda item: (-item[1], item[0]))
    return {
        "root": root.name,
        "total_bytes": sum(size for _, size in files),
        "file_count": len(files),
        "largest_folders": [{"path": p, "bytes": b} for p, b in folders.most_common(top)],
        "largest_files": [{"path": p, "bytes": b} for p, b in files[:top]],
    }


def render(report: dict) -> str:
    mb = 1024 * 1024
    lines = [f"{report['root']}: {report['total_bytes'] / mb:.1f} MiB in {report['file_count']} files", "", "Largest folders:"]
    lines += [f"  {item['bytes'] / mb:8.1f} MiB  {item['path']}" for item in report["largest_folders"]]
    lines += ["", "Largest files:"]
    lines += [f"  {item['bytes'] / mb:8.1f} MiB  {item['path']}" for item in report["largest_files"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args(argv)
    report = size_report(args.package, top=args.top)
    print(render(report))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
