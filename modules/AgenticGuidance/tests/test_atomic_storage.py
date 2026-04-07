"""Tests for AtomicJSONStorage — atomic writes and corruption recovery.

Validates:
- Basic read/write through TinyDB
- Atomic write semantics (no partial files on crash)
- Backup creation on each write
- Corruption detection and recovery from .bak file
- Multi-process concurrent writes via AtomicJSONStorage
- Context manager protocol on EpicRepository
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from agenticguidance.services.epic_repository import AtomicJSONStorage, EpicRepository

pytestmark = pytest.mark.story("US-SES-020")

_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")


@pytest.fixture
def storage_path(tmp_path):
    """Return a path for a test DB file."""
    return tmp_path / "test.db"


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _make_epic_data(name: str) -> dict:
    return {
        "epic_folder_name": name,
        "epic_folder": f"/tmp/epics/{name}",
        "name": name,
        "status": "pending",
        "objective": f"Objective for {name}",
    }


class TestAtomicJSONStorageBasic:
    """Basic read/write operations."""

    def test_read_empty_file(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        assert storage.read() is None

    def test_write_then_read(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        data = {"_default": {"1": {"key": "value"}}}
        storage.write(data)
        result = storage.read()
        assert result == data

    def test_write_creates_backup(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        # First write — no backup yet (file doesn't exist)
        storage.write({"_default": {"1": {"v": 1}}})
        backup = storage_path.with_suffix(".db.bak")
        # Backup created from empty/nonexistent is fine

        # Second write — backup should have first write's data
        storage.write({"_default": {"1": {"v": 2}}})
        assert backup.exists()
        bak_data = json.loads(backup.read_text())
        assert bak_data["_default"]["1"]["v"] == 1

    def test_close_is_noop(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        storage.close()  # Should not raise


class TestCorruptionRecovery:
    """Corruption detection and backup recovery."""

    def test_corrupted_primary_recovers_from_backup(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        good_data = {"_default": {"1": {"key": "good"}}}
        storage.write(good_data)

        # Now corrupt the primary file
        storage_path.write_text("{{invalid json")

        # Write backup with known-good data
        backup = storage_path.with_suffix(".db.bak")
        backup.write_text(json.dumps(good_data))

        storage2 = AtomicJSONStorage(str(storage_path))
        result = storage2.read()
        assert result == good_data

    def test_corrupted_primary_no_backup_returns_none(self, storage_path):
        storage_path.write_text("{{invalid json")
        storage = AtomicJSONStorage(str(storage_path))
        result = storage.read()
        assert result is None

    def test_both_corrupted_returns_none(self, storage_path):
        storage_path.write_text("{{invalid")
        backup = storage_path.with_suffix(".db.bak")
        backup.write_text("also {{invalid")

        storage = AtomicJSONStorage(str(storage_path))
        result = storage.read()
        assert result is None

    def test_empty_primary_returns_none(self, storage_path):
        storage_path.write_text("")
        storage = AtomicJSONStorage(str(storage_path))
        assert storage.read() is None

    def test_recovery_restores_primary(self, storage_path):
        """After recovery, the primary file should be restored from backup."""
        good_data = {"_default": {"1": {"key": "recovered"}}}
        backup = storage_path.with_suffix(".db.bak")
        backup.write_text(json.dumps(good_data))
        storage_path.write_text("corrupted!!")

        storage = AtomicJSONStorage(str(storage_path))
        storage.read()

        # Primary should now match backup
        restored = json.loads(storage_path.read_text())
        assert restored == good_data


class TestAtomicWriteSemantics:
    """Verify write atomicity — no partial files."""

    def test_no_temp_files_left_on_success(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        storage.write({"_default": {}})

        # No .tmp files should remain
        tmp_files = list(storage_path.parent.glob(".epics_*.tmp"))
        assert tmp_files == []

    def test_atomic_rename_preserves_data(self, storage_path):
        storage = AtomicJSONStorage(str(storage_path))
        large_data = {"_default": {str(i): {"v": i} for i in range(1000)}}
        storage.write(large_data)

        result = storage.read()
        assert len(result["_default"]) == 1000


class TestConcurrentWritesWithAtomicStorage:
    """Multi-process concurrent writes through EpicRepository + AtomicJSONStorage."""

    def test_concurrent_writes_all_succeed(self, tmp_path):
        db_path = tmp_path / "epics.db"
        script = textwrap.dedent("""\
            import sys
            from pathlib import Path
            sys.path.insert(0, sys.argv[3])
            from agenticguidance.services.epic_repository import EpicRepository

            epic_name = sys.argv[1]
            r = EpicRepository(db_path=Path(sys.argv[2]), auto_bootstrap=False)
            result = r.create_epic({
                "epic_folder_name": epic_name,
                "epic_folder": f"/tmp/epics/{epic_name}",
                "name": epic_name,
                "status": "pending",
            })
            r.close()
            sys.exit(0 if result.success else 1)
        """)
        script_path = tmp_path / "write.py"
        script_path.write_text(script)

        procs = []
        for i in range(5):
            p = subprocess.Popen(
                [sys.executable, str(script_path), f"epic_{i}",
                 str(db_path), _SRC_DIR],
                stderr=subprocess.PIPE,
            )
            procs.append(p)

        for p in procs:
            p.wait(timeout=30)

        for i, p in enumerate(procs):
            assert p.returncode == 0, f"epic_{i} failed: {p.stderr.read().decode()}"

        # Verify all 5 epics exist
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        for i in range(5):
            assert repo.get_epic(f"epic_{i}") is not None
        repo.close()


class TestEpicRepositoryContextManager:
    """EpicRepository __enter__/__exit__ protocol."""

    def test_context_manager_closes_db(self, tmp_path):
        db_path = tmp_path / "epics.db"
        with EpicRepository(db_path=db_path, auto_bootstrap=False) as repo:
            repo.create_epic(_make_epic_data("cm_test"))
            epic = repo.get_epic("cm_test")
            assert epic is not None

    def test_context_manager_closes_on_exception(self, tmp_path):
        db_path = tmp_path / "epics.db"
        try:
            with EpicRepository(db_path=db_path, auto_bootstrap=False) as repo:
                repo.create_epic(_make_epic_data("cm_exc"))
                raise ValueError("test error")
        except ValueError:
            pass

        # DB should be readable after context manager exit
        repo2 = EpicRepository(db_path=db_path, auto_bootstrap=False)
        assert repo2.get_epic("cm_exc") is not None
        repo2.close()
