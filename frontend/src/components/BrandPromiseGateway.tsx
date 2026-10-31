import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

/* ────────────────────────────────────────────────────────────────────────────
 * BrandPromiseGateway — FineFit "The Journey of Trust" center-focused 3-D
 * coverflow carousel.
 *
 * Layout
 *   • Editorial heading above the carousel.
 *   • Fifteen journey cards distributed across five unique horizontal slots:
 *       far-left (-2 step), left (-1 step), center (0), right (+1 step),
 *       far-right (+2 step). Cards beyond ±2 sit off-screen, waiting to
 *       enter as the carousel advances.
 *   • Each slot's X coordinate is computed in PIXELS from the measured track
 *     width: x = -halfCardWidth + rel * stepPx. Because translateX pixel
 *     values are absolute (not % of the card's own width), cards never
 *     cluster at the centre — they occupy distinct positions with a visible
 *     gap between every neighbour.
 *   • No gateway, no marquee — a discrete coverflow carousel.
 *
 * Animation
 *   • Advancing moves right→center, center→left, left→far-left, far-right→
 *     right, far-left→far-right (wrap). New card enters from far-right.
 *   • Every transition animates x, scale, rotateY, translateZ and opacity
 *     together over 800ms with a premium cubic-bezier ease.
 *   • Auto-advance every 3.5 s; pauses on hover/focus and under
 *     prefers-reduced-motion.
 *
 * Interaction
 *   • Prev / Next buttons step one card. Five-dot indicator shows active stage.
 *   • Touch/swipe pauses and resumes auto-play. Native scroll not hijacked.
 * ──────────────────────────────────────────────────────────────────────────── */

export interface JourneyStage {
  id: string
  number: string
  title: string
  description: string
  accent?: string
}

export interface BrandPromiseGatewayProps {
  stages?: JourneyStage[]
  className?: string
}

const STAGES: JourneyStage[] = [
  {
    id: 'promise',
    number: '01',
    title: 'Promise',
    description:
      'The refined wardrobe begins here — thoughtfully made, never over-engineered.',
    accent: '#0D4966',
  },
  {
    id: 'expectation',
    number: '02',
    title: 'Expectation',
    description: 'We aim to exceed what you thought the wardrobe could be.',
    accent: '#0D4966',
  },
  {
    id: 'experience',
    number: '03',
    title: 'Experience',
    description:
      'Every detail considered, every touch felt before you wear it.',
    accent: '#0D4966',
  },
  {
    id: 'trust',
    number: '04',
    title: 'Trust',
    description:
      'A relationship built on quiet confidence and lasting quality.',
    accent: '#0D4966',
  },
  {
    id: 'choice',
    number: '05',
    title: 'Choice',
    description:
      'One space to begin — the whole collection at your fingertips.',
    accent: '#0D4966',
  },
  {
    id: 'craft',
    number: '06',
    title: 'Craft',
    description: 'Hands that know fabric, seams that hold, finishes that last.',
    accent: '#0D4966',
  },
  {
    id: 'detail',
    number: '07',
    title: 'Detail',
    description:
      'The quiet difference is in the elements you almost never notice.',
    accent: '#0D4966',
  },
  {
    id: 'legacy',
    number: '08',
    title: 'Legacy',
    description: 'Pieces made to outlive the season and pass on intact.',
    accent: '#0D4966',
  },
  {
    id: 'vision',
    number: '09',
    title: 'Vision',
    description: 'Looking ahead, dressing for the life you want to lead.',
    accent: '#0D4966',
  },
  {
    id: 'essence',
    number: '10',
    title: 'Essence',
    description:
      'Not fashion that shouts — wardrobe that speaks only when it should.',
    accent: '#0D4966',
  },
  {
    id: 'poise',
    number: '11',
    title: 'Poise',
    description:
      'Carrying yourself with quiet confidence in everything you wear.',
    accent: '#0D4966',
  },
  {
    id: 'balance',
    number: '12',
    title: 'Balance',
    description:
      'Where comfort meets refinement, every single day.',
    accent: '#0D4966',
  },
  {
    id: 'grace',
    number: '13',
    title: 'Grace',
    description:
      'Effortless elegance that follows you beyond the first impression.',
    accent: '#0D4966',
  },
  {
    id: 'refine',
    number: '14',
    title: 'Refine',
    description:
      'Curating less, choosing better — the art of editing your wardrobe.',
    accent: '#0D4966',
  },
  {
    id: 'endure',
    number: '15',
    title: 'Endure',
    description:
      'Built to last, designed to be worn again and again.',
    accent: '#0D4966',
  },
]

