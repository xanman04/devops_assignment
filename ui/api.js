// Credentials live only in this module's memory. Reloading requires sign-in.
let token = '';
let user = null;
export const currentUser = () => user;
export function session(value = '', person = null) {
  token = value; user = person;
  window.dispatchEvent(new Event('sessionchange'));
}
export function base(service) {
  const value = window.BASSLINE_CONFIG?.[`${service}Url`];
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== '/') throw new Error('The service URL configuration is invalid.');
  return parsed.origin;
}
export async function api(service, path, {method = 'GET', data, signal, headers = {}} = {}) {
  if (!path.startsWith('/api/')) throw new Error('Invalid API path.');
  let response;
  try {
    response = await fetch(base(service) + path, {
      method, signal: AbortSignal.any([AbortSignal.timeout(12000), ...(signal ? [signal] : [])]),
      credentials: 'omit', redirect: 'error', cache: 'no-store',
      headers: {...headers, ...(token ? {Authorization: `Bearer ${token}`} : {}), ...(data !== undefined ? {'Content-Type': 'application/json'} : {})},
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error(`${service === 'discovery' ? 'Discovery' : 'Groups'} is unreachable. Please try again.`);
  }
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && token) session();
    throw new Error(result.error || result.errors?.join(' ') || 'The request could not be completed.');
  }
  return result;
}
