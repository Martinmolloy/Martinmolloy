// Tests for functions/api/enquiry.js with FormSubmit replaced by a local fake, so nothing is
// emailed. Run with: npm test
import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { onRequestPost } from '../functions/api/enquiry.js';

const realFetch = globalThis.fetch;
let calls;
let nextIp = 1;

beforeEach(() => { calls = []; });
afterEach(() => { globalThis.fetch = realFetch; });

function fakeFormSubmit(reply = { success: 'true', message: 'The form was submitted successfully.' }, status = 200) {
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    if (reply instanceof Error) throw reply;
    return new Response(JSON.stringify(reply), { status, headers: { 'content-type': 'application/json' } });
  };
}

const ENV = { ENQUIRY_TO: 'leads@example.com' };
const QUOTE = {
  form: 'quote', name: 'Aoife Byrne', email: 'aoife@example.ie', phone: '01 555 0100', company: 'Byrne Foods',
  county: 'Dublin', sector: 'Manufacturing', spend: '€5,000 to €10,000', model: 'Solar PPA',
  message: 'Two buildings,\nboth with flat roofs.', source: 'CTA: hero',
};

function post(fields, { origin = 'https://aura-energy.pages.dev', ip, accept = 'application/json', as = 'form' } = {}) {
  const headers = { Accept: accept, 'CF-Connecting-IP': ip || `198.51.100.${nextIp++}` };
  if (origin) headers.Origin = origin;
  let body;
  if (as === 'json') {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(fields);
  } else {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    body = new URLSearchParams(fields).toString();
  }
  return new Request('https://aura-energy.pages.dev/api/enquiry', { method: 'POST', headers, body });
}

const sent = () => JSON.parse(calls[0].init.body);

test('a quote request is emailed through FormSubmit with labelled fields', async () => {
  fakeFormSubmit();
  const res = await onRequestPost({ request: post({ ...QUOTE, _next: 'https://evil.example', extra: 'dropped' }), env: ENV });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, form: 'quote' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://formsubmit.co/ajax/leads@example.com');
  assert.equal(calls[0].init.headers.Referer, 'https://auraenergy.ie/');
  assert.deepEqual(sent(), {
    _subject: 'New quote request | auraenergy.ie', _template: 'table', _captcha: 'false', _replyto: 'aoife@example.ie',
    Name: 'Aoife Byrne', Email: 'aoife@example.ie', Phone: '01 555 0100', Company: 'Byrne Foods', County: 'Dublin',
    Sector: 'Manufacturing', 'Monthly spend': '€5,000 to €10,000', 'Preferred model': 'Solar PPA',
    Message: 'Two buildings,\nboth with flat roofs.', 'Came from': 'CTA: hero',
  });
});

test('the estimate and investor forms work too, and JSON bodies are accepted', async () => {
  fakeFormSubmit();
  let res = await onRequestPost({ request: post({ form: 'estimate', email: 'ops@example.ie', estimate: 'Manufacturing · 436 kWp' }), env: ENV });
  assert.deepEqual(await res.json(), { ok: true, form: 'estimate' });
  assert.equal(sent()._subject, 'New roof estimate request | auraenergy.ie');
  assert.equal(sent().Estimate, 'Manufacturing · 436 kWp');

  calls = [];
  res = await onRequestPost({ request: post({ form: 'investor', name: 'Sam', email: 'sam@example.com', type: 'A family office' }, { as: 'json' }), env: ENV });
  assert.deepEqual(await res.json(), { ok: true, form: 'investor' });
  assert.equal(sent()._subject, 'New investor enquiry | auraenergy.ie');
  assert.equal(sent()['Investor type'], 'A family office');
});

test('the destination address only comes from the ENQUIRY_TO setting', async () => {
  fakeFormSubmit();
  for (const env of [{}, { ENQUIRY_TO: 'not an address' }]) {
    const res = await onRequestPost({ request: post(QUOTE), env });
    assert.equal(res.status, 503);
    assert.deepEqual(await res.json(), { error: 'unavailable', form: 'quote' });
  }
  assert.equal(calls.length, 0);
});

test('missing or wrong details are sent back before anything is emailed', async () => {
  fakeFormSubmit();
  let res = await onRequestPost({ request: post({ form: 'quote', name: 'Aoife', email: 'aoife@example.ie' }), env: ENV });
  assert.equal(res.status, 400);
  assert.deepEqual(await res.json(), { error: 'invalid', fields: ['company', 'county', 'sector', 'spend'], form: 'quote' });

  res = await onRequestPost({ request: post({ ...QUOTE, email: 'aoife at example' }), env: ENV });
  assert.deepEqual(await res.json(), { error: 'invalid', fields: ['email'], form: 'quote' });

  for (const form of ['', 'contact', '__proto__', 'toString']) {
    res = await onRequestPost({ request: post({ ...QUOTE, form }), env: ENV });
    assert.equal(res.status, 400, form);
  }
  res = await onRequestPost({ request: post(['not', 'an', 'object'], { as: 'json' }), env: ENV });
  assert.equal(res.status, 400);
  assert.equal(calls.length, 0);
});

