import signal
import time

from app.core.config import get_settings


shutdown_requested = False


def request_shutdown(signum: int, frame: object) -> None:
    del signum, frame
    global shutdown_requested
    shutdown_requested = True


def main() -> None:
    settings = get_settings()
    print(f"Starting {settings.app_name} worker in {settings.environment} mode")
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    while not shutdown_requested:
        time.sleep(5)

    print("Worker shutdown requested")


if __name__ == "__main__":
    main()
