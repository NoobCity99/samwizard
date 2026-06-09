from __future__ import annotations

import argparse
import tarfile
from pathlib import Path


DEFAULT_VERSION = "0.6.0"
DEFAULT_OUTPUT = Path("dist/samwizard-app.tar.gz")
INCLUDE_PATHS = [
    Path("app"),
    Path("requirements.txt"),
    Path("README.md"),
    Path("VERSION"),
]
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".venv-wsl",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def should_include(path: Path) -> bool:
    return not any(part in EXCLUDED_PARTS for part in path.parts)


def build_bundle(output: Path = DEFAULT_OUTPUT, version: str = DEFAULT_VERSION) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    version_path = Path("VERSION")
    version_path.write_text(version.strip() + "\n", encoding="utf-8")

    with tarfile.open(output, "w:gz") as archive:
        for include_path in INCLUDE_PATHS:
            if not include_path.exists():
                raise FileNotFoundError(include_path)
            if include_path.is_dir():
                for item in include_path.rglob("*"):
                    if item.is_file() and should_include(item):
                        archive.add(item, arcname=item.as_posix())
            elif should_include(include_path):
                archive.add(include_path, arcname=include_path.as_posix())
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Samba Wizard release bundle.")
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = build_bundle(args.output, args.version)
    print(f"Built {output}")


if __name__ == "__main__":
    main()
