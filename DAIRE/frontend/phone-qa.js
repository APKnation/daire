// Deeper phone-width polish probe for the dashboard.
const puppeteer = require('/home/egovridc/.npm/_npx/7d92d9a2d2ccc630/node_modules/puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2 });
  await page.goto('http://localhost:4200/', { waitUntil: 'networkidle2', timeout: 30000 });
  await page.type('#username-input', 'qa_mobile');
  await page.type('#password-input', 'QaMobile!2026');
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }).catch(() => {}), page.click('#login-submit')]);
  await page.goto('http://localhost:4200/dashboard', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise((r) => setTimeout(r, 1500));

  const findings = await page.evaluate(() => {
    const clipped = [];
    const smallTargets = [];
    const all = [...document.querySelectorAll('main *')];
    for (const el of all) {
      if (!(el instanceof HTMLElement) || !el.offsetParent) continue;
      const inScroller = !!el.closest('.overflow-x-auto');
      // Text cut off without intentional truncation
      if (!inScroller && el.children.length === 0 && el.textContent.trim()
          && el.scrollWidth > el.clientWidth + 2 && !el.classList.contains('truncate')) {
        clipped.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 50), over: el.scrollWidth - el.clientWidth });
      }
      // Touch targets below 40px
      if ((el.tagName === 'BUTTON' || el.tagName === 'A') && el.offsetParent) {
        const r = el.getBoundingClientRect();
        if (r.height > 0 && r.height < 36) smallTargets.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 30), h: Math.round(r.height) });
      }
    }
    // KPI number fit: does the strong fit its card?
    const kpis = [...document.querySelectorAll('main section article.card')].slice(0, 4).map((c) => {
      const strong = c.querySelector('strong');
      return {
        label: c.querySelector('p')?.textContent.trim(),
        cardW: Math.round(c.clientWidth),
        fits: strong ? strong.scrollWidth <= strong.clientWidth + 1 : true,
      };
    });
    return { clipped, smallTargets, kpis };
  });

  await page.screenshot({ path: 'phone-375-top.png' });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await new Promise((r) => setTimeout(r, 400));
  await page.screenshot({ path: 'phone-375-bottom.png' });
  console.log(JSON.stringify(findings, null, 2));
  await browser.close();
})();
