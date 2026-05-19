import json
import unittest

from backend.repositories.persistence_interfaces import SystemStateRecord
from backend.repositories.persistence_interfaces import ProjectSnapshotRecord
from backend.repositories.postgres_persistence import PostgresProjectSnapshotRepository, PostgresSystemStateRepository
from backend.system.postgres_schema import POSTGRES_MIGRATIONS


class _Cursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self):
        self.last_sql = None
        self.last_params = None
        self.next_row = None

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = tuple(params or ())
        return _Cursor(self.next_row)


class _Session:
    def __init__(self, connection):
        self.raw_connection = connection


class PostgresSystemStateRepositoryTest(unittest.TestCase):
    def test_upsert_serializes_idgen_counters_as_stable_json(self):
        conn = _Connection()
        session = _Session(conn)

        PostgresSystemStateRepository().upsert(
            session,
            SystemStateRecord(
                schema_version=3,
                idgen_counters={"subject": 2, "project": 1},
                updated_at="2026-05-11T00:00:00Z",
            ),
        )

        self.assertIn("INSERT INTO system_state", conn.last_sql)
        self.assertEqual(3, conn.last_params[0])
        self.assertEqual('{"project":1,"subject":2}', conn.last_params[1])
        self.assertEqual("2026-05-11T00:00:00Z", conn.last_params[2])

    def test_get_parses_idgen_counters_json(self):
        conn = _Connection()
        conn.next_row = {
            "schema_version": 4,
            "idgen_counters_json": json.dumps({"subject": 9, "project": 8}),
            "updated_at": "2026-05-11T00:01:00Z",
        }
        session = _Session(conn)

        state = PostgresSystemStateRepository().get(session)

        self.assertIsNotNone(state)
        self.assertEqual(4, state.schema_version)
        self.assertEqual({"subject": 9, "project": 8}, state.idgen_counters)
        self.assertEqual("2026-05-11T00:01:00Z", state.updated_at)


class PostgresProjectSnapshotRepositoryTest(unittest.TestCase):
    def test_project_snapshot_schema_keeps_required_snapshot_json_shell(self):
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "project_snapshot_json_shell")

        sql = migration.sql_factory()

        self.assertIn("ALTER TABLE project_snapshots", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS snapshot_json TEXT NOT NULL DEFAULT '{}'", sql)

    def test_video_watch_progress_index_migration_is_current_store_migration(self):
        migration = next(item for item in POSTGRES_MIGRATIONS if item.name == "video_watch_progress_index")

        sql = migration.sql_factory()

        self.assertEqual("store", migration.scope)
        self.assertEqual(13, migration.version)
        self.assertIn("CREATE TABLE IF NOT EXISTS video_watch_progress_index", sql)
        self.assertIn("ranges_json TEXT NOT NULL", sql)
        self.assertIn("PRIMARY KEY(project_id, instance_id)", sql)

    def test_upsert_writes_empty_snapshot_shell_for_non_null_legacy_column(self):
        conn = _Connection()
        session = _Session(conn)

        PostgresProjectSnapshotRepository().upsert(
            session,
            ProjectSnapshotRecord(
                project_id="proj_000001",
                project_title="Project",
                project_state="ACTIVE",
                created_at_ms=100,
                deleted_at_ms=None,
                subject_id="subj_000001",
                scoped_project_id="course",
                project_sequence=1,
                updated_at="2026-05-11T00:02:00Z",
            ),
        )

        self.assertIn("snapshot_json", conn.last_sql)
        self.assertEqual("{}", conn.last_params[5])
        self.assertEqual("subj_000001", conn.last_params[6])
        self.assertEqual("course", conn.last_params[7])


if __name__ == "__main__":
    unittest.main()
