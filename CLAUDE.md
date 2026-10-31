# Project notes

## Brand / style (Martin's standing preference)

Every tool or page built in this repo (including anything under `products/`) uses the
**Aura Energy palette** — the same tokens as `public/index.html`:

- Orange: `#FE5000` (brand), `#E54800` (deep / CTAs / chart marks), `#B83A0A` (accessible
  text/links), `#FFEDE3` (soft fill), `#FFD2BC` (line)
- Green: `#12714B` · Ink: `#111113` · Muted: `#5C5D60` · Background: `#F6F6F7` ·
  Surface: `#FFFFFF` · Line: `#E9E9E7`
- Radii: `20px` panels, `14px` small elements · Soft shadows
- Type: `'Helvetica Neue', Helvetica, Arial, system-ui, sans-serif` (IBM Plex Mono is fine
  for data/figures)

When adding dark-mode variants, derive them from these hues (keep the orange/green
identity) rather than introducing new colours.
