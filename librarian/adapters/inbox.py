import time
from pathlib import Path

SETTLE_SECONDS = 60


class FolderInbox:
    """`root/inbox`, where files land; a read one goes to `root/processed/{kind}/{id}.ext`, a
    failed one to `root/quarantine/{id}.ext`."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.inbox = root / "inbox"

    def files(self) -> list[Path]:
        self.inbox.mkdir(parents=True, exist_ok=True)
        files: list[Path] = []
        for path in sorted(self.inbox.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                files.append(path)
        return files

    def settled(self, path: Path) -> bool:
        """Unchanged for SETTLE_SECONDS."""
        return time.time() - path.stat().st_mtime >= SETTLE_SECONDS

    def size(self, path: Path) -> int:
        return path.stat().st_size

    def move(self, path: Path, ingestion_id: int, kind: str | None) -> str:
        name = f"{ingestion_id}{path.suffix.lower()}"
        target = self.root / "quarantine" / name
        if kind is not None:
            target = self.root / "processed" / kind / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"{target} exists: was the database wiped without the files?")
        path.rename(target)
        return str(target.relative_to(self.root))

    def move_back(self, destination: str, path: Path) -> None:
        (self.root / destination).rename(path)

    def delete(self, path: Path) -> None:
        path.unlink()
