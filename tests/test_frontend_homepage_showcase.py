from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME_PAGE = ROOT / "frontend" / "src" / "views" / "home" / "HomePage.tsx"
SHOWCASE_CHROME = ROOT / "frontend" / "src" / "views" / "home" / "ShowcaseChrome.tsx"
INDEX_CSS = ROOT / "frontend" / "src" / "index.css"
ASSETS_DIR = ROOT / "frontend" / "src" / "assets"


def test_homepage_carousel_no_longer_renders_intro_subtitle() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")

    assert 'className="lp-showcase-carousel-intro"' not in source
    assert "{item.intro}" not in source


def test_homepage_carousel_uses_requested_main_titles() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    assert "<h2>速成？期末？考研？给我 4 个选择 LearningPyramid 的理由</h2>" in source
    assert "<h2>我是考研大学生，给我 4 个选择 LearningPyramid 的理由</h2>" not in source

    section_start = source.index("const graduateReasons = [")
    section_end = source.index("] as const", section_start)
    section = source[section_start:section_end]

    expected_titles = [
        'title: "你为什么这么累？"',
        'title: "这些建议帮到你了吗？"',
        'title: "我们的系统做了什么？"',
        'title: "用它看视频有什么不同？"',
    ]

    last_position = -1
    for title in expected_titles:
        position = section.index(title)
        assert position > last_position
        last_position = position

    old_titles = [
        'title: "你为什么学得这么累"',
        'title: "常见建议为什么很难真正解决问题"',
        'title: "我们的系统到底做了什么"',
        'title: "视频播放功能"',
    ]

    for title in old_titles:
        assert title not in section


def test_homepage_carousel_tag_sits_after_each_slide_title() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")
    render_start = source.index("{graduateReasons.map((item) => (")
    render_end = source.index('<div className="lp-showcase-carousel-points">', render_start)
    render_source = source[render_start:render_end]

    assert 'className="lp-showcase-carousel-meta"' not in render_source
    assert 'className="lp-showcase-carousel-title-row"' in render_source
    assert "<h3>{item.title}</h3>" in render_source
    assert "<span className=\"lp-showcase-carousel-tag\">{item.tag}</span>" in render_source
    assert render_source.index("<h3>{item.title}</h3>") < render_source.index("<span className=\"lp-showcase-carousel-tag\">{item.tag}</span>")
    assert 'className="lp-showcase-carousel-count"' in render_source
    assert ".lp-showcase-carousel-title-row" in css


def test_homepage_removes_standalone_feature_section() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    chrome_source = SHOWCASE_CHROME.read_text(encoding="utf-8")

    assert "const featureCards = [" not in source
    assert 'id="features"' not in source
    assert 'buildHomeSectionHref("features", homeSectionPrefix)' not in chrome_source

    removed_cards = [
        'title: "本地素材目录接入"',
        'title: "学习结构化视图"',
        'title: "视频锚点式复述点"',
        'title: "学习任务与复习任务切换"',
    ]

    for removed_card in removed_cards:
        assert removed_card not in source


def test_homepage_method_cards_use_requested_short_body_copy() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")
    section_start = source.index("const mechanismCards = [")
    section_end = source.index("] as const", section_start)
    section = source[section_start:section_end]

    expected_cards = [
        (
            'title: "重点压缩"',
            'body: "这次只复习上次忘掉的，下次只复习这次忘掉的"',
            'body: "先做一次当前层的全量筛选，把“现在讲不出来”的内容收成重点集合；下一轮不再回到全量，而是只复习这个重点集合，并继续递缩，直到这一层封顶。"',
        ),
        (
            'title: "分层复习"',
            'body: "每一节、每一章，都有独立的复习组织机制"',
            'body: "当内容范围扩大、时间间隔拉长，原来的重点会漂移。系统要求你回到更大范围重新筛选，用当前状态重定位重点，避免漏掉已经重新变生疏的内容。"',
        ),
        (
            'title: "穿插复习"',
            'body: "缺失的复习就像债务，而系统不会让你债台高筑"',
            'body: "系统不会把学习和复习拆成互不相干的两段，而是在学习任务之间及时插入复习任务。你刚学完，就会接上该复习的内容，避免一路只学不回头，最后把压力堆到后面。"',
        ),
    ]

    last_position = -1
    for title, body, old_body in expected_cards:
        position = section.index(title)
        assert position > last_position
        last_position = position
        assert body in section
        assert old_body not in section

    assert 'imageSrc: methodFocusCompression' in section
    assert 'imageSrc: methodLayeredReview' in section
    assert 'imageSrc: methodInterleavedReview' in section
    assert 'import methodFocusCompression from "@/assets/method-focus-compression.webp"' in source
    assert 'import methodLayeredReview from "@/assets/method-layered-review.webp"' in source
    assert 'import methodInterleavedReview from "@/assets/method-interleaved-review.webp"' in source
    assert len(list(ASSETS_DIR.glob("method-*.webp"))) == 3
    for asset in ASSETS_DIR.glob("method-*.webp"):
        assert asset.stat().st_size <= 120_000

    render_start = source.index('id="method"')
    render_end = source.index('id="onboarding"', render_start)
    render_section = source[render_start:render_end]
    assert '<h3>{item.title}</h3>' in render_section
    assert '<p>{item.body}</p>' in render_section
    assert render_section.index('<h3>{item.title}</h3>') < render_section.index('<p>{item.body}</p>') < render_section.index(
        'className="lp-showcase-method-card-visual"',
    )
    assert 'className="lp-showcase-method-card-copy"' in render_section
    assert ".lp-showcase-method-card-copy p" in css
    assert "align-self: center;" in css


