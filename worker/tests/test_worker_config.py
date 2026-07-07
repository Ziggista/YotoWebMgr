from app.core.config import get_settings


def test_default_worker_settings() -> None:
    settings = get_settings()
    assert settings.app_name == "YotoWebMgr"

