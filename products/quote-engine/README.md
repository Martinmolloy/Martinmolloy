# Commercial Solar Quote Engine

A white-label **instant quote and lead-capture tool** for commercial solar installers in
the UK and Ireland. One self-contained HTML file, no build step, no dependencies. Drop it
on any website (Cloudflare Pages, Netlify, plain hosting, or an iframe on WordPress) and
the installer's "get a quote" contact form becomes a live estimate engine that qualifies
and sizes leads before a human ever touches them.

## What it does

A visitor answers six questions (country, sector, postcode/Eircode, electricity
spend **or** annual kWh, usage pattern, roof type/area) and gets, live:

- **Recommended system size** (kWp + panel count), sized from consumption and capped by roof area
- **Budget cost range** from tiered £/€ per-kWp rates
- **SEAI Non-Domestic Microgen Grant** estimate for Irish sites (marginal tiers, €162,600 cap)
- **Year-1 saving**, self-consumption vs. export split (SEG / Clean Export Guarantee rates)
- **Payback and 25-year benefit**, with degradation and energy inflation, plus a
  cumulative-savings chart with the breakeven point marked and a year-by-year table
- **Grid-connection flag** — G99/DNO (UK) or ESB Networks NC6/NC7 (Ireland) — framed as
  "we file this at survey stage", which is the installer's real differentiator
- **Transparent assumptions panel** (unit rates editable by the visitor) — transparency is
  what wins commercial deals
- **Lead capture** that posts a structured JSON "lead packet" (contact + site + inputs +
  full estimate) to any webhook/CRM endpoint

## White-labelling for a client installer

Everything lives in the `CONFIG` object at the top of the `<script>` in `index.html`:

| Key | What to change per client |
|---|---|
| `brand` | Name, tagline, email, phone (header, footer, page title all follow) |
| `webhookUrl` | Where the lead packet POSTs. `""` = demo mode (shows the packet on screen — useful when pitching) |
| `regions.UK` / `regions.IE` | Unit rates, export rates, yield, cost tiers (£/€ per kWp by size band), grant tiers, grid-application copy |
| `profiles` | Self-consumption % and sizing factor per usage pattern |
| `roofTypes` | m² per kWp by mounting type |
| `panelKwp`, `degradation`, `energyInflation`, `costRangePct` | Engineering assumptions |

Colours and fonts are CSS tokens in `:root` (light and dark themes) — swap the accent and
band colours to the client's brand in one place.

## Wiring the lead webhook

The packet is plain JSON (`source`, `contact`, `site`, `energy`, `estimate`). Point
`webhookUrl` at:

- a **Cloudflare Pages Function** (see `functions/api/enquiry.js` in this repo for the
  email-forwarding pattern), or
- **Zapier/Make/n8n** webhook → CRM (HubSpot, Pipedrive, Monday), or
- the installer's existing form endpoint.

Because the packet includes the computed estimate, the sales team receives a
**pre-sized, pre-qualified lead** — system kWp, budget, payback, grid-application status —
not a bare name and phone number.

## Caveats to keep honest

- SEAI grant tiers and the temporary uplift change; confirm current rates at
  https://www.seai.ie/grants/business-grants/commercial-solar-pv before each client deploy.
- Default unit rates, yields and cost tiers are indicative 2026 figures — tune per client.
- The output is a budget estimate, not an MCS performance estimate or a quotation; the
  footer disclaimer says so and should stay.

## Selling it

Positioning: *"Your 'request a quote' form is where commercial leads go to die. This turns
it into an engine that sizes, prices and grant-checks the lead before your estimator opens
their laptop — and files the G99/ESB application the week of the survey."* Price as a
setup fee (branding, rate tuning, webhook/CRM wiring, deploy) plus a monthly retainer
(rate updates when SEAI/SEG/tariffs move, lead-flow reporting).
