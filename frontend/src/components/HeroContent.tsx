import { motion } from 'framer-motion'
import type { Variants } from 'framer-motion'
import { Link } from 'react-router-dom'
import type { Campaign } from '../data/campaigns'
import type { HeroPhase } from '../hooks/useHeroSequence'

/* ────────────────────────────────────────────────────────────────────────────
 * HeroContent — collection label, headline, description and CTA.
 *
 * The copy is present but invisible during the entrance, then arrives in a
 * staggered cascade while the photograph settles sharp (the reveal phase), and
 * leaves before the snow does.
 *
 * Motion is expressed as variants keyed by the sequence phase, so this component
 * has no timers of its own: the timeline stays in useHeroSequence.
 * ──────────────────────────────────────────────────────────────────────── */

interface HeroContentProps {
  campaign: Campaign
  phase: HeroPhase
  reducedMotion: boolean
}

/* The label → headline → copy → CTA cascade finishes inside the reveal phase
 * (0.04s + 3 × 0.1s stagger + 0.8s of motion ≈ 1.14s of a 1.2s phase), so the
 * copy never still be moving when the camera settles. */
const container: Variants = {
  enter: { opacity: 0 },
  reveal: {
    opacity: 1,
    transition: { duration: 0.35, ease: 'linear', delayChildren: 0.04, staggerChildren: 0.1 },
  },
  stay: { opacity: 1 },
  /* The parent stays opaque during the exit and lets the children carry it in
   * reverse — the CTA leaves first and the collection label last. Fading the
   * whole block at once, as it used to, hid the stagger entirely. */
  dissolve: {
    opacity: 1,
    transition: { delayChildren: 0.02, staggerChildren: 0.07, staggerDirection: -1 },
  },
}

const item: Variants = {
  enter: { opacity: 0, y: 24 },
  reveal: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } },
  stay: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
  dissolve: { opacity: 0, y: -14, transition: { duration: 0.45, ease: 'easeIn' } },
}

const quietContainer: Variants = {
  enter: { opacity: 0 },
  reveal: { opacity: 1, transition: { duration: 0.5 } },
  stay: { opacity: 1 },
  dissolve: { opacity: 0, transition: { duration: 0.4 } },
}

const quietItem: Variants = {
  enter: { opacity: 0 },
  reveal: { opacity: 1, transition: { duration: 0.5 } },
  stay: { opacity: 1 },
  dissolve: { opacity: 0, transition: { duration: 0.4 } },
}

export function HeroContent({ campaign, phase, reducedMotion }: HeroContentProps) {
  return (
    <motion.div
      className="pointer-events-none relative z-10 flex h-full items-end"
      variants={reducedMotion ? quietContainer : container}
      initial={false}
      animate={phase}
    >
      {/* Desktop left padding clears the fixed side navigation arrows. */}
      <div className="mx-auto w-full max-w-[1440px] px-6 pb-28 sm:pb-32 lg:pl-24 lg:pr-10 lg:pb-36 xl:pl-28">
        <div className="pointer-events-auto max-w-xl">
          <motion.p
            variants={reducedMotion ? quietItem : item}
            className="text-[11px] font-medium uppercase tracking-[0.38em] text-white/70"
          >
            {campaign.collection}
          </motion.p>

          <motion.h2
            variants={reducedMotion ? quietItem : item}
            className="mt-4 font-serif text-4xl leading-[1.04] tracking-[-0.01em] text-white sm:text-5xl lg:text-6xl xl:text-[4.6rem]"
          >
            {campaign.headline}
          </motion.h2>

          <motion.p
            variants={reducedMotion ? quietItem : item}
            className="mt-5 max-w-md text-sm font-light leading-relaxed text-white/80 sm:text-base"
          >
            {campaign.description}
          </motion.p>

          <motion.div variants={reducedMotion ? quietItem : item} className="mt-9">
            <Link
              to={campaign.ctaLink}
              className="inline-block border border-white/80 px-9 py-3.5 text-[11px] font-medium uppercase tracking-[0.2em] text-white transition-colors duration-300 hover:border-white hover:bg-white hover:text-stone-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black sm:text-xs"
            >
              {campaign.ctaLabel}
            </Link>
          </motion.div>
        </div>
      </div>
    </motion.div>
  )
}
