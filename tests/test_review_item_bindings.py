import unittest

from backend.models.enums import MaterialSourceKind, ProjectType
from backend.models.rich_content import rich_text
from backend.models.review_chain import ReviewChainItemKind
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem


def _create_review_chain_sample(api: SystemAPI):
    project_id = api.create_project(
        "Review bindings",
        initial_source_kind=MaterialSourceKind.MANUAL,
        initial_project_type=ProjectType.LOOSE_POINTS,
    )
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[(rich_text("问题"), rich_text("答案"), None)],
        title="绑定测试任务",
    )
    reg = api.get_learning_task_node_entry_registration(project_id, entry_node_id)
    chain = api.get_review_chain(project_id, reg.review_chain_id)
    direct_review_task_id = next(item.id for item in chain.queue if item.kind == ReviewChainItemKind.REVIEW_TASK)
    convergence_id = next(item.id for item in chain.queue if item.kind == ReviewChainItemKind.CONVERGENCE)
    return project_id, reg.review_chain_id, direct_review_task_id, convergence_id


class ReviewItemBindingTest(unittest.TestCase):
    def test_convergence_binding_points_to_parent_review_chain(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id, review_chain_id, _, convergence_id = _create_review_chain_sample(api)

        binding = api.get_convergence_binding(project_id, convergence_id)

        self.assertEqual("REVIEW_CHAIN", binding.kind)
        self.assertEqual(review_chain_id, binding.review_chain_id)
        self.assertIsNone(binding.convergence_id)

    def test_review_task_binding_prefers_convergence_over_review_chain(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id, review_chain_id, direct_review_task_id, convergence_id = _create_review_chain_sample(api)

        direct_binding = api.get_review_task_binding(project_id, direct_review_task_id)

        self.assertEqual("REVIEW_CHAIN", direct_binding.kind)
        self.assertEqual(review_chain_id, direct_binding.review_chain_id)
        self.assertIsNone(direct_binding.convergence_id)

        api.executor_commit_review_task(project_id, direct_review_task_id, [0])
        api.submit_learning_task(
            project_id,
            items=[(rich_text("触发推进问题"), rich_text("触发推进答案"), None)],
            title="触发收敛推进",
        )
        convergence = api.get_convergence(project_id, convergence_id)
        convergence_review_task_id = convergence.review_task_ids[0]

        convergence_task_binding = api.get_review_task_binding(project_id, convergence_review_task_id)

        self.assertEqual("CONVERGENCE", convergence_task_binding.kind)
        self.assertEqual(review_chain_id, convergence_task_binding.review_chain_id)
        self.assertEqual(convergence_id, convergence_task_binding.convergence_id)


if __name__ == "__main__":
    unittest.main()