def test_homepage_onboarding_path_links_to_four_guide_documents() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    chrome_source = SHOWCASE_CHROME.read_text(encoding="utf-8")
    section_start = source.index("const onboardingSteps = [")
    section_end = source.index("] as const", section_start)
    data_section = source[section_start:section_end]
    render_start = source.index('id="onboarding"')
    render_end = source.index('id="membership"', render_start)
    render_section = source[render_start:render_end]

    expected_guides = [
        ('title: "创建学科项目"', 'to: "/guide"', 'label: "去管理专业课的学习"'),
        ('title: "学习复习"', 'to: "/guide?doc=study-review"', 'label: "去体验自动复习推送"'),
        ('title: "使用 AI 问答"', 'to: "/guide?doc=use-ai-chat"', 'label: "去感受AI学习赋能"'),
        ('title: "使用番茄钟"', 'to: "/guide?doc=use-pomodoro"', 'label: "去定明早9点的番茄钟"'),
    ]

    last_position = -1
    for title, to, label in expected_guides:
        position = data_section.index(title)
        assert position > last_position
        last_position = position
        assert to in data_section
        assert label in data_section

    assert data_section.count("to: ") == 4
    assert 'title: "如何' not in data_section
    assert 'title: "创建学科"' not in data_section
    assert 'title: "绑定并授权目录"' not in data_section
    assert 'title: "导入内容目录"' not in data_section
    assert 'title: "回工作台选内容开始学习"' not in data_section

    assert "<h2>改变，从现在开始</h2>" in render_section
    assert "<h2>快速上手</h2>" not in render_section
    assert "<h2>上手路径</h2>" not in render_section
    assert 'buildHomeSectionHref("onboarding", homeSectionPrefix), label: "快速上手"' in chrome_source
    assert 'label: "上手路径"' not in chrome_source
    assert "第一次使用先照着这 4 步走" not in render_section
    assert "<Link" in render_section
    assert "to={item.to}" in render_section
    assert 'className="lp-showcase-step-action"' in render_section
    assert "查看指引" not in render_section


def test_homepage_onboarding_uses_pill_action_labels() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")
    render_start = source.index('id="onboarding"')
    render_end = source.index('id="membership"', render_start)
    render_section = source[render_start:render_end]

    assert '<article key={item.index} className="lp-showcase-step">' in render_section
    assert '<Link to={item.to} className="lp-showcase-step-action">' in render_section
    assert "{item.label}" in render_section
    assert '<strong>查看指引</strong>' not in render_section
    assert ".lp-showcase-step-action" in css
    assert "border-radius: 999px;" in css


def test_homepage_pill_actions_vertically_center_text() -> None:
    css = INDEX_CSS.read_text(encoding="utf-8")
    step_action_start = css.index(".lp-showcase-step-action {")
    step_action_end = css.index("}", step_action_start)
    step_action_css = css[step_action_start:step_action_end]
    carousel_action_start = css.index(".lp-showcase-carousel-slide-action {")
    carousel_action_end = css.index("}", carousel_action_start)
    carousel_action_css = css[carousel_action_start:carousel_action_end]

    for action_css in (step_action_css, carousel_action_css):
        assert "display: inline-flex;" in action_css
        assert "align-items: center;" in action_css
        assert "justify-content: center;" in action_css
        assert "min-height: 44px;" in action_css
        assert "line-height: 1;" in action_css


