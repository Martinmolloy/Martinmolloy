// Records every link in the print-edition HTML: its page, where it sits and where it points.
// Usage: node anchors.js scout.html anchors.json
const { chromium } = require('playwright-core');
// Full Chromium rather than the headless shell, so text sets exactly as in a normal browser.
// All three scripts must use the same browser, or link positions won't match the PDF.
const LAUNCH = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : { channel: 'chromium' };
const fs = require('fs');
const path = require('path');
(async () => {
  const b = await chromium.launch({ ...LAUNCH, args: ['--no-sandbox', '--disable-background-networking'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto('file://' + path.resolve(process.argv[2]));
  await p.evaluate(() => document.fonts.ready);
  const out = await p.evaluate(() => [...document.querySelectorAll('section.page')].map((s, i) => {
    const pr = s.getBoundingClientRect();
    return { i, id: s.id, links: [...s.querySelectorAll('a[href]')].map(a => { const rects = [...a.getClientRects()].filter(r => r.width && r.height).map(r => ({ x: r.left - pr.left, y: r.top - pr.top, w: r.width, h: r.height })); return { href: a.getAttribute('href'), rects, text: (a.getAttribute('aria-label') || a.innerText).trim().slice(0, 40) }; }) };
  }));
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
  await b.close();
})();
