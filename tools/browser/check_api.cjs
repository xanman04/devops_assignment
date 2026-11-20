// Dependency-free request/session regressions; fetch responses deliberately vary.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  global.window = new EventTarget();
  window.BASSLINE_CONFIG = {discoveryUrl: 'https://discovery.example', groupsUrl: 'https://groups.example'};
  const source = fs.readFileSync(path.resolve(__dirname, '../../ui/api.js'), 'utf8');
  const {api, session, currentUser} = await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const originalFetch = global.fetch;
  try {
    let finish;
    global.fetch = () => new Promise(resolve => {finish = resolve;});
    session('old-token', {id: 1});
    const delayed = api('discovery', '/api/account/').catch(error => error);
    session('new-token', {id: 2});
    finish(new Response('<html>Expired</html>', {status: 401}));
    assert((await delayed) instanceof Error);
    assert.equal(currentUser().id, 2, 'An older 401 cannot clear a newer login');

    global.fetch = async () => new Response('<html>Expired</html>', {status: 401});
    await assert.rejects(api('discovery', '/api/account/'), /401/);
    assert.equal(currentUser(), null, 'A current non-JSON 401 must clear the session');
    global.fetch = async () => new Response('<html>Gateway unavailable</html>', {status: 502});
    await assert.rejects(api('groups', '/api/groups/mine/'), /502/);
    global.fetch = async () => new Response('<html>App port is not ready</html>', {status: 503});
    await assert.rejects(api('groups', '/api/groups/mine/'), /starting up.*try again/i);
    global.fetch = async () => new Response(null, {status: 204});
    assert.deepEqual(await api('discovery', '/api/auth/logout/', {method: 'POST'}), {});

    session('current', {id: 3});
    global.fetch = async (_url, options) => {
      assert.equal(options.headers.Authorization, 'Bearer provisional');
      assert.equal(options.credentials, 'omit');
      return Response.json({id: 4});
    };
    assert.deepEqual(await api('discovery', '/api/auth/identity/', {authToken: 'provisional'}), {id: 4});
    assert.equal(currentUser().id, 3, 'Provisional identity lookup does not publish a session');
    global.fetch = async (_url, options) => {
      assert(options.signal.aborted);
      throw new DOMException('Aborted', 'AbortError');
    };
    const controller = new AbortController(); controller.abort();
    await assert.rejects(api('discovery', '/api/account/', {signal: controller.signal}), {name: 'AbortError'});
    assert.equal(currentUser().id, 3);
    console.log('Request/session regressions passed: stale/current HTML 401, gateway HTML, 204, provisional identity and cancellation.');
  } finally {session(); global.fetch = originalFetch;}
})().catch(error => {console.error(error); process.exitCode = 1;});
