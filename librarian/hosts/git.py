import subprocess
from pathlib import Path


def git_sha() -> str | None:
    """The commit this code runs from, -dirty with uncommitted changes; None when git
    can't answer (the image has no git and no .git)."""
    here = Path(__file__).parent
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=here,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "status", "--porcelain"], cwd=here, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if changes:
        return head + "-dirty"
    return head
