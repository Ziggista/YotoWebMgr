from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def reset_database_if_enabled() -> None:
    settings = get_settings()
    if not settings.reset_database_on_start:
        print("Database reset disabled; keeping existing schema.")
        return

    if settings.environment != "development":
        raise RuntimeError("Refusing to reset database outside the development environment.")

    database_url = make_url(settings.database_url)
    if not database_url.drivername.startswith("postgresql"):
        raise RuntimeError("Refusing to reset a non-PostgreSQL database.")

    database_user = database_url.username
    escaped_database_user = database_user.replace('"', '""') if database_user else None
    engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with engine.begin() as connection:
        print("Dropping PostgreSQL public schema for a clean development deployment.")
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        if escaped_database_user:
            connection.execute(text(f'GRANT ALL ON SCHEMA public TO "{escaped_database_user}"'))
        connection.execute(text("GRANT ALL ON SCHEMA public TO public"))
    engine.dispose()


if __name__ == "__main__":
    reset_database_if_enabled()
