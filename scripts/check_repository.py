"""Dependency-free checks for the initial repository scaffold."""
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "CONTRIBUTING.md", ".github/workflows/ci.yml",
    "frontend/README.md", "backend/README.md",
    "frontend/.env.example", "backend/.env.example",
    "docs/architecture.md", "docs/api-contract.md", "docs/decisions.md",
    "docs/deployment.md", "docs/devops-guide.md", "docs/first-week.md",
)


def main():
    errors = []
    for name in REQUIRED:
        path = ROOT / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"Missing or empty file: {name}")
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    paths = [Path(p) for p in result.stdout.decode().split("\0") if p]
    for relative in paths:
        path = ROOT / relative
        if path.name == ".env" or (
            path.name.startswith(".env.") and path.name != ".env.example"
        ):
            errors.append(f"Environment file must not be committed: {relative}")
        if path.suffix == ".md" and path.is_file():
            content = path.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
                if "://" in link or link.startswith(("#", "mailto:")):
                    continue
                target = unquote(link.split("#", 1)[0])
                if target and not (path.parent / target).exists():
                    errors.append(f"Broken local link in {relative}: {link}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Repository checks passed. Application checks are not configured yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