const TOTAL = STAGES.length
const AUTO_ADVANCE_MS = 3500
const TRANSITION_MS = 0.8

/** Per-breakpoint layout: card width and centre-to-centre step (% of track).
 * stepPct always exceeds cardWidthPct by a deliberate visible gap.
 * Crucially, stepPct stays below 25% on desktop so the far-left card's right
 * edge remains in view (50% - 2 * stepPct > 0). */
function getLayout(width: number) {
  if (width < 640) {
    // Mobile: three-card composition — center dominant, partial neighbours
    return { cardWidthPct: 40, stepPct: 48, rotateY: 10, zNear: 22 }
  }
  if (width < 1024) {
    // Tablet: centre three visible, far cards off-screen
    return { cardWidthPct: 36, stepPct: 44, rotateY: 14, zNear: 26 }
  }
  // Desktop: all five cards visible with gaps
  return { cardWidthPct: 20, stepPct: 23, rotateY: 18, zNear: 32 }
}

/** Map relative slot (-2..2) to coverflow visual values.
 * Cards beyond ±2 sit off-screen; their visual values are capped so they
 * never rotate excessively while waiting to enter. */
function coverflowValues(
  rel: number,
  { rotateY, zNear }: { rotateY: number; zNear: number },
) {
  const ad = Math.abs(rel)
  const scale = rel === 0 ? 1 : ad === 1 ? 0.86 : 0.72
  // Side cards rotate toward the centre so their faces stay readable.
  // Far cards (rel ±2+) rotate slightly more than immediate neighbours.
  const cappedRel = Math.max(-2, Math.min(2, rel))
  const rotation =
    cappedRel === 0 ? 0 : cappedRel > 0 ? -rotateY * 1.25 : rotateY * 1.25
  const z = rel === 0 ? zNear : ad === 1 ? zNear * 0.55 : zNear * 0.3
  const opacity = rel === 0 ? 1 : ad === 1 ? 0.92 : 0.72
  return { scale, rotation, z, opacity }
}

/** Single coverflow card. Positioned at a unique slot via pixel-accurate x. */
function JourneyCard({
  stage,
  cardIndex,
  activeIndex,
  trackWidth,
  isWrapping,
  reducedMotion,
}: {
  stage: JourneyStage
  cardIndex: number
  activeIndex: number
  trackWidth: number
  isWrapping: boolean
  reducedMotion: boolean
}) {
  const layout = getLayout(trackWidth || 1024)

  // Wrapped relative slot: 0 = centre, -1 = left, 1 = right, etc.
  let rel = cardIndex - activeIndex
  rel = ((rel + TOTAL / 2) % TOTAL + TOTAL) % TOTAL - TOTAL / 2

  const { cardWidthPct, stepPct } = layout
  const { scale, rotation, z, opacity } = coverflowValues(rel, {
    rotateY: layout.rotateY,
    zNear: layout.zNear,
  })

  // Pixel-accurate offsets (translateX px values are absolute, not % of card).
  const stepPx = (trackWidth * stepPct) / 100
  const halfCardPx = (trackWidth * (cardWidthPct / 100)) / 2
  const x = -halfCardPx + rel * stepPx

  const cardHeight = trackWidth < 640 ? 'clamp(200px, 40vh, 420px)' : 'clamp(250px, 46vh, 560px)'

  return (
    <motion.div
      className="brand-promise-card"
        style={{
          left: '50%',
          top: '50%',
          width: `${cardWidthPct}%`,
          height: cardHeight,
          zIndex: rel === 0 ? 30 : rel === -1 || rel === 1 ? 20 : 10,
          transformStyle: 'preserve-3d',
          willChange: 'transform, opacity',
        }}
      initial={false}
      animate={{
        x,
        y: '-50%',
        scale,
        rotateY: rotation,
        z,
        opacity: reducedMotion ? (rel === 0 ? 1 : 0.5) : opacity,
      }}
      transition={{
        duration: reducedMotion || isWrapping ? 0 : TRANSITION_MS,
        ease: [0.25, 0.1, 0.25, 1],
      }}
      aria-label={`Stage ${stage.number}: ${stage.title}`}
    >
      <div
        className="brand-promise-card__wall"
        aria-hidden="true"
        style={{
          transform: 'translateZ(-14px)',
          transformStyle: 'preserve-3d',
        }}
      />
      {rel === 0 && (
        <div
          className="brand-promise-card__glow"
          aria-hidden="true"
          style={{ transformStyle: 'preserve-3d' }}
        />
      )}

      <div
        className="brand-promise-card__body"
        style={{
          transform: `translateZ(${rel === 0 ? 40 : 20}px)`,
        }}
      >
        {/* Rotating light beam hugging the *visible* card surface (the body's
          * own box and z-plane) so its ring coincides with the card's actual
          * border on all four edges. Rendered only for rel === 0, so exactly
          * one card ever carries the beam. */}
        {rel === 0 && (
          <div className="brand-promise-card__beam" aria-hidden="true" />
        )}
        <span
          className="brand-promise-card__number"
          style={{ color: stage.accent }}
        >
          {stage.number}
        </span>
        <h3 className="brand-promise-card__title">{stage.title}</h3>
        <p className="brand-promise-card__desc">
          {stage.description}
        </p>
      </div>
    </motion.div>
  )
}

