# Campaign hero images

The homepage hero slider (`src/components/HeroCampaignSlider.tsx`) reads its
photography from this directory, driven by `src/data/campaigns.ts`.

Each campaign ships **two crops** so the subject survives both ends of the
responsive range instead of relying on one aggressive CSS crop:

- `campaign-<name>.jpg` — 2560×1440 (16:9) landscape, used from `md` up
- `campaign-<name>-mobile.jpg` — 1080×1920 (9:16) portrait, used below `md`
  via `<source media="(max-width: 767px)">`

`HeroCampaignSlider` additionally applies `object-position` from
`imagePosition` / `mobileImagePosition` in `src/data/campaigns.ts`, which
fine-tunes the crop on viewports whose aspect ratio differs from the file
(e.g. ultra-wide desktop, landscape phone). If a `-mobile` file is missing the
browser falls back to the landscape image — still functional, just a less
controlled crop.

## Current files

| File | Slide | Source |
| :--- | :--- | :--- |
| `campaign-new-season.jpg` + `-mobile` | New Season — "Beyond the Ordinary" | Pexels photo [35785549](https://www.pexels.com/photo/35785549/) |
| `campaign-editorial.jpg` + `-mobile` | The Edit — "Crafted for Your Expression" | Pexels photo [28601583](https://www.pexels.com/photo/28601583/) |
| `campaign-autumn.jpg` + `-mobile` | FineFit Exclusives — "A New Perspective" | Pexels photo [30411964](https://www.pexels.com/photo/30411964/) |

All three are used under the [Pexels License](https://www.pexels.com/license/):
free for commercial use, modification permitted, attribution not required
(credited here anyway). No brand campaign photography is included.

**These are stock stand-ins.** They are licensed and safe to ship, but they are
not FineFit's own campaign work — swap them for original or bought photography
before launch by replacing the files at these exact paths (no code change
needed), or by editing `image` / `mobileImage` in `src/data/campaigns.ts`.

## Replacing or adding art

- **Composition**: leave negative space on the left third of landscape images —
  the campaign copy sits there — and keep the subject clear of the bottom ~25%.
- **Tone**: dark or mid-tone imagery keeps the white type legible. The per-slide
  overlay is tuned in `HeroCampaignSlider.tsx` under `THEME_STYLES`.
- **Crop control**: `imagePosition` / `mobileImagePosition` accept any CSS
  `object-position` value.
- **Weight**: aim for ≤ 400 KB per image — these are the largest paint on the
  site. Current files are 100–300 KB. Consider WebP/AVIF sources later.
- **Licensing**: only add images you own or have licensed. Do not commit
  third-party brand campaign photography.

## Adding a fourth campaign

Append an entry to `CAMPAIGNS` in `src/data/campaigns.ts`. The slider derives
navigation, indicators, autoplay and swipe behaviour from the array length, so
no component changes are needed.
