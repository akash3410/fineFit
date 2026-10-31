/* ────────────────────────────────────────────────────────────────────────────
 * campaigns.ts — local, typed slide data for the cinematic homepage hero.
 *
 * This is the single source of truth for hero content. Changing the collection
 * label, headline, copy, CTA target or photography should only require editing
 * this file — never the animation components.
 *
 * IMAGE ASSETS
 * ------------
 * Photography lives in `public/images/campaigns/` and is referenced by a
 * root-relative URL, so images can be swapped without touching the bundle or
 * rebuilding the app.
 *
 * Each campaign ships a 16:9 landscape crop for desktop and a 9:16 portrait
 * crop for phones (served through `<picture>`), so the subject is protected at
 * both ends of the range instead of relying on a single aggressive CSS crop.
 * Current files are Pexels-licensed stock — see the directory README for the
 * source photo and license of each.
 *
 * The particle engine samples these images directly, so they must be served
 * same-origin (or with CORS headers) for `getImageData` to read their pixels.
 * If an image cannot be sampled, the dissolve degrades to a plain fade.
 * ──────────────────────────────────────────────────────────────────────── */

/**
 * Visual treatment for a campaign.
 *
 * Kept as a closed union (rather than free-form class strings) so the slide
 * component owns the actual Tailwind classes and campaign data cannot inject
 * arbitrary styles.
 *
 * - `noir`  — cool, monochrome; suited to black-and-white editorial photography
 * - `ember` — warm sandstone tones; suited to golden-hour / desert imagery
 * - `ivory` — soft neutral tones; suited to bright, airy studio photography
 */
export type CampaignTheme = 'noir' | 'ember' | 'ivory'

export interface Campaign {
  /** Stable unique id — used as the React key and for analytics later. */
  id: string
  /** Collection label above the headline (uppercase, letter-spaced). */
  collection: string
  /** Editorial headline. */
  headline: string
  /** One-line supporting copy. */
  description: string
  /** CTA button label. */
  ctaLabel: string
  /** CTA destination — must be an existing client route. */
  ctaLink: string
  /** Desktop / default campaign photograph (root-relative URL). */
  image: string
  /** Optional portrait-oriented crop used below the `md` breakpoint. */
  mobileImage?: string
  /** Required alt text describing the photograph. */
  altText: string
  /** CSS `object-position` for the desktop crop, e.g. `'center 30%'`. */
  imagePosition?: string
  /** CSS `object-position` for the mobile crop. Falls back to `imagePosition`. */
  mobileImagePosition?: string
  /**
   * Overlay tint for the photograph, and the gradient shown if the image is
   * missing or fails to decode.
   */
  theme: CampaignTheme
}

export const CAMPAIGNS: Campaign[] = [
  {
    id: 'new-season',
    collection: 'New Season',
    headline: 'Redefine Your Everyday Style.',
    description: 'Discover timeless essentials designed for modern living.',
    ctaLabel: 'Explore Collection',
    ctaLink: '/shop',
    image: '/images/campaigns/campaign-new-season.jpg',
    mobileImage: '/images/campaigns/campaign-new-season-mobile.jpg',
    altText:
      'Model in a flowing black gown and wide-brimmed hat crossing a windswept desert ridge, in black and white',
    /* Y pinned to the top: the figure is framed high, so ultrawide viewports
     * should give up the (already faded) bottom of the frame, not her head. */
    imagePosition: 'center 0%',
    mobileImagePosition: 'center 42%',
    theme: 'noir',
  },
  {
    id: 'autumn-winter',
    collection: 'Autumn / Winter',
    headline: 'Elegance in Every Detail.',
    description: 'Discover the art of effortless sophistication.',
    ctaLabel: 'Discover More',
    ctaLink: '/shop',
    image: '/images/campaigns/campaign-editorial.jpg',
    mobileImage: '/images/campaigns/campaign-editorial-mobile.jpg',
    altText:
      'Model in a red tulle evening gown walking across warm desert dunes under a clear sky',
    /* Y pinned to the top for the same reason: her face sits near the top edge. */
    imagePosition: 'center 0%',
    mobileImagePosition: 'center 40%',
    theme: 'ember',
  },
  {
    id: 'signature',
    collection: 'Signature Collection',
    headline: 'Designed to Make an Impression.',
    description: 'Express your individuality through contemporary fashion.',
    ctaLabel: 'Shop Now',
    ctaLink: '/shop',
    image: '/images/campaigns/campaign-autumn.jpg',
    mobileImage: '/images/campaigns/campaign-autumn-mobile.jpg',
    altText:
      'Model in a black evening dress reclining within a circular pool of studio light',
    imagePosition: 'center 40%',
    mobileImagePosition: 'center 50%',
    theme: 'ivory',
  },
]
