from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _api_root() -> Path:
    # .../apps/api/app/ml/lightgbm_alpha/runtime.py -> .../apps/api
    return Path(__file__).resolve().parents[3]


def _candidate_site_packages() -> list[Path]:
    api_root = _api_root()
    venv_root = api_root / ".venv"
    candidates: list[Path] = []

    windows_site_packages = venv_root / "Lib" / "site-packages"
    if windows_site_packages.exists():
        candidates.append(windows_site_packages)

    lib_root = venv_root / "lib"
    if lib_root.exists():
        candidates.extend(sorted(lib_root.glob("python*/site-packages")))

    return [path for path in candidates if path.exists()]


def import_lightgbm() -> tuple[Any | None, str | None]:
    try:
        import lightgbm as lgb  # type: ignore[import-untyped]

        return lgb, None
    except Exception:
        pass

    for site_packages in _candidate_site_packages():
        site_packages_str = str(site_packages)
        if site_packages_str not in sys.path:
            sys.path.insert(0, site_packages_str)
        try:
            import lightgbm as lgb  # type: ignore[import-untyped]

            return lgb, site_packages_str
        except Exception:
            continue

    return None, None
