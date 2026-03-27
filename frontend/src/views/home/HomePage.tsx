import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

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

const heroMetaItems = [
  {
    title: "重点压缩",
    body: "让会的内容尽快退出高频循环，把重复留给真正薄弱的部分。",
  },
  {
    title: "分层校准",
    body: "当时间拉长、材料变多时，回到更大范围重新定位重点。",
  },
  {
    title: "可落地流程",
    body: "项目创建、目录导入、复述点录入、复习闭环，一条路径跑通。",
  },
] as const

const flowItems = [
  {
    index: "01",
    title: "创建项目",
    body: "先建立一个学习主题，再进入项目设置。",
  },
  {
    index: "02",
    title: "绑定目录并导入内容",
    body: "系统根据授权目录重建学习对象树，不需要手工建目录树。",
  },
  {
    index: "03",
    title: "在工作台录入复述点",
    body: "暂停视频、添加时间锚点、填写问答、提交学习任务。",
  },
  {
    index: "04",
    title: "完成复习并继续递缩",
    body: "先判断会不会，再由系统继续安排下一轮复习与上推。",
  },
] as const

const methodBullets = [
  {
    lead: "问题：",
    body: "为什么常规复习会让已会内容长期陪跑？",
  },
  {
    lead: "机制：",
    body: "重点压缩 + 分层校准如何把时间集中到薄弱点？",
  },
  {
    lead: "路径：",
    body: "创建项目后如何把本地视频材料真正变成可复习的任务链？",
  },
] as const