test('bots that fill the hidden field are thanked and nothing is sent', async () => {
  fakeFormSubmit();
  const res = await onRequestPost({ request: post({ ...QUOTE, _honey: 'http://spam.example' }), env: ENV });
  assert.deepEqual(await res.json(), { ok: true, form: 'quote' });
  assert.equal(calls.length, 0);
});

test('long or messy values are cleaned and capped', async () => {
  fakeFormSubmit();
  await onRequestPost({ request: post({ ...QUOTE, name: '  Aoife\u0000 Byrne\u0007  ', company: 'x'.repeat(500), message: 'm'.repeat(5000) }), env: ENV });
  assert.equal(sent().Name, 'Aoife  Byrne');
  assert.equal(sent().Company.length, 300);
  assert.equal(sent().Message.length, 3000);
});

test('if FormSubmit refuses or is unreachable, the visitor is told it did not send', async () => {
  fakeFormSubmit({ success: 'false', message: 'This form needs Activation.' });
  let res = await onRequestPost({ request: post(QUOTE), env: ENV });
  assert.equal(res.status, 502);
  assert.deepEqual(await res.json(), { error: 'unavailable', form: 'quote' });

  fakeFormSubmit({ message: 'Server error' }, 500);
  res = await onRequestPost({ request: post(QUOTE), env: ENV });
  assert.equal(res.status, 502);

  fakeFormSubmit(new TypeError('fetch failed'));
  res = await onRequestPost({ request: post(QUOTE), env: ENV });
  assert.equal(res.status, 502);
});

test('without JavaScript the visitor gets a short page back, never the address', async () => {
  fakeFormSubmit();
  let res = await onRequestPost({ request: post(QUOTE, { accept: 'text/html' }), env: ENV });
  assert.equal(res.status, 200);
  assert.match(res.headers.get('content-type'), /text\/html/);
  let html = await res.text();
  assert.match(html, /Thanks, we have your details/);
  assert.match(html, /href="\/#quote"/);
  assert.equal(html.includes('leads@example.com'), false);

  res = await onRequestPost({ request: post({ ...QUOTE, email: '' }, { accept: 'text/html' }), env: ENV });
  assert.equal(res.status, 400);
  html = await res.text();
  assert.match(html, /did not send/);
  assert.match(html, /check the form/);
});

test('SITE_URL sets the page FormSubmit sees', async () => {
  fakeFormSubmit();
  await onRequestPost({ request: post(QUOTE), env: { ...ENV, SITE_URL: 'https://www.auraenergy.ie/' } });
  assert.equal(calls[0].init.headers.Referer, 'https://www.auraenergy.ie/');
  assert.equal(calls[0].init.headers.Origin, 'https://www.auraenergy.ie');
});

test('other websites are refused', async () => {
  fakeFormSubmit();
  for (const origin of ['https://evil.example', null]) {
    const res = await onRequestPost({ request: post(QUOTE, { origin }), env: ENV });
    assert.equal(res.status, 403);
  }
  const live = await onRequestPost({ request: post(QUOTE, { origin: 'https://auraenergy.ie' }), env: ENV });
  assert.equal(live.status, 200);
  assert.equal(calls.length, 1);
});

test('each visitor can send 6 enquiries in 10 minutes', async () => {
  fakeFormSubmit();
  const ip = '203.0.113.99';
  for (let i = 0; i < 6; i++) {
    const res = await onRequestPost({ request: post(QUOTE, { ip }), env: ENV });
    assert.equal(res.status, 200);
  }
  const blocked = await onRequestPost({ request: post(QUOTE, { ip }), env: ENV });
  assert.equal(blocked.status, 429);
  assert.deepEqual(await blocked.json(), { error: 'busy' });
  assert.equal(calls.length, 6);
});

test('a configured Cloudflare rate limiter is used instead', async () => {
  fakeFormSubmit();
  const env = { ...ENV, ENQUIRY_LIMITER: { limit: async () => ({ success: false }) } };
  const res = await onRequestPost({ request: post(QUOTE), env });
  assert.equal(res.status, 429);
  assert.equal(calls.length, 0);
});
