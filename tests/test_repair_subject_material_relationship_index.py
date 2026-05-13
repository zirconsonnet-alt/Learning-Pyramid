import unittest
from contextlib import contextmanager

from tools.repair_subject_material_relationship_index import repair_postgres


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
        if normalized.startswith("SELECT p.project_id, p.project_title"):
            return FakeCursor(
                [
                    {
                        "project_id": "subj_000003",
                        "project_title": "Subject",
                        "project_state": "ACTIVE",
                        "created_at_ms": 1000,
                        "subject_id": None,
                        "scoped_project_id": None,
                        "project_type": "COURSE",
                    },
                    {
                        "project_id": "proj_000099",
                        "project_title": "网课材料",
                        "project_state": "ACTIVE",
                        "created_at_ms": 2000,
                        "subject_id": "subj_000003",
                        "scoped_project_id": "proj_000001",
                        "project_type": "COURSE",
                    },
                ]
            )
        if normalized.startswith("SELECT subject_id, material_id"):
            return FakeCursor([])
        if normalized.startswith("INSERT INTO subject_material_collection_index"):
            if params is None:
                raise AssertionError("insert params are required")
            self.inserted.append(params)
            return FakeCursor([])
        if normalized.startswith("INSERT INTO subject_material_relationship_index"):
            if params is None:
                raise AssertionError("insert params are required")
            self.inserted.append(params)
            return FakeCursor([])
        raise AssertionError(f"unexpected SQL: {normalized}")

    @contextmanager
    def transaction(self):
        yield


class SubjectMaterialRelationshipIndexRepairTest(unittest.TestCase):
    def test_dry_run_reports_recoverable_plan_without_insert(self) -> None:
        conn = FakeConnection()

        result = repair_postgres(conn, apply=False, updated_at="2026-05-13T00:00:00+00:00")

        self.assertEqual(True, result["ok"])
        self.assertEqual("dry-run", result["mode"])
        self.assertEqual(1, result["plannedCount"])
        self.assertEqual(0, result["appliedCount"])
        self.assertEqual([], conn.inserted)
        self.assertEqual(
            {
                "subjectId": "subj_000003",
                "materialId": "mat_recovered_proj_000099",
                "materialType": "COURSE",
                "title": "网课材料",
                "createdAtMs": 2000,
                "scopedProjectId": "proj_000001",
                "internalProjectId": "proj_000099",
            },
            result["items"][0],
        )

    def test_apply_inserts_collection_and_relationship_rows(self) -> None:
        conn = FakeConnection()

        result = repair_postgres(conn, apply=True, updated_at="2026-05-13T00:00:00+00:00")

        self.assertEqual(1, result["plannedCount"])
        self.assertEqual(1, result["appliedCount"])
        self.assertEqual(
            [
                ("subj_000003", True, "2026-05-13T00:00:00+00:00"),
                (
                    "subj_000003",
                    "mat_recovered_proj_000099",
                    "COURSE",
                    "网课材料",
                    2000,
                    "proj_000001",
                    "proj_000099",
                    "2026-05-13T00:00:00+00:00",
                ),
            ],
            conn.inserted,
        )


if __name__ == "__main__":
    unittest.main()
