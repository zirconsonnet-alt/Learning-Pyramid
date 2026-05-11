import unittest
from contextlib import contextmanager

from tools.repair_project_material_source_binding_index import (
    build_repair_plan,
    repair_postgres,
    source_kind_for_project_type,
)


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._rows)


class FakeConnection:
    def __init__(self) -> None:
        self.inserted: list[tuple[object, ...]] = []

    def execute(self, sql: str, params: tuple[object, ...] | None = None):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT p.project_id FROM project_snapshots"):
            return FakeCursor([])
        if normalized.startswith("SELECT p.project_id, p.project_state, c.config_json"):
            return FakeCursor(
                [
                    {"project_id": "proj_course", "project_state": "ACTIVE", "config_json": '{"projectType":"COURSE"}'},
                    {"project_id": "proj_loose", "project_state": "ACTIVE", "config_json": '{"projectType":"LOOSE_POINTS"}'},
                ]
            )
        if normalized.startswith("INSERT INTO project_material_source_binding_index"):
            if params is None:
                raise AssertionError("insert params are required")
            self.inserted.append(params)
            return FakeCursor([])
        raise AssertionError(f"unexpected SQL: {normalized}")

    @contextmanager
    def transaction(self):
        yield


class ProjectMaterialSourceBindingIndexRepairTest(unittest.TestCase):
    def test_source_kind_is_derived_from_project_type(self) -> None:
        self.assertEqual("SERVER_FS", source_kind_for_project_type("COURSE"))
        self.assertEqual("MANUAL", source_kind_for_project_type("BOOK"))
        self.assertEqual("MANUAL", source_kind_for_project_type("LOOSE_POINTS"))

    def test_unknown_project_type_blocks_repair(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported projectType"):
            source_kind_for_project_type("VIDEO")

    def test_build_plan_only_includes_missing_active_bindings(self) -> None:
        rows = [
            {"project_id": "proj_course", "project_state": "ACTIVE", "config_json": '{"projectType":"COURSE"}'},
            {"project_id": "proj_book", "project_state": "ACTIVE", "config_json": '{"projectType":"BOOK"}'},
            {"project_id": "proj_deleted", "project_state": "DELETED", "config_json": '{"projectType":"COURSE"}'},
        ]

        plan = build_repair_plan(rows, updated_at_ms=1234)

        self.assertEqual(
            [
                {
                    "projectId": "proj_course",
                    "projectType": "COURSE",
                    "sourceKind": "SERVER_FS",
                    "sourceRootLabel": None,
                    "updatedAtMs": 1234,
                },
                {
                    "projectId": "proj_book",
                    "projectType": "BOOK",
                    "sourceKind": "MANUAL",
                    "sourceRootLabel": None,
                    "updatedAtMs": 1234,
                },
            ],
            [item.to_json() for item in plan],
        )

    def test_invalid_config_json_blocks_repair(self) -> None:
        with self.assertRaisesRegex(ValueError, "config_json"):
            build_repair_plan(
                [{"project_id": "proj_bad", "project_state": "ACTIVE", "config_json": "not-json"}],
                updated_at_ms=1234,
            )

    def test_dry_run_does_not_insert_rows(self) -> None:
        conn = FakeConnection()

        result = repair_postgres(conn, apply=False, updated_at_ms=1234)

        self.assertEqual(2, result["plannedCount"])
        self.assertEqual(0, result["appliedCount"])
        self.assertEqual([], conn.inserted)

    def test_apply_inserts_planned_rows(self) -> None:
        conn = FakeConnection()

        result = repair_postgres(conn, apply=True, updated_at_ms=1234)

        self.assertEqual(2, result["plannedCount"])
        self.assertEqual(2, result["appliedCount"])
        self.assertEqual(
            [
                ("proj_course", "SERVER_FS", None, 1234),
                ("proj_loose", "MANUAL", None, 1234),
            ],
            conn.inserted,
        )


if __name__ == "__main__":
    unittest.main()
