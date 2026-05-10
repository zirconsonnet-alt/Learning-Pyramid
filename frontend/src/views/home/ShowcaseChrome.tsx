/* eslint-disable react-refresh/only-export-components */
import { useEffect, useMemo, useRef, useState } from "react"
import { ChevronDown } from "lucide-react"
import { Link, useLocation } from "react-router-dom"

import { useCurrentUser } from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { cn } from "@/ui/utils"

type ShowcaseNavItem = {
  href: string
  label: string
}

const SHOWCASE_SCROLL_SPY_OFFSET = 156
const BRAND_LOGO_SRC = "/product-logo-192.png"

function buildHomeSectionHref(sectionId: string, homeSectionPrefix: string) {
  return `${homeSectionPrefix}#${sectionId}`
}

function getSectionIdFromHref(href: string) {
  const hashIndex = href.indexOf("#")
  if (hashIndex < 0) return ""
  return href.slice(hashIndex + 1)
}

export function getShowcaseNavItems(homeSectionPrefix = ""): ShowcaseNavItem[] {
  return [
    { href: buildHomeSectionHref("method", homeSectionPrefix), label: "方法" },
    { href: buildHomeSectionHref("onboarding", homeSectionPrefix), label: "改变，从现在开始" },
    { href: buildHomeSectionHref("membership", homeSectionPrefix), label: "会员" },
    { href: buildHomeSectionHref("faq", homeSectionPrefix), label: "常见问题" },
  ]
}

function getShowcasePrimaryNavItems(): ShowcaseNavItem[] {
  return [
    { href: "/subtitle-tool", label: "字幕工具" },
  ]
}

export function useShowcaseEntryPaths() {
  const capabilitiesQ = useSystemCapabilities()
  const authKnown = capabilitiesQ.data !== undefined
  const authEnabled = capabilitiesQ.data?.authEnabled ?? true
  const allowSignup = capabilitiesQ.data?.allowSignup ?? false
  const currentUserQ = useCurrentUser(authKnown && authEnabled)
  const isLoggedIn = Boolean(currentUserQ.data)

  const navActionHref = isLoggedIn || !authEnabled ? "/subjects" : allowSignup ? "/login?mode=register" : "/login"
  const navActionLabel = isLoggedIn || !authEnabled ? "进入项目" : allowSignup ? "登录/注册" : "登录"
  const registerHref = isLoggedIn || !authEnabled ? "/subjects" : allowSignup ? "/login?mode=register" : "/login"
  const registerLabel = isLoggedIn || !authEnabled ? "进入项目" : allowSignup ? "立即注册" : "去登录"

  return {
    allowSignup,
    authEnabled,
    isLoggedIn,
    navActionHref,
    navActionLabel,
    registerHref,
    registerLabel,
  }
}

function ShowcaseNavLink(props: ShowcaseNavItem & { isActive: boolean; className?: string; onNavigate?: () => void }) {
  const { href, label, isActive, className, onNavigate } = props
  const linkClassName = cn(className ?? "lp-showcase-nav-link", isActive && "is-active")

  if (href.startsWith("/#")) {
    return (
      <Link to={href} className={linkClassName} aria-current={isActive ? "location" : undefined} onClick={onNavigate}>
        {label}
      </Link>
    )
  }

  if (href.startsWith("#")) {
    return (
      <a href={href} className={linkClassName} aria-current={isActive ? "location" : undefined} onClick={onNavigate}>
        {label}
      </a>
    )
  }

  return (
    <Link to={href} className={linkClassName} aria-current={isActive ? "page" : undefined} onClick={onNavigate}>
      {label}
    </Link>
  )
}

