import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.system.app_paths import resolve_store_path
from backend.system.version import APP_ID


class AppPathTests(unittest.TestCase):
    def test_resolve_store_path_prefers_env_override(self) -> None:
        with TemporaryDirectory() as tmp:
            expected = Path(tmp) / "custom-store.json"
            with patch.dict(os.environ, {"PLM_STORE_PATH": str(expected)}, clear=False):
                actual = resolve_store_path(legacy_root=Path(tmp))
            self.assertEqual(actual, expected)

    def test_resolve_store_path_migrates_legacy_store_to_user_data_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / ".plm_store.json"
            legacy.write_text('{"ok":true}', encoding="utf-8")
            data_dir = root / "plm-data"

            with patch.dict(
                os.environ,
                {
                    "PLM_DATA_DIR": str(data_dir),
                    "PLM_STORE_PATH": "",
                },
                clear=False,
            ):
                actual = resolve_store_path(legacy_root=root)

            self.assertEqual(actual, data_dir / "plm_store.json")
            self.assertTrue(actual.exists())
            self.assertEqual(actual.read_text(encoding="utf-8"), '{"ok":true}')

    def test_resolve_store_path_migrates_legacy_app_data_store(self) -> None:
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
                actual = resolve_store_path(legacy_root=root / "missing-root")

            self.assertEqual(actual, local_appdata / APP_ID / "plm_store.json")
            self.assertTrue(actual.exists())
            self.assertEqual(actual.read_text(encoding="utf-8"), '{"migrated":true}')

    def test_resolve_store_path_migrates_previous_branded_app_data_store(self) -> None:
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
                actual = resolve_store_path(legacy_root=root / "missing-root")

            self.assertEqual(actual, local_appdata / APP_ID / "plm_store.json")
            self.assertTrue(actual.exists())
            self.assertEqual(actual.read_text(encoding="utf-8"), '{"migratedFromBrand":true}')


if __name__ == "__main__":
    unittest.main()
