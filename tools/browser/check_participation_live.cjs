// Main-only operator workflow, never CI: real UI flow, then one stopped domain at a time.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {promisify} = require('node:util');
const execute = promisify(require('node:child_process').execFile);
const {chromium} = require('playwright');
const directory = path.join(process.env.RUNNER_TEMP, 'bassline-live-evidence');
const config = JSON.parse(fs.readFileSync(path.join(directory, 'configuration.json')));
const fixture = JSON.parse(fs.readFileSync(path.join(directory, 'fixture.json')));
const evidence = {sha: config.sha, run_id: config.run_id, checks: [], started_at: new Date().toISOString()};
let phase = 'initialization';

async function control(...args) {
  await execute('python', ['tools/live_release.py', ...args], {timeout: 750000, maxBuffer: 1048576});
}
async function healthy(name) {
  const r = await fetch(config.urls[name]+'/health', {signal: AbortSignal.timeout(30000)});
  assert.equal(r.status, 200);
  const body = await r.json();
  assert.equal(body.db, 'ok'); assert.equal(body.version, config.sha);
}
async function go(page, route) {
  await page.evaluate(value => {
    if (location.hash === '#'+value) window.dispatchEvent(new HashChangeEvent('hashchange'));
    else location.hash = value;
  }, route);
}
async function login(page, username) {
  await page.goto(config.ui.replace(/\/$/, '')+'/#login');
  await page.getByLabel('Username', {exact: true}).fill(username);
  await page.getByLabel('Password', {exact: true}).fill(process.env.LIVE_CHECK_PASSWORD);
  await page.locator('main').getByRole('button', {name: 'Log in', exact: true}).click();
  await page.getByRole('button', {name: 'Save profile', exact: true}).waitFor({timeout: 60000});
}
async function screenshot(page, name) {
  await page.screenshot({path: path.join(directory, name+'.png'), fullPage: true});
}
async function fixtureIds(owner, guest) {
  return Promise.all([owner, guest].map(page => page.evaluate(async () => (await import('./api.js')).currentUser().id)));
}
async function leaveManagedGroups(page, ids) {
  await page.evaluate(async ({eventId, ids}) => {
    const {api} = await import('./api.js');
    const mine = await api('groups', '/api/groups/mine/');
    for (const group of mine.groups) {
      if (group.event_id === eventId && ids.includes(group.owner_id) && /^Release verification [0-9]+$/.test(group.name)) {
        await api('groups', `/api/groups/${group.id}/leave/`, {method: 'POST', data: {}});
      }
    }
  }, {eventId: fixture.event_id, ids});
}

