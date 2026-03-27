import { useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"

import brandLogo from "@/assets/logo.png"
import methodFocusCompression from "@/assets/method-focus-compression.png"
import methodInterleavedReview from "@/assets/method-interleaved-review.png"
import methodLayeredReview from "@/assets/method-layered-review.png"
import { useCurrentUser } from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"

const navItems = [
  { href: "#method", label: "方法" },
  { href: "#features", label: "功能" },
  { href: "#onboarding", label: "上手路径" },
  { href: "#membership", label: "会员" },
  { href: "#faq", label: "常见问题" },
] as const

const mechanismCards = [
  {
    icon: "A",
    title: "重点压缩",
    body: "先做一次当前层的全量筛选，把“现在讲不出来”的内容收成重点集合；下一轮不再回到全量，而是只复习这个重点集合，并继续递缩，直到这一层封顶。",
    imageSrc: methodFocusCompression,
  },
  {
    icon: "B",
    title: "分层复习",
    body: "当材料范围扩大、时间间隔拉长，原来的重点会漂移。系统要求你回到更大范围重新筛选，用当前状态重定位重点，避免漏掉已经重新变生疏的内容。",
    imageSrc: methodLayeredReview,
  },
  {
    icon: "C",
    title: "穿插复习",
    body: "系统不会把学习和复习拆成互不相干的两段，而是在学习任务之间及时插入复习任务。你刚学完，就会接上该复习的内容，避免一路只学不回头，最后把压力堆到后面。",
    imageSrc: methodInterleavedReview,
  },
] as const

const featureCards = [
  {
    icon: "01",
    title: "本地素材目录接入",
    body: "一个项目对应一个你自己管理的视频目录。系统通过目录授权与导入，自动识别视频文件与层级结构，而不是让你在界面里手工搭树。",
  },
  {
    icon: "02",
    title: "学习结构化视图",
    body: "左侧学习对象树来自目录扫描结果，学习任务树与时间线则帮助你回看项目运行过程。它们一起把材料结构、任务推进和层级位置展示清楚，而不是只给你一批零散卡片。",
  },
  {
    icon: "03",
    title: "视频锚点式复述点",
    body: "在工作台里暂停视频，点击添加复述点，系统自动记录当前时间锚点。随后填写问题与答案，逐步把材料里的关键记忆目标录进去。",
  },
  {
    icon: "04",
    title: "学习任务与复习任务切换",
    body: "当系统已排出待做复习时，工作台中间区域会从“复述点录入”切到“复习”。你只需要先回忆，再显示答案，再诚实判断“会 / 不会”。",
  },
] as const

const onboardingSteps = [
  {
    index: "1",
    title: "创建项目",
    body: "先在项目页新建一个主题，例如机器学习、英语听力或操作系统。创建完成后直接进入项目，而不是停在列表页。",
  },
  {
    index: "2",
    title: "绑定目录",
    body: "到项目设置里选择并授权本地素材目录。一个项目可以理解为绑定到一个你自己管理的视频目录。",
  },
  {
    index: "3",
    title: "导入内容目录",
    body: "授权之后再点击“导入内容目录”。系统会识别目录层级、重建学习对象树，并为材料实例建立索引。",
  },
  {
    index: "4",
    title: "开始录入与复习",
    body: "回到工作台，选择视频，添加复述点并提交学习；之后按系统排出的复习链完成“会 / 不会”判断，形成最小闭环。",
  },
] as const

const inviteBullets = [
  "好友绑定你的邀请码并完成首个会员订单后，你会获得 1 张 5 元券。",
  "每个被邀请人只能绑定 1 个邀请人，也只会触发 1 次奖励。",
  "奖励券可用于首单，也可用于后续续费。",
  "会员中心可以统一查看邀请码、优惠券、订单和邀请记录。",
] as const

const faqItems = [
  {
    title: "为什么左侧“学习对象”还是空的？",
    body: "优先检查四件事：有没有点导入内容目录、目录是否已授权、根目录是否选对、当前浏览器是否支持或保留了目录授权。",
  },
  {
    title: "为什么视频区域提示找不到本地文件？",
    body: "最常见原因是授权了错误目录、文件后来被移动、目录变了但没有重新导入，或者浏览器站点权限已经失效。先回项目设置处理，不要急着删项目。",
  },
  {
    title: "什么时候要再回“项目设置”？",
    body: "第一次上手、换电脑、换浏览器、文件被移动或重命名、需要补授权、需要重新导入内容目录、或者要确认项目路径与同步策略时，都应该先回项目设置。",
  },
  {
    title: "它适合哪些学习内容？",
    body: "专业课、概念体系、题型模板、论证骨架、听力材料都可以。只要你能给出明确的“会”标准，系统就能围绕它组织筛选和复习。",
  },
] as const

const graduateReasons = [
  {
    index: "01",
    tag: "问题",
    title: "你为什么学得这么累",
    intro: "很多考研的疲惫，不是因为你不努力，而是因为学过的内容没有被记录、筛选和定期回收。",
    points: [
      {
        title: "视频越刷越多，心里却越来越慌",
        lines: [
          { label: "现象", text: "你一遍遍刷同一节课，总担心某个知识点会漏掉。" },
          { label: "原因", text: "因为你没有把从视频里真正学到的内容沉淀下来，它们只停留在“我好像听过”。" },
        ],
      },
      {
        title: "知道该复习，却不知道从哪里开始",
        lines: [
          { label: "现象", text: "你知道复习重要，但总不知道该什么时候复习、复习哪一部分。" },
          { label: "原因", text: "因为你还没有形成一个稳定、可持续的学习与复习节奏。" },
        ],
      },
      {
        title: "时间都花在熟悉内容上",
        lines: [
          { label: "现象", text: "你明明有很多不会的地方，却总在重复那些早就熟了的知识点。" },
          { label: "原因", text: "因为你还没有从庞杂内容里筛出此刻最该处理的重点。" },
        ],
      },
      {
        title: "前面学得好，往后推进又忘了",
        lines: [
          { label: "现象", text: "这段时间你对章节 A 掌握得很好，可学到章节 D 时，前面的内容又开始松动。" },
          { label: "原因", text: "因为你缺少一个“回到全集做检查”的机制，不知道什么时候该重新做一轮完整捕捞。" },
        ],
      },
    ],
  },
  {
    index: "02",
    tag: "建议",
    title: "常见建议为什么很难真正解决问题",
    intro: "很多建议本身没错，问题是它们太抽象，或者对执行力要求太高，最后很难落到每天的学习动作里。",
    points: [
      {
        title: "记笔记",
        lines: [
          { label: "是否有用", text: "有用，但对大多数人来说，这件事很难长期稳定坚持。" },
          { label: "你需要什么", text: "你更需要一个随时能回看、并且和视频内容一一对应的知识仓库。" },
        ],
      },
      {
        title: "艾宾浩斯式学习方法",
        lines: [
          { label: "是否有用", text: "理论上成立，但现实里很难坚持。复习量会越滚越大，一旦断一天，节奏就很容易崩掉。" },
          { label: "你需要什么", text: "你真正需要的是学完就能接上复习，并且清楚知道“现在该复习什么”的节律。" },
        ],
      },
      {
        title: "挑重点",
        lines: [
          { label: "是否有用", text: "方向是对的，但太抽象了，很多人根本不知道重点到底该怎么挑。" },
          { label: "你需要什么", text: "你需要的是可执行的重点压缩机制，从重要内容里继续筛出更重要的部分。" },
        ],
      },
      {
        title: "重新学一遍 A",
        lines: [
          { label: "是否有用", text: "通常不合理，因为重学整章的成本太高，也很难长期接受。" },
          { label: "你需要什么", text: "你需要的是固定学完 N 个章节后，对它们的全集做一次全量捕捞，不是重学，而是重新检查一遍所有知识点。" },
        ],
      },
    ],
  },
  {
    index: "03",
    tag: "系统",
    title: "我们的系统到底做了什么",
    intro: "LearningPyramid 不是一句“更高效复习”的口号，而是把记录、复习、筛选和回捞拆成了一条能每天执行的流程。",
    points: [
      {
        title: "看视频时顺手留下复述点",
        lines: [
          { label: "做法", text: "看课时随手记录复述点，一边强化记忆，一边留下“我学过什么”的痕迹。" },
          { label: "流程", text: "看视频 -> 暂停 -> 记录时间锚点 -> 写下问题和答案 -> 留下之后可复习的知识单元。" },
        ],
      },
      {
        title: "学完立即进入复习",
        lines: [
          { label: "做法", text: "每次提交学习后，系统都会立即接上复习，而且复习内容来自你的历史记忆表现。" },
          { label: "流程", text: "提交学习 -> 生成复习任务 -> 先回忆 -> 再看答案 -> 标记会或不会。" },
        ],
      },
      {
        title: "下一轮只盯住上次不会的内容",
        lines: [
          { label: "做法", text: "新的复习任务优先来自你上一次标记为不会的部分。" },
          { label: "流程", text: "不会 -> 进入下一轮重点集合 -> 再复习 -> 继续筛掉会的，只留下仍然不会的内容。" },
        ],
      },
      {
        title: "用上推机制和分层任务树递归复习",
        lines: [
          { label: "做法", text: "系统通过上推机制和分层学习任务树，把复习做成递归推进，而不是零散补漏。" },
          { label: "流程", text: "小范围筛重点 -> 逐层压缩 -> 到一定阶段回到更大范围重新捕捞 -> 再继续递缩。" },
        ],
      },
    ],
  },
  {
    index: "04",
    tag: "结语",
    title: "现在开始，最合适的方式是什么",
    intro: "不要等到完全理解系统再开始。先用一门最焦虑、最容易遗忘的科目跑通一轮，你就会知道它到底适不适合你。",
    points: [
      {
        title: "先选一门最需要减负的科目",
        lines: [
          { label: "建议", text: "不要一上来四科并行。先拿最容易遗忘、最需要压重复的那一科做样板。" },
        ],
      },
      {
        title: "建立项目并接入资料目录",
        lines: [
          { label: "建议", text: "先让视频、章节和学习对象形成稳定结构，后面的复习节律才有地方承接。" },
        ],
      },
      {
        title: "看课时边学边留复述点",
        lines: [
          { label: "建议", text: "不要只把课听过去。遇到关键知识点就停一下，留下之后能回忆、能复习的记录。" },
        ],
      },
      {
        title: "学完后立刻进入第一次复习",
        lines: [
          { label: "建议", text: "让系统第一次根据你的会/不会来安排节律，你会立刻体会到“终于知道该复习什么”的区别。" },
        ],
      },
    ],
  },
] as const

export function HomePage() {
  const capabilitiesQ = useSystemCapabilities()
  const authKnown = capabilitiesQ.data !== undefined
  const authEnabled = capabilitiesQ.data?.authEnabled ?? true
  const allowSignup = capabilitiesQ.data?.allowSignup ?? false
  const currentUserQ = useCurrentUser(authKnown && authEnabled)
  const isLoggedIn = Boolean(currentUserQ.data)

  usePageMeta({
    title: "LearningPyramid | 把每一次遍历都变得更值",
    description: "LearningPyramid 是一套基于 PLM 的学习系统：先做全量筛选，再对重点递缩压缩，并在时间与范围变化时重新校准。",
    path: "/",
  })

  const navActionHref = isLoggedIn || !authEnabled ? "/projects" : allowSignup ? "/login?mode=register" : "/login"
  const navActionLabel = isLoggedIn || !authEnabled ? "进入项目" : allowSignup ? "登录/注册" : "登录"
  const registerHref = isLoggedIn || !authEnabled ? "/projects" : allowSignup ? "/login?mode=register" : "/login"
  const registerLabel = isLoggedIn || !authEnabled ? "进入项目" : allowSignup ? "立即注册" : "去登录"
  const [activeReasonIndex, setActiveReasonIndex] = useState(0)
  const [isReasonCarouselPaused, setIsReasonCarouselPaused] = useState(false)

  useEffect(() => {
    if (isReasonCarouselPaused) {
      return undefined
    }

    const timer = window.setInterval(() => {
      setActiveReasonIndex((current) => (current + 1) % graduateReasons.length)
    }, 6800)

    return () => window.clearInterval(timer)
  }, [isReasonCarouselPaused])

  function showPrevReason() {
    setActiveReasonIndex((current) => (current - 1 + graduateReasons.length) % graduateReasons.length)
  }

  function showNextReason() {
    setActiveReasonIndex((current) => (current + 1) % graduateReasons.length)
  }

  return (
    <div className="lp-showcase-page">
      <header className="lp-showcase-site-header">
        <div className="lp-showcase-container lp-showcase-nav">
          <Link className="lp-showcase-brand" to="/">
            <img className="lp-showcase-brand-mark" src={brandLogo} alt="LearningPyramid logo" />
            <span>LearningPyramid</span>
          </Link>

          <nav className="lp-showcase-nav-links" aria-label="主导航">
            {navItems.map((item) => (
              <a key={item.href} href={item.href}>
                {item.label}
              </a>
            ))}
          </nav>

          <div className="lp-showcase-nav-actions">
            <Link className="lp-showcase-btn lp-showcase-btn-primary" to={navActionHref}>
              {navActionLabel}
            </Link>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="lp-showcase-section lp-showcase-carousel-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-carousel-shell">
              <div className="lp-showcase-carousel-header">
                <h2>我是考研大学生，给我 4 个选择 LearningPyramid 的理由</h2>
              </div>

              <div
                className="lp-showcase-carousel-viewport"
                onMouseEnter={() => setIsReasonCarouselPaused(true)}
                onMouseLeave={() => setIsReasonCarouselPaused(false)}
              >
                <button
                  type="button"
                  className="lp-showcase-carousel-edge lp-showcase-carousel-edge-left"
                  onClick={showPrevReason}
                  aria-label="查看上一组理由"
                >
                  <ChevronLeft className="h-6 w-6" />
                </button>

                <div className="lp-showcase-carousel-track" style={{ transform: `translateX(-${activeReasonIndex * 100}%)` }}>
                  {graduateReasons.map((item) => (
                    <article key={item.index} className="lp-showcase-carousel-slide">
                      <div className="lp-showcase-carousel-meta">
                        <span className="lp-showcase-carousel-tag">{item.tag}</span>
                        <span className="lp-showcase-carousel-count">
                          {item.index} / {graduateReasons.length.toString().padStart(2, "0")}
                        </span>
                      </div>
                      <h3>{item.title}</h3>
                      <p className="lp-showcase-carousel-intro">{item.intro}</p>
                      <div className="lp-showcase-carousel-points">
                        {item.points.map((point) => (
                          <div key={point.title} className="lp-showcase-carousel-point">
                            <h4>{point.title}</h4>
                            <div className="lp-showcase-carousel-point-lines">
                              {point.lines.map((line) => (
                                <p key={line.label}>
                                  <strong>{line.label}：</strong>
                                  {line.text}
                                </p>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>

                <button
                  type="button"
                  className="lp-showcase-carousel-edge lp-showcase-carousel-edge-right"
                  onClick={showNextReason}
                  aria-label="查看下一组理由"
                >
                  <ChevronRight className="h-6 w-6" />
                </button>
              </div>
            </div>
          </div>
        </section>

        <section id="method" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>方法</h2>
            </div>
            <div className="lp-showcase-grid-3">
              {mechanismCards.map((item) => (
                <article key={item.title} className="lp-showcase-feature lp-showcase-method-card">
                  <div className="lp-showcase-method-card-head">
                    <div className="lp-showcase-method-card-copy">
                      <div className="lp-showcase-feature-icon">{item.icon}</div>
                      <h3>{item.title}</h3>
                    </div>
                    <div className="lp-showcase-method-card-visual">
                      <img src={item.imageSrc} alt={`${item.title}示意图`} loading="lazy" />
                    </div>
                  </div>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>功能</h2>
            </div>
            <div className="lp-showcase-grid-2">
              {featureCards.map((item) => (
                <article key={item.title} className="lp-showcase-feature">
                  <div className="lp-showcase-feature-icon">{item.icon}</div>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="onboarding" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>上手路径</h2>
            </div>
            <div className="lp-showcase-steps-grid">
              {onboardingSteps.map((item) => (
                <article key={item.index} className="lp-showcase-step">
                  <div className="lp-showcase-step-no">{item.index}</div>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="membership" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>会员</h2>
            </div>
            <div className="lp-showcase-pricing-grid">
              <article className="lp-showcase-pricing-card">
                <h3>月会员</h3>
                <div className="lp-showcase-price">
                  <strong>¥19.9</strong>
                  <span>/ 月</span>
                </div>
                <div className="lp-showcase-price-note">首单价 ¥14.9，首单叠券最低可到 ¥9.9</div>
                <div className="lp-showcase-hero-actions lp-showcase-membership-actions">
                  <Link className="lp-showcase-btn lp-showcase-btn-primary" to="/membership">
                    查看会员
                  </Link>
                  <Link className="lp-showcase-btn lp-showcase-btn-secondary" to={registerHref}>
                    {registerLabel}
                  </Link>
                </div>
              </article>

              <article className="lp-showcase-pricing-card">
                <h3>邀请机制</h3>
                <ul className="lp-showcase-pricing-list">
                  {inviteBullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </div>
          </div>
        </section>

        <section id="faq" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>常见问题</h2>
            </div>
            <div className="lp-showcase-faq-grid">
              {faqItems.map((item) => (
                <article key={item.title} className="lp-showcase-faq-item">
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

      </main>

      <footer className="lp-showcase-footer">
        <div className="lp-showcase-container lp-showcase-footer-line">
          <div>© 2026 LearningPyramid · Focus compression for real learning.</div>
          <div>把时间留给真正不会的部分。</div>
        </div>
      </footer>
    </div>
  )
}
