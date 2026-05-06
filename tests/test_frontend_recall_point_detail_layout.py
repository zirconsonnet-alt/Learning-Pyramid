from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "recallPoints" / "RecallPointPage.tsx"


def test_recall_point_detail_moves_editing_into_content_card() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "概览与修改" not in source
    assert "锚点位置" not in source
    assert "onClick={openAnchorEditor}" in source
    assert "const [editingContent" in source
    assert "<CardTitle>当前内容</CardTitle>" in source
    content_card_source = source[source.index("<CardTitle>当前内容</CardTitle>"):]
    assert "<RichContentEditor" in content_card_source
    assert "保存修改" in content_card_source


def test_recall_point_detail_uses_shared_detail_page_card_style() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "RecallPointSummaryCard" in source
    assert "RecallPointContentCard" in source
    assert "theme-card-main" not in source
    assert "theme-card-header" not in source


def test_recall_point_detail_drops_explanatory_copy() -> None:
    page_source = PAGE.read_text(encoding="utf-8")
    projection_source = (REPO_ROOT / "frontend" / "src" / "views" / "recallPoints" / "components" / "ReviewProjectionCard.tsx").read_text(encoding="utf-8")

    assert "元信息、锚点和复习状态集中在这里。" not in page_source
    assert "按复习任务里的阅读顺序展示题面和答案。" not in page_source
    assert "这条复述点引用到的其他复述点不会写进题面或答案文本里。" not in page_source
    assert "基于遗忘曲线加权法，按最近正式复习记录估算当前记忆强度与复习紧迫度。" not in projection_source


def test_recall_point_review_curve_uses_full_history_convolution() -> None:
    projection_source = (REPO_ROOT / "frontend" / "src" / "views" / "recallPoints" / "components" / "ReviewProjectionCard.tsx").read_text(encoding="utf-8")

    assert "buildConvolvedReviewCurve" in projection_source
    assert "firstHistoryAtMs" in projection_source
    assert "recordsAtPoint" in projection_source
    assert "estimatedMemoryStrength" in projection_source
    assert "curveStartMs = lastReviewedAt" not in projection_source
    assert "最近一次正式复习往当前时刻衰减" not in projection_source


def test_recall_point_detail_hides_history_explanation_blocks() -> None:
    page_source = PAGE.read_text(encoding="utf-8")
    projection_source = (REPO_ROOT / "frontend" / "src" / "views" / "recallPoints" / "components" / "ReviewProjectionCard.tsx").read_text(encoding="utf-8")

    assert "正式复习时追加的理解会沉淀在这里。" not in page_source
    assert "参与计算的历史记录" not in projection_source


def test_recall_point_detail_edits_anchor_inline_with_clock_input() -> None:
    source = PAGE.read_text(encoding="utf-8")
    content_card_source = source[source.index("function RecallPointContentCard("):]

    assert "normalizeAnchorInputToPosition" in source
    assert 'placeholder="0:43"' in source
    assert "setEditingAnchor(true)" in source
    assert "保存锚点" in source
    assert "修改锚点" in source
    assert "当前项目类型不要求为复述点绑定锚点" in source
    assert "内容实例 #ee4bcb" not in content_card_source
    assert "formatInstanceReference(recallPoint.anchor.instanceId" not in content_card_source
    assert "onClick={onOpenAnchorEditor}" not in content_card_source


def test_recall_point_detail_uses_readable_instance_summary_and_curve_axis_labels() -> None:
    page_source = PAGE.read_text(encoding="utf-8")
    projection_source = (REPO_ROOT / "frontend" / "src" / "views" / "recallPoints" / "components" / "ReviewProjectionCard.tsx").read_text(encoding="utf-8")

    assert "useInstances(projectId)" in page_source
    assert 'label: "当前引用"' not in page_source
    assert 'to={`/p/${projectId}/instances/${recallPoint.anchor.instanceId}`}' in page_source
    assert "materialDisplayName" in page_source
    assert "buildXAxisTicks" in projection_source
    assert "toLocaleDateString" in projection_source
    assert "chart.xAxisTicks.map" in projection_source


def test_recall_point_references_live_inside_current_content_card() -> None:
    source = PAGE.read_text(encoding="utf-8")
    content_card_source = source[source.index("function RecallPointContentCard("):]

    assert "<CardTitle>引用关系</CardTitle>" not in source
    assert "referenceRecallPoints={referenceRecallPoints}" in source
    assert "referencesCount" in content_card_source
    assert "引用" in content_card_source
    assert "buildRecallPointDetailPath" in source
