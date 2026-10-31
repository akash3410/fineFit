import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'

/* ────────────────────────────────────────────────────────────────────────────
 * Navbar — Gucci-inspired luxury navigation
 *
 * On the homepage ("/"), the navbar overlays the hero with a transparent
 * background and white text/icons. On all other routes it renders with a
 * solid white background and dark text.
 *
 * Right-side slide-out menu panel with blurred backdrop mirrors the
 * reference design.
 * ──────────────────────────────────────────────────────────────────────── */

/* Menu items adapted for FineFit's fashion categories */
const MENU_ITEMS = [
  { label: 'New Arrivals', to: '/shop' },
  { label: 'Women', to: '/shop?category=women' },
  { label: 'Men', to: '/shop?category=men' },
  { label: 'Accessories', to: '/shop?category=accessories' },
  { label: 'Collections', to: '/shop' },
  { label: 'Sale', to: '/shop' },
] as const

export function Navbar() {
  const location = useLocation()
  const isHome = location.pathname === '/'

  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isScrolled, setIsScrolled] = useState(false)
  const [menuAnimating, setMenuAnimating] = useState(false)

  const menuPanelRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  /* Track scroll position for navbar background on homepage */
  useEffect(() => {
    if (!isHome) return

    const handleScroll = () => {
      setIsScrolled(window.scrollY > 60)
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [isHome])

  /* Lock body scroll when menu is open */
  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isMenuOpen])

  /* Focus trap inside menu panel */
  useEffect(() => {
    if (isMenuOpen && closeButtonRef.current) {
      closeButtonRef.current.focus()
    }
  }, [isMenuOpen])

  const openMenu = useCallback(() => {
    setMenuAnimating(true)
    setIsMenuOpen(true)
    /* Allow DOM to render before applying active class */
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setMenuAnimating(false)
      })
    })
  }, [])

  const closeMenu = useCallback(() => {
    setMenuAnimating(true)
    /* Wait for exit animation to finish */
    setTimeout(() => {
      setIsMenuOpen(false)
      setMenuAnimating(false)
    }, 350)
  }, [])

  /* Keyboard: Escape closes menu */
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMenuOpen) {
        closeMenu()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isMenuOpen, closeMenu])

  /* Determine styling mode */
  const isTransparent = isHome && !isScrolled && !isMenuOpen
  const navBg = isTransparent
    ? 'bg-transparent'
    : 'bg-white/95 backdrop-blur-sm border-b border-stone-200'
  const textColor = isTransparent ? 'text-white' : 'text-stone-900'
  const iconColor = isTransparent ? 'text-white' : 'text-stone-900'
  const hoverColor = isTransparent
    ? 'hover:text-white/70'
    : 'hover:text-stone-600'

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${navBg}`}
      >
        <nav className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-5 lg:px-10">
          {/* ── Left: Contact link (desktop) / Hamburger (mobile) ── */}
          <div className="flex items-center gap-3 w-[200px]">
            {/* Mobile hamburger */}
            <button
              className={`lg:hidden ${iconColor} ${hoverColor} transition-colors`}
              onClick={openMenu}
              aria-label="Open navigation menu"
            >
              <svg
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
            {/* Desktop contact link */}
            <Link
              to="/shop"
              className={`hidden lg:inline-flex items-center gap-1.5 text-xs tracking-widest uppercase ${textColor} ${hoverColor} transition-colors`}
            >
              <span className="text-[10px]">+</span>
              <span>Contact Us</span>
            </Link>
          </div>

          {/* ── Center: Brand logo ── */}
          <Link to="/" className="flex-shrink-0">
            <h1
              className={`font-serif text-3xl sm:text-4xl lg:text-[2.5rem] font-semibold tracking-[0.08em] uppercase ${textColor} transition-colors duration-300`}
            >
              FineFit
            </h1>
          </Link>

          {/* ── Right: Search + Menu ── */}
          <div className="flex items-center gap-5 w-[200px] justify-end">
            {/* Search icon (UI-only, no functionality implemented) */}
            <button
              className={`${iconColor} ${hoverColor} transition-colors`}
              aria-label="Search (coming soon)"
              tabIndex={0}
            >
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                />
              </svg>
            </button>

            {/* Menu button */}
            <button
              className={`hidden lg:inline-flex items-center gap-2 ${iconColor} ${hoverColor} transition-colors`}
              onClick={openMenu}
              aria-label="Open navigation menu"
              aria-expanded={isMenuOpen}
            >
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
                />
              </svg>
              <span className="text-xs tracking-widest uppercase font-medium">
                Menu
              </span>
            </button>
          </div>
        </nav>
      </header>

      {/* ── Slide-out Menu Panel ── */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true">
          {/* Backdrop with blur */}
          <div
            className={`absolute inset-0 bg-black/30 backdrop-blur-sm ${
              menuAnimating && !isMenuOpen
                ? 'backdrop-exit'
                : menuAnimating
                  ? 'backdrop-enter'
                  : 'backdrop-active'
            }`}
            onClick={closeMenu}
            aria-hidden="true"
          />

          {/* Panel */}
          <div
            ref={menuPanelRef}
            className={`absolute top-0 right-0 h-full w-full sm:w-[480px] lg:w-[520px] bg-white shadow-2xl ${
              menuAnimating && isMenuOpen
                ? 'menu-panel-enter'
                : menuAnimating && !isMenuOpen
                  ? 'menu-panel-exit'
                  : 'menu-panel-active'
            }`}
          >
            {/* Close button */}
            <div className="flex justify-end p-6 lg:p-8">
              <button
                ref={closeButtonRef}
                onClick={closeMenu}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-stone-900 text-white hover:bg-stone-700 transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2"
                aria-label="Close navigation menu"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Menu items */}
            <nav className="px-10 lg:px-16">
              <ul className="space-y-1">
                {MENU_ITEMS.map((item) => (
                  <li key={item.label}>
                    <Link
                      to={item.to}
                      onClick={closeMenu}
                      className="block py-3 text-lg font-medium text-stone-900 hover:text-stone-500 transition-colors tracking-wide"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>

              {/* Divider + secondary links */}
              <div className="mt-10 pt-8 border-t border-stone-200">
                <Link
                  to="/"
                  onClick={closeMenu}
                  className="block py-2 text-sm text-stone-500 hover:text-stone-900 transition-colors"
                >
                  Home
                </Link>
                <Link
                  to="/shop"
                  onClick={closeMenu}
                  className="block py-2 text-sm text-stone-500 hover:text-stone-900 transition-colors"
                >
                  All Products
                </Link>
                <span className="block py-2 text-sm text-stone-400">
                  FineFit Services
                </span>
              </div>
            </nav>
          </div>
        </div>
      )}
    </>
  )
}
