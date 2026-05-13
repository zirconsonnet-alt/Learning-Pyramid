import unittest
import sqlite3
import tempfile
from typing import Any
from pathlib import Path

from backend.repositories.persistence_interfaces import (
    SubjectMaterialCollectionRecord,
    SubjectMaterialRelationshipRecord,
)
from backend.repositories.postgres_persistence import PostgresSubjectMaterialRelationshipRepository
from backend.repositories.sqlite_persistence import SQLitePersistenceSession, SQLiteSubjectMaterialRelationshipRepository
from backend.system.persistence_store import SQLiteSnapshotStore
from backend.system.postgres_schema import POSTGRES_MIGRATIONS
from backend.system.postgres_store import PostgresStore


class _Cursor:
    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[object]:
        return []


class _FakeSystemStateRepository:
    def upsert(self, session: object, state: object) -> None:
        pass


class _FakeProjectSnapshotRepository:
    def __init__(self, calls: list[tuple[str, str]]) -> None:
        self._calls = calls

    def delete_absent(self, session: object, keep_project_ids: tuple[str, ...]) -> None:
        pass

    def upsert(self, session: object, record: object) -> None:
        self._calls.append(("upsert", str(getattr(record, "project_id"))))


class _FakeUnitOfWork:
    def __init__(self, calls: list[tuple[str, str]]) -> None:
        self.session = object()
        self.connection = object()
        self.system_state = _FakeSystemStateRepository()
        self.project_snapshots = _FakeProjectSnapshotRepository(calls)

    def __enter__(self) -> "_FakeUnitOfWork":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _PostgresStoreUnderTest(PostgresStore):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def begin_unit_of_work(self, *, project_id: str | None = None) -> _FakeUnitOfWork:
        return _FakeUnitOfWork(self.calls)

    def _replace_global_llm_settings_payload(self, conn: object, payload: dict[str, Any] | None, *, updated_at: str) -> None:
        pass

    def _refresh_project_entity_indexes(self, conn: object, *, project_id: str, project_payload: dict[str, Any]) -> None:
        self.calls.append(("refresh", str(project_id)))


def _active_project_payload(project_id: str, *, study_materials: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "project": {
            "projectId": project_id,
            "title": project_id,
            "state": "ACTIVE",
            "createdAtMs": 1,
            "deletedAtMs": None,
            "subjectId": None,
            "scopedProjectId": None,
            "projectSequence": 1,
        },
        "studyMaterialsInitialized": study_materials is not None,
        "studyMaterials": study_materials or {},
    }


class PostgresSubjectMaterialRelationshipSaveOrderTest(unittest.TestCase):
    def test_save_snapshot_upserts_all_project_snapshots_before_relationship_indexes(self) -> None:
        store = _PostgresStoreUnderTest()

        store.save_snapshot(
            {
                "schemaVersion": 1,
                "idgenCounters": {},
                "projects": {
                    "subj_000001": _active_project_payload(
                        "subj_000001",
                        study_materials={
                            "mat_000001": {
                                "subjectId": "subj_000001",
                                "materialId": "mat_000001",
                                "materialType": "COURSE",
                                "title": "Course",
                                "createdAtMs": 1,
                                "scopedProjectId": "proj_000001",
                                "internalProjectId": "proj_000099",
                            }
                        },
                    ),
                    "proj_000099": _active_project_payload("proj_000099"),
                },
            }
        )

        self.assertEqual(
            [
                ("upsert", "subj_000001"),
                ("upsert", "proj_000099"),
                ("refresh", "subj_000001"),
                ("refresh", "proj_000099"),
            ],
            store.calls,
        )


