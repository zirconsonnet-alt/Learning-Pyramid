import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  CreditCard,
  Gift,
  Layers3,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  Ticket,
  UsersRound,
  Workflow,
} from "lucide-react"
import { Link, Navigate } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useCurrentUser } from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"

const capabilityCopy = {
  hosted: {
    mode: "云端协作",
    body: "适合团队协作、持续交付与线上运营，让学习系统和业务履约留在同一套空间里。",
  },
  local: {
    mode: "本地工作区",
    body: "适合个人知识工程、自托管项目和私有素材管理，把学习方法留在自己可控的环境里。",
  },
} as const

const topNavItems = [
  { href: "#features", label: "产品能力" },
  { href: "#product", label: "界面预览" },
  { href: "#membership", label: "会员方案" },
  { href: "#faq", label: "常见问题" },
] as const

const heroSignals = [
  {
    title: "结构化项目",
    value: "对象树 + 任务树",
    description: "把内容组织、学习目标和执行路径放进同一个项目。",
  },
  {
    title: "可回放学习",
    value: "实例 + 复习链",
    description: "让学习过程可复盘，而不是只留下结果。",
  },
  {
    title: "内建转化",
    value: "会员 + 邀请奖励",
    description: "让付费、订单和权益发放自然接在产品内部。",
  },
] as const

const featureCards = [
  {
    title: "项目化组织",
    description: "从对象树、任务树到节点关系，内容结构和学习推进不再分散在多个入口里。",
    icon: Layers3,
  },
  {
    title: "学习过程可沉淀",
    description: "实例回放、复习链和召回点把学习动作变成可追踪、可复盘、可持续优化的过程资产。",
    icon: PlayCircle,
  },
  {
    title: "会员与履约一体化",
    description: "会员、邀请码、优惠券、订单状态和退款处理属于同一套产品能力，而不是外挂模块。",
    icon: Workflow,
  },
] as const

const journeySteps = [
  {
    step: "01",
    title: "组织知识",
    description: "先把素材、层级和学习对象放进可维护的项目结构里。",
  },
  {
    step: "02",
    title: "推进学习",
    description: "围绕任务、回放和复习链持续执行，而不是每次重新搭流程。",
  },
  {
    step: "03",
    title: "完成转化",
    description: "用会员、邀请奖励和订单履约承接持续增长，而不是另起一套系统。",
  },
] as const

const surfaceCards = [
  {
    label: "项目空间",
    title: "让项目首页直接承接下一步动作",
    description: "一眼看到项目状态、最近学习节奏与下一步入口，不需要先翻菜单再决定做什么。",
    previewSrc: "/home-preview-projects.svg",
    href: "/projects",
    actionLabel: "进入项目空间",
    highlights: ["项目状态清晰", "最近学习一眼可见", "可直接进入工作台"],
  },
  {
    label: "会员中心",
    title: "把购买、邀请和优惠券放在同一页里",
    description: "用户可以清楚看到会员权益、首单价格、可用优惠券与订单状态，不用在多个页面之间来回跳转。",
    previewSrc: "/home-preview-membership.svg",
    href: "/membership",
    actionLabel: "查看会员方案",
    highlights: ["首单 14.9 元", "邀请成功返 5 元券", "订单状态可追踪"],
  },
  {
    label: "运营与履约",
    title: "把支付同步、异常关单和退款处理留在产品内部",
    description: "从支付成功到后续售后，运营动作和用户体验讲的是同一个产品故事。",
    previewSrc: "/home-preview-admin.svg",
    href: "/login",
    actionLabel: "进入工作区",
    highlights: ["订单细节可核对", "异常订单可收口", "退款链路可回滚"],
  },
] as const

const audienceCards = [
  {
    title: "知识产品团队",
    description: "适合需要同时管理内容结构、学习执行和会员增长的教育或训练型产品。",
    icon: UsersRound,
  },
  {
    title: "重度自学者",
    description: "适合想把素材、任务、回放与复盘整理成长期系统，而不只是做笔记的人。",
    icon: BrainCircuit,
  },
  {
    title: "自托管项目",
    description: "适合对数据控制、部署方式和支付履约都有要求的产品负责人。",
    icon: ShieldCheck,
  },
] as const

const faqItems = [
  {
    question: "LearningPyramid 更适合哪类产品？",
    answer: "适合长期知识产品、训练营、自学系统和需要自托管能力的教育型项目。",
  },
  {
    question: "支持什么样的工作方式？",
    answer: "既支持云端协作，也保留本地工作区能力，能根据部署模式承接团队或个人的不同习惯。",
  },
  {
    question: "会员体系现在能承接什么？",
    answer: "标准月会员 19.9 元，新用户首单 14.9 元，邀请成功返 5 元券，并支持订单同步、异常关单和退款回滚。",
  },
] as const

