"""Docs consistency checks for CI."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def _schema_version() -> str:
    constants = (ROOT / "src" / "daylog" / "constants.py").read_text(encoding="utf-8")
    for line in constants.splitlines():
        if line.startswith("SCHEMA_VERSION"):
            return line.split("=")[1].strip().strip('"')
    raise SystemExit("SCHEMA_VERSION not found")


def _dependencies() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    cleaned = []
    for dep in deps:
        name = dep.split(";")[0].strip()
        for token in ["<", ">", "=", "!", "~"]:
            name = name.split(token)[0]
        cleaned.append(name.strip())
    return cleaned


def main() -> int:
    schema_version = _schema_version()
    data_formats = (ROOT / "docs" / "wiki" / "data_formats.md").read_text(
        encoding="utf-8"
    )
    if schema_version not in data_formats:
        raise SystemExit("data_formats.md missing SCHEMA_VERSION")

    deps_doc = (ROOT / "docs" / "wiki" / "dependencies.md").read_text(encoding="utf-8").lower()
    missing = [dep for dep in _dependencies() if dep.lower() not in deps_doc]
    if missing:
        raise SystemExit(f"dependencies.md missing: {', '.join(missing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
