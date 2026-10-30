# Deploying the Aura Energy site

The site is plain HTML in `public/`. Two Cloudflare Pages Functions run alongside it: the
Aura AI chat (`functions/api/chat.js`, which calls the Claude API) and the enquiry forms
(`functions/api/enquiry.js`, which emails each enquiry to the team). Everything deploys
together as one Cloudflare Pages project.

## 1. Get a Claude API key

1. Sign in at https://console.anthropic.com and add billing.
2. Create an API key (Settings, API keys). Name it something like `aura-website`.
3. Set a monthly spend limit (Settings, Limits) so a busy month can't surprise you.

## 2. Create the Cloudflare Pages project

Pick one:

- **From GitHub (recommended, deploys on every push):** Cloudflare dashboard, Workers & Pages,
  Create, Pages, Connect to Git, choose this repository and branch. Framework preset: None.
  Build command: leave empty. Build output directory: `public`. Cloudflare installs the
  dependencies from `package-lock.json` and builds the function automatically.
- **From your computer:** install Node.js 20 or later, then in this folder run
  `npm install` and `npx wrangler pages deploy public --project-name aura-energy`.

Drag-and-drop uploads in the dashboard publish the website but not the functions (the chat
and the forms), so use one of the two options above.

## 3. Add the API key and the enquiry address

In the Pages project: Settings, Variables and Secrets, add two **Secrets**, for Production
(and Preview if you want the chat and forms on preview links), then redeploy:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | the key from step 1 |
| `ENQUIRY_TO` | the inbox that receives quote, estimate and investor enquiries. For now that is Martin's own address; at launch, change it to the shared inbox. |

The enquiry address is deliberately not in the code: this repository is public, and the
website never shows it. Visitors only ever see info@auraenergy.ie.

Optional variables:

| Name | What it does |
|---|---|
| `AURA_AI_MODEL` | Model for the chat. Default `claude-opus-5-5`. `claude-haiku-5-5` is far cheaper per message (roughly a fortieth of the price) and fine for short FAQ answers. |
| `ALLOWED_ORIGINS` | Domains allowed to use the chat and forms, comma-separated. Default `https://auraenergy.ie,https://www.auraenergy.ie`. The project's own `*.pages.dev` address always works. |
| `SITE_URL` | The live address FormSubmit shows as the form's page. Default `https://auraenergy.ie/`. |

## 4. Connect the domain

Pages project, Custom domains, add `auraenergy.ie` and `www.auraenergy.ie`.

## 5. Limit abuse of the chat

The function already caps message length and history, and counts requests per visitor. For a
hard limit, add a rate limiting rule: your domain in Cloudflare, Security, WAF, Rate limiting
rules, match the URI path `/api/chat`, 20 requests per minute per IP, action Block.

## 6. Activate the forms (one time)

The quote, estimate and investor forms post to `/api/enquiry`, which passes each enquiry to
FormSubmit (formsubmit.co) to email it to `ENQUIRY_TO`, with the visitor's address as the
reply-to. FormSubmit needs a one-time activation for each address:

1. After deploying, send a test enquiry through the quote form yourself. The form shows an
   error this first time; that is expected.
2. FormSubmit emails an "Activate Form" link to the `ENQUIRY_TO` inbox (check spam). Click it.
3. Send the test again. It should arrive within a minute, and every enquiry after it will too.

Do this again whenever `ENQUIRY_TO` changes. If FormSubmit ever refuses an enquiry, the
visitor sees a message asking them to email info@auraenergy.ie instead, and the reason is in
the function's logs (Pages project, Functions, Real-time logs).

The investor form lives on its own page, `public/investors.html` (`/investors`), linked only
from the footer and kept out of search results and the sitemap.

## Launch checklist

Before pointing auraenergy.ie at the site:

1. Fill in every `[bracketed]` detail: the company particulars line in the footer of
   `public/index.html`, and the details in `public/privacy.html` and `public/terms.html`
   (company number, registered office, retention period). Irish company law requires the
   name, legal form, place of registration, number and registered office on the website.
2. Delete the `noindex` robots line near the top of the four legal pages (each has a TODO
   comment marking it) so they can be indexed.
3. Set the `ENQUIRY_TO` secret, then activate FormSubmit (section 6).
4. Have a solicitor review `public/investors.html` before it goes live. It is visible from the
   UK, where a page inviting investment can be a regulated financial promotion.
5. Check the LinkedIn and X links in the footer land on the right profiles
   (linkedin.com/company/aurenergy and x.com/auraenergyie).
6. Confirm the SEAI registered installer claim and keep the registration evidence; the badge
   appears in the hero, trust bar and footer.
7. A trademark search for "Aura Energy" is sensible before spending more on the brand; Aura
   Power, an established solar developer, is active in Ireland and the UK.

## Working on it

- `npm test` runs the tests for both functions (no API key needed, nothing is charged or
  emailed).
- `npm run dev` serves the site and the functions locally (put `ANTHROPIC_API_KEY=...` and
  `ENQUIRY_TO=...` in a `.dev.vars` file, which git ignores).
- `npm run build:art` regenerates the building illustrations in `public/assets/sectors/`
  from `tools/sector-art/build.py`.
- Aura AI's knowledge lives in `lib/aura-knowledge.js`. When prices, grants or the process
  change on the site, update it in the same change.
