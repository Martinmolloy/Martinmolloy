// Prints the print-edition HTML to a 1280x720 PDF.
// Usage: node render.js scout.html raw.pdf
const { chromium } = require('playwright-core');
// Full Chromium rather than the headless shell, so text sets exactly as in a normal browser.
// All three scripts must use the same browser, or link positions won't match the PDF.
const LAUNCH = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : { channel: 'chromium' };
(async () => {
  const b = await chromium.launch({ ...LAUNCH, args: ['--no-sandbox', '--disable-background-networking', '--disable-component-update'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto('file://' + require('path').resolve(process.argv[2]), { waitUntil: 'load' });
  await p.evaluate(() => document.fonts.ready);
  const overflow = await p.evaluate(() => [...document.querySelectorAll('.page')].map(s => {
    const over = [...s.querySelectorAll('*')].filter(e => { const r = e.getBoundingClientRect(), pr = s.getBoundingClientRect(); return r.width && (r.bottom > pr.bottom - 40 + 0.5 && !e.closest('.foot')) ; }).map(e => e.className || e.tagName);
    return { id: s.id, over: [...new Set(over)].slice(0, 5) };
  }).filter(x => x.over.length));
  console.log('elements running into the footer:', JSON.stringify(overflow));
  await p.pdf({ path: process.argv[3], width: '1280px', height: '720px', printBackground: true, preferCSSPageSize: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await b.close();
})();
