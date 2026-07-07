from app.db.base import Base
from app.models import ImportRequest, Job, LibraryItem, Setting, User


def test_user_model_is_registered_in_metadata() -> None:
    table = Base.metadata.tables["users"]

    assert User.__tablename__ == "users"
    assert {"slug", "display_name", "username", "password_hash"}.issubset(table.columns.keys())
    assert table.columns["slug"].unique is True
    assert table.columns["username"].unique is True


def test_foundation_models_are_registered_in_metadata() -> None:
    assert LibraryItem.__tablename__ in Base.metadata.tables
    assert ImportRequest.__tablename__ in Base.metadata.tables
    assert Job.__tablename__ in Base.metadata.tables
    assert Setting.__tablename__ in Base.metadata.tables