export function HomePage() {
  const capabilitiesQ = useSystemCapabilities()
  const authKnown = capabilitiesQ.data !== undefined
  const authEnabled = capabilitiesQ.data?.authEnabled ?? true
  const allowSignup = capabilitiesQ.data?.allowSignup ?? false
  const currentUserQ = useCurrentUser(authKnown && authEnabled)
  const appMode = capabilitiesQ.data?.appMode ?? "hosted"
  const narrative = capabilityCopy[appMode]

  usePageMeta({
    title: "LearningPyramid | 把内容组织、学习推进与会员转化放进同一个工作空间",
    description: "LearningPyramid 把知识工程、学习回放和会员体系收进同一个真正可运行的产品空间。",
    path: "/",
  })

  if (currentUserQ.data) {
    return <Navigate to="/projects" replace />
  }

  const primaryHref = authEnabled ? (allowSignup ? "/login?mode=register" : "/login") : "/projects"
  const primaryLabel = authEnabled ? (allowSignup ? "立即开始" : "进入工作区") : "直接进入项目空间"
  const headerActionHref = authEnabled ? "/login" : "/projects"
  const headerActionLabel = authEnabled ? "登录" : "进入"
  const capabilityPills = [
    narrative.mode,
    authEnabled ? (allowSignup ? "开放注册" : "账号登录") : "免登录体验",
    capabilitiesQ.data?.browserLocalMediaEnabled ? "浏览器直连素材" : "统一在线工作区",
  ]

  return (
    <div className="landing-home-bg relative min-h-dvh overflow-hidden text-slate-900">
      <div className="landing-grid pointer-events-none absolute inset-0 opacity-55" />
      <div className="landing-orb landing-orb-a" />
      <div className="landing-orb landing-orb-b" />
      <div className="landing-orb landing-orb-c" />

      <div className="relative mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-6 pb-16 pt-6 lg:px-10">
        <header className="landing-reveal flex items-center justify-between gap-4 rounded-full border border-white/70 bg-white/68 px-4 py-3 shadow-[0_18px_48px_-32px_rgba(23,52,88,0.28)] backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#16385a,#305f93)] text-white shadow-[0_18px_32px_-20px_rgba(22,56,90,0.48)]">
              <BrainCircuit className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.24em] text-slate-500">LearningPyramid</p>
              <p className="text-sm font-medium text-slate-700">知识工程、学习回放与会员体系</p>
            </div>
          </div>

          <nav className="hidden items-center gap-1 rounded-full border border-white/60 bg-white/55 px-2 py-2 backdrop-blur lg:flex">
            {topNavItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="rounded-full px-3 py-2 text-sm font-medium text-[#5e748e] transition hover:bg-white/88 hover:text-[#17385d]"
              >
                {item.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" className="hidden sm:inline-flex">
              <a href="#product">产品概览</a>
            </Button>
            <Button asChild variant="outline">
              <Link to={headerActionHref}>{headerActionLabel}</Link>
            </Button>
          </div>
        </header>

        <main className="flex flex-1 flex-col">
          <section className="grid gap-10 pb-16 pt-10 lg:grid-cols-[minmax(0,1.02fr)_minmax(360px,0.98fr)] lg:items-center lg:gap-12 lg:pt-18">
            <div className="space-y-8">
              <div className="landing-reveal landing-reveal-delay-1 flex flex-wrap gap-3">
                {capabilityPills.map((item) => (
                  <span key={item} className="rounded-full border border-[#d8e2ee] bg-white/76 px-3 py-1.5 text-xs font-semibold text-[#51677f] backdrop-blur">
                    {item}
                  </span>
                ))}
              </div>

              <div className="space-y-5">
                <p className="landing-reveal landing-reveal-delay-2 text-sm font-semibold uppercase tracking-[0.28em] text-[#6b7d95]">
                  Knowledge system with real momentum
                </p>
                <div className="space-y-4">
                  <h1
                    className="landing-reveal landing-reveal-delay-3 max-w-4xl text-5xl leading-[0.95] tracking-[-0.05em] text-[#13293f] sm:text-6xl lg:text-[5.2rem]"
                    style={{ fontFamily: "\"Iowan Old Style\", \"Palatino Linotype\", Georgia, serif" }}
                  >
                    把内容组织、学习推进与会员转化放进同一个工作空间。
                  </h1>
                  <p className="landing-reveal landing-reveal-delay-4 max-w-2xl text-lg leading-8 text-[#556a82]">
                    LearningPyramid 面向长期知识产品和高密度学习项目，让项目结构、学习回放与会员体系自然衔接。
                    {narrative.body}
                  </p>
                </div>
              </div>

              <div className="landing-reveal landing-reveal-delay-5 flex flex-col gap-4 sm:flex-row">
                <Button asChild size="lg" className="h-12 px-7 text-base">
                  <Link to={primaryHref}>
                    {primaryLabel}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline" className="h-12 px-7 text-base">
                  <a href="#product">查看产品界面</a>
                </Button>
              </div>

              <div className="landing-reveal landing-reveal-delay-6 flex flex-wrap items-center gap-4 text-sm text-[#5d728a]">
                <div className="inline-flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-[#2c6ab0]" />
                  项目、学习与会员从同一入口进入
                </div>
                <div className="inline-flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-[#2c6ab0]" />
                  既能承接个人学习，也能承接真实产品运营
                </div>
              </div>
            </div>

            <div className="landing-reveal landing-reveal-delay-4 relative">
              <div className="landing-hero-board">
                <div className="flex items-start justify-between gap-4 border-b border-slate-200/85 pb-5">
                  <div className="space-y-2">
                    <span className="inline-flex items-center gap-2 rounded-full bg-[#edf4ff] px-3 py-1 text-xs font-semibold text-[#245791]">
                      <Sparkles className="h-3.5 w-3.5" />
                      一套系统，三层能力
                    </span>
                    <h2 className="text-2xl font-semibold tracking-tight text-[#13293f]">更像完整产品，而不是拼起来的页面集合</h2>
                    <p className="max-w-md text-sm leading-7 text-[#5c7088]">
                      从知识结构到学习执行，再到会员方案和订单履约，用户看到的是一个连续、可信的产品体验。
                    </p>
                  </div>

                  <div className="landing-float-card hidden min-w-[150px] rounded-[1.5rem] border border-[#d7e4f3] bg-white/88 p-4 shadow-[0_26px_62px_-38px_rgba(22,58,95,0.42)] md:block">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#6f84a0]">Membership</p>
                    <p className="mt-3 text-3xl font-semibold tracking-tight text-[#15304c]">14.9</p>
                    <p className="mt-2 text-sm leading-6 text-[#64788f]">新用户首单价，邀请成功后可继续获得 5 元券。</p>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  {heroSignals.map((item) => (
                    <div key={item.title} className="landing-stat-card">
                      <span className="landing-stat-label">{item.title}</span>
                      <strong className="block text-lg font-semibold tracking-tight text-[#18324d]">{item.value}</strong>
                      <p className="mt-2 text-sm leading-6 text-[#64788f]">{item.description}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-5 grid gap-4">
                  {featureCards.map((item) => {
                    const Icon = item.icon
                    return (
                      <div
                        key={item.title}
                        className="rounded-[1.45rem] border border-[#d9e5f2] bg-white/82 px-4 py-4 shadow-[0_20px_48px_-34px_rgba(21,47,82,0.24)]"
                      >
                        <div className="flex items-start gap-4">
                          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#eef5ff,#dcebff)] text-[#205890]">
                            <Icon className="h-5 w-5" />
                          </div>
                          <div>
                            <h3 className="text-base font-semibold text-[#18344f]">{item.title}</h3>
                            <p className="mt-1.5 text-sm leading-7 text-[#657991]">{item.description}</p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </section>

          <section id="features" className="py-10">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-end">
              <div className="landing-reveal space-y-3">
                <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#72839a]">How it works</p>
                <h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-[#142b45] sm:text-4xl">
                  它不只是在展示功能，而是在定义一条清晰的产品节奏。
                </h2>
                <p className="max-w-2xl text-base leading-8 text-[#60748c]">
                  首页要做的不是“把所有功能都说一遍”，而是先让人理解这套系统如何从知识组织走到学习执行，再走到会员与履约。
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                {journeySteps.map((item) => (
                  <Card key={item.step} className="landing-reveal border-white/75 bg-white/86 backdrop-blur-sm">
                    <CardHeader className="space-y-3">
                      <span className="text-sm font-semibold uppercase tracking-[0.22em] text-[#8194ab]">{item.step}</span>
                      <CardTitle className="text-xl text-[#17324e]">{item.title}</CardTitle>
                      <CardDescription className="text-sm leading-7 text-[#61758d]">{item.description}</CardDescription>
                    </CardHeader>
                  </Card>
                ))}
              </div>
            </div>
          </section>

          <section id="product" className="space-y-7 py-10">
            <div className="landing-reveal space-y-3">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#72839a]">Product surfaces</p>
              <h2 className="max-w-4xl text-3xl font-semibold tracking-tight text-[#142b45] sm:text-4xl">
                让用户在进入之前，就看到产品将如何陪他持续工作。
              </h2>
              <p className="max-w-3xl text-base leading-8 text-[#61748c]">
                下面这些界面不是装饰性占位图，而是代表这套产品真正提供的核心体验：项目空间、会员中心和订单履约能力。
              </p>
            </div>

            <div className="grid gap-5 xl:grid-cols-3">
              {surfaceCards.map((item, index) => (
                <div
                  key={item.title}
                  className={`landing-reveal rounded-[1.9rem] border border-white/72 bg-white/76 p-4 shadow-[0_28px_72px_-42px_rgba(22,58,95,0.3)] backdrop-blur-sm ${index === 1 ? "xl:-translate-y-4" : ""}`}
                >
                  <div className="rounded-[1.55rem] border border-[#dce7f3] bg-[linear-gradient(180deg,rgba(249,252,255,0.98),rgba(238,245,252,0.92))] p-4">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <span className="rounded-full border border-white/85 bg-white/82 px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.2em] text-[#6b829e]">
                        {item.label}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-[#f0a56d]" />
                        <span className="h-2.5 w-2.5 rounded-full bg-[#e8c464]" />
                        <span className="h-2.5 w-2.5 rounded-full bg-[#94c98d]" />
                      </div>
                    </div>

                    <div className="space-y-4 rounded-[1.35rem] border border-white/88 bg-white/88 p-4 shadow-[0_18px_44px_-34px_rgba(24,59,96,0.24)]">
                      <div className="landing-preview-frame overflow-hidden rounded-[1.1rem] border border-[#dde8f2] bg-[#edf4fa]">
                        <img src={item.previewSrc} alt={item.title} className="h-auto w-full" loading="lazy" />
                      </div>
                      <div className="space-y-2">
                        <h3 className="text-xl font-semibold text-[#18344f]">{item.title}</h3>
                        <p className="text-sm leading-7 text-[#60738b]">{item.description}</p>
                      </div>
                      <div className="space-y-2.5">
                        {item.highlights.map((line) => (
                          <div key={line} className="flex items-start gap-3 rounded-2xl border border-[#e2ecf6] bg-[#f9fbff] px-3 py-2.5">
                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#2d6eb0]" />
                            <span className="text-sm leading-6 text-[#667c93]">{line}</span>
                          </div>
                        ))}
                      </div>
                      <Button asChild variant="ghost" className="justify-start px-0 text-[#204f82] hover:bg-transparent hover:text-[#173c68]">
                        <Link to={item.href}>
                          {item.actionLabel}
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section id="membership" className="py-10">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:items-start">
              <div className="landing-reveal overflow-hidden rounded-[2rem] border border-[#d8e4f0] bg-[linear-gradient(135deg,rgba(16,44,76,0.96),rgba(32,84,138,0.92))] p-6 text-white shadow-[0_34px_82px_-44px_rgba(17,40,71,0.62)] lg:p-8">
                <div className="space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-white/18 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/76">
                    <CreditCard className="h-3.5 w-3.5" />
                    Membership plan
                  </div>
                  <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">会员方案应该增强产品价值，而不是打断体验。</h2>
                  <p className="max-w-xl text-base leading-8 text-white/76">
                    用户看到的是清晰的价格、优惠和权益，团队看到的是顺畅的订单履约和售后处理。首页只需要把这件事讲清楚。
                  </p>
                </div>

                <div className="landing-growth-board mt-6">
                  <div className="landing-price-row">
                    <span>标准月会员</span>
                    <strong>19.9 元</strong>
                  </div>
                  <div className="landing-price-row">
                    <span>新用户首单</span>
                    <strong>14.9 元</strong>
                  </div>
                  <div className="landing-price-row">
                    <span>邀请成功奖励</span>
                    <strong>5 元券</strong>
                  </div>
                </div>

                <div className="mt-6 space-y-3">
                  {[
                    "优惠券既可用于首单，也可用于续费",
                    "支付状态可以同步，异常订单可以关闭",
                    "退款、订单回滚与邀请奖励撤销属于同一条履约链路",
                  ].map((line) => (
                    <div key={line} className="flex items-start gap-3 rounded-2xl border border-white/12 bg-white/7 px-4 py-3">
                      <Ticket className="mt-0.5 h-4 w-4 shrink-0 text-white/78" />
                      <span className="text-sm leading-7 text-white/74">{line}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-6">
                <div className="landing-reveal space-y-3">
                  <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#72839a]">Who it is for</p>
                  <h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-[#142b45] sm:text-4xl">
                    无论你是做产品，还是认真学习，这套系统都在服务长期积累。
                  </h2>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  {audienceCards.map((item, index) => {
                    const Icon = item.icon
                    return (
                      <div
                        key={item.title}
                        className={`landing-reveal rounded-[1.6rem] border border-white/74 bg-white/86 p-5 shadow-[0_22px_58px_-40px_rgba(23,58,94,0.28)] ${index === 1 ? "md:-translate-y-3" : ""}`}
                      >
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#edf5ff,#dcecff)] text-[#205790]">
                          <Icon className="h-5 w-5" />
                        </div>
                        <h3 className="mt-4 text-xl font-semibold text-[#17324d]">{item.title}</h3>
                        <p className="mt-3 text-sm leading-7 text-[#62768e]">{item.description}</p>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </section>

          <section id="faq" className="space-y-6 py-10">
            <div className="landing-reveal space-y-3">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#72839a]">FAQ</p>
              <h2 className="max-w-4xl text-3xl font-semibold tracking-tight text-[#142b45] sm:text-4xl">
                在决定开始之前，先把最关键的问题讲清楚。
              </h2>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              {faqItems.map((item, index) => (
                <div
                  key={item.question}
                  className={`landing-reveal rounded-[1.6rem] border border-white/76 bg-white/86 p-5 shadow-[0_20px_54px_-40px_rgba(23,58,94,0.26)] ${index === 1 ? "lg:-translate-y-3" : ""}`}
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf5ff] text-[#245a96]">
                    {index === 0 ? <UsersRound className="h-4 w-4" /> : index === 1 ? <Workflow className="h-4 w-4" /> : <Gift className="h-4 w-4" />}
                  </div>
                  <h3 className="mt-4 text-lg font-semibold leading-7 text-[#18344f]">{item.question}</h3>
                  <p className="mt-2 text-sm leading-7 text-[#64788f]">{item.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="py-10">
            <div className="landing-reveal rounded-[2rem] border border-[#d7e4f0] bg-[linear-gradient(180deg,rgba(255,255,255,0.86),rgba(240,246,253,0.9))] p-8 shadow-[0_30px_80px_-46px_rgba(21,47,82,0.34)] lg:p-10">
              <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-3">
                    <span className="rounded-full border border-[#dbe6f1] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#6f839d]">
                      Ready for real work
                    </span>
                    <span className="rounded-full border border-[#dbe6f1] bg-white px-3 py-1 text-xs font-medium text-[#5f758d]">
                      项目、学习、会员与履约从同一入口进入
                    </span>
                  </div>
                  <h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-[#142b45] sm:text-4xl">
                    当首页足够像成品，用户就更愿意把真正的工作和学习放进来。
                  </h2>
                  <p className="max-w-2xl text-base leading-8 text-[#61758d]">
                    如果已经准备开始，就直接进入工作空间；如果还在了解，这个首页也应该先把产品价值讲明白，而不是用内部讨论口吻把人挡在门外。
                  </p>
                </div>

                <div className="flex flex-col gap-3">
                  <Button asChild size="lg" className="h-12 min-w-[220px]">
                    <Link to={primaryHref}>
                      {primaryLabel}
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                  <Button asChild size="lg" variant="outline" className="h-12 min-w-[220px]">
                    <a href="#product">先看产品界面</a>
                  </Button>
                </div>
              </div>
            </div>
          </section>

          <footer className="landing-reveal border-t border-white/60 py-10">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_repeat(2,minmax(0,0.8fr))]">
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#16385a,#305f93)] text-white shadow-[0_18px_32px_-20px_rgba(16,58,102,0.55)]">
                    <BrainCircuit className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[#6e8199]">LearningPyramid</p>
                    <p className="text-sm text-[#64788f]">让知识结构、学习执行与会员体系自然协作。</p>
                  </div>
                </div>
                <p className="max-w-xl text-sm leading-7 text-[#62778f]">
                  用项目承接内容，用回放推动学习，用会员与履约支撑长期增长。
                </p>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#17344f]">站点导航</p>
                <div className="footer-link-stack">
                  {topNavItems.map((item) => (
                    <a key={item.href} href={item.href}>
                      {item.label}
                    </a>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#17344f]">开始使用</p>
                <div className="footer-link-stack">
                  <Link to={primaryHref}>{primaryLabel}</Link>
                  <Link to="/login">登录</Link>
                  <Link to="/guide">产品指南</Link>
                  <Link to="/membership">会员中心</Link>
                </div>
              </div>
            </div>
          </footer>
        </main>
      </div>
    </div>
  )
}