class PostgresSubjectMaterialRelationshipSchemaTest(unittest.TestCase):
    def test_collection_initialized_column_is_boolean(self) -> None:
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "subject_material_relationship_index")

        self.assertIn("initialized BOOLEAN NOT NULL", migration.sql_factory())

    def test_relationship_backfill_converts_collection_initialized_before_writing_boolean(self) -> None:
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "subject_material_relationship_backfill")
        sql = migration.sql_factory()

        self.assertIn("ALTER COLUMN initialized TYPE BOOLEAN", sql)
        self.assertIn("LOWER(initialized::TEXT)", sql)
        self.assertLess(
            sql.index("ALTER COLUMN initialized TYPE BOOLEAN"),
            sql.index("INSERT INTO subject_material_collection_index"),
        )

    def test_collection_initialized_boolean_followup_migration_is_idempotent(self) -> None:
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "subject_material_collection_initialized_boolean")
        sql = migration.sql_factory()

        self.assertEqual(12, migration.version)
        self.assertIn("ALTER COLUMN initialized TYPE BOOLEAN", sql)
        self.assertIn("LOWER(initialized::TEXT)", sql)

    def test_relationship_backfill_migration_uses_internal_project_id_for_recovered_material_id(self) -> None:
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "subject_material_relationship_backfill")
        sql = migration.sql_factory()

        self.assertIn("mat_recovered_' || p.project_id", sql)
        self.assertIn("p.project_id AS internal_project_id", sql)
        self.assertIn("p.scoped_project_id", sql)

    def test_relationship_backfill_migration_only_uses_active_subject_and_material_rows(self) -> None:
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "subject_material_relationship_backfill")
        sql = " ".join(migration.sql_factory().split())

        self.assertIn("p.project_state = 'ACTIVE'", sql)
        self.assertIn("subj.project_state = 'ACTIVE'", sql)
        self.assertIn("p.subject_id IS NOT NULL", sql)
        self.assertIn("p.scoped_project_id IS NOT NULL", sql)


class SQLiteSubjectMaterialRelationshipRepositoryTest(unittest.TestCase):
    def test_repository_round_trips_subject_material_relationships(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-sqlite-subject-material-repo-") as temp_dir:
            db_path = Path(temp_dir) / "store.sqlite3"
            SQLiteSnapshotStore(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                session = SQLitePersistenceSession(raw_connection=conn)
                repo = SQLiteSubjectMaterialRelationshipRepository()

                repo.upsert_collection(
                    session,
                    SubjectMaterialCollectionRecord(
                        subject_id="subj_000001",
                        initialized=True,
                        updated_at="2026-05-12T00:00:00+00:00",
                    ),
                )
                repo.insert_relationships(
                    session,
                    (
                        SubjectMaterialRelationshipRecord(
                            subject_id="subj_000001",
                            material_id="mat_000001",
                            material_type="COURSE",
                            title="Course",
                            created_at_ms=1,
                            scoped_project_id="proj_000001",
                            internal_project_id="proj_000099",
                            updated_at="2026-05-12T00:00:00+00:00",
                        ),
                    ),
                )

                collection = repo.get_collection(session, "subj_000001")
                relationships = repo.list_for_subject(session, "subj_000001")
                link = repo.get_by_internal_project(session, "proj_000099")

                self.assertEqual(True, collection.initialized if collection else None)
                self.assertEqual(("mat_000001", "proj_000001", "proj_000099"), (
                    relationships[0].material_id,
                    relationships[0].scoped_project_id,
                    relationships[0].internal_project_id,
                ))
                self.assertEqual(relationships[0], link)
            finally:
                conn.close()


class PostgresSubjectMaterialRelationshipRepositoryTest(unittest.TestCase):
    def test_insert_relationships_uses_subject_material_relationship_index(self) -> None:
        class _Connection:
            def __init__(self) -> None:
                self.calls: list[tuple[str, tuple[object, ...]]] = []

            def execute(self, sql: str, params: tuple[object, ...] | None = None):
                self.calls.append((sql, tuple(params or ())))
                return _Cursor()

        class _Session:
            def __init__(self, connection: _Connection) -> None:
                self.raw_connection = connection

        conn = _Connection()
        repo = PostgresSubjectMaterialRelationshipRepository()

        repo.insert_relationships(
            _Session(conn),  # type: ignore[arg-type]
            (
                SubjectMaterialRelationshipRecord(
                    subject_id="subj_000001",
                    material_id="mat_000001",
                    material_type="COURSE",
                    title="Course",
                    created_at_ms=1,
                    scoped_project_id="proj_000001",
                    internal_project_id="proj_000099",
                    updated_at="2026-05-12T00:00:00+00:00",
                ),
            ),
        )

        self.assertIn("subject_material_relationship_index", conn.calls[0][0])
        self.assertEqual("subj_000001", conn.calls[0][1][0])
        self.assertEqual("proj_000099", conn.calls[0][1][6])


if __name__ == "__main__":
    unittest.main()
