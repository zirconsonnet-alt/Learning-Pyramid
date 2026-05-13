import unittest

from backend.models.errors import PreconditionFailure
from backend.models.enums import MaterialSourceKind, ProjectType
from backend.models.study_material import StudyMaterialType
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem


class SubjectMaterialAtomicityTest(unittest.TestCase):
    def _fail_persist_once(self, api: SystemAPI):
        original_persist_to_disk = api.sys._persist_to_disk
        persist_attempts = 0

        def fail_persist_to_disk(*args, **kwargs):
            nonlocal persist_attempts
            persist_attempts += 1
            raise PreconditionFailure("simulated atomic persist failure")

        api.sys._persist_to_disk = fail_persist_to_disk  # type: ignore[method-assign]
        return original_persist_to_disk, lambda: persist_attempts

    def test_create_subject_material_publishes_subject_and_child_together(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")

        material = api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )

        materials = api.list_subject_materials(subject_id)
        self.assertIn(material, materials)
        self.assertIsNotNone(material.internal_project_id)
        child_store = api.sys.g.projects[str(material.internal_project_id)]
        self.assertIsNotNone(child_store.project)
        self.assertEqual(subject_id, child_store.project.subject_id)
        self.assertEqual(material.scoped_project_id, child_store.project.scoped_project_id)
        self.assertFalse(hasattr(child_store.project, "legacy_global_project_id"))
        self.assertIsNotNone(child_store.subject_material_link)
        self.assertEqual(subject_id, child_store.subject_material_link.subject_id)
        self.assertEqual(material.material_id, child_store.subject_material_link.material_id)
        self.assertEqual(material.scoped_project_id, child_store.subject_material_link.scoped_project_id)

    def test_bare_project_is_not_treated_as_subject_material_root(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Course",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )
        api.edit_project(project_id, "Course Renamed")
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        with self.assertRaises(PreconditionFailure):
            api.list_subject_materials(project_id)

        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_edit_subject_material_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)
        before_materials = api.list_subject_materials(subject_id)
        before_child_title = api.sys.g.projects[str(material_project_id)].project.title
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.edit_subject_material(subject_id, material.material_id, title="Renamed")
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        after_materials = api.list_subject_materials(subject_id)
        after_child_title = api.sys.g.projects[str(material_project_id)].project.title
        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_materials, after_materials)
        self.assertEqual(before_child_title, after_child_title)
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_delete_subject_material_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)
        before_materials = api.list_subject_materials(subject_id)
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.delete_subject_material(subject_id, material.material_id)
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_materials, api.list_subject_materials(subject_id))
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_delete_subject_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.delete_subject(subject_id)
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_edit_material_project_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)
        before_materials = api.list_subject_materials(subject_id)
        before_child_title = api.sys.g.projects[str(material_project_id)].project.title
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.edit_project(material_project_id, "Renamed")
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        after_materials = api.list_subject_materials(subject_id)
        after_child_title = api.sys.g.projects[str(material_project_id)].project.title
        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_materials, after_materials)
        self.assertEqual(before_child_title, after_child_title)
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_delete_material_project_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)
        before_materials = api.list_subject_materials(subject_id)
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.delete_project(material_project_id)
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_materials, api.list_subject_materials(subject_id))
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_delete_subject_project_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        api.create_subject_material(
            subject_id,
            material_type=StudyMaterialType.BOOK,
            title="Book",
        )
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.delete_project(subject_id)
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_create_subject_does_not_publish_partial_state_when_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk, persist_attempts = self._fail_persist_once(api)
        try:
            with self.assertRaises(PreconditionFailure):
                api.create_subject("Subject")
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        self.assertEqual(1, persist_attempts())
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_create_subject_material_does_not_publish_partial_state_when_atomic_persist_fails(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        before_material_ids = {item.material_id for item in api.list_subject_materials(subject_id)}
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        original_persist_to_disk = api.sys._persist_to_disk
        persist_attempts = 0

        def fail_persist_to_disk(*args, **kwargs):
            nonlocal persist_attempts
            persist_attempts += 1
            raise PreconditionFailure("simulated atomic persist failure")

        api.sys._persist_to_disk = fail_persist_to_disk  # type: ignore[method-assign]
        try:
            with self.assertRaises(PreconditionFailure):
                api.create_subject_material(
                    subject_id,
                    material_type=StudyMaterialType.BOOK,
                    title="Book",
                )
        finally:
            api.sys._persist_to_disk = original_persist_to_disk  # type: ignore[method-assign]

        after_material_ids = {item.material_id for item in api.list_subject_materials(subject_id)}
        after_project_ids = set(api.sys.g.projects.keys())
        after_idgen_counters = dict(api.idgen._counters)
        self.assertEqual(1, persist_attempts)
        self.assertEqual(before_material_ids, after_material_ids)
        self.assertEqual(before_project_ids, after_project_ids)
        self.assertEqual(before_idgen_counters, after_idgen_counters)

    def test_list_subjects_does_not_migrate_bare_projects(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Course",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )
        api.edit_project(project_id, "Course Renamed")
        before_project_ids = set(api.sys.g.projects.keys())
        before_idgen_counters = dict(api.idgen._counters)

        subjects = api.list_subjects()

        self.assertNotIn(project_id, [subject.project_id for subject in subjects])
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(before_idgen_counters, dict(api.idgen._counters))

    def test_subject_context_requires_bound_material_project(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Course",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )
        before_project_ids = set(api.sys.g.projects.keys())

        with self.assertRaises(PreconditionFailure):
            api.get_subject_context(project_id)

        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))

    def test_edit_subject_requires_subject_root_project(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Course",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )

        with self.assertRaises(PreconditionFailure):
            api.edit_subject(project_id, "Renamed")

        self.assertEqual("Course", api._get_active_project_metadata(project_id).title)

    def test_subject_material_list_requires_subject_root_id(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.list_subject_materials(subject_id)[0]
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)

        with self.assertRaises(PreconditionFailure):
            api.list_subject_materials(material_project_id)

    def test_delete_subject_requires_subject_root_id(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.list_subject_materials(subject_id)[0]
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)

        with self.assertRaises(PreconditionFailure):
            api.delete_subject(material_project_id)

        self.assertEqual("Subject", api._get_active_project_metadata(subject_id).title)
        self.assertEqual(material_project_id, api.list_subject_materials(subject_id)[0].internal_project_id)

    def test_subject_material_mutations_require_subject_root_id(self) -> None:
        api = SystemAPI(InMemorySystem())
        subject_id = api.create_subject("Subject")
        material = api.list_subject_materials(subject_id)[0]
        material_project_id = material.internal_project_id
        self.assertIsNotNone(material_project_id)
        before_project_ids = set(api.sys.g.projects.keys())

        with self.assertRaises(PreconditionFailure):
            api.create_subject_material(
                material_project_id,
                material_type=StudyMaterialType.BOOK,
                title="Book",
            )
        with self.assertRaises(PreconditionFailure):
            api.edit_subject_material(material_project_id, material.material_id, title="Renamed")
        with self.assertRaises(PreconditionFailure):
            api.delete_subject_material(material_project_id, material.material_id)

        materials = api.list_subject_materials(subject_id)
        self.assertEqual(before_project_ids, set(api.sys.g.projects.keys()))
        self.assertEqual(1, len(materials))
        self.assertEqual(material, materials[0])


if __name__ == "__main__":
    unittest.main()
