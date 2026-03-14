import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.system.app_paths import resolve_legacy_store_path, resolve_store_db_path
from backend.system.version import APP_ID

class AppPathTests(unittest.TestCase):
    def test_resolve_legacy_store_path_prefers_env_override(self) -> None:
        with TemporaryDirectory() as tmp:
            expected = Path(tmp) / "custom-store.json"
            expected.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"PLM_STORE_PATH": str(expected)}, clear=False):
                actual = resolve_legacy_store_path(legacy_root=Path(tmp))
            self.assertEqual(actual, expected)

    def test_resolve_store_db_path_prefers_env_override(self) -> None:
        with TemporaryDirectory() as tmp:
            expected = Path(tmp) / "custom-store.sqlite3"
            with patch.dict(os.environ, {"PLM_STORE_DB_PATH": str(expected)}, clear=False):
                actual = resolve_store_db_path()
            self.assertEqual(actual, expected)

    def test_resolve_legacy_store_path_finds_repo_local_legacy_store(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / ".plm_store.json"
            legacy.write_text('{"ok":true}', encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(root / "local-appdata"),
                    "PLM_DATA_DIR": "",
                    "PLM_STORE_PATH": "",
                },
                clear=False,
            ):
                actual = resolve_legacy_store_path(legacy_root=root)

            self.assertEqual(actual, legacy)

    def test_resolve_legacy_store_path_finds_legacy_app_data_store(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_appdata = root / "local-appdata"
            legacy_store = local_appdata / "PLM3" / "plm_store.json"
            legacy_store.parent.mkdir(parents=True, exist_ok=True)
            legacy_store.write_text('{"migrated":true}', encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_appdata),
                    "PLM_DATA_DIR": "",
                    "PLM_STORE_PATH": "",
                },
                clear=False,
            ):
                actual = resolve_legacy_store_path(legacy_root=root / "missing-root")

            self.assertEqual(actual, legacy_store)

    def test_resolve_legacy_store_path_finds_previous_branded_app_data_store(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_appdata = root / "local-appdata"
            legacy_store = local_appdata / "学习金字塔" / "plm_store.json"
            legacy_store.parent.mkdir(parents=True, exist_ok=True)
            legacy_store.write_text('{"migratedFromBrand":true}', encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_appdata),
                    "PLM_DATA_DIR": "",
                    "PLM_STORE_PATH": "",
                },
                clear=False,
            ):
                actual = resolve_legacy_store_path(legacy_root=root / "missing-root")

            self.assertEqual(actual, legacy_store)

    def test_resolve_store_db_path_defaults_under_app_data_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            local_appdata = Path(tmp) / "local-appdata"
            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_appdata),
                    "PLM_DATA_DIR": "",
                    "PLM_STORE_DB_PATH": "",
                },
                clear=False,
            ):
                actual = resolve_store_db_path()

            self.assertEqual(actual, local_appdata / APP_ID / "plm_store.sqlite3")


if __name__ == "__main__":
    unittest.main()
