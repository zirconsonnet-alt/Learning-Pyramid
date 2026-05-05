from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "instances" / "InstancePage.tsx"
VIDEO_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx"


def test_instance_page_uses_task_detail_layout_with_player() -> None:
    source = INSTANCE_PAGE.read_text(encoding="utf-8")

    assert "const summaryPanel = instance ? (" in source
    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "InstanceSummaryCard" in source
    assert "<VideoPane" in source
    assert "allowCaptureDrafts={false}" in source
    assert 'title="相关复述点"' in source


def test_instance_page_player_disables_recall_point_capture_only() -> None:
    instance_source = INSTANCE_PAGE.read_text(encoding="utf-8")
    video_source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "allowCaptureDrafts = true" in video_source
    assert 'mode === "capture" && !allowCaptureDrafts' in video_source
    assert "allowCaptureDrafts ? (" in video_source
    assert 'title="记复述点 (Enter)"' in video_source
    assert "allowCaptureDrafts={false}" in instance_source
    assert '"记复述点"' not in instance_source
    assert '"保存复述点"' not in instance_source
