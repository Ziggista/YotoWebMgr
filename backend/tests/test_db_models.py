from app.db.base import Base
from app.models import User


def test_user_model_is_registered_in_metadata() -> None:
    table = Base.metadata.tables["users"]

    assert User.__tablename__ == "users"
    assert {"slug", "display_name", "username", "password_hash"}.issubset(table.columns.keys())
    assert table.columns["slug"].unique is True
    assert table.columns["username"].unique is True