def test_homepage_problem_cards_use_short_titles_and_previous_titles_as_symptoms() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")

    expected_cards = [
        (
            'title: "进度焦虑"',
            '{ label: "现象", text: "视频刷的越多，心里越慌" }',
            '{ label: "原因", text: "你没有强制自己看完视频必须产出点什么" }',
            'title: "视频越刷越多，心里却越来越慌"',
        ),
        (
            'title: "不会复习"',
            '{ label: "现象", text: "知道复习很重要，却只是拿来当口号" }',
            '{ label: "原因", text: "你缺乏复习组织能力，不知道哪些是现在最应该复习的" }',
            'title: "知道该复习，却不知道从哪里开始"',
        ),
        (
            'title: "低效重复"',
            '{ label: "现象", text: "虽然不会的只是一小撮，可你还是一遍遍重刷全部内容" }',
            '{ label: "原因", text: "你不知道哪些是重点，只能再刷一遍求心理安慰" }',
            'title: "时间都花在熟悉内容上"',
        ),
        (
            'title: "学完就忘"',
            '{ label: "现象", text: "第一章学得很好，可学到第六章的时候忘光了" }',
            '{ label: "原因", text: "你没有以章为复习单位组织复习" }',
            'title: "前面学得好，往后推进又忘了"',
        ),
    ]

    for title, symptom, cause, old_title in expected_cards:
        assert title in source
        assert symptom in source
        assert cause in source
        assert old_title not in source


def test_homepage_carousel_cards_use_compressed_right_side_illustrations() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")
    section_start = source.index("const graduateReasons = [")
    section_end = source.index("] as const", section_start)
    section = source[section_start:section_end]

    expected_cards = [
        (
            'title: "进度焦虑"',
            'imageSrc: carouselProgressAnxiety',
            'import carouselProgressAnxiety from "@/assets/carousel-progress-anxiety.webp"',
        ),
        (
            'title: "不会复习"',
            'imageSrc: carouselReviewConfusion',
            'import carouselReviewConfusion from "@/assets/carousel-review-confusion.webp"',
        ),
        (
            'title: "低效重复"',
            'imageSrc: carouselInefficientRepeat',
            'import carouselInefficientRepeat from "@/assets/carousel-inefficient-repeat.webp"',
        ),
        (
            'title: "学完就忘"',
            'imageSrc: carouselForgettingAfterLearning',
            'import carouselForgettingAfterLearning from "@/assets/carousel-forgetting-after-learning.webp"',
        ),
        (
            'title: "记笔记"',
            'imageSrc: carouselTakeNotes',
            'import carouselTakeNotes from "@/assets/carousel-take-notes.webp"',
        ),
        (
            'title: "挑重点"',
            'imageSrc: carouselChooseFocus',
            'import carouselChooseFocus from "@/assets/carousel-choose-focus.webp"',
        ),
        (
            'title: "艾宾浩斯"',
            'imageSrc: carouselEbbinghaus',
            'import carouselEbbinghaus from "@/assets/carousel-ebbinghaus.webp"',
        ),
        (
            'title: "无脑重复"',
            'imageSrc: carouselBlindRepeat',
            'import carouselBlindRepeat from "@/assets/carousel-blind-repeat.webp"',
        ),
        (
            'title: "边看边记"',
            'imageSrc: carouselLearnAndNote',
            'import carouselLearnAndNote from "@/assets/carousel-learn-and-note.webp"',
        ),
        (
            'title: "笔记推送"',
            'imageSrc: carouselNotePush',
            'import carouselNotePush from "@/assets/carousel-note-push.webp"',
        ),
        (
            'title: "重点压缩"',
            'imageSrc: carouselFocusCompression',
            'import carouselFocusCompression from "@/assets/carousel-focus-compression.webp"',
        ),
        (
            'title: "分层复习"',
            'imageSrc: carouselLayeredReview',
            'import carouselLayeredReview from "@/assets/carousel-layered-review.webp"',
        ),
        (
            'title: "微休息神经重放"',
            'imageSrc: carouselNeuralReplay',
            'import carouselNeuralReplay from "@/assets/carousel-neural-replay.webp"',
        ),
        (
            'title: "AI问答"',
            'imageSrc: carouselAiQa',
            'import carouselAiQa from "@/assets/carousel-ai-qa.webp"',
        ),
        (
            'title: "快捷记笔记"',
            'imageSrc: carouselQuickNote',
            'import carouselQuickNote from "@/assets/carousel-quick-note.webp"',
        ),
        (
            'title: "番茄钟"',
            'imageSrc: carouselPomodoro',
            'import carouselPomodoro from "@/assets/carousel-pomodoro.webp"',
        ),
    ]

    for title, image_src, import_line in expected_cards:
        position = section.index(title)
        assert image_src in section[position : position + 280]
        assert import_line in source

    assert section.count('imageSrc: carousel') == 16

    for asset in ASSETS_DIR.glob("carousel-*.webp"):
        assert asset.stat().st_size <= 120_000

    expected_asset_count = 16
    assert len(list(ASSETS_DIR.glob("carousel-*.webp"))) == expected_asset_count

    assert 'const pointImageSrc = "imageSrc" in point ? point.imageSrc : undefined' in source
    assert 'className={`lp-showcase-carousel-point${pointImageSrc ? " lp-showcase-carousel-point-with-image" : ""}`}' in source
    assert 'className="lp-showcase-carousel-point-copy"' in source
    assert 'className="lp-showcase-carousel-point-visual"' in source
    assert 'alt={`${point.title}示意图`}' in source
    assert ".lp-showcase-carousel-point-with-image" in css
    assert ".lp-showcase-carousel-point-visual" in css


