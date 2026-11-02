"""Create a consistent SQLite backup using the online backup API.

Environment variables:
  DB_PATH: source database file (default: data/career.db)
  BACKUP_DIR: destination directory (default: backups)
  BACKUP_RETENTION_DAYS: delete older backup files (default: 14)
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def create_backup(
    source_path: str | Path,
    backup_dir: str | Path,
    retention_days: int = 14,
) -> Path:
    source = Path(source_path).expanduser().resolve()
    destination_dir = Path(backup_dir).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Banco SQLite não encontrado: {source}")
    if retention_days < 1:
        raise ValueError("retention_days precisa ser maior ou igual a 1")

    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination_dir / f"career-{timestamp}.db"
    suffix = 1
    while target.exists():
        target = destination_dir / f"career-{timestamp}-{suffix}.db"
        suffix += 1

    try:
        with sqlite3.connect(source) as source_conn, sqlite3.connect(target) as backup_conn:
            source_conn.backup(backup_conn)
            integrity = backup_conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise sqlite3.DatabaseError(f"Falha na integridade do backup: {integrity}")
    except Exception:
        target.unlink(missing_ok=True)
        raise

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for old_backup in destination_dir.glob("career-*.db"):
        if old_backup == target:
            continue
        modified = datetime.fromtimestamp(old_backup.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            old_backup.unlink(missing_ok=True)

    return target


def main() -> None:
    source = os.getenv("DB_PATH", "data/career.db")
    backup_dir = os.getenv("BACKUP_DIR", "backups")
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))
    result = create_backup(source, backup_dir, retention_days)
    print(f"Backup criado e validado: {result}")


if __name__ == "__main__":
    main()
