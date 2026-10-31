import { useCallback, useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'
import { FashionSlide } from './FashionSlide'
import { SliderControls } from './SliderControls'
import { CAMPAIGNS } from '../data/campaigns'
import type { Campaign } from '../data/campaigns'
import { useHeroSequence } from '../hooks/useHeroSequence'

/* ────────────────────────────────────────────────────────────────────────────
 * FashionHeroSlider — orchestrates the cinematic sequence.
 *
 *   enter → reveal → stay → dissolve → (next slide, overlapping) → …
 *
 * The timeline itself lives in useHeroSequence; this component owns the input
 * surface (hover, focus, tab visibility, keys, swipe) and the layer stack. Two
 * slides can be mounted at once: the current one dissolving into particles and
 * the incoming one rising out of the background behind it, which is what keeps
 * the hero from ever showing an empty frame.
 *
 * Both are rendered in the same keyed list, so promoting the incoming slide does
 * not remount it and its entrance is never replayed.
 * ──────────────────────────────────────────────────────────────────────── */

/** Minimum horizontal travel (px) before a touch gesture counts as a swipe. */
const SWIPE_THRESHOLD_PX = 48

export function FashionHeroSlider() {
  const reducedMotion = useReducedMotion() ?? false
  const [isHovered, setIsHovered] = useState(false)
  const [isFocusWithin, setIsFocusWithin] = useState(false)
  const [isPageHidden, setIsPageHidden] = useState(false)

  const paused = isHovered || isFocusWithin || isPageHidden
  const { current, incoming, phase, goTo, next, previous } = useHeroSequence(
    CAMPAIGNS.length,
    paused,
  )

  /** Touch gesture origin, captured on touchstart. */
  const touchOrigin = useRef<{ x: number; y: number } | null>(null)

  /* Stop the timeline while the tab is in the background. */
  useEffect(() => {
    const handleVisibilityChange = () => setIsPageHidden(document.visibilityState === 'hidden')
    handleVisibilityChange()
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [])

  /* Warm the cache ahead of the sequence: by the time a slide mounts, both of
   * its crops are decoded and its entrance never starts on an empty frame. The
   * Image objects are held for the session so nothing is collected mid-flight. */
  const preloaded = useRef(new Map<string, HTMLImageElement>())

  const warm = useCallback((campaign: Campaign) => {
    /* <picture> swaps crops at the md breakpoint. Warming both would double the
     * hero's network cost for a file this device can never display. */
    const src = window.matchMedia('(max-width: 767px)').matches
      ? campaign.mobileImage ?? campaign.image
      : campaign.image
    if (preloaded.current.has(src)) return

    const image = new Image()
    image.decoding = 'async'
    image.src = src
    preloaded.current.set(src, image)
    void image.decode?.().catch(() => {})
  }, [])

  useEffect(() => {
    /* The next slide up is the one that will mount behind this one; the one
     * after it covers fast manual navigation. */
    for (const offset of [1, 2]) warm(CAMPAIGNS[(current + offset) % CAMPAIGNS.length])
  }, [current, warm])

  const handleTouchStart = useCallback((event: React.TouchEvent<HTMLElement>) => {
    const touch = event.touches[0]
    touchOrigin.current = { x: touch.clientX, y: touch.clientY }
  }, [])

  const handleTouchEnd = useCallback(
    (event: React.TouchEvent<HTMLElement>) => {
      const origin = touchOrigin.current
      touchOrigin.current = null
      if (!origin) return

      const touch = event.changedTouches[0]
      const deltaX = touch.clientX - origin.x
      const deltaY = touch.clientY - origin.y

      /* Ignore mostly-vertical gestures so page scrolling is unaffected. */
      if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX || Math.abs(deltaX) < Math.abs(deltaY)) return

      if (deltaX < 0) next()
      else previous()
    },
    [next, previous],
  )

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLElement>) => {
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        next()
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        previous()
      }
    },
    [next, previous],
  )

  return (
    <section
      className="relative h-[100svh] min-h-[560px] w-full overflow-hidden bg-stone-950"
      aria-roledescription="carousel"
      aria-label="FineFit campaign"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setIsFocusWithin(true)}
      onBlur={() => setIsFocusWithin(false)}
      onKeyDown={handleKeyDown}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Layer stack: the incoming slide paints underneath the dissolving one. */}
      <div className="absolute inset-0">
        {incoming !== null && (
          <FashionSlide
            key={CAMPAIGNS[incoming].id}
            campaign={CAMPAIGNS[incoming]}
            phase="enter"
            active={false}
            reducedMotion={reducedMotion}
            number={incoming + 1}
            total={CAMPAIGNS.length}
          />
        )}
        <FashionSlide
          key={CAMPAIGNS[current].id}
          campaign={CAMPAIGNS[current]}
          phase={phase}
          active
          reducedMotion={reducedMotion}
          number={current + 1}
          total={CAMPAIGNS.length}
        />
      </div>

      {/* Desktop side navigation, clear of the photograph's subject. */}
      {CAMPAIGNS.length > 1 && (
        <>
          <button
            type="button"
            onClick={previous}
            className="absolute left-4 top-1/2 z-30 hidden h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/25 text-white/80 backdrop-blur-sm transition-all duration-300 hover:border-white/70 hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 lg:flex xl:left-8"
            aria-label="Previous slide"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>

          <button
            type="button"
            onClick={next}
            className="absolute right-4 top-1/2 z-30 hidden h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/25 text-white/80 backdrop-blur-sm transition-all duration-300 hover:border-white/70 hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 lg:flex xl:right-8"
            aria-label="Next slide"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            </svg>
          </button>
        </>
      )}

      <SliderControls
        campaigns={CAMPAIGNS}
        activeIndex={current}
        onSelect={goTo}
        onPrevious={previous}
        onNext={next}
      />

      {/* Screen-reader announcement of the slide being shown. */}
      <p className="sr-only" aria-live="polite">
        Slide {current + 1} of {CAMPAIGNS.length}: {CAMPAIGNS[current].headline}
      </p>
    </section>
  )
}