export function ShowcaseSiteHeader(props: { homeSectionPrefix?: string }) {
  const { homeSectionPrefix = "" } = props
  const location = useLocation()
  const { navActionHref, navActionLabel } = useShowcaseEntryPaths()
  const navItems = useMemo(() => getShowcaseNavItems(homeSectionPrefix), [homeSectionPrefix])
  const primaryNavItems = useMemo(() => getShowcasePrimaryNavItems(), [])
  const homeSectionIds = useMemo(
    () => navItems.map((item) => getSectionIdFromHref(item.href)).filter(Boolean),
    [navItems],
  )
  const [activeHomeSectionId, setActiveHomeSectionId] = useState("")
  const activeHomeSectionLabel = useMemo(
    () => navItems.find((item) => getSectionIdFromHref(item.href) === activeHomeSectionId)?.label ?? "",
    [activeHomeSectionId, navItems],
  )
  const [sectionMenuState, setSectionMenuState] = useState<{ open: boolean; routeKey: string }>({
    open: false,
    routeKey: `${location.pathname}${location.hash}`,
  })
  const currentRouteKey = `${location.pathname}${location.hash}`
  const sectionMenuOpen = sectionMenuState.open && sectionMenuState.routeKey === currentRouteKey
  const sectionMenuRef = useRef<HTMLDivElement | null>(null)
  const homeSectionMenuLabel =
    location.pathname === "/" ? (activeHomeSectionLabel ? `导览 · ${activeHomeSectionLabel}` : "导览") : "首页导览"

  function openSectionMenu() {
    setSectionMenuState({ open: true, routeKey: currentRouteKey })
  }

  function closeSectionMenu() {
    setSectionMenuState((current) => ({ ...current, open: false }))
  }

  useEffect(() => {
    const resolveActiveSection = () => {
      if (location.pathname !== "/") {
        setActiveHomeSectionId("")
        return
      }

      const sectionElements = homeSectionIds
        .map((sectionId) => document.getElementById(sectionId))
        .filter((element): element is HTMLElement => Boolean(element))

      if (sectionElements.length === 0) return

      const viewportAnchorY = window.scrollY + SHOWCASE_SCROLL_SPY_OFFSET
      let nextActiveSectionId = ""

      for (const sectionElement of sectionElements) {
        if (sectionElement.offsetTop <= viewportAnchorY) {
          nextActiveSectionId = sectionElement.id
        } else {
          break
        }
      }

      setActiveHomeSectionId((current) => (current === nextActiveSectionId ? current : nextActiveSectionId))
    }

    let frameId = window.requestAnimationFrame(resolveActiveSection)
    const onScroll = () => {
      window.cancelAnimationFrame(frameId)
      frameId = window.requestAnimationFrame(resolveActiveSection)
    }

    window.addEventListener("scroll", onScroll, { passive: true })
    window.addEventListener("resize", onScroll)
    return () => {
      window.cancelAnimationFrame(frameId)
      window.removeEventListener("scroll", onScroll)
      window.removeEventListener("resize", onScroll)
    }
  }, [homeSectionIds, location.hash, location.pathname])

  useEffect(() => {
    if (!sectionMenuOpen) return

    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (sectionMenuRef.current?.contains(target)) return
      setSectionMenuState((current) => ({ ...current, open: false }))
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSectionMenuState((current) => ({ ...current, open: false }))
    }

    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("touchstart", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("touchstart", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [sectionMenuOpen])

  return (
    <header className="lp-showcase-site-header theme-shell-header">
      <div className="lp-showcase-container lp-showcase-nav">
        <Link className="lp-showcase-brand" to="/">
          <img
            className="lp-showcase-brand-mark"
            src={BRAND_LOGO_SRC}
            alt="LearningPyramid logo"
            width="48"
            height="48"
            fetchPriority="high"
            decoding="async"
          />
          <span>LearningPyramid</span>
        </Link>

        <nav className="lp-showcase-nav-links" aria-label="主导航">
          <div
            ref={sectionMenuRef}
            className="lp-showcase-nav-dropdown"
            onMouseEnter={openSectionMenu}
            onMouseLeave={closeSectionMenu}
            onFocusCapture={openSectionMenu}
            onBlurCapture={(event) => {
              const currentTarget = event.currentTarget
              window.requestAnimationFrame(() => {
                if (!currentTarget.contains(document.activeElement)) closeSectionMenu()
              })
            }}
          >
            <button
              type="button"
              className={cn("lp-showcase-nav-link lp-showcase-nav-dropdown-trigger", location.pathname === "/" && "is-active")}
              aria-haspopup="menu"
              aria-expanded={sectionMenuOpen}
              onClick={() => setSectionMenuState({ open: !sectionMenuOpen, routeKey: currentRouteKey })}
            >
              <span>{homeSectionMenuLabel}</span>
              <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", sectionMenuOpen && "rotate-180")} />
            </button>

            {sectionMenuOpen ? (
              <div className="lp-showcase-nav-dropdown-menu" aria-label={homeSectionMenuLabel}>
                <div className="lp-showcase-nav-dropdown-menu-panel">
                  {navItems.map((item) => {
                    const sectionId = getSectionIdFromHref(item.href)
                    const isActive = location.pathname === "/" && sectionId === activeHomeSectionId
                    return (
                      <ShowcaseNavLink
                        key={`menu-${item.label}-${item.href}`}
                        {...item}
                        isActive={isActive}
                        className="lp-showcase-nav-dropdown-item"
                        onNavigate={closeSectionMenu}
                      />
                    )
                  })}
                </div>
              </div>
            ) : null}
          </div>

          {primaryNavItems.map((item) => {
            const sectionId = getSectionIdFromHref(item.href)
            const isPageLink = item.href.startsWith("/") && !item.href.includes("#")
            const isActive = isPageLink
              ? location.pathname === item.href || location.pathname.startsWith(`${item.href}/`)
              : location.pathname === "/" && sectionId === activeHomeSectionId

            return <ShowcaseNavLink key={`${item.label}-${item.href}`} {...item} isActive={isActive} />
          })}
        </nav>

        <div className="lp-showcase-nav-actions">
          <Link className="lp-showcase-btn lp-showcase-btn-primary" to={navActionHref}>
            {navActionLabel}
          </Link>
        </div>
      </div>
    </header>
  )
}

export function ShowcaseFooter() {
  return (
    <footer className="lp-showcase-footer">
      <div className="lp-showcase-container lp-showcase-footer-line">
        <div>© 2026 LearningPyramid · Focus compression for real learning.</div>
        <div>把时间留给真正不会的部分。</div>
      </div>
    </footer>
  )
}
