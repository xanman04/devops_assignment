import {el, heading, message, link} from './dom.js';
import {discover, eventDetail, genre, artist, near} from './discovery.js';

let active;
export async function route() {
  active?.abort(); active = new AbortController();
  const signal = active.signal;
  const root = document.querySelector('main');
  const filters = document.querySelector('#filters');
  root.replaceChildren(); filters.replaceChildren(); root.className = 'live-main ui-page';
  const [path, query = ''] = location.hash.slice(1).split('?');
  const [name = 'near', id] = (path || 'near').split('/');
  document.querySelectorAll('.live-nav a').forEach(a => a.hash === `#${name}` ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  document.title = 'Bassline';
  document.querySelector('#site-search').value = name === 'discover' ? new URLSearchParams(query).get('q') || '' : '';
  const loading = message('Loading…'); root.append(loading);
  try {
    if (name === 'near') await near(root, filters, signal);
    else if (name === 'discover') await discover(root, new URLSearchParams(query).get('q'), signal);
    else if (name === 'event' && /^\d+$/.test(id)) await eventDetail(root, id, signal);
    else if (name === 'genre' && /^\d+$/.test(id)) await genre(root, id, signal);
    else if (name === 'artist' && /^\d+$/.test(id)) await artist(root, id, signal);
    else root.append(heading('Coming next'), el('p', {}, 'Account and group screens are being connected.'), link('Explore Discover', '#discover'));
  } catch (error) {
    if (!signal.aborted) root.replaceChildren(heading('Unable to load this page'), message(error.message), link('Try Discover', '#discover'));
  } finally {loading.remove();}
}
document.querySelector('#search').addEventListener('submit', event => {
  event.preventDefault(); location.hash = `discover?${new URLSearchParams(new FormData(event.currentTarget))}`;
});
window.addEventListener('hashchange', route);
route();
