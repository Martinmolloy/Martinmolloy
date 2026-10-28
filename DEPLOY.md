# Deploying the Aura Energy site

The site is plain HTML in `public/`. The Aura AI chat runs as a Cloudflare Pages Function
(`functions/api/chat.js`) that calls the Claude API. Everything deploys together as one
Cloudflare Pages project.

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

Drag-and-drop uploads in the dashboard publish the website but not the chat function, so use
one of the two options above.

## 3. Add the API key

In the Pages project: Settings, Variables and Secrets, add a **Secret** named
`ANTHROPIC_API_KEY` with the key from step 1, for Production (and Preview if you want the chat
on preview links). Redeploy so it takes effect.

Optional variables:

| Name | What it does |
|---|---|
| `AURA_AI_MODEL` | Model for the chat. Default `claude-opus-5-5`. `claude-haiku-5-5` is far cheaper per message (roughly a fortieth of the price) and fine for short FAQ answers. |
| `ALLOWED_ORIGINS` | Extra domains allowed to use the chat, comma-separated. Default `https://auraenergy.ie,https://www.auraenergy.ie`. The project's own `*.pages.dev` address always works. |

## 4. Connect the domain

Pages project, Custom domains, add `auraenergy.ie` and `www.auraenergy.ie`.

## 5. Limit abuse of the chat

The function already caps message length and history, and counts requests per visitor. For a
hard limit, add a rate limiting rule: your domain in Cloudflare, Security, WAF, Rate limiting
rules, match the URI path `/api/chat`, 20 requests per minute per IP, action Block.

## 6. Activate the forms (one time)

The quote, estimate and investor forms send to martin@swarmsolar.co.uk through FormSubmit.
After the site is live, submit the quote form once yourself. FormSubmit emails an activation
link to martin@swarmsolar.co.uk; click it, and every later submission is delivered. The
activation email can land in spam. FormSubmit's activation email also offers a random alias
address; swapping it into the three `action="https://formsubmit.co/..."` attributes in
`public/index.html` hides the email address from the page source.

## Working on it

- `npm test` runs the chat function's tests (no API key needed, nothing is charged).
- `npm run dev` serves the site and the function locally (put `ANTHROPIC_API_KEY=...` in a
  `.dev.vars` file, which git ignores).
- `npm run build:art` regenerates the building illustrations in `public/assets/sectors/`
  from `tools/sector-art/build.py`.
- Aura AI's knowledge lives in `lib/aura-knowledge.js`. When prices, grants or the process
  change on the site, update it in the same change.
