from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "reviewChains" / "ReviewChainPage.tsx"


def test_review_chain_page_uses_task_detail_layout() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const summaryPanel = chainQ.data ? (" in source
    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "ReviewChainSummaryCard" in source
    assert "ReviewChainQueueListCard" in source
    assert "复习链队列" in source
    assert "describeQueueItemKind(item.kind)" in source
    assert '/learning-task-nodes/${bindingQ.data.entryNodeId}' in source
    assert '/task-tree/${bindingQ.data.entryNodeId}' not in source
