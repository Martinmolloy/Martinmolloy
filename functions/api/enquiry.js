// POST /api/enquiry: the quote, roof estimate and investor forms (Cloudflare Pages Function).
//
// The forms post here rather than straight to an email service, so the address enquiries go
// to never appears in the page or in this repository: it comes from the ENQUIRY_TO setting.
// Each enquiry is passed to FormSubmit (formsubmit.co), which emails it there with the
// visitor's address as the reply-to.
//
//   ENQUIRY_TO  where enquiries are emailed. Required: set it in Cloudflare Pages (Settings,
//               Variables and Secrets). Without it the forms show an error asking the
//               visitor to email or call instead, so nothing is lost silently.
//   SITE_URL    the live site address, which FormSubmit shows as the form's page
//               (default https://auraenergy.ie/).
//
// FormSubmit asks the ENQUIRY_TO address to activate the form once: send one test enquiry
// after deploying and click the link in the email it sends. Until then enquiries fail with an
// error the visitor can see.
//
// The page sends each form with fetch and gets JSON back:
//   { "ok": true, "form": "quote" }
//   { "error": "invalid", "fields": ["email"] }       a required field is missing or wrong
//   { "error": "busy" | "forbidden" | "unavailable" }
// Without JavaScript the browser posts the form normally and gets a short page back.

import { originAllowed, rateLimiter, json } from '../../lib/request-guards.js';

const DEFAULT_SITE = 'https://auraenergy.ie/';
const FORMSUBMIT = 'https://formsubmit.co/ajax/';
const RATE_WINDOW_MS = 10 * 60_000;
const RATE_MAX = 6;                // enquiries per visitor IP per 10 minutes
const MAX_FIELD = 300;             // characters per field
const MAX_LONG = 3000;             // for the message and the estimate summary
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Every field each form may send, with its label in the email. Anything else is dropped.
const FORMS = {
  quote: {
    subject: 'New quote request | auraenergy.ie',
    back: '/#quote',
    required: ['name', 'email', 'company', 'county', 'sector', 'spend'],
    fields: {
      name: 'Name', email: 'Email', phone: 'Phone', company: 'Company', role: 'Role',
      county: 'County', sector: 'Sector', eircode: 'Eircode', ownership: 'Premises ownership',
      spend: 'Monthly spend', model: 'Preferred model', timeframe: 'Timeframe',
      message: 'Message', source: 'Came from',
    },
  },
  estimate: {
    subject: 'New roof estimate request | auraenergy.ie',
    back: '/#calculator',
    required: ['email'],
    fields: { email: 'Email', estimate: 'Estimate' },
  },
  investor: {
    subject: 'New investor enquiry | auraenergy.ie',
    back: '/investors',
    required: ['name', 'email', 'type'],
    fields: {
      name: 'Name', email: 'Email', type: 'Investor type', amount: 'Indicative amount',
      organisation: 'Organisation', message: 'Message',
    },
  },
};
const LONG_FIELDS = new Set(['message', 'estimate']);

// Uses a Cloudflare rate limiting binding called ENQUIRY_LIMITER when one is configured.
const withinRateLimit = rateLimiter({ windowMs: RATE_WINDOW_MS, max: RATE_MAX });