def test_homepage_advice_cards_use_theory_benefits_and_practice_difficulties() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")

    expected_cards = [
        (
            'title: "记笔记"',
            '{ label: "理论优点", text: "强化学习效果，提供复习锚点" }',
            '{ label: "实践难题", text: "笔记与视频资源无法绑定，难以找到来源" }',
        ),
        (
            'title: "挑重点"',
            '{ label: "理论优点", text: "效率高，方向对" }',
            '{ label: "实践难题", text: "你知道什么是重点吗？" }',
        ),
        (
            'title: "艾宾浩斯"',
            '{ label: "理论优点", text: "抗遗忘效果强" }',
            '{ label: "实践难题", text: "一日摆烂，满盘皆输" }',
        ),
        (
            'title: "无脑重复"',
            '{ label: "理论优点", text: "无" }',
            '{ label: "实践难题", text: "时间真的够吗？" }',
        ),
    ]

    last_position = -1
    for title, theory_benefit, practice_difficulty in expected_cards:
        position = source.index(title)
        assert position > last_position
        last_position = position
        assert theory_benefit in source
        assert practice_difficulty in source

    assert 'label: "是否有用"' not in source
    assert 'label: "你需要什么"' not in source


def test_homepage_system_cards_use_requested_titles_actions_and_outcomes() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    section_start = source.index('index: "03"')
    section_end = source.index('index: "04"')
    section = source[section_start:section_end]

    expected_cards = [
        (
            'title: "边看边记"',
            '{ label: "做法", text: "看视频快速记录复述点" }',
            '{ label: "解决了什么", text: "看完不再觉得什么都没留下" }',
        ),
        (
            'title: "笔记推送"',
            '{ label: "做法", text: "以复述点为单位组织你的复习" }',
            '{ label: "解决了什么", text: "学完不再困惑到底该复习什么" }',
        ),
        (
            'title: "重点压缩"',
            '{ label: "做法", text: "每次只推你最该复习的内容" }',
            '{ label: "解决了什么", text: "高效复习，节省不必要的重复" }',
        ),
        (
            'title: "分层复习"',
            '{ label: "做法", text: "小节、章都有自己的复习推送节奏" }',
            '{ label: "解决了什么", text: "缓解了大跨度层面的遗忘" }',
        ),
    ]

    last_position = -1
    for title, action, outcome in expected_cards:
        position = section.index(title)
        assert position > last_position
        last_position = position
        assert action in section
        assert outcome in section

    assert 'label: "流程"' not in section


def test_homepage_featured_fourth_slide_uses_requested_copy_and_single_guide_button() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")
    section_start = source.index('index: "04"')
    section_end = source.index("] as const", section_start)
    section = source[section_start:section_end]

    expected_cards = [
        (
            'title: "微休息神经重放"',
            '{ label: "介绍", text: "视频播放时，每隔几分钟强制休息10秒，神经重放的同时强化对学习的渴望" }',
        ),
        (
            'title: "AI问答"',
            '{ label: "介绍", text: "视频播放时，随时举手提问，AI会结合视频关键帧和字幕回答你的问题，课后也可选择范围继续提问" }',
        ),
        (
            'title: "快捷记笔记"',
            '{ label: "介绍", text: "视频播放时，使用回车等快捷键记录复述点，截取视频内容，双手无需离开键盘" }',
        ),
        (
            'title: "番茄钟"',
            '{ label: "介绍", text: "你只能在一个番茄的时间内学习指定的项目，或许这会让你更加珍惜学习的时光" }',
        ),
    ]

    assert 'title: "用它看视频有什么不同？"' in section
    assert 'tag: "功能"' in section

    last_position = -1
    for title, intro in expected_cards:
        position = section.index(title)
        assert position > last_position
        last_position = position
        assert intro in section

    assert 'ctaLabel: "立即体验"' not in section
    assert 'ctaHref: "#onboarding"' not in section
    assert "guideDocSlug" not in section
    assert "memberFeature: true" not in section

    assert 'title: "现在开始，最合适的方式是什么"' not in section
    assert 'title: "先选一门最需要减负的科目"' not in section
    assert 'title: "建立项目并接入资料目录"' not in section
    assert 'title: "看课时边学边留复述点"' not in section
    assert 'title: "学完后立刻进入第一次复习"' not in section

    assert 'import { startGuideWalkthrough } from "@/ui/guideWalkthrough/guideWalkthroughController"' not in source
    assert 'startGuideWalkthrough(point.guideDocSlug)' not in source
    assert 'startGuideWalkthrough(item.guideDocSlug)' not in source
    assert '<Link to={item.ctaHref}' not in source
    assert "lp-showcase-carousel-slide-actions" not in source
    assert "lp-showcase-carousel-slide-action" not in source
    assert "color: #4d3508;" in css


