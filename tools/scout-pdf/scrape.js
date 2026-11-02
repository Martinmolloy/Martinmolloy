// Runs a Scout page at every drive-time / minimum-size setting and saves what it shows.
// Usage: node scrape.js <path to the Scout page's index.html> <data.json>
const { chromium } = require('playwright-core');
// Full Chromium rather than the headless shell, so text sets exactly as in a normal browser.
// All three scripts must use the same browser, or link positions won't match the PDF.
const LAUNCH = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : { channel: 'chromium' };
const fs = require('fs');
const path = require('path');

const SRC = 'file://' + path.resolve(process.argv[2]);
const DRIVES = [60, 90, 120], SIZES = [50, 100, 250];

async function run(page, drive, size) {
  await page.goto(SRC);
  await page.click(`button[data-set="drive"][data-val="${drive}"]`);
  await page.click(`button[data-set="minKwp"][data-val="${size}"]`);
  await page.getByRole('button', { name: /Run Scout/i }).first().click();
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: /Skip to results/i }).click();
  await page.waitForFunction(() => /Sweep complete/.test(document.getElementById('status').innerText), null, { timeout: 15000 });
  await page.waitForTimeout(800);
  return page.evaluate(() => {
    const q = s => document.querySelector(s), t = el => (el ? el.innerText.trim() : '');
    const radar = q('#radar').getBoundingClientRect(), lim = q('#limit').getBoundingClientRect();
    return {
      status: t(q('#status')),
      counts: { read: t(q('#nRead')), keep: t(q('#nKeep')), drop: t(q('#nDrop')), ppl: t(q('#nPpl')) },
      limitFrac: lim.width / radar.width, limitLbl: t(q('#limitLbl')),
      blips: [...q('#blips').children].map(b => ({ title: b.getAttribute('title'), left: parseFloat(b.style.left), top: parseFloat(b.style.top), keep: b.classList.contains('is-keep'), drop: b.classList.contains('is-drop') })),
      rows: [...q('#log').querySelectorAll('button.row')].map(r => ({ id: r.dataset.id, n: t(r.querySelector('.row__n')), name: t(r.querySelector('.row__co')), keep: r.querySelector('.pill--keep') !== null, pill: t(r.querySelector('.pill')), why: t(r.querySelector('.row__why')) })),
      plan: {
        head: t(q('#pHead')), why: t(q('#pWhy')),
        figs: [...document.querySelectorAll('#plan .fig')].map(f => ({ k: t(f.querySelector('dt')), v: t(f.querySelector('dd')) })),
        spec: (() => { const out = []; const dl = q('#spec'); if (!dl) return out; let k = null; for (const el of dl.children) { if (el.tagName === 'DT') k = t(el); else if (el.tagName === 'DD') out.push({ k, v: t(el) }); else if (el.querySelector('dt')) out.push({ k: t(el.querySelector('dt')), v: t(el.querySelector('dd')) }); } return out; })(),
        tSites: t(q('#tSites')), tPeople: t(q('#tPeople')),
        shortN: t(q('#shortN')),
        short: [...q('#shortBody').querySelectorAll('tr')].map(tr => [...tr.children].map(td => td.innerText.trim())),
        next: t(q('#nextTxt')),
      },
    };
  });
}

async function card(page) {
  return page.evaluate(() => {
    const q = s => document.querySelector(s), t = el => (el ? el.innerText.trim() : '');
    const vis = el => el && !el.hidden && getComputedStyle(el).display !== 'none';
    return {
      idx: t(q('#cIdx')), verdict: t(q('#cVerdict')), verdictClass: q('#cVerdict').className,
      name: t(q('#cName')), tags: [...q('#cTags').children].map(s => ({ text: t(s), cls: s.className })),
      plate: q('#cPlate').outerHTML, plateCap: t(q('#cPlateCap')),
      stats: { kwp: t(q('#vKwp')), out: t(q('#vOut')), use: t(q('#vUse')), bill: t(q('#vBill')) },
      checks: [...q('#cChecks').children].map(li => ({ cls: li.className, k: t(li.querySelector('.check__k')), v: t(li.querySelector('.check__v')) })),
      peopleN: t(q('#cPeopleN')),
      people: [...q('#cPeople').children].map(li => ({ cls: li.className, av: t(li.querySelector('.av')), name: (li.querySelector('.person__n')?.firstChild?.textContent || '').trim(), role: t(li.querySelector('.person__r')).replace(/^,\s*/, ''), tag: t(li.querySelector('.tag')), tagCls: li.querySelector('.tag')?.className || '', why: t(li.querySelector('.person__why')) })),
      skip: vis(q('#cSkip')) ? t(q('#cSkip')) : '',
      why: vis(q('#cWhy')) ? t(q('#cWhy')) : '',
    };
  });
}

(async () => {
  const browser = await chromium.launch({ ...LAUNCH, args: ['--no-sandbox', '--disable-background-networking'] });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();

  // The client, the headline and the settings the page opens with
  await page.goto(SRC);
  const data = await page.evaluate(() => {
    const c = k => { const el = document.querySelector(`[data-c="${k}"]`); return el ? el.innerText.trim() : ''; };
    const on = set => Number(document.querySelector(`button[data-set="${set}"][aria-pressed="true"]`).dataset.val);
    return {
      title: document.title,
      client: { name: c('name'), depot: c('depot'), town: c('town'), contactName: c('contactName'), contactEmail: c('contactEmail') },
      hook: document.querySelector('.brief__h').innerText.trim(),
      defaults: { drive: on('drive'), size: on('minKwp') },
    };
  });
  data.settings = [];
  data.sites = {};
  for (const d of DRIVES) for (const s of SIZES) {
    const r = await run(page, d, s);
    data.settings.push({ drive: d, size: s, ...r });
    console.log(`${d} min / ${s} kWp: ${r.status}`);
  }
  // Full site records at the page's own starting settings
  await run(page, data.defaults.drive, data.defaults.size);
  const ids = await page.$$eval('#log button.row', rs => rs.map(r => r.dataset.id));
  for (const id of ids) {
    await page.click(`#log button.row[data-id="${id}"]`);
    await page.waitForTimeout(350);
    data.sites[id] = await card(page);
  }
  // Styling the PDF reuses: the page's fonts and its radar / roof-plan rules
  data.css = await page.evaluate(() => {
    const out = { fontFaces: [], rules: [] };
    for (const sh of document.styleSheets) for (const r of sh.cssRules) {
      if (r instanceof CSSFontFaceRule) out.fontFaces.push(r.cssText);
      else if (r instanceof CSSStyleRule && /^\.(rings|plate)\b/.test(r.selectorText)) out.rules.push(r.cssText);
    }
    return out;
  });
  data.rings = await page.$eval('#rings', e => e.outerHTML);
  fs.writeFileSync(process.argv[3], JSON.stringify(data, null, 1));
  console.log(`${data.client.name}: ${Object.keys(data.sites).length} sites, starting at ${data.defaults.drive} min / ${data.defaults.size} kWp`);
  await browser.close();
})();
