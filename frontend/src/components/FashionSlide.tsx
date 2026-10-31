import { motion } from 'framer-motion'
import type { Variants } from 'framer-motion'
import type { CSSProperties } from 'react'
import { HeroContent } from './HeroContent'
import { ParticleDissolveCanvas } from './ParticleDissolveCanvas'
import type { Campaign, CampaignTheme } from '../data/campaigns'
import { HERO_TIMING, type HeroPhase } from '../hooks/useHeroSequence'

/* ────────────────────────────────────────────────────────────────────────────
 * FashionSlide — one campaign: the photograph, its legibility overlays, the
 * copy, and the particle layer that breaks the photograph apart.
 *
 * The photograph lives on its own transformed layer so the entrance can move it
 * through space (scale + depth + blur) without touching the type: scaled text
 * is unreadable text.
 * ──────────────────────────────────────────────────────────────────────── */

interface FashionSlideProps {
  campaign: Campaign
  phase: HeroPhase
  /** True for the slide on screen; the incoming slide is rendered behind it. */
  active: boolean
  reducedMotion: boolean
  number: number
  total: number
}

/**
 * Per-theme overlay tint, plus the gradient painted if a photograph is missing
 * or fails to decode.
 */
const THEME_STYLES: Record<CampaignTheme, { fallback: string; overlay: string }> = {
  noir: {
    fallback:
      'bg-[radial-gradient(130%_120%_at_72%_18%,#45464d_0%,#26272c_38%,#121215_68%,#060607_100%)]',
    overlay: 'bg-gradient-to-r from-black/85 via-black/45 to-black/15',
  },
  ember: {
    fallback:
      'bg-[radial-gradient(130%_120%_at_70%_22%,#7a5f45_0%,#43352a_40%,#1d1713_72%,#080706_100%)]',
    overlay: 'bg-gradient-to-r from-black/80 via-black/40 to-[#2a1a10]/20',
  },
  ivory: {
    fallback:
      'bg-[radial-gradient(130%_120%_at_68%_20%,#6d6d68_0%,#3c3c39_40%,#1c1c1a_72%,#0a0a09_100%)]',
    overlay: 'bg-gradient-to-r from-black/80 via-black/40 to-black/10',
  },
}

/* Phase 1: out of the deep background — small, pushed back on the z axis,
 * slightly off-centre and out of focus, like a long lens racking focus as the
 * camera dollies in. Phase 3: a barely perceptible push-in. Phase 4: the
 * photograph fades while the particle canvas takes over.
 *
 * Every phase names the full set of animated properties. A variant that leaves
 * one out is not left alone by Framer — it falls back to `initial`, which would
 * snap the photograph back to its deep-background pose mid-sequence.
 *
 * Timing comes from HERO_TIMING so the photograph, the type and the snow share
 * one clock. */
const photoVariants: Variants = {
  enter: {
    opacity: 1,
    scale: 1,
    z: 0,
    x: '0%',
    y: '0%',
    filter: 'blur(0px)',
    transition: {
      duration: HERO_TIMING.enter / 1000,
      /* A true camera ease-in-out: unhurried off the mark, gathering speed
       * through the middle, settling at the end. The old curve (an expo-style
       * ease-out) covered most of the distance in the first fifth of the move,
       * which is what made the entrance read as a zoom rather than a dolly. */
      ease: [0.45, 0, 0.25, 1],
      /* The photograph only becomes visible once it is well into the dolly.
       * Coming up earlier would (a) expose a small, sharp-edged rectangle
       * floating over the outgoing slide and (b) put two legible photographs on
       * screen at the same time. By the time it is clearly visible, the outgoing
       * image has already given way to snow, so it reads as emerging from the
       * atmosphere rather than cross-dissolving. */
      opacity: { duration: 1.35, delay: 0.5, ease: [0.4, 0, 0.2, 1] },
      /* Focus lands just before the dolly does, so the photograph is never a
       * hard-edged rectangle sitting in the frame: the blur eases out quickly
       * but its last pixel or two stay until the image has filled the frame. */
      filter: { duration: 1.9, ease: 'easeOut' },
    },
  },
  reveal: {
    opacity: 1,
    scale: 1.006,
    z: 0,
    x: '0%',
    y: '0%',
    filter: 'blur(0px)',
    transition: { duration: 1, ease: [0.22, 1, 0.36, 1] },
  },
  stay: {
    opacity: 1,
    scale: 1.03,
    z: 0,
    x: '0%',
    y: '0%',
    filter: 'blur(0px)',
    transition: { duration: HERO_TIMING.stay / 1000, ease: 'easeInOut' },
  },
  dissolve: {
    opacity: 0,
    scale: 1.045,
    z: 0,
    x: '0%',
    y: '0%',
    filter: 'blur(0px)',
    transition: {
      duration: HERO_TIMING.dissolve / 1000,
      ease: 'linear',
      /* The photograph hands over to the snow early: by the time it is gone the
       * particle field is still holding its colours, so it breaks up rather than
       * simply fading — and the incoming slide is not exposed as a half-lit
       * rectangle behind it. */
      opacity: { duration: 0.9, delay: 0.1, ease: [0.45, 0, 0.8, 0.3] },
    },
  },
}

