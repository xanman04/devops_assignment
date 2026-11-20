// Read-only production smoke check, run explicitly after deployment; never by CI.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const url = process.env.BROWSER_UI_URL;
  const sha = process.env.DEPLOYED_SHA;
  assert(url?.startsWith('https://') && /^[0-9a-f]{40}$/.test(sha || ''), 'Set BROWSER_UI_URL and DEPLOYED_SHA explicitly');
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(url.replace(/\/$/, '') + '/#discover');
    assert.equal(response.status(), 200);
    await page.locator('main').getByRole('heading', {name: 'Artists & DJs', exact: true}).waitFor({timeout: 60000});
    const health = await page.evaluate(async () => {
      const result = {};
      for (const name of ['discovery', 'groups']) {
        const base = window.BASSLINE_CONFIG[name + 'Url'];
        const response = await fetch(base + '/health', {signal: AbortSignal.timeout(30000)});
        result[name] = {url: base, status: response.status, body: await response.json()};
      }
      return result;
    });
    assert.notEqual(health.discovery.url, health.groups.url, 'The two services must have distinct API addresses');
    for (const [name, result] of Object.entries(health)) {
      assert.equal(result.status, 200, name);
      assert.equal(result.body.db, 'ok', name);
      assert.equal(result.body.version, sha, name);
    }
    const artifacts = path.resolve('tools/browser/artifacts/live');
    fs.mkdirSync(artifacts, {recursive: true});
    await page.screenshot({path: path.join(artifacts, 'discover-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
    await page.screenshot({path: path.join(artifacts, 'discover-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ui: url, sha, health, checks: ['rendered Discovery', 'both APIs from browser origin', 'exact-SHA DB health', 'mobile width', 'no JavaScript exceptions']}, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
