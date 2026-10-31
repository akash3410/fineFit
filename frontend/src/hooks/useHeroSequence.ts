import { useCallback, useEffect, useRef, useState } from 'react'

/* ────────────────────────────────────────────────────────────────────────────
 * useHeroSequence — the hero's narrative timeline.
 *
 * One slide is "current" at a time, and it moves through four phases:
 *
 *   enter    (2200ms)  the photograph travels forward out of deep background
 *   reveal   (1200ms)  it settles sharp while the headline and CTA arrive
 *   stay     (3400ms)  held on screen with a slow, barely-there camera push
 *   dissolve (2200ms)  the photograph breaks into falling snow
 *
 * The next slide's entrance starts on the first frame of the dissolve, so the
 * incoming photograph is already rising behind the dissolving one and the hero
 * is never empty. The entrance is deliberately a little shorter than the
 * dissolve (2000ms of visible movement inside a 2200ms window), so the incoming
 * image has fully arrived — sharp, in focus, motionless — before it is promoted.
 * That overlap is what turns two separate animations into one continuous move:
 * the next photograph is already resolved while the last snowflakes are still
 * falling over it.
 *
 * Manual navigation rides the same hand-off rather than cutting: `goTo` starts a
 * dissolve of the slide on screen and lets the target rise behind it, so a
 * click, key press or swipe never produces a black frame.
 *
 * Pausing (hover, keyboard focus, hidden tab) freezes the countdown and resumes
 * with the remaining time. The dissolve phase is exempt: pausing halfway through
 * one would leave the frame showing nothing but snow.
 * ──────────────────────────────────────────────────────────────────────── */

export type HeroPhase = 'enter' | 'reveal' | 'stay' | 'dissolve'

/**
 * Phase durations in milliseconds.
 *
 * These are the single source of truth: the Framer variants in FashionSlide and
 * the particle engine both derive their timings from here, so the photograph,
 * the type and the snow can never drift out of sync.
 */
export const HERO_TIMING: Record<HeroPhase, number> = {
  enter: 2200,
  reveal: 1200,
  stay: 3400,
  dissolve: 2200,
}

/**
 * Full cycle length: the gap between one slide taking over and the next one
 * doing so. The `enter` phase is deliberately absent — the incoming slide's
 * entrance runs *inside* the outgoing slide's dissolve, not after it.
 */
export const HERO_CYCLE_MS = HERO_TIMING.reveal + HERO_TIMING.stay + HERO_TIMING.dissolve

export interface HeroSequence {
  /** Index of the slide on screen. */
  current: number
  /** Index of the slide rising behind the current one, or null. */
  incoming: number | null
  phase: HeroPhase
  /** Jump to a slide (manual navigation), dissolving the current one out. */
  goTo: (index: number) => void
  next: () => void
  previous: () => void
}

interface SequenceState {
  current: number
  incoming: number | null
  phase: HeroPhase
}

const wrap = (value: number, count: number) => ((value % count) + count) % count

export function useHeroSequence(slideCount: number, paused: boolean): HeroSequence {
  const [state, setState] = useState<SequenceState>({
    current: 0,
    incoming: null,
    phase: 'enter',
  })

  /* Time left in the running phase, kept across a pause. `key` identifies the
   * phase it belongs to so a stale remainder is never applied to the next one. */
  const pending = useRef<{ key: string; remaining: number } | null>(null)
  const phaseKey = `${state.current}:${state.phase}`

  /* Holding during the dissolve would strand a fully-dissolved slide. */
  const hold = paused && state.phase !== 'dissolve'

  useEffect(() => {
    if (hold || slideCount < 2) return

    const total = HERO_TIMING[state.phase]
    const duration = pending.current?.key === phaseKey ? pending.current.remaining : total
    pending.current = null
    const startedAt = performance.now()

    const timer = window.setTimeout(() => {
      pending.current = null
      setState((previous) => {
        switch (previous.phase) {
          case 'enter':
            return { ...previous, phase: 'reveal' }
          case 'reveal':
            return { ...previous, phase: 'stay' }
          case 'stay':
            return {
              ...previous,
              incoming: (previous.current + 1) % slideCount,
              phase: 'dissolve',
            }
          case 'dissolve':
            /* The incoming slide finished its entrance during the dissolve, so
             * it takes over already sharp and just plays its text reveal. */
            return {
              current: previous.incoming ?? previous.current,
              incoming: null,
              phase: 'reveal',
            }
        }
      })
    }, Math.max(0, duration))

    return () => {
      window.clearTimeout(timer)
      const elapsed = performance.now() - startedAt
      pending.current = { key: phaseKey, remaining: Math.max(0, duration - elapsed) }
    }
  }, [phaseKey, hold, state.phase, slideCount])

  const goTo = useCallback(
    (index: number) => {
      const target = wrap(index, slideCount)

      /* A single-slide hero has nothing to hand off to. */
      if (slideCount < 2) {
        pending.current = null
        setState({ current: target, incoming: null, phase: 'enter' })
        return
      }

      pending.current = null
      setState((previous) => {
        /* Already showing it, or already on its way to it. */
        if (target === previous.current) return previous
        if (target === previous.incoming) return previous

        return { current: previous.current, incoming: target, phase: 'dissolve' }
      })
    },
    [slideCount],
  )

  const { current, incoming, phase } = state

  /* Navigate from where the sequence is heading, not where it is, so repeated
   * clicks during a dissolve keep stepping forward instead of stalling. */
  const anchor = incoming ?? current
  const next = useCallback(() => goTo(anchor + 1), [goTo, anchor])
  const previous = useCallback(() => goTo(anchor - 1), [goTo, anchor])

  return { current, incoming, phase, goTo, next, previous }
}
