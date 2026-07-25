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


def test_alembic_down_revisions_reference_existing_revisions() -> None:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revision_files = sorted(path for path in versions_dir.glob("*.py") if path.name != ".gitkeep")

    assert revision_files, "Expected at least one Alembic revision file."

    modules = []
    known_revisions: set[str] = set()

    for revision_file in revision_files:
        spec = importlib.util.spec_from_file_location(revision_file.stem, revision_file)
        assert spec and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append((revision_file.name, module))

        revision = getattr(module, "revision")
        assert isinstance(revision, str)
        known_revisions.add(revision)

    for filename, module in modules:
        down_revision = getattr(module, "down_revision", None)
        if down_revision is None:
            continue

        if isinstance(down_revision, str):
            referenced_revisions = [down_revision]
        else:
            referenced_revisions = list(down_revision)

        for referenced_revision in referenced_revisions:
            assert referenced_revision in known_revisions, (
                f"Alembic down_revision '{referenced_revision}' from {filename} does not match any known revision."
            )