const quietPhotoVariants: Variants = {
  enter: { opacity: 1, transition: { duration: 0.6 } },
  reveal: { opacity: 1, transition: { duration: 0.5 } },
  stay: { opacity: 1 },
  dissolve: { opacity: 0, transition: { duration: 0.5 } },
}

export function FashionSlide({
  campaign,
  phase,
  active,
  reducedMotion,
  number,
  total,
}: FashionSlideProps) {
  const theme = THEME_STYLES[campaign.theme]

  /* Crop control: desktop and mobile `object-position` are applied by
   * `.hero-campaign-image` in index.css from these custom properties. */
  const imageStyle = {
    '--hero-pos-desktop': campaign.imagePosition ?? 'center',
    '--hero-pos-mobile': campaign.mobileImagePosition ?? campaign.imagePosition ?? 'center',
  } as CSSProperties

  /* A dissolving slide no longer has anything worth clicking. */
  const dissolving = active && phase === 'dissolve'

  return (
    <div
      className={`absolute inset-0 overflow-hidden ${active ? 'z-[2]' : 'z-[1]'} ${
        dissolving ? 'pointer-events-none' : ''
      }`}
      role="group"
      aria-roledescription="slide"
      aria-label={`${number} of ${total}`}
      aria-hidden={!active}
      inert={!active}
      data-hero-slide=""
      data-phase={phase}
    >
      <motion.div
        data-hero-photo=""
        className="absolute inset-0"
        style={{ transformPerspective: 1400, willChange: 'transform, opacity, filter' }}
        variants={reducedMotion ? quietPhotoVariants : photoVariants}
        initial={
          reducedMotion
            ? { opacity: 0 }
            : { scale: 0.38, opacity: 0, z: -560, x: '-1.1%', y: '1.4%', filter: 'blur(14px)' }
        }
        animate={phase}
      >
        <picture>
          {campaign.mobileImage && (
            <source media="(max-width: 767px)" srcSet={campaign.mobileImage} />
          )}
          <img
            src={campaign.image}
            alt={campaign.altText}
            className="hero-campaign-image absolute inset-0 h-full w-full object-cover"
            style={imageStyle}
            draggable={false}
            loading="eager"
            decoding="async"
          />
        </picture>

        <div className={`absolute inset-0 ${theme.overlay}`} aria-hidden="true" />
        <div
          className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/85 via-black/25 to-transparent"
          aria-hidden="true"
        />
      </motion.div>

      <HeroContent campaign={campaign} phase={phase} reducedMotion={reducedMotion} />

      {/* Mounted during the stay phase and only *armed* — the particle field is
       * decoded, sampled and built ahead of time, so the dissolve starts on its
       * first frame instead of spending it behind an empty canvas. */}
      {!reducedMotion && (phase === 'stay' || phase === 'dissolve') && (
        <ParticleDissolveCanvas
          imageSrc={campaign.image}
          imagePosition={campaign.imagePosition}
          active={phase === 'dissolve'}
          duration={HERO_TIMING.dissolve}
          className="pointer-events-none absolute inset-0 z-20 h-full w-full"
        />
      )}
    </div>
  )
}
