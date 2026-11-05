/* ────────────────────────────────────────────────────────────────────────────
 * BrandPromiseStrip — premium horizontal animated promise strip.
 *
 * A continuous right-to-left marquee of compact promise cards. Cards sit on a
 * track that is duplicated once; animating translateX from 0% to -50% slides
 * the second copy exactly over the first, producing a seamless loop without a
 * visible jump. The duplicated cards are hidden from assistive technology so
 * accessible content is not repeated.
 *
 * Interaction
 *   • Pauses on hover / focus (container).
 *   • Respects prefers-reduced-motion: animation disabled, strip renders as a
 *     static scrollable row.
 *   • Touch-friendly: native horizontal scroll is not hijacked.
 * ────────────────────────────────────────────────────────────────────────── */

import { useRef } from "react";

const PROMISES = [
  { name: "Premium Quality", icon: "quality" },
  { name: "Thoughtful Design", icon: "design" },
  { name: "Everyday Comfort", icon: "comfort" },
  { name: "Modern Style", icon: "style" },
  { name: "Attention to Detail", icon: "detail" },
  { name: "Customer First", icon: "customer" },
] as const;

function Icon({ name }: { name: (typeof PROMISES)[number]["icon"] }) {
  return (
    <svg
      className="brand-promise-strip__icon"
      aria-hidden="true"
      focusable="false"
      width={20}
      height={20}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {name === "quality" && (
        <>
          <polyline points="20 6 9 17 4 12" />
          <path d="M20 6H9v11h11V6z" />
        </>
      )}
      {name === "design" && (
        <>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <path d="M3 9h18M3 15h18" />
          <circle cx="12" cy="12" r="1" />
        </>
      )}
      {name === "comfort" && (
        <>
          <path d="M12 2C8 2 5 5 5 9c0 5 7 11 7 11s7-6 7-11c0-4-3-7-7-7Z" />
          <path d="M8 13c0 1.1 0.9 2 2 2 1.1 0 2-0.9 2-2s0-1-1-1-1 1-1 1" />
          <path d="M16 13c0 1.1 0.9 2 2 2 1.1 0 2-0.9 2-2s0-1-1-1-1 1-1 1" />
        </>
      )}
      {name === "style" && (
        <>
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M12 22l10-5" />
        </>
      )}
      {name === "detail" && (
        <>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <path d="M7 7h.01M7 12h.01M7 17h.01M12 7h.01M12 12h.01M12 17h.01M17 7h.01M17 12h.01M17 17h.01" />
        </>
      )}
      {name === "customer" && (
        <>
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </>
      )}
    </svg>
  );
}

interface BrandPromiseStripProps {
  className?: string;
}

export function BrandPromiseStrip({ className }: BrandPromiseStripProps) {
  const reducedMotion =
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;
  const containerRef = useRef<HTMLDivElement>(null);

  const cards = PROMISES.map((p) => (
    <div key={p.name} className="brand-promise-strip__card" role="none">
      <Icon name={p.icon} />
      <span className="brand-promise-strip__name">{p.name}</span>
    </div>
  ));
  const duplicateCards = PROMISES.map((p) => (
    <div key={`${p.name}-dup`} className="brand-promise-strip__card" role="none" aria-hidden="true">
      <Icon name={p.icon} />
      <span className="brand-promise-strip__name" aria-hidden="true">{p.name}</span>
    </div>
  ));

  // Seamless loop: track holds two identical copies; translating -50% of the
  // track width slides the second copy exactly over the first. The second copy
  // is aria-hidden so accessible content is not repeated.
  const duplicated = !reducedMotion ? [...cards, ...duplicateCards] : cards;

  const containerEvents: React.DOMAttributes<HTMLDivElement> = {
    onMouseEnter: (e) => {
      if (reducedMotion) return;
      const el = e.currentTarget;
      el.style.animationPlayState = "paused";
    },
    onMouseLeave: (e) => {
      if (reducedMotion) return;
      const el = e.currentTarget;
      el.style.animationPlayState = "running";
    },
    onFocus: (e) => {
      if (reducedMotion) return;
      const el = e.currentTarget;
      el.style.animationPlayState = "paused";
    },
    onBlur: (e) => {
      if (reducedMotion) return;
      const el = e.currentTarget;
      el.style.animationPlayState = "running";
    },
  };

  return (
    <section
      className={["brand-promise-strip", className].filter(Boolean).join(" ")}
      aria-label="FineFit brand promises"
      {...containerEvents}
      ref={containerRef}
    >
      <div className="brand-promise-strip__viewport">
        <div
          className={[
            "brand-promise-strip__track",
            duplicated.length === cards.length ? "brand-promise-strip__track--static" : "",
          ].filter(Boolean).join(" ")}
        >
          {duplicated}
        </div>
      </div>
    </section>
  );
}