function SliderControls({
  onPrev,
  onNext,
  activeIndex,
}: {
  onPrev: () => void
  onNext: () => void
  activeIndex: number
}) {
  return (
    <div className="brand-promise-slider__controls mt-12 flex items-center justify-between gap-6 px-2 sm:px-0">
      <button
        onClick={onPrev}
        aria-label="Previous stage"
        className="flex h-10 w-10 items-center justify-center rounded-full border border-stone-300/60 bg-white/80 px-3 text-sm text-stone-900 hover:bg-stone-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-900/30 disabled:opacity-40 disabled:pointer-events-none"
      >
        <span className="sr-only">Previous</span>
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      <div
        className="brand-promise-slider__dots flex gap-2 sm:gap-3"
        aria-label="Stage navigation"
      >
        {Array.from({ length: TOTAL }).map((_, i) => (
          <button
            key={i}
            onClick={() => {}}
            aria-label={`Go to stage ${i + 1}`}
            aria-current={i === activeIndex ? 'true' : undefined}
            className={`h-1.5 w-1.5 rounded-full transition-colors ${
              i === activeIndex
                ? 'bg-stone-900 w-3'
                : 'bg-stone-300/60 hover:bg-stone-500/80'
            }`}
          />
        ))}
      </div>

      <button
        onClick={onNext}
        aria-label="Next stage"
        className="flex h-10 w-10 items-center justify-center rounded-full border border-stone-300/60 bg-white/80 px-3 text-sm text-stone-900 hover:bg-stone-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-900/30 disabled:opacity-40 disabled:pointer-events-none"
      >
        <span className="sr-only">Next</span>
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  )
}

