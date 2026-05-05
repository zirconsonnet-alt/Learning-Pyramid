import { useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"

import carouselAiQa from "@/assets/carousel-ai-qa.webp"
import carouselBlindRepeat from "@/assets/carousel-blind-repeat.webp"
import carouselChooseFocus from "@/assets/carousel-choose-focus.webp"
import carouselEbbinghaus from "@/assets/carousel-ebbinghaus.webp"
import carouselFocusCompression from "@/assets/carousel-focus-compression.webp"
import carouselForgettingAfterLearning from "@/assets/carousel-forgetting-after-learning.webp"
import carouselInefficientRepeat from "@/assets/carousel-inefficient-repeat.webp"
import carouselLayeredReview from "@/assets/carousel-layered-review.webp"
import carouselLearnAndNote from "@/assets/carousel-learn-and-note.webp"
import carouselNeuralReplay from "@/assets/carousel-neural-replay.webp"
import carouselNotePush from "@/assets/carousel-note-push.webp"
import carouselPomodoro from "@/assets/carousel-pomodoro.webp"
import carouselProgressAnxiety from "@/assets/carousel-progress-anxiety.webp"
import carouselQuickNote from "@/assets/carousel-quick-note.webp"
import carouselReviewConfusion from "@/assets/carousel-review-confusion.webp"
import carouselTakeNotes from "@/assets/carousel-take-notes.webp"
import methodFocusCompression from "@/assets/method-focus-compression.webp"
import methodInterleavedReview from "@/assets/method-interleaved-review.webp"
import methodLayeredReview from "@/assets/method-layered-review.webp"
import { startGuideWalkthrough } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { ShowcaseFooter, ShowcaseSiteHeader, useShowcaseEntryPaths } from "@/views/home/ShowcaseChrome"

const mechanismCards = [
  {
    icon: "A",
    title: "重点压缩",
    body: "这次只复习上次忘掉的，下次只复习这次忘掉的",
    imageSrc: methodFocusCompression,
  },
  {
    icon: "B",
    title: "分层复习",
    body: "每一节、每一章，都有独立的复习组织机制",
    imageSrc: methodLayeredReview,
  },
  {
    icon: "C",
    title: "穿插复习",
    body: "缺失的复习就像债务，而系统不会让你债台高筑",
    imageSrc: methodInterleavedReview,
  },
] as const

const onboardingSteps = [
  {
    index: "1",
    title: "创建学科",
    body: "先在项目页新建一门学科，例如机器学习、英语听力或操作系统。创建完成后直接进入项目，而不是停在列表页。",
  },
  {
    index: "2",
    title: "绑定并授权目录",
    body: "到项目设置里选择并授权本地素材目录。一个项目可以理解为绑定到一个你自己管理的视频目录。",
  },
  {
    index: "3",
    title: "导入内容目录",
    body: "授权之后再点击“导入内容目录”。系统会识别目录层级、重建学习对象树，并为内容实例建立索引。",
  },
  {
    index: "4",
    title: "回工作台选内容开始学习",
    body: "回到工作台，先从左侧选中当前视频，再添加复述点并提交学习；之后按系统排出的复习链手写答案，必要时跳过，并完成“记得 / 不记得”判断，先跑通最小闭环。",
  },
] as const

const inviteBullets = [
  "绑定邀请码获7.5元券",
  "被邀请者有效充值满15元，获5元佣金",
  "已结算佣金满20，随时提现",
] as const

const faqItems = [
  {
    title: "创建项目前需要干什么？",
    body: "请在本地准备好你的视频或其他学习资料",
  },
  {
    title: "为什么佣金不立即生效？",
    body: "用户充值后有3天退款期，退款期过后才视为有效",
  },
  {
    title: "购买会员立刻就能使用AI功能吗？",
    body: "购买会员仅代表获得AI使用能力，实际使用前还需设置您的API供系统调用",
  },
  {
    title: "我的视频资料没有字幕怎么办？",
    body: "可以免费下载我们的字幕工具，下载后导入目录，稍作等待，即可生成字幕",
  },
] as const

const graduateReasons = [
  {
    index: "01",
    tag: "问题",
    title: "你为什么这么累？",
    intro: "很多考研的疲惫，不是因为你不努力，而是因为学过的内容没有被记录、筛选和定期回收。",
    points: [
      {
        title: "进度焦虑",
        imageSrc: carouselProgressAnxiety,
        lines: [
          { label: "现象", text: "视频刷的越多，心里越慌" },
          { label: "原因", text: "你没有强制自己看完视频必须产出点什么" },
        ],
      },
      {
        title: "不会复习",
        imageSrc: carouselReviewConfusion,
        lines: [
          { label: "现象", text: "知道复习很重要，却只是拿来当口号" },
          { label: "原因", text: "你缺乏复习组织能力，不知道哪些是现在最应该复习的" },
        ],
      },
      {
        title: "低效重复",
        imageSrc: carouselInefficientRepeat,
        lines: [
          { label: "现象", text: "虽然不会的只是一小撮，可你还是一遍遍重刷全部内容" },
          { label: "原因", text: "你不知道哪些是重点，只能再刷一遍求心理安慰" },
        ],
      },
      {
        title: "学完就忘",
        imageSrc: carouselForgettingAfterLearning,
        lines: [
          { label: "现象", text: "第一章学得很好，可学到第六章的时候忘光了" },
          { label: "原因", text: "你没有以章为复习单位组织复习" },
        ],
      },
    ],
  },
  {
    index: "02",
    tag: "建议",
    title: "这些建议帮到你了吗？",
    intro: "很多建议本身没错，问题是它们太抽象，或者对执行力要求太高，最后很难落到每天的学习动作里。",
    points: [
      {
        title: "记笔记",
        imageSrc: carouselTakeNotes,
        lines: [
          { label: "理论优点", text: "强化学习效果，提供复习锚点" },
          { label: "实践难题", text: "笔记与视频资源无法绑定，难以找到来源" },
        ],
      },
      {
        title: "挑重点",
        imageSrc: carouselChooseFocus,
        lines: [
          { label: "理论优点", text: "效率高，方向对" },
          { label: "实践难题", text: "你知道什么是重点吗？" },
        ],
      },
      {
        title: "艾宾浩斯",
        imageSrc: carouselEbbinghaus,
        lines: [
          { label: "理论优点", text: "抗遗忘效果强" },
          { label: "实践难题", text: "一日摆烂，满盘皆输" },
        ],
      },
      {
        title: "无脑重复",
        imageSrc: carouselBlindRepeat,
        lines: [
          { label: "理论优点", text: "无" },
          { label: "实践难题", text: "时间真的够吗？" },
        ],
      },
    ],
  },
  {
    index: "03",
    tag: "系统",
    title: "我们的系统做了什么？",
    intro: "LearningPyramid 不是一句“更高效复习”的口号，而是把记录、复习、筛选和回捞拆成了一条能每天执行的流程。",
    points: [
      {
        title: "边看边记",
        imageSrc: carouselLearnAndNote,
        lines: [
          { label: "做法", text: "看视频快速记录复述点" },
          { label: "解决了什么", text: "看完不再觉得什么都没留下" },
        ],
      },
      {
        title: "笔记推送",
        imageSrc: carouselNotePush,
        lines: [
          { label: "做法", text: "以复述点为单位组织你的复习" },
          { label: "解决了什么", text: "学完不再困惑到底该复习什么" },
        ],
      },
      {
        title: "重点压缩",
        imageSrc: carouselFocusCompression,
        lines: [
          { label: "做法", text: "每次只推你最该复习的内容" },
          { label: "解决了什么", text: "高效复习，节省不必要的重复" },
        ],
      },
      {
        title: "分层复习",
        imageSrc: carouselLayeredReview,
        lines: [
          { label: "做法", text: "小节、章都有自己的复习推送节奏" },
          { label: "解决了什么", text: "缓解了大跨度层面的遗忘" },
        ],
      },
    ],
  },
  {
    index: "04",
    tag: "功能",
    title: "用它看视频有什么不同？",
    intro: "不要等到完全理解系统再开始。先用一门最焦虑、最容易遗忘的科目跑通一轮，你就会知道它到底适不适合你。",
    ctaLabel: "立即体验",
    guideDocSlug: "study-review",
    points: [
      {
        title: "微休息神经重放",
        imageSrc: carouselNeuralReplay,
        lines: [
          { label: "介绍", text: "视频播放时，每隔几分钟强制休息10秒，神经重放的同时强化对学习的渴望" },
        ],
      },
      {
        title: "AI问答",
        imageSrc: carouselAiQa,
        lines: [
          { label: "介绍", text: "视频播放时，随时举手提问，AI会结合视频关键帧和字幕回答你的问题，课后也可选择范围继续提问" },
        ],
      },
      {
        title: "快捷记笔记",
        imageSrc: carouselQuickNote,
        lines: [
          { label: "介绍", text: "视频播放时，使用回车等快捷键记录复述点，截取视频内容，双手无需离开键盘" },
        ],
      },
      {
        title: "番茄钟",
        imageSrc: carouselPomodoro,
        lines: [
          { label: "介绍", text: "你只能在一个番茄的时间内学习指定的项目，或许这会让你更加珍惜学习的时光" },
        ],
      },
    ],
  },
] as const

export function HomePage() {
  const { authEnabled, isLoggedIn, registerHref, registerLabel } = useShowcaseEntryPaths()

  usePageMeta({
    title: "LearningPyramid | 把每一次遍历都变得更值",
    description: "LearningPyramid 是一套基于 PLM 的学习系统：先做全量筛选，再对重点递缩压缩，并在时间与范围变化时重新校准。",
    path: "/",
  })

  const membershipEntryHref = isLoggedIn || !authEnabled ? "/profile" : registerHref
  const membershipEntryLabel = isLoggedIn || !authEnabled ? "去个人中心查看" : "登录后在个人中心查看"
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
      <ShowcaseSiteHeader />

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
                      <div className="lp-showcase-carousel-points">
                        {item.points.map((point) => {
                          const pointImageSrc = "imageSrc" in point ? point.imageSrc : undefined

                          return (
                            <div key={point.title} className={`lp-showcase-carousel-point${pointImageSrc ? " lp-showcase-carousel-point-with-image" : ""}`}>
                              <div className="lp-showcase-carousel-point-copy">
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
                              {pointImageSrc ? (
                                <div className="lp-showcase-carousel-point-visual">
                                  <img src={pointImageSrc} alt={`${point.title}示意图`} loading="lazy" />
                                </div>
                              ) : null}
                            </div>
                          )
                        })}
                      </div>
                      {"ctaLabel" in item ? (
                        <div className="lp-showcase-carousel-slide-actions">
                          <button
                            type="button"
                            className="lp-showcase-carousel-slide-action lp-showcase-carousel-slide-action-member"
                            onClick={() => startGuideWalkthrough(item.guideDocSlug)}
                          >
                            {item.ctaLabel}
                          </button>
                        </div>
                      ) : null}
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
                      <p>{item.body}</p>
                    </div>
                    <div className="lp-showcase-method-card-visual">
                      <img src={item.imageSrc} alt={`${item.title}示意图`} loading="lazy" />
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="onboarding" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>上手路径</h2>
              <p>第一次使用先照着这 4 步走：创建学科，绑定并授权目录，导入内容，再回工作台选内容开始学习。</p>
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
              <article className="lp-showcase-pricing-card lp-showcase-pricing-card-primary">
                <div className="lp-showcase-membership-card-top">
                  <div className="lp-showcase-membership-price-block">
                    <h3>月会员</h3>
                    <div className="lp-showcase-price">
                      <strong>¥20</strong>
                      <span>/ 月</span>
                    </div>
                  </div>
                  <div className="lp-showcase-membership-benefits">
                    <h4>会员权益</h4>
                    <ul>
                      <li>番茄钟：学习规划与督促</li>
                      <li>AI交互：你的助理及良师</li>
                    </ul>
                  </div>
                </div>
                <div className="lp-showcase-price-note">邀请码 7.5 折券可让首单实付 ¥15</div>
                <div className="lp-showcase-hero-actions lp-showcase-membership-actions">
                  <Link className="lp-showcase-btn lp-showcase-btn-primary" to={membershipEntryHref}>
                    {membershipEntryLabel}
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
      <ShowcaseFooter />
    </div>
  )
}
