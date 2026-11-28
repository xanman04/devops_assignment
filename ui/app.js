import {el, heading, message, link} from './dom.js';
import {discover, eventDetail, genre, artist, near} from './discovery.js';
import * as accounts from './accounts.js';
import * as groups from './groups.js';
import {moderation} from './moderation.js';
import {listeningLinks} from './references.js';

let active;
export async function route() {
  active?.abort(); active = new AbortController();
  const signal = active.signal;
  const root = document.querySelector('main');
  const filters = document.querySelector('#filters');
  root.replaceChildren(); filters.replaceChildren(); root.className = 'live-main ui-page';
  const [path, query = ''] = location.hash.slice(1).split('?');
  const [name = 'near', id, part] = (path || 'near').split('/');
  const section = ['group', 'create-group', 'edit-group', 'event-groups'].includes(name) ? 'groups'
    : ['event', 'genre', 'artist'].includes(name) ? 'discover'
    : ['create-event', 'edit-event', 'event-references', 'propose-venue'].includes(name) ? 'my-events'
    : ['login', 'register', 'moderation'].includes(name) ? 'profile' : name;
  document.querySelectorAll('.live-nav a').forEach(a => a.hash === `#${section}` ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  document.title = 'Bassline';
  document.querySelector('#site-search').value = name === 'discover' ? new URLSearchParams(query).get('q') || '' : '';
  const loading = message('Loading…'); root.append(loading);
  try {
    if (name === 'near') await near(root, filters, signal);
    else if (name === 'discover') await discover(root, new URLSearchParams(query).get('q'), signal);
    else if (name === 'event' && /^\d+$/.test(id)) {await eventDetail(root, id, signal); if (!signal.aborted) accounts.participation(root, id, signal);}
    else if (name === 'genre' && /^[-\w]+$/.test(id)) await genre(root, id, signal, part);
    else if (name === 'artist' && /^\d+$/.test(id)) await artist(root, id, signal);
    else if (name === 'login' || name === 'register') await accounts.login(root, name === 'register', signal);
    else if (name === 'profile') await accounts.profile(root, signal);
    else if (name === 'moderation') await moderation(root, signal);
    else if (name === 'my-events') await accounts.myEvents(root, signal);
    else if (name === 'create-event' || name === 'edit-event') await accounts.eventForm(root, name === 'edit-event' ? id : null, signal);
    else if (name === 'event-references' && /^\d+$/.test(id)) await listeningLinks(root, id, signal);
    else if (name === 'propose-venue') await accounts.proposeVenue(root, signal);
    else if (name === 'notifications') await accounts.notifications(root, signal);
    else if (name === 'groups') await groups.mine(root, signal);
    else if (name === 'event-groups' && /^\d+$/.test(id)) await groups.eventGroups(root, id, signal);
    else if (name === 'group' && /^\d+$/.test(id)) await groups.detail(root, id, signal);
    else if (name === 'create-group') await groups.groupForm(root, id, null, signal);
    else if (name === 'edit-group') await groups.groupForm(root, null, id, signal);
    else root.append(heading('Page not found'), link('Explore Discover', '#discover'));
  } catch (error) {
    if (!signal.aborted) root.replaceChildren(heading('Unable to load this page'), message(error.message), link('Try Discover', '#discover'));
  } finally {loading.remove();}
}
document.querySelector('#search').addEventListener('submit', event => {
  event.preventDefault(); location.hash = `discover?${new URLSearchParams(new FormData(event.currentTarget))}`;
});
window.addEventListener('hashchange', route);
window.addEventListener('sessionchange', () => {
  accounts.accountMenu();
  // Abort protected reads/polling and discard private DOM immediately on expiry/logout.
  active?.abort(); document.querySelector('main').replaceChildren();
  if (location.hash !== '#login' && location.hash !== '#register') route();
});
accounts.accountMenu();
route();
