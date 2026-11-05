/* ────────────────────────────────────────────────────────────────────────────
 * EventsAnnouncement — compact rotating event card.
 *
 * Shows a single active event at a time (fetched from the backend) with a
 * smooth fade transition to the next. Hides entirely when no active event
 * exists. Pauses on hover/focus and respects prefers-reduced-motion.
 * ────────────────────────────────────────────────────────────────────────── */

import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getEvents } from "../../api/catalog";
import type { Event } from "../../types/catalog";

interface EventsAnnouncementProps {
  className?: string;
}

export function EventsAnnouncement({ className }: EventsAnnouncementProps) {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);
  const [fadingOut, setFadingOut] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transitionRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reducedMotion =
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;

  const activeEvent = events[current];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getEvents();
        const list = Array.isArray(data) ? data : (data as any).results || [];
        if (!cancelled) setEvents(list);
      } catch {
        if (!cancelled) setError("Failed to load events");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (transitionRef.current) clearTimeout(transitionRef.current);
    };
  }, []);

  const startTimer = useCallback(function startTimer(): void {
    if (reducedMotion || events.length <= 1) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setFadingOut(true);
      transitionRef.current = setTimeout(() => {
        setCurrent((i) => (i + 1) % events.length);
        setFadingOut(false);
        // Named function expression allows a lint-safe self-reference for
        // rescheduling the next cycle.
        startTimer();
      }, 300);
    }, 4000);
  }, [events.length, reducedMotion]);

  useEffect(() => {
    startTimer();
  }, [startTimer, events.length]);

  const pause = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const resume = useCallback(() => {
    if (!reducedMotion && events.length > 1 && !timerRef.current) startTimer();
  }, [reducedMotion, events.length, startTimer]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        pause();
        setFadingOut(true);
        transitionRef.current = setTimeout(() => {
          setCurrent((i) => (i + 1) % events.length);
          setFadingOut(false);
          resume();
        }, 300);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        pause();
        setFadingOut(true);
        transitionRef.current = setTimeout(() => {
          setCurrent((i) => (i - 1 + events.length) % events.length);
          setFadingOut(false);
          resume();
        }, 300);
      }
    },
    [events.length, pause, resume]
  );

  if (loading) return null;
  if (error || events.length === 0) return null;

  const ctaLabel = activeEvent.cta_label?.trim();
  const ctaLink = activeEvent.cta_link?.trim();

  const isInternalPath = (url: string) =>
    url.startsWith("/") && !url.startsWith("//") && !url.includes("://");

  const isSafeExternalUrl = (url: string) => {
    try {
      const parsed = new URL(url);
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {
      return false;
    }
  };

  const validCta =
    Boolean(ctaLabel) &&
    Boolean(ctaLink) &&
    (isInternalPath(ctaLink) || isSafeExternalUrl(ctaLink));

  const isExternal = validCta && isSafeExternalUrl(ctaLink!);

  return (
    <section
      className={["events-announcement", className].filter(Boolean).join(" ")}
      aria-label="FineFit events & announcements"
      onMouseEnter={pause}
      onMouseLeave={resume}
      onFocus={pause}
      onBlur={resume}
      onKeyDown={handleKeyDown}
    >
      <div className="events-announcement__card" role="region" aria-roledescription="event">
        <div
          className={[
            "events-announcement__surface",
            fadingOut ? "events-announcement__surface--fade-out" : "",
          ].filter(Boolean).join(" ")}
        >
          <div className="events-announcement__media">
            {activeEvent.image && (
              <img
                src={activeEvent.image}
                alt=""
                className="events-announcement__image"
                aria-hidden="true"
                loading="lazy"
                decoding="async"
              />
            )}
          </div>
          <div className="events-announcement__content">
            <h3 className="events-announcement__title">{activeEvent.title}</h3>
            {activeEvent.announcement && (
              <p className="events-announcement__announcement">
                {activeEvent.announcement}
              </p>
            )}
            {validCta && (
              isExternal ? (
                <a
                  href={ctaLink as string}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="events-announcement__cta"
                  aria-label={ctaLabel}
                >
                  {ctaLabel}
                  <svg
                    className="events-announcement__cta-arrow"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  >
                    <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </a>
              ) : (
                <Link
                  to={ctaLink as string}
                  className="events-announcement__cta"
                  aria-label={ctaLabel}
                >
                  {ctaLabel}
                  <svg
                    className="events-announcement__cta-arrow"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  >
                    <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </Link>
              )
            )}
          </div>
        </div>
      </div>

      {events.length > 1 && !reducedMotion && (
        <div className="events-announcement__indicators" aria-label="Event navigation">
          {events.map((_, i) => (
            <button
              key={i}
              onClick={() => {
                pause();
                setFadingOut(true);
                transitionRef.current = setTimeout(() => {
                  setCurrent(i);
                  setFadingOut(false);
                  resume();
                }, 300);
              }}
              aria-current={i === current ? "true" : undefined}
              className={`events-announcement__dot ${
                i === current ? "events-announcement__dot--active" : ""
              }`}
              aria-label={`Show event ${i + 1} of ${events.length}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}
