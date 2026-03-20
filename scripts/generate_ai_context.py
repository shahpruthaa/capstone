from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "__pycache__",
    ".venv",
    ".idea",
    ".vscode",
}

DEFAULT_EXCLUDED_PREFIXES = (
    "data/raw/",
)

TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".css",
    ".html",
    ".yml",
    ".yaml",
    ".env",
    ".example",
    ".ini",
    ".toml",
    ".sql",
    ".mako",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a directory-aware AI context text file for this project.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output",
        default="project_context.txt",
        help="Output text file path. Defaults to project_context.txt",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=200_000,
        help="Maximum size of an included text file in bytes. Larger files are summarized instead.",
    )
    return parser.parse_args()


def should_skip(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    if any(part in DEFAULT_EXCLUDED_DIRS for part in path.parts):
        return True
    return any(relative.startswith(prefix) for prefix in DEFAULT_EXCLUDED_PREFIXES)


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.name in {".gitignore", ".dockerignore", ".env.example"}


def build_tree_lines(root: Path) -> list[str]:
    lines = [f"{root.name}/"]

    def walk(directory: Path, prefix: str = "") -> None:
        children = [
            child for child in sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
            if not should_skip(child, root)
        ]
        for index, child in enumerate(children):
            connector = "`-- " if index == len(children) - 1 else "|-- "
            lines.append(f"{prefix}{connector}{child.name}{'/' if child.is_dir() else ''}")
            if child.is_dir():
                extension = "    " if index == len(children) - 1 else "|   "
                walk(child, prefix + extension)

    walk(root)
    return lines


def iter_project_files(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    skipped_summaries: list[str] = []

    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        relative_root = current_path.relative_to(root).as_posix() if current_path != root else "."

        kept_dirs = []
        for dirname in sorted(dirnames):
            candidate = current_path / dirname
            if should_skip(candidate, root):
                skipped_summaries.append(f"{relative_root}/{dirname} | skipped directory")
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            candidate = current_path / filename
            if should_skip(candidate, root):
                continue
            files.append(candidate)

    return files, skipped_summaries


def summarize_files(root: Path, output: Path, max_file_bytes: int) -> tuple[list[str], list[str], list[Path]]:
    included = []
    skipped = []
    content_files: list[Path] = []

    project_files, skipped_dirs = iter_project_files(root)
    skipped.extend(skipped_dirs)

    for path in project_files:
        if path.resolve() == output.resolve():
            continue
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        if is_text_file(path) and size <= max_file_bytes:
            included.append(f"{relative} | {size} bytes | full text included")
            content_files.append(path)
        elif is_text_file(path):
            included.append(f"{relative} | {size} bytes | text file too large, summary only")
        else:
            skipped.append(f"{relative} | {size} bytes | non-text or binary-like file")

    return included, skipped, content_files


def build_output(root: Path, included: list[str], skipped: list[str], content_files: list[Path]) -> str:
    sections: list[str] = []
    sections.append("# AI Context Export")
    sections.append("")
    sections.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    sections.append(f"Project root: {root.resolve()}")
    sections.append("")
    sections.append("## Directory Tree")
    sections.append("")
    sections.extend(build_tree_lines(root))
    sections.append("")
    sections.append("## Included Files")
    sections.append("")
    sections.extend(included or ["(none)"])
    sections.append("")
    sections.append("## Skipped Files")
    sections.append("")
    sections.extend(skipped or ["(none)"])
    sections.append("")
    sections.append("## File Contents")
    sections.append("")

    for path in content_files:
        relative = path.relative_to(root).as_posix()
        sections.append(f"### {relative}")
        sections.append("")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        sections.append("```text")
        sections.append(content.rstrip())
        sections.append("```")
        sections.append("")

    return "\n".join(sections)


if __name__ == "__main__":
    args = parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    included_files, skipped_files, content_files = summarize_files(root, output, args.max_file_bytes)
    output.write_text(
        build_output(root, included_files, skipped_files, content_files),
        encoding="utf-8",
    )
    print(f"Wrote AI context export to: {output}")
