from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Starting {settings.app_name} worker in {settings.environment} mode")


if __name__ == "__main__":
    main()

