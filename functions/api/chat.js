// POST /api/chat: Aura AI, the chat assistant on the website (Cloudflare Pages Function).
//
// The browser sends the conversation as plain text turns:
//   { "messages": [ { "role": "user" | "assistant", "content": "..." }, ... ] }
// and gets the reply back as server-sent events, one JSON object per event:
//   data: {"text": "..."}                    the next piece of the reply
//   data: {"done": true, "stop": "end_turn"}  the reply is complete (stop is the API's stop_reason)
//   data: {"error": "busy" | "unavailable"}   it failed; nothing follows
// Requests that fail before streaming starts get a JSON error with an HTTP status instead.
//
// The conversation lives in the visitor's browser, so it is untrusted. Only plain text goes
// back to the API: nothing signed (such as thinking blocks) round-trips through the browser.
// That keeps the history append-only between requests, which also keeps the prompt cache warm.

import Anthropic from '@anthropic-ai/sdk';
import { AURA_SYSTEM_PROMPT } from '../../lib/aura-knowledge.js';

// Override with the AURA_AI_MODEL environment variable (for example claude-haiku-5-5 to cut cost).
const DEFAULT_MODEL = 'claude-opus-5-5';
const DEFAULT_ORIGINS = 'https://auraenergy.ie,https://www.auraenergy.ie';
const MAX_TURNS = 16;              // most recent messages kept from the browser's history
const MAX_USER_CHARS = 1500;       // per visitor message (the chat box allows 1,000)
const MAX_ASSISTANT_CHARS = 4000;  // per earlier reply sent back as context
const MAX_TOTAL_CHARS = 16000;     // across everything sent
// Covers the reply and the model's thinking, which counts towards max_tokens.
// Replies are a few sentences by design; this is a hard cost ceiling for a public endpoint.
const MAX_TOKENS = 4096;
const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 12;               // requests per visitor IP per minute (best effort, per isolate)

const recent = new Map();          // ip -> timestamps of recent requests

export async function onRequestPost({ request, env }) {
  if (!originAllowed(request.headers.get('Origin'), request.url, env.ALLOWED_ORIGINS)) {
    return json({ error: 'forbidden' }, 403);
  }
  if (!env.ANTHROPIC_API_KEY) {
    console.error('aura-ai: ANTHROPIC_API_KEY is not set');
    return json({ error: 'unavailable' }, 503);
  }
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  if (!(await withinRateLimit(ip, env))) {
    return json({ error: 'busy' }, 429);
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: 'invalid' }, 400);
  }
  const history = cleanHistory(payload && payload.messages);
  if (history.error) {
    return json({ error: history.error }, 400);
  }

  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY, maxRetries: 1 });
  const stream = client.beta.messages.stream({
    model: env.AURA_AI_MODEL || DEFAULT_MODEL,
    max_tokens: MAX_TOKENS,
    // A chat reply should start quickly, and these questions don't need deep reasoning.
    output_config: { effort: 'low' },
    // If a safety classifier declines a harmless question, the API re-runs it on its
    // recommended fallback model instead of returning a refusal. Models without
    // fallback support ignore this and run alone.
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    // The knowledge base never changes between requests, so it is cached as the prefix.
    system: [{ type: 'text', text: AURA_SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    messages: history.messages,
  });

  const encoder = new TextEncoder();
  const body = new ReadableStream({
    async start(controller) {
      const send = (event) => controller.enqueue(encoder.encode('data: ' + JSON.stringify(event) + '\n\n'));
      try {
        for await (const event of stream) {
          if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
            send({ text: event.delta.text });
          }
        }
        const message = await stream.finalMessage();
        send({ done: true, stop: message.stop_reason });
      } catch (err) {
        const code = errorCode(err);
        if (code !== 'aborted') {
          send({ error: code });
        }
      } finally {
        controller.close();
      }
    },
    cancel() {
      // The visitor closed the page or started a new chat: stop generating.
      stream.abort();
    },
  });

  return new Response(body, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

// Most specific first, so retryable failures (rate limits, overloads, network) are told
// apart from configuration problems. Never logs what the visitor wrote.
function errorCode(err) {
  if (err instanceof Anthropic.APIUserAbortError) return 'aborted';
  if (err instanceof Anthropic.RateLimitError) return 'busy';
  if (err instanceof Anthropic.InternalServerError) return 'busy';      // 5xx, including overloaded
  if (err instanceof Anthropic.APIConnectionError) return 'busy';       // network failure or timeout
  if (err instanceof Anthropic.AuthenticationError || err instanceof Anthropic.PermissionDeniedError) {
    console.error('aura-ai: the API key was rejected', err.status);
    return 'unavailable';
  }
  if (err instanceof Anthropic.APIError) {
    console.error('aura-ai: API error', err.status, err.message);
    return 'unavailable';
  }
  console.error('aura-ai: unexpected error', err && err.message);
  return 'unavailable';
}

// Plain text turns only, newest kept, starting with a visitor message and ending with one.
function cleanHistory(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return { error: 'invalid' };
  const turns = [];
  for (const m of raw.slice(-MAX_TURNS)) {
    if (!m || (m.role !== 'user' && m.role !== 'assistant') || typeof m.content !== 'string') {
      return { error: 'invalid' };
    }
    const content = m.content.trim();
    if (!content) continue;
    if (m.role === 'user' && content.length > MAX_USER_CHARS) return { error: 'too_long' };
    turns.push({ role: m.role, content: m.role === 'assistant' ? content.slice(0, MAX_ASSISTANT_CHARS) : content });
  }
  if (!turns.length || turns[turns.length - 1].role !== 'user') return { error: 'invalid' };
  // Drop the oldest turns until everything fits, then make sure it still opens with the visitor.
  let total = turns.reduce((n, t) => n + t.content.length, 0);
  while (total > MAX_TOTAL_CHARS && turns.length > 1) {
    total -= turns.shift().content.length;
  }
  while (turns.length && turns[0].role !== 'user') turns.shift();
  return turns.length ? { messages: turns } : { error: 'invalid' };
}

// The chat panel calls this endpoint from the same site, so the browser's Origin header
// matches; ALLOWED_ORIGINS adds other domains (comma-separated). This stops other websites
// using the assistant from a visitor's browser. It is not authentication: rate limiting
// (below, and a Cloudflare rate limiting rule in production) is what limits direct abuse.
function originAllowed(origin, url, list) {
  if (!origin) return false;
  if (origin === new URL(url).origin) return true;
  return (list || DEFAULT_ORIGINS).split(',').map((s) => s.trim()).includes(origin);
}

// Uses a Cloudflare rate limiting binding called CHAT_LIMITER when one is configured,
// otherwise a best-effort in-memory count (each isolate keeps its own).
async function withinRateLimit(ip, env) {
  if (env.CHAT_LIMITER && typeof env.CHAT_LIMITER.limit === 'function') {
    const { success } = await env.CHAT_LIMITER.limit({ key: ip });
    return success;
  }
  const now = Date.now();
  const times = (recent.get(ip) || []).filter((t) => now - t < RATE_WINDOW_MS);
  if (times.length >= RATE_MAX) {
    recent.set(ip, times);
    return false;
  }
  times.push(now);
  recent.set(ip, times);
  if (recent.size > 5000) {
    for (const [key, list] of recent) {
      if (!list.length || now - list[list.length - 1] >= RATE_WINDOW_MS) recent.delete(key);
    }
  }
  return true;
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