const mechanismCards = [
  {
    icon: "A",
    title: "重点压缩",
    body: "先做一次当前层的全量筛选，把“现在讲不出来”的内容收成重点集合；下一轮不再回到全量，而是只复习这个重点集合，并继续递缩，直到这一层封顶。",
  },
  {
    icon: "B",
    title: "分层校准",
    body: "当材料范围扩大、时间间隔拉长，原来的重点会漂移。系统要求你回到更大范围重新筛选，用当前状态重定位重点，避免漏掉已经重新变生疏的内容。",
  },
  {
    icon: "C",
    title: "可执行判定",
    body: "不同材料的“会”标准不同。单词、概念、题型、论证都可以作为学习单元，只要你能给出明确的输出标准，系统就能围绕它组织筛选和复习。",
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
    title: "学习对象树",
    body: "左侧学习对象树来自目录扫描结果。你可以把它理解为“材料结构本身”，用于确认视频是否已识别、目录结构是否符合预期。",
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
  {
    icon: "05",
    title: "学习任务树与时间线",
    body: "学习任务树展示任务与分层上推结构，时间线用于回溯项目运行记录。它们帮助用户确认自己已经走到哪一层，而不是只盯着一批零散卡片。",
  },
  {
    icon: "06",
    title: "材料源模式可扩展",
    body: "规格层已经把 SERVER_FS、BROWSER_LOCAL、NATIVE_LOCAL、MANUAL 四种材料源模式抽象出来，展示页可以先对外强调“本地素材友好”和“可扩展的材料接入面”。",
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

const valueBullets = [
  {
    lead: "对大体量任务友好：",
    body: "专业课、定义系统、题型模板、论证骨架都可以纳入同一方法。",
  },
  {
    lead: "不是单纯背卡工具：",
    body: "系统核心是“学习对象与数据管理 + 重点筛选与编排”。",
  },
  {
    lead: "先跑通，再调参数：",
    body: "首次使用建议先完成一轮录入和复习，再回项目设置调整层配置。",
  },
] as const

const promiseBullets = [
  {
    lead: "材料在你自己目录里：",
    body: "浏览器本地素材模式下，播放器直接读取你当前设备上的本地文件。",
  },
  {
    lead: "对象树自动生成：",
    body: "学习对象树不是手工搭建，而是来自目录导入结果。",
  },
  {
    lead: "故障定位清晰：",
    body: "左侧为空、视频打不开、材料缺失时，都优先回到“项目设置”处理授权、导入和路径问题。",
  },
] as const

const inviteBullets = [
  "每个被邀请人只能绑定 1 个邀请人，只触发 1 次邀请奖励。",
  "邀请成功的定义是：被邀请人完成自己的首个成功会员订单。",
  "邀请成功后，邀请人获得 1 张 5 元券，可用于首单或续费。",
  "会员中心可集中展示会员状态、邀请码、邀请记录、可用券和订单历史。",
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
    title: "为什么不建议一进来就只给登录页？",
    body: "对展示型产品来说，公开首页应该先解释产品价值、方法差异和上手路径。登录页适合承接受保护操作，不适合替代对外介绍页。",
  },
] as const

const graduateReasons = [
  {
    index: "01",
    tag: "重点压缩",
    title: "不会的点会越来越少，不是整本书永远重刷",
    body: "考研最痛苦的不是学不会，而是明明会了还要陪着整轮再过一遍。LearningPyramid 会先筛掉已经会的，把时间集中到当下真正讲不出来的部分。",
    detail: "适合专业课、英语长难句、政治知识点这类“会和不会差别很大”的复习对象。",
  },
  {
    index: "02",
    tag: "长周期复习",
    title: "从现在到冲刺，复习重点会不断重新校准",
    body: "考研不是三天冲刺，而是几个月甚至一年的长线战。系统会在时间拉长、范围扩大时重新回到大层级筛选，避免你只盯旧重点，漏掉新薄弱点。",
    detail: "适合暑期打基础、强化阶段、冲刺阶段这种跨度很长的节奏。",
  },
  {
    index: "03",
    tag: "多科管理",
    title: "英语、政治、数学、专业课可以按项目拆开跑",
    body: "考研不是单科作战，真正难的是多科并行。LearningPyramid 用项目来承接不同科目，不会把所有材料、任务和复习记录混在一起。",
    detail: "每一科都能有自己的目录、任务链和复习节奏，脑子会轻松很多。",
  },
  {
    index: "04",
    tag: "视频友好",
    title: "看网课时能直接记下复述点，而不是课后再回忆",
    body: "如果你主要靠网课推进，最容易出现的情况就是“听的时候懂，关掉视频就散了”。系统支持按时间锚点记录复述点，把关键问题和答案留在视频上下文里。",
    detail: "特别适合数学、专业课和技巧型课程的暂停记录与回放复盘。",
  },
  {
    index: "05",
    tag: "本地资料",
    title: "资料放在你自己的目录里，不用到处搬运和重命名",
    body: "很多考研资料都散落在电脑文件夹、网盘和播放器里。LearningPyramid 可以直接围绕你自己的本地目录来组织材料，减少二次整理的摩擦。",
    detail: "目录结构就是学习结构，后续查找、导入和补资料会顺很多。",
  },
  {
    index: "06",
    tag: "复述判断",
    title: "先回忆，再判断会不会，比只看答案更诚实",
    body: "考研里最大的错觉之一，就是“看懂了就以为自己会了”。这套系统要求你先输出，再判断会不会，能更早发现伪掌握。",
    detail: "对背诵型内容、定义型内容和主观题框架尤其有帮助。",
  },
  {
    index: "07",
    tag: "专业课优势",
    title: "它不只适合单词卡，更适合大块知识和论证骨架",
    body: "很多工具在词汇类任务上还行，但一到专业课名词解释、简答题、论述题框架就不好用了。LearningPyramid 更适合承接成体系的知识对象。",
    detail: "如果你有大量定义、模型、比较题、答题框架，这会比普通背卡工具更合适。",
  },
  {
    index: "08",
    tag: "进度可见",
    title: "你能明确看到自己学到哪、漏在哪、下一步做什么",
    body: "考研焦虑很多时候来自“做了很多，但不知道有没有推进”。项目结构、学习任务树和复习链能把状态显性化，不再靠感觉估进度。",
    detail: "这会显著减少“今天到底该学什么”的决策疲劳。",
  },
  {
    index: "09",
    tag: "冲刺适配",
    title: "到后期时间变少时，系统会更像一个优先级放大器",
    body: "越接近考试，越不可能再全量地刷完所有内容。LearningPyramid 的价值会在后期更明显，因为它天然适合做重点聚焦和时间压缩。",
    detail: "冲刺阶段最重要的不是做得更满，而是把有限时间花在提分点上。",
  },
  {
    index: "10",
    tag: "降低内耗",
    title: "它帮你把复习从“凭意志”变成“按流程走”",
    body: "考研真正消耗人的，往往不是难题本身，而是每天都要重新决定学什么、怎么记、什么时候回顾。系统化流程能把这些重复决策固定下来。",
    detail: "当你的注意力应该留给内容本身时，流程越稳，复习状态越容易持续。",
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

  const loginHref = isLoggedIn || !authEnabled ? "/projects" : "/login"
  const loginLabel = isLoggedIn || !authEnabled ? "进入项目" : "登录"
  const registerHref = isLoggedIn || !authEnabled ? "/projects" : allowSignup ? "/login?mode=register" : "/login"
  const registerLabel = isLoggedIn || !authEnabled ? "进入项目" : allowSignup ? "立即注册" : "去登录"
  const [activeReasonIndex, setActiveReasonIndex] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveReasonIndex((current) => (current + 1) % graduateReasons.length)
    }, 4800)

    return () => window.clearInterval(timer)
  }, [])

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
            <span className="lp-showcase-brand-mark">LP</span>
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
            <Link className="lp-showcase-btn lp-showcase-btn-secondary" to={loginHref}>
              {loginLabel}
            </Link>
            <Link className="lp-showcase-btn lp-showcase-btn-primary" to="/projects">
              开始使用
            </Link>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="lp-showcase-hero">
          <div className="lp-showcase-container lp-showcase-hero-grid">
            <div className="lp-showcase-hero-copy">
              <span className="lp-showcase-badge">PLM · 重点压缩与分层校准</span>
              <h1>
                不是让你反复全量重学，
                <br />
                而是把重复集中到现在真正不会的部分。
              </h1>
              <p className="lp-showcase-lead">
                LearningPyramid 面向大体量学习任务设计。它先帮你从当前材料中筛出薄弱点，再把复习成本持续压缩到重点集合上；当时间拉长、范围扩大时，再回到更大层级重新校准，避免旧重点被盲追、新薄弱点被漏掉。
              </p>
              <div className="lp-showcase-hero-actions">
                <a className="lp-showcase-btn lp-showcase-btn-primary" href="#onboarding">
                  查看首次使用路径
                </a>
                <a className="lp-showcase-btn lp-showcase-btn-secondary" href="#method">
                  先理解方法
                </a>
              </div>
              <div className="lp-showcase-hero-meta">
                {heroMetaItems.map((item) => (
                  <div key={item.title} className="lp-showcase-meta-box">
                    <strong>{item.title}</strong>
                    <span>{item.body}</span>
                  </div>
                ))}
              </div>
            </div>

            <aside className="lp-showcase-hero-panel" aria-label="产品流程概览">
              <div>
                <div className="lp-showcase-mini-title">从材料到复习的最小闭环</div>
                <ul className="lp-showcase-flow-list">
                  {flowItems.map((item) => (
                    <li key={item.index}>
                      <span className="lp-showcase-flow-index">{item.index}</span>
                      <div className="lp-showcase-flow-copy">
                        <strong>{item.title}</strong>
                        <span>{item.body}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="lp-showcase-panel-note">
                <strong>这不是展示一个“工具箱”。</strong>
                <br />
                它更像一条完整的学习操作链：材料接入 → 重点提取 → 复习编排 → 分层收敛。
              </div>
            </aside>
          </div>
        </section>

        <section className="lp-showcase-section lp-showcase-carousel-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-carousel-shell">
              <div className="lp-showcase-carousel-header">
                <span className="lp-showcase-badge">考研场景</span>
                <h2>我是考研大学生，给我10个选择LearningPyramid的理由</h2>
                <p>如果你准备的是一场长线考试，你真正需要的不是更多材料，而是一套能帮你持续筛重点、压重复、稳节奏的复习系统。</p>
              </div>

              <div className="lp-showcase-carousel-viewport">
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
                      <p>{item.body}</p>
                      <div className="lp-showcase-carousel-detail">{item.detail}</div>
                    </article>
                  ))}
                </div>
              </div>

              <div className="lp-showcase-carousel-footer">
                <div className="lp-showcase-carousel-controls">
                  <button type="button" className="lp-showcase-carousel-control" onClick={showPrevReason} aria-label="查看上一条理由">
                    上一条
                  </button>
                  <button type="button" className="lp-showcase-carousel-control" onClick={showNextReason} aria-label="查看下一条理由">
                    下一条
                  </button>
                </div>

                <div className="lp-showcase-carousel-dots" aria-label="轮播分页">
                  {graduateReasons.map((item, index) => (
                    <button
                      key={item.index}
                      type="button"
                      className={index === activeReasonIndex ? "lp-showcase-carousel-dot is-active" : "lp-showcase-carousel-dot"}
                      onClick={() => setActiveReasonIndex(index)}
                      aria-label={`查看第 ${item.index} 条理由`}
                      aria-pressed={index === activeReasonIndex}
                    >
                      <span>{item.index}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="method" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>为什么它适合展示型主页</h2>
              <p>这个首页不把用户一进站就推去登录，而是先回答三个公开问题：系统在解决什么问题、和普通复习工具有什么不同、第一次上手到底该怎么走。</p>
            </div>
            <div className="lp-showcase-quote-panel">
              <div className="lp-showcase-quote-main">
                <blockquote>
                  “你追求的不是更少遍历，而是<span className="lp-showcase-highlight">更值的遍历</span>。”
                </blockquote>
                <p>首页主叙事围绕这一句展开：先说明 PLM 的方法价值，再用工作流把它落到具体界面和操作上，最后再接会员和邀请转化，而不是一开始只放价格和登录框。</p>
              </div>
              <div className="lp-showcase-panel">
                <h3>首页要先讲清的三件事</h3>
                <ul className="lp-showcase-bullet-list">
                  {methodBullets.map((item) => (
                    <li key={item.lead}>
                      <strong>{item.lead}</strong>
                      {item.body}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>PLM 的两个核心机制</h2>
              <p>首页不需要把规格书全部展开，但要把用户真正关心的机制说清楚：为什么这套系统能比“每轮都全量刷”更节省精力，且不会把整体结构刷丢。</p>
            </div>
            <div className="lp-showcase-grid-3">
              {mechanismCards.map((item) => (
                <article key={item.title} className="lp-showcase-feature">
                  <div className="lp-showcase-feature-icon">{item.icon}</div>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>这不是抽象理论，它已经落到明确功能上</h2>
              <p>展示页应该直接把用户将看到的关键界面和能力讲清楚：材料怎么进来、复述点怎么形成、复习怎么推进、出了问题去哪里修。</p>
            </div>
            <div className="lp-showcase-grid-3">
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
              <h2>首次使用路径</h2>
              <p>这是最适合放在首页中部的内容。因为用户最怕的不是“不懂概念”，而是“看完介绍后不知道第一步该点哪里”。</p>
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

        <section className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-grid-2">
              <article className="lp-showcase-panel">
                <h3>适合放在首页上的价值表达</h3>
                <ul className="lp-showcase-bullet-list">
                  {valueBullets.map((item) => (
                    <li key={item.lead}>
                      <strong>{item.lead}</strong>
                      {item.body}
                    </li>
                  ))}
                </ul>
              </article>

              <article className="lp-showcase-panel">
                <h3>适合放在首页上的使用承诺</h3>
                <ul className="lp-showcase-bullet-list">
                  {promiseBullets.map((item) => (
                    <li key={item.lead}>
                      <strong>{item.lead}</strong>
                      {item.body}
                    </li>
                  ))}
                </ul>
              </article>
            </div>
          </div>
        </section>

        <section id="membership" className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-section-head">
              <h2>会员与邀请，不应盖过方法，但应该在首页完成转化</h2>
              <p>会员区块适合放在首页靠后位置：前面先把方法和产品价值讲清楚，这里再承接下单、邀请和价格感知。</p>
            </div>
            <div className="lp-showcase-pricing-grid">
              <article className="lp-showcase-pricing-card">
                <span className="lp-showcase-badge">会员计划</span>
                <h3>面向持续学习者的月会员</h3>
                <div className="lp-showcase-price">
                  <strong>¥19.9</strong>
                  <span>/ 月</span>
                </div>
                <p>新用户首个成功会员订单可按首单价购买，且若账户里已有 5 元券，可与首单优惠叠加。</p>
                <div className="lp-showcase-price-note">首单价 ¥14.9，首单叠券最低可到 ¥9.9</div>
                <div className="lp-showcase-hero-actions lp-showcase-membership-actions">
                  <Link className="lp-showcase-btn lp-showcase-btn-primary" to="/membership">
                    查看会员中心
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
              <p>FAQ 建议直接选取最真实的上手问题，而不是写一堆营销问答。这样首页既能承接首次访问，也能降低支持成本。</p>
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

        <section className="lp-showcase-section">
          <div className="lp-showcase-container">
            <div className="lp-showcase-cta-box">
              <div>
                <h2>先理解产品，再进入系统。</h2>
                <p>这才是展示型主页该做的事。对外先把 PLM 的方法、LearningPyramid 的操作闭环和会员转化说明白；对内再用登录与项目页承接真正的使用流程。</p>
              </div>
              <div className="lp-showcase-hero-actions lp-showcase-cta-actions">
                <Link className="lp-showcase-btn lp-showcase-btn-primary" to="/projects">
                  开始使用
                </Link>
                <Link className="lp-showcase-btn lp-showcase-btn-secondary" to="/membership">
                  查看会员
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-showcase-footer">
        <div className="lp-showcase-container lp-showcase-footer-line">
          <div>© 2026 LearningPyramid · Focus compression for real learning.</div>
          <div>公开首页用于展示方法与产品路径，工作台与项目页用于实际学习操作。</div>
        </div>
      </footer>
    </div>
  )
}