def test_homepage_invite_mechanism_uses_three_short_bullets() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    section_start = source.index("const inviteBullets = [")
    section_end = source.index("] as const", section_start)
    section = source[section_start:section_end]

    expected_bullets = [
        '"绑定邀请码获7.5元券"',
        '"被邀请者有效充值满15元，获5元佣金"',
        '"已结算佣金满20，随时提现"',
    ]

    for bullet in expected_bullets:
        assert bullet in section

    assert section.count('"') == len(expected_bullets) * 2
    assert "好友绑定你的邀请码后，会获得 1 张会员 7.5 折券。" not in section
    assert "好友实际支付满 15 元并过 24 小时退款窗口后，你会获得 5 元佣金。" not in section
    assert "已结算佣金可在会员中心申请提现到本人微信支付账户。" not in section
    assert "会员中心可以统一查看邀请码、折扣券、佣金、提现和订单记录。" not in section


def test_homepage_faq_uses_requested_four_questions() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    section_start = source.index("const faqItems = [")
    section_end = source.index("] as const", section_start)
    section = source[section_start:section_end]

    expected_faqs = [
        (
            'title: "创建项目前需要干什么？"',
            'body: "请在本地准备好你的视频或其他学习资料"',
        ),
        (
            'title: "为什么佣金不立即生效？"',
            'body: "用户充值后有3天退款期，退款期过后才视为有效"',
        ),
        (
            'title: "购买会员立刻就能使用AI功能吗？"',
            'body: "购买会员仅代表获得AI使用能力，实际使用前还需设置您的API供系统调用"',
        ),
        (
            'title: "我的视频资料没有字幕怎么办？"',
            'body: "可以免费下载我们的字幕工具，下载后导入目录，稍作等待，即可生成字幕"',
        ),
    ]

    last_position = -1
    for title, body in expected_faqs:
        position = section.index(title)
        assert position > last_position
        last_position = position
        assert body in section

    assert section.count("title: ") == 4
    assert section.count("body: ") == 4
    assert "为什么左侧“学习对象”还是空的？" not in section
    assert "为什么视频区域提示找不到本地文件？" not in section
    assert "什么时候要再回“项目设置”？" not in section
    assert "它适合哪些学习内容？" not in section


def test_homepage_membership_card_highlights_member_benefits() -> None:
    source = HOME_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")
    section_start = source.index('id="membership"')
    section_end = source.index('id="faq"', section_start)
    section = source[section_start:section_end]

    assert 'className="lp-showcase-pricing-grid lp-showcase-membership-grid"' in section
    assert 'className="lp-showcase-membership-card-top"' in section
    assert 'className="lp-showcase-membership-plan-grid"' in section
    assert 'className="lp-showcase-membership-price-block"' in section
    assert 'className="lp-showcase-membership-benefits"' in section
    assert "<h3>月会员</h3>" in section
    assert "<h3>考研套餐</h3>" in section
    assert "<strong>¥0.5</strong>" in section
    assert "按购买当天到 12 月 21 日计费" in section
    assert "<h4>会员权益</h4>" in section
    assert "<li>番茄钟：学习规划与督促</li>" in section
    assert "<li>AI交互：你的助理及良师</li>" in section

    assert ".lp-showcase-membership-card-top" in css
    assert ".lp-showcase-membership-grid" in css
    assert "grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);" in css
    assert ".lp-showcase-membership-plan-grid" in css
    assert ".lp-showcase-membership-price-block" in css
    assert ".lp-showcase-membership-benefits" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(170px, 220px);" in css
