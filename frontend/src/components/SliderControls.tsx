import type { Campaign } from '../data/campaigns'

/* ────────────────────────────────────────────────────────────────────────────
 * SliderControls — counter, slide indicators, and previous/next navigation.
 *
 * Kept deliberately quiet: a hairline rule, two thin ticks per slide and a
 * bordered circle set. Everything is a real button so the hero is operable by
 * keyboard and announced correctly by screen readers.
 * ──────────────────────────────────────────────────────────────────────── */

interface SliderControlsProps {
  campaigns: Campaign[]
  activeIndex: number
  onSelect: (index: number) => void
  onPrevious: () => void
  onNext: () => void
}

const pad = (value: number) => String(value).padStart(2, '0')

export function SliderControls({
  campaigns,
  activeIndex,
  onSelect,
  onPrevious,
  onNext,
}: SliderControlsProps) {
  const total = campaigns.length

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30">
      <div className="mx-auto w-full max-w-[1440px] px-6 pb-7 lg:pb-9 lg:pl-24 lg:pr-10 xl:pl-28">
        <div className="pointer-events-auto flex items-center justify-between gap-6 border-t border-white/15 pt-5">
          <p className="shrink-0 text-[11px] tracking-[0.25em] text-white/60 tabular-nums">
            <span className="text-white">{pad(activeIndex + 1)}</span>
            <span className="mx-1">/</span>
            <span>{pad(total)}</span>
          </p>

          <div className="flex items-center gap-2" style={{ minHeight: 24 }}>
            {campaigns.map((campaign, index) => {
              const isActive = index === activeIndex
              return (
                <button
                  key={campaign.id}
                  type="button"
                  aria-current={isActive ? 'true' : undefined}
                  aria-label={`Show ${campaign.collection}: ${campaign.headline}`}
                  onClick={() => onSelect(index)}
                  className="group flex h-6 items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                >
                  <span
                    className={`h-[2px] transition-all duration-500 ${
                      isActive ? 'w-14 bg-white' : 'w-8 bg-white/35 group-hover:bg-white/60'
                    }`}
                  />
                </button>
              )
            })}
          </div>

          {/* Desktop uses the side arrows over the photograph. */}
          <div className="flex shrink-0 items-center gap-2 lg:hidden">
            <button
              type="button"
              onClick={onPrevious}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/25 text-white/80 transition-colors hover:border-white/70 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
              aria-label="Previous slide"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onNext}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/25 text-white/80 transition-colors hover:border-white/70 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
              aria-label="Next slide"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