export function BrandPromiseGateway({
  stages = STAGES,
  className,
}: BrandPromiseGatewayProps) {
  const reducedMotion = useReducedMotion() ?? false
  const total = stages.length
  const [activeIndex, setActiveIndex] = useState(0)
  const trackRef = useRef<HTMLDivElement | null>(null)
  const [trackWidth, setTrackWidth] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1024,
  )
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isDragging = useRef(false)
  const prevActiveIndexRef = useRef(activeIndex)

  // Detect wrap (activeIndex jumps from 4→0 or 0→4). On wrap frames we use an
  // instant transition so the card that moves from one edge to the other does
  // not animate across the screen.
  const isWrapping = useMemo(() => {
    const wasWrapping = Math.abs(activeIndex - prevActiveIndexRef.current) === TOTAL - 1
    prevActiveIndexRef.current = activeIndex
    return wasWrapping
  }, [activeIndex])

  useLayoutEffect(() => {
    const track = trackRef.current
    if (!track) return
    const measure = () => setTrackWidth(track.offsetWidth)
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  /* ── Auto-advance ──────────────────────────────────────────────────── */
  const startTimerRef = useRef<(() => void) | null>(null)

  const startTimer = useCallback((): void => {
    if (reducedMotion || timerRef.current) return
    timerRef.current = setTimeout(() => {
      setActiveIndex((i) => (i + 1) % total)
      timerRef.current = null
      startTimerRef.current?.()
    }, AUTO_ADVANCE_MS)
  }, [reducedMotion, total])

  useEffect(() => {
    startTimerRef.current = startTimer
  }, [startTimer])

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    if (reducedMotion) {
      stopTimer()
      return
    }
    startTimer()
    return () => stopTimer()
  }, [reducedMotion, startTimer, stopTimer])

  const resumeTimer = useCallback(() => {
    if (reducedMotion) return
    stopTimer()
    startTimer()
  }, [reducedMotion, startTimer, stopTimer])

  /* ── Navigation ────────────────────────────────────────────────────── */
  const goTo = useCallback(
    (index: number) => {
      if (reducedMotion) return
      stopTimer()
      setActiveIndex(((index % total) + total) % total)
      if (!isDragging.current) resumeTimer()
    },
    [total, reducedMotion, stopTimer, resumeTimer],
  )

  const onPrev = useCallback(() => goTo(activeIndex - 1), [activeIndex, goTo])
  const onNext = useCallback(() => goTo(activeIndex + 1), [activeIndex, goTo])

  /* ── Pause on hover / focus ────────────────────────────────────────── */
  const onMouseEnter = useCallback(() => stopTimer(), [stopTimer])
  const onMouseLeave = useCallback(() => resumeTimer(), [resumeTimer])
  const onFocus = useCallback(() => stopTimer(), [stopTimer])
  const onBlur = useCallback(() => resumeTimer(), [resumeTimer])

  /* ── Touch / drag ──────────────────────────────────────────────────── */
  const onPointerDown = useCallback(() => {
    if (reducedMotion) return
    isDragging.current = true
    stopTimer()
  }, [reducedMotion, stopTimer])

  const onPointerUp = useCallback(() => {
    if (!isDragging.current) return
    isDragging.current = false
    if (document.visibilityState !== 'hidden') resumeTimer()
  }, [resumeTimer])

  /* ── Render ────────────────────────────────────────────────────────── */
  const sectionClass = [
    'brand-promise-slider',
    'relative',
    'overflow-hidden',
    'py-16 sm:py-20 md:pt-28 md:pb-20',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <section className={sectionClass} aria-label="FineFit Brand Promise">
      <div className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12">
        {/* ── Editorial heading ── */}
        <div className="brand-promise-slider__head text-left sm:text-center">
          <h2 className="brand-promise-slider__title">
            The Journey of Trust
          </h2>
          <p className="brand-promise-slider__subtitle">
            Every promise begins a journey. Every experience builds trust.
          </p>
        </div>

        {/* ── Carousel viewport ── */}
        <div
          ref={trackRef}
          className="brand-promise-slider__viewport relative overflow-hidden"
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          onFocus={onFocus}
          onBlur={onBlur}
          onPointerDown={onPointerDown}
          onPointerUp={onPointerUp}
          tabIndex={0}
        >
          <div
            className="brand-promise-slider__track"
            style={{
              position: 'relative',
              height: 'clamp(400px, 60vh, 700px)',
              transformStyle: 'preserve-3d',
              perspective: '1200px',
            } as CSSProperties}
          >
            {stages.map((stage, i) => (
              <JourneyCard
                key={stage.id}
                stage={stage}
                cardIndex={i}
                activeIndex={activeIndex}
                trackWidth={trackWidth}
                isWrapping={isWrapping}
                reducedMotion={reducedMotion}
              />
            ))}
          </div>
        </div>

        {/* ── Controls ── */}
        <SliderControls onPrev={onPrev} onNext={onNext} activeIndex={activeIndex} />
      </div>
    </section>
  )
}
