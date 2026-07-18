#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
OUTPUT_DIR = ROOT_DIR / "public" / "live-updates" / "android"
PACKAGE_JSON = ROOT_DIR / "package.json"


def git_short_sha() -> str:
    env_sha = os.environ.get("VITE_APP_BUILD_SHA") or os.environ.get("APP_BUILD_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        return (
            subprocess.check_output(["git", "-C", str(ROOT_DIR.parent), "rev-parse", "--short", "HEAD"], text=True)
            .strip()
        )
    except Exception:
        return "dev"


def main() -> int:
    if not DIST_DIR.exists():
        raise SystemExit(f"dist directory not found at {DIST_DIR}")

    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    app_version = str(package.get("version") or "0.0.0")
    build_sha = git_short_sha()
    ota_version = f"{app_version}+{build_sha}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for existing in OUTPUT_DIR.glob("yotowebmgr-web-update-*.zip"):
        existing.unlink()

    archive_stem = OUTPUT_DIR / f"yotowebmgr-web-update-{app_version}-{build_sha}"
    archive_path = Path(shutil.make_archive(str(archive_stem), "zip", root_dir=DIST_DIR))

    manifest = {
        "version": ota_version,
        "build_sha": build_sha,
        "app_version": app_version,
        "bundle_url": f"/live-updates/android/{archive_path.name}",
        "generated_at": datetime.now(UTC).isoformat(),
        "notes": "Web-only OTA bundle. Native/plugin changes still require a rebuilt APK.",
    }
    (OUTPUT_DIR / "latest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote OTA bundle {archive_path}")
    print(f"Wrote OTA manifest {(OUTPUT_DIR / 'latest.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
