const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_CORE_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {})});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    // Deterministic offline map fallback; live map is inspected separately.
    await context.route('https://unpkg.com/**', route => route.abort());
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => {errors.push('Unexpected dialog: '+dialog.message()); dialog.dismiss();});
    const root = page.locator('main');
    await page.goto(process.env.BROWSER_UI_URL+'/#discover');
    await root.getByRole('heading', {name: 'Discover', exact: true}).waitFor();
    await root.getByRole('link', {name: 'Browser <img src=x onerror=alert(1)> night'}).waitFor();
    assert.equal(await root.locator('img[onerror]').count(), 0);
    await page.getByRole('searchbox').fill('absent-query');
    await page.getByRole('button', {name: 'Search Discover'}).click();
    await root.getByText('No upcoming events match.', {exact: false}).waitFor();
    await page.goto(process.env.BROWSER_UI_URL+'/#genre/1');
    await root.locator('details').first().waitFor();
    await page.goto(process.env.BROWSER_UI_URL+'/#discover');
    await root.getByRole('heading', {name: 'Artists & DJs'}).waitFor();
    await root.locator('a[href^="#artist/"]').first().click();
    await root.getByRole('heading', {name: 'Tracks & sets'}).waitFor();
    await page.goto(process.env.BROWSER_UI_URL+'/#event/1');
    await root.getByRole('heading', {name: 'The sound'}).waitFor();
    await root.getByText('Safe fixture description').waitFor();
    await page.goto(process.env.BROWSER_UI_URL+'/#near');
    await root.getByText('The map could not load.', {exact: false}).waitFor();
    await root.getByRole('link', {name: 'Browser <img src=x onerror=alert(1)> night'}).waitFor();
    const artifacts = path.resolve('tools/browser/artifacts');
    fs.mkdirSync(artifacts, {recursive: true});
    await page.goto(process.env.BROWSER_UI_URL+'/#discover');
    await root.getByRole('heading', {name: 'Artists & DJs'}).waitFor();
    await page.screenshot({path: path.join(artifacts, 'discover-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile page must not overflow horizontally');
    await page.screenshot({path: path.join(artifacts, 'discover-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    await context.close();
    console.log('Public browser checks passed: real HTTP services, search, safe text, profiles, detail, map fallback, desktop/mobile.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
