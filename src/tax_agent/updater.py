"""Self-update logic for tax-agent installed via git clone."""

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


CLONE_DIR = Path.home() / ".tax-agent-source"

REPO_URL = "https://github.com/mrelph/tax-prep-agent.git"


@dataclass
class UpdateResult:
    updated: bool = False
    old_ref: str = ""
    new_ref: str = ""
    commit_summary: list[str] = field(default_factory=list)
    error: str = ""


def get_install_type() -> str:
    """Detect how tax-agent was installed.

    Returns "git-clone" if running from a git repo (e.g. ~/.tax-agent-source),
    "editable" if installed as editable from a dev checkout with .git,
    or "pip" for a plain pip/pipx install with no .git directory.
    """
    # Check if the package source directory is inside a git repo
    package_dir = Path(__file__).resolve().parent  # src/tax_agent/
    src_dir = package_dir.parent  # src/
    repo_dir = src_dir.parent  # project root

    if (repo_dir / ".git").is_dir():
        # Installed from a git repo — distinguish clone vs editable dev
        try:
            resolved = repo_dir.resolve()
            clone_resolved = CLONE_DIR.resolve()
            if resolved == clone_resolved:
                return "git-clone"
        except OSError:
            pass
        return "editable"

    return "pip"


def get_repo_dir() -> Path | None:
    """Return the git repo root Path, or None if not a git install."""
    install_type = get_install_type()
    if install_type in ("git-clone", "editable"):
        package_dir = Path(__file__).resolve().parent
        return package_dir.parent.parent
    return None


def _run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def check_for_updates() -> UpdateResult:
    """Check if updates are available without applying them."""
    repo_dir = get_repo_dir()
    if repo_dir is None:
        return UpdateResult(error="Not installed from a git repository. Re-run install.sh to enable updates.")

    # Get current HEAD
    result = _run_git("rev-parse", "--short", "HEAD", cwd=repo_dir)
    if result.returncode != 0:
        return UpdateResult(error=f"Failed to get current ref: {result.stderr.strip()}")
    old_ref = result.stdout.strip()

    # Fetch latest
    result = _run_git("fetch", "origin", cwd=repo_dir)
    if result.returncode != 0:
        return UpdateResult(error=f"Failed to fetch updates: {result.stderr.strip()}")

    # Get remote HEAD
    result = _run_git("rev-parse", "--short", "origin/main", cwd=repo_dir)
    if result.returncode != 0:
        # Try master as fallback
        result = _run_git("rev-parse", "--short", "origin/master", cwd=repo_dir)
        if result.returncode != 0:
            return UpdateResult(error=f"Failed to get remote ref: {result.stderr.strip()}")
    new_ref = result.stdout.strip()

    if old_ref == new_ref:
        return UpdateResult(updated=False, old_ref=old_ref, new_ref=new_ref)

    # Get commit summary between current and remote
    result = _run_git("log", "--oneline", f"{old_ref}..{new_ref}", cwd=repo_dir)
    commit_summary = [line for line in result.stdout.strip().splitlines() if line] if result.returncode == 0 else []

    return UpdateResult(
        updated=True,
        old_ref=old_ref,
        new_ref=new_ref,
        commit_summary=commit_summary,
    )


def perform_update() -> UpdateResult:
    """Check for updates and apply them if available."""
    repo_dir = get_repo_dir()
    if repo_dir is None:
        return UpdateResult(error="Not installed from a git repository. Re-run install.sh to enable updates.")

    check = check_for_updates()
    if check.error:
        return check
    if not check.updated:
        return check

    # Pull changes (fast-forward only)
    result = _run_git("pull", "--ff-only", "origin", "main", cwd=repo_dir)
    if result.returncode != 0:
        # Try master as fallback
        result = _run_git("pull", "--ff-only", "origin", "master", cwd=repo_dir)
        if result.returncode != 0:
            return UpdateResult(error=f"Failed to pull updates: {result.stderr.strip()}")

    # Re-install in editable mode
    pip_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if pip_result.returncode != 0:
        return UpdateResult(error=f"Failed to install updated package: {pip_result.stderr.strip()}")

    return check
