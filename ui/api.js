// Credentials live only in this module's memory. Reloading requires sign-in.
let token = '';
let user = null;
let expiry;
export const currentUser = () => user;
export function session(value = '', person = null) {
  clearTimeout(expiry);
  token = value; user = person;
  if (token) expiry = setTimeout(() => session(), 900000);
  window.dispatchEvent(new Event('sessionchange'));
}
export function base(service) {
  const value = window.BASSLINE_CONFIG?.[`${service}Url`];
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/') throw new Error('The service URL configuration is invalid.');
  return parsed.origin;
}
export async function api(service, path, {method = 'GET', data, signal, headers = {}, authToken} = {}) {
  if (!path.startsWith('/api/')) throw new Error('Invalid API path.');
  const sentToken = authToken ?? token;
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timeout = setTimeout(abort, 12000);
  if (signal?.aborted) abort();
  else signal?.addEventListener('abort', abort, {once: true});
  let response;
  try {
    response = await fetch(base(service) + path, {
      method, signal: controller.signal,
      credentials: 'omit', redirect: 'error', cache: 'no-store',
      headers: {...headers, ...(sentToken ? {Authorization: `Bearer ${sentToken}`} : {}), ...(data !== undefined ? {'Content-Type': 'application/json'} : {})},
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
    // A late response for a previous login cannot clear a newer account's session.
    if (response.status === 401 && sentToken && sentToken === token) session();
    let result = {};
    if (response.status !== 204) {
      try {result = await response.json();}
      catch {
        if (response.ok) throw new Error('The service returned an invalid response. Please try again.');
      }
    }
    if (response.status === 503) throw new Error('The service is starting up or temporarily unavailable. Please try again shortly.');
    if (!response.ok) throw new Error(result?.error || result?.errors?.join(' ') || `The service returned ${response.status}. Please try again.`);
    return result;
  } catch (error) {
    if (signal?.aborted) throw error;
    if (!response) throw new Error(`${service === 'discovery' ? 'Discovery' : 'Groups'} is unreachable. Please try again.`);
    throw error;
  } finally {
    clearTimeout(timeout); signal?.removeEventListener('abort', abort);
  }
}