export async function onRequestPost({ request, env }) {
  const wantsJson = (request.headers.get('Accept') || '').includes('application/json');
  const reply = (body, status) => (wantsJson ? json(body, status) : page(body, status));

  if (!originAllowed(request.headers.get('Origin'), request.url, env.ALLOWED_ORIGINS)) {
    return reply({ error: 'forbidden' }, 403);
  }
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  if (!(await withinRateLimit(ip, env.ENQUIRY_LIMITER))) {
    return reply({ error: 'busy' }, 429);
  }

  const data = await readBody(request);
  const name = data && Object.hasOwn(FORMS, data.form) ? data.form : null;
  if (!name) return reply({ error: 'invalid', fields: [] }, 400);
  const form = FORMS[name];
  // People never see the _honey field; bots fill it in. Say thanks and send nothing.
  if (data._honey) return reply({ ok: true, form: name }, 200);

  const values = {};
  for (const key of Object.keys(form.fields)) {
    values[key] = clean(data[key], LONG_FIELDS.has(key) ? MAX_LONG : MAX_FIELD);
  }
  const bad = form.required.filter((key) => !values[key]);
  if (values.email && !EMAIL.test(values.email)) bad.push('email');
  if (bad.length) return reply({ error: 'invalid', fields: [...new Set(bad)], form: name }, 400);

  const to = (env.ENQUIRY_TO || '').trim();
  if (!EMAIL.test(to)) {
    console.error('enquiry: ENQUIRY_TO is not set, so enquiries cannot be sent');
    return reply({ error: 'unavailable', form: name }, 503);
  }

  const message = { _subject: form.subject, _template: 'table', _captcha: 'false', _replyto: values.email };
  for (const [key, label] of Object.entries(form.fields)) {
    if (values[key]) message[label] = values[key];
  }
  const site = env.SITE_URL || DEFAULT_SITE;
  try {
    const res = await fetch(FORMSUBMIT + encodeURIComponent(to).replace('%40', '@'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Referer: site,
        Origin: new URL(site).origin,
      },
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(15_000),
    });
    const result = await res.json().catch(() => null);
    if (!res.ok || !result || String(result.success) !== 'true') {
      // Until the form is activated, FormSubmit answers with a message asking for that.
      console.error('enquiry: FormSubmit did not send it', res.status, result && result.message);
      return reply({ error: 'unavailable', form: name }, 502);
    }
  } catch (err) {
    console.error('enquiry: could not reach FormSubmit', err && err.message);
    return reply({ error: 'unavailable', form: name }, 502);
  }
  return reply({ ok: true, form: name }, 200);
}

// Form posts (with or without JavaScript) and JSON both work. Only text values are kept.
async function readBody(request) {
  try {
    if ((request.headers.get('Content-Type') || '').includes('application/json')) {
      const body = await request.json();
      return body && typeof body === 'object' && !Array.isArray(body) ? body : null;
    }
    const out = {};
    for (const [key, value] of await request.formData()) {
      if (typeof value === 'string' && !(key in out)) out[key] = value;
    }
    return out;
  } catch {
    return null;
  }
}

// Plain text: control characters removed (newlines kept), trimmed, capped.
function clean(value, max) {
  if (typeof value !== 'string') return '';
  return value.replace(/[\u0000-\u0009\u000B\u000C\u000E-\u001F\u007F]/g, ' ').trim().slice(0, max);
}

// The page a visitor sees after sending a form without JavaScript. Nothing they typed is echoed.
function page(body, status) {
  const ok = Boolean(body && body.ok);
  const back = (body && Object.hasOwn(FORMS, body.form || '') && FORMS[body.form].back) || '/';
  const title = ok ? 'Thanks, we have your details' : 'Sorry, that did not send';
  const text = ok
    ? 'The team will be in touch within one business day.'
    : body && body.error === 'invalid'
      ? 'Some details were missing or not quite right. Please go back and check the form.'
      : 'Please try again in a few minutes, or email info@auraenergy.ie.';
  const html = `<!doctype html>
<html lang="en-IE">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${title} | Aura Energy</title>
<style>
body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px; box-sizing: border-box;
  background: #F7F5F0; color: #0E0E0F; font: 17px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 460px; }
h1 { font-size: 1.6rem; line-height: 1.25; margin: 0 0 12px; }
a { color: #B83A0A; font-weight: 600; }
</style>
</head>
<body>
<main>
<h1>${title}</h1>
<p>${text}</p>
<p><a href="${back}">Back to Aura Energy</a></p>
</main>
</body>
</html>`;
  return new Response(html, {
    status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' },
  });
}
