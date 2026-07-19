from __future__ import annotations

import importlib.util
from pathlib import Path


def test_alembic_revision_ids_fit_default_version_table_width() -> None:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revision_files = sorted(path for path in versions_dir.glob("*.py") if path.name != ".gitkeep")

    assert revision_files, "Expected at least one Alembic revision file."

    for revision_file in revision_files:
        spec = importlib.util.spec_from_file_location(revision_file.stem, revision_file)
        assert spec and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        revision = getattr(module, "revision")
        assert isinstance(revision, str)
        assert len(revision) <= 32, (
            f"Alembic revision '{revision}' from {revision_file.name} exceeds the default "
            "alembic_version.version_num width of 32 characters."
        )