(async () => {
  assert.equal(process.env.GITHUB_ACTIONS, 'true');
  assert.equal(process.env.GITHUB_REF, 'refs/heads/main');
  assert(process.env.LIVE_CHECK_PASSWORD?.length >= 32);
  const browser = await chromium.launch({headless: true});
  let owner, guest, groupId;
  let success = false;
  try {
    phase = 'authenticated participation';
    owner = await browser.newPage({viewport: {width: 1440, height: 1000}});
    guest = await browser.newPage({viewport: {width: 390, height: 844}});
    owner.on('dialog', dialog => dialog.accept()); guest.on('dialog', dialog => dialog.accept());
    await login(owner, fixture.owner_username); await login(guest, fixture.guest_username);
    // A previous failed exercise may have left memberships. Only leave reserved fixture groups.
    const ids = await fixtureIds(owner, guest);
    await leaveManagedGroups(guest, ids); await leaveManagedGroups(owner, ids);
    const groupName = 'Release verification '+config.run_id;
    await go(owner, 'create-group/'+fixture.event_id);
    await owner.getByLabel('Group name', {exact: true}).fill(groupName);
    await owner.getByLabel('Description', {exact: true}).fill('Controlled end-to-end release verification.');
    await owner.getByLabel('Who can join?', {exact: true}).selectOption('approval_required');
    await owner.getByRole('button', {name: 'Create group', exact: true}).click();
    await owner.getByRole('heading', {name: 'Chat', exact: true}).waitFor({timeout: 60000});
    assert.equal(await owner.getByRole('button', {name: 'Delete group', exact: true}).count(), 0, 'Regular owner has no moderator-delete permission');
    groupId = new URL(owner.url()).hash.split('/')[1];
    assert(/^[1-9][0-9]*$/.test(groupId));
    await go(guest, 'group/'+groupId);
    await guest.getByRole('button', {name: 'Request to join', exact: true}).click();
    await guest.locator('main').getByText('Saved.', {exact: true}).waitFor();
    await go(owner, 'groups'); await owner.getByRole('heading', {name: 'My groups', exact: true}).waitFor();
    await go(owner, 'group/'+groupId);
    await owner.getByRole('button', {name: 'Approve', exact: true}).click();
    await owner.getByText('Request approved.', {exact: true}).waitFor();
    await go(guest, 'groups'); await guest.getByRole('heading', {name: groupName, exact: true}).waitFor();
    await go(guest, 'group/'+groupId);
    await guest.getByLabel('Message', {exact: true}).fill('Hello from the controlled Azure release check.');
    await guest.getByRole('button', {name: 'Send message', exact: true}).click();
    await owner.getByRole('log').getByText('Hello from the controlled Azure release check.', {exact: true}).waitFor();
    await screenshot(owner, 'participation-desktop'); await screenshot(guest, 'participation-mobile');
    evidence.checks.push('Private group creation, request, approval and cross-service chat through the real UI');

    phase = 'Groups stopped';
    await control('stop', 'groups');
    await healthy('discovery');
    await go(owner, 'discover');
    await owner.getByRole('heading', {name: 'Artists & DJs', exact: true}).waitFor();
    await screenshot(owner, 'groups-stopped-discovery-working');
    await go(guest, 'groups');
    await guest.getByRole('heading', {name: 'Unable to load this page', exact: true}).waitFor();
    await guest.locator('main').getByText(/unreachable|temporarily unavailable|Please try again/).waitFor();
    await screenshot(guest, 'groups-stopped-clear-error');
    evidence.checks.push('Groups actually stopped; Discovery own DB health/browse work and Groups UI shows a retry error');
    await control('restore');

    phase = 'Discovery stopped';
    await control('stop', 'discovery');
    await healthy('groups');
    await go(owner, 'event-groups/'+fixture.event_id);
    await owner.getByRole('heading', {name: groupName, exact: true}).waitFor();
    await screenshot(owner, 'discovery-stopped-groups-public-working');
    const refused = guest.waitForResponse(response => response.url() === config.urls.groups+'/api/groups/mine/' && response.status() === 503);
    await go(guest, 'groups');
    await refused;
    await guest.getByRole('heading', {name: 'Unable to load this page', exact: true}).waitFor();
    await guest.locator('main').getByText(/unreachable|temporarily unavailable|Please try again/).waitFor();
    await screenshot(guest, 'discovery-stopped-protected-flow-error');
    evidence.checks.push('Discovery actually stopped; Groups public records/own DB health work, protected peer-dependent UI fails clearly');
    await control('restore');
    success = true;
  } finally {
    phase = success ? 'cleanup' : phase;
    try {
      await control('restore');
      if (owner && guest && groupId) {
        // Direct group deletion is moderator-only. Ordinary fixture members leave;
        // the existing domain rule deletes the group after its final member leaves.
        await login(owner, fixture.owner_username); await login(guest, fixture.guest_username);
        const ids = await fixtureIds(owner, guest);
        await leaveManagedGroups(guest, ids); await leaveManagedGroups(owner, ids);
        const remaining = await fetch(config.urls.groups+'/api/groups/'+groupId+'/', {signal: AbortSignal.timeout(30000)});
        assert.equal(remaining.status, 404, 'The emptied fixture group must be removed');
      }
      evidence.recovered = true;
    } catch {
      success = false; evidence.recovered = false;
      evidence.cleanup_group_id = groupId || null;
    }
    if (!success) {
      try {if (owner) await screenshot(owner, 'failed-owner'); if (guest) await screenshot(guest, 'failed-guest');} catch {}
    }
    await browser.close();
    evidence.success = success; evidence.last_phase = phase; evidence.finished_at = new Date().toISOString();
    fs.writeFileSync(path.join(directory, 'browser-evidence.json'), JSON.stringify(evidence, null, 2)+'\n');
  }
  if (!success) throw Error('Live verification or recovery failed');
  console.log('Live participation, both partial failures and recovery verified. Evidence contains no credentials.');
})().catch(() => {
  // Playwright call logs can include fill() arguments: never print raw errors.
  console.error('Live browser verification failed during '+phase+'. Inspect sanitized evidence and run recovery.');
  process.exitCode = 1;
});
