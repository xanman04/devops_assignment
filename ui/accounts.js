import {api, currentUser, session} from './api.js';
import {el, link, button, heading, message, field, formAction, date} from './dom.js';
import {cards} from './discovery.js';

export function requireAccount(root) {
  if (currentUser()) return true;
  root.append(heading('Log in to continue'), el('p', {}, 'Your events and groups belong to your account.'), link('Log in', '#login'), ' · ', link('Create account', '#register'));
  return false;
}
export function accountMenu() {
  const account = document.querySelector('#account');
  const user = currentUser();
  account.replaceChildren(...(user ? [el('span', {}, user.display_name), button('Log out', async () => {
    let failure;
    try {await api('discovery', '/api/auth/logout/', {method: 'POST', data: {}});}
    catch (error) {failure = error.message;}
    finally {session(); location.hash = 'login'; if (failure) account.append(message(`Signed out here. Server revocation failed: ${failure} The credential expires within 15 minutes.`));}
  })] : [link('Log in', '#login'), link('Create account', '#register')]));
}
export async function login(root, register, signal) {
  root.append(heading(register ? 'Create account' : 'Log in'), el('p', {}, 'Sign-in lasts up to 15 minutes in this tab. Reloading signs you out.'));
  const form = el('form', {class: 'ui-form'},
    field('Username', 'username', 'text', {required: true, maxlength: 150, autocomplete: 'username'}),
    field('Password', register ? 'password1' : 'password', 'password', {required: true, autocomplete: register ? 'new-password' : 'current-password'}),
    register && field('Repeat password', 'password2', 'password', {required: true, autocomplete: 'new-password'}),
    register && field('Display name (optional)', 'display_name', 'text', {maxlength: 80}),
    register && el('p', {}, 'Use at least 8 characters; avoid common, numeric or username-like passwords.'),
    el('button', {type: 'submit'}, register ? 'Create account' : 'Log in'));
  root.append(formAction(form, async data => {
    const fields = Object.fromEntries(data);
    if (register) {
      await api('discovery', '/api/auth/register/', {method: 'POST', data: fields, signal});
      if (signal.aborted) return;
      root.replaceChildren(heading('Account created'), message('You can now log in.'), link('Log in', '#login'));
      return;
    }
    const credential = await api('discovery', '/api/auth/token/', {method: 'POST', data: fields, signal});
    // Resolve identity before publishing the session to other screens.
    const person = await api('discovery', '/api/auth/identity/', {authToken: credential.token, signal});
    if (signal.aborted) return;
    session(credential.token, person); location.hash = 'profile';
  }));
}

const profileFields = [
  ['Display name', 'display_name', 'text', 80], ['Bio', 'bio', 'text', 280],
  ['Email (private, optional; recovery is not available)', 'email', 'email', 254],
  ['Instagram profile', 'instagram_url', 'url', 2048], ['Spotify profile', 'spotify_url', 'url', 2048],
  ['Apple Music profile', 'apple_music_url', 'url', 2048], ['SoundCloud profile', 'soundcloud_url', 'url', 2048],
];
export async function profile(root, signal) {
  if (!requireAccount(root)) return;
  const user = await api('discovery', '/api/account/', {signal});
  if (signal.aborted) return;
  root.append(heading(user.display_name || user.username, `@${user.username}`));
  const form = el('form', {class: 'ui-form'}, profileFields.map(([label, name, type, maxlength]) => field(label, name, type, {value: user[name], maxlength})), el('button', {type: 'submit'}, 'Save profile'));
  root.append(formAction(form, async data => {
    const saved = await api('discovery', '/api/account/', {method: 'PUT', data: Object.fromEntries(data), signal});
    const person = currentUser();
    sessionName(saved.display_name || saved.username, person);
  }));
}
function sessionName(name, person) {
  if (person) person.display_name = name;
  accountMenu();
}

export async function myEvents(root, signal) {
  if (!requireAccount(root)) return;
  root.append(heading('My events'), link('Create event', '#create-event', {class: 'button'}), ' · ', link('Propose a venue', '#propose-venue'));
  const data = await api('discovery', '/api/my-events/', {signal});
  if (signal.aborted) return;
  root.append(el('h2', {}, 'Followed events'), data.followed.length ? cards(data.followed) : message('No followed events yet. Explore Discover to find a night.'),
    el('h2', {}, 'Your listings'), ...data.owned.map(event => el('article', {class: 'ui-row'},
      el('div', {}, el('h3', {}, event.title), el('p', {}, `${event.venue.name} · ${date(event.starts_at, event.venue.timezone)}`), event.cancelled && el('p', {}, 'Cancelled')),
      link('Edit event', `#edit-event/${event.id}`), link('Public page', `#event/${event.id}`),
      !event.cancelled && action('Cancel event', async () => {await api('discovery', `/api/events/${event.id}/cancel/`, {method: 'POST', data: {}, signal}); location.hash = 'my-events'; window.dispatchEvent(new HashChangeEvent('hashchange'));}, 'Cancel this event? It will remain visible with a cancellation label.'))));
}

export function action(label, callback, confirmText = '') {
  const status = message(''); status.hidden = true;
  const control = button(label, async () => {
    if (confirmText && !window.confirm(confirmText)) return;
    control.disabled = true; status.hidden = false; status.textContent = 'Saving…';
    try {await callback(); status.textContent = 'Saved.';}
    catch (error) {status.textContent = error.message;}
    finally {control.disabled = false;}
  });
  return el('div', {class: 'ui-action'}, control, status);
}

function multi(label, name, items, selected = []) {
  const select = el('select', {name, multiple: true, size: 6, 'aria-label': label}, items.map(item => el('option', {value: item.id, selected: selected.includes(item.id)}, item.name)));
  return el('label', {}, label, select);
}
export async function eventForm(root, id, signal) {
  if (!requireAccount(root)) return;
  const [data, genres, artists] = await Promise.all([
    api('discovery', id ? `/api/event-form/${id}/` : '/api/event-form/', {signal}),
    api('discovery', '/api/genres/', {signal}), api('discovery', '/api/artists/', {signal}),
  ]);
  if (signal.aborted) return;
  const initial = data.initial;
  const venue = el('select', {name: 'venue', required: true, 'aria-label': 'Venue'}, el('option', {value: ''}, 'Choose a venue'), data.venues.map(v => el('option', {value: v.id, selected: initial.venue === v.id}, `${v.name} · ${v.timezone}`)));
  const form = el('form', {class: 'ui-form ui-form-wide'},
    field('Event title', 'title', 'text', {required: true, maxlength: 200, value: initial.title || ''}),
    el('label', {}, 'Venue', venue), el('p', {}, 'Times use the selected venue’s timezone. Changing venue reinterprets the entered times. Ambiguous or missing daylight-saving times are rejected.'),
    field('Start (venue local time)', 'starts_at', 'datetime-local', {required: true, value: initial.starts_at || ''}),
    field('End (venue local time)', 'ends_at', 'datetime-local', {required: true, value: initial.ends_at || ''}),
    el('label', {}, 'Description', el('textarea', {name: 'description', required: true, rows: 5}, initial.description || '')),
    field('Tickets URL (optional)', 'ticket_url', 'url', {value: initial.ticket_url || '', maxlength: 2048}),
    multi('Genres (choose at least one)', 'categories', genres.categories, initial.categories),
    multi('Subgenres (optional)', 'tags', genres.tags, initial.tags), multi('Artists & DJs (optional)', 'performers', artists.artists, initial.performers),
    el('p', {}, 'Use Ctrl / Command to select multiple options. A pending venue keeps its event unpublished until review.'),
    el('button', {type: 'submit'}, id ? 'Save event' : 'Create event'));
  root.append(heading(id ? 'Edit event' : 'Create event'), formAction(form, async fields => {
    const values = Object.fromEntries(fields);
    for (const name of ['categories', 'tags', 'performers']) values[name] = fields.getAll(name).map(Number);
    const result = await api('discovery', id ? `/api/event-form/${id}/` : '/api/event-form/', {method: id ? 'PUT' : 'POST', data: values, signal});
    root.replaceChildren(heading('Event saved'), message('Your listing is saved. Pending venues need approval before public discovery.'), link('My events', '#my-events'), ' · ', link('Public event page', `#event/${result.id}`));
  }));
}

export async function proposeVenue(root, signal) {
  if (!requireAccount(root)) return;
  const form = el('form', {class: 'ui-form'}, field('Venue name', 'name', 'text', {required: true, maxlength: 160}),
    field('Address', 'address'), field('Latitude (decimal)', 'latitude', 'number', {step: '0.000001', min: -90, max: 90, required: true}),
    field('Longitude (decimal)', 'longitude', 'number', {step: '0.000001', min: -180, max: 180, required: true}),
    field('IANA timezone, for example Europe/Madrid', 'timezone', 'text', {required: true}), el('button', {type: 'submit'}, 'Submit for review'));
  root.append(heading('Propose a venue', 'New venues require moderator approval before their events appear publicly.'), formAction(form, async fields => {
    await api('discovery', '/api/venues/propose/', {method: 'POST', data: Object.fromEntries(fields), signal});
    root.replaceChildren(heading('Venue submitted'), message('You can use the pending venue in your own listings.'), link('Create event', '#create-event'));
  }));
}

export async function notifications(root, signal) {
  if (!requireAccount(root)) return;
  root.append(heading('Notifications'));
  // Failure is local to each domain's inbox; Discovery notifications remain usable when Groups is down.
  for (const service of ['discovery', 'groups']) {
    if (signal.aborted) return;
    const section = el('section', {}, el('h2', {}, service === 'discovery' ? 'Events' : 'Groups')); root.append(section);
    try {
      const result = await api(service, '/api/notifications/', {signal});
      if (signal.aborted) return;
      section.append(...(result.notifications.length ? result.notifications.map(n => el('article', {class: 'ui-row'},
        el('div', {}, el('p', {}, n.summary), el('small', {}, date(n.created_at))),
        n.read_at ? el('span', {}, 'Read') : action('Mark read', async () => {await api(service, `/api/notifications/${n.id}/read/`, {method: 'POST', data: {}, signal});}))) : [message('No notifications yet.')]));
    } catch (error) {if (!signal.aborted) section.append(message(error.message));}
  }
}

export function participation(root, id, signal) {
  const section = root.querySelector('#event-participation');
  if (!section || !currentUser()) return;
  section.prepend(action('Follow event', () => api('discovery', `/api/events/${id}/follow/`, {method: 'POST', data: {}, signal})),
    action('Unfollow event', () => api('discovery', `/api/events/${id}/unfollow/`, {method: 'POST', data: {}, signal})));
  const form = el('form', {class: 'ui-form'}, el('label', {}, 'Reason', el('select', {name: 'reason', 'aria-label': 'Reason'},
    [['incorrect_information', 'Incorrect information'], ['spam_scam', 'Spam or scam'], ['safety_concern', 'Safety concern'], ['other', 'Other']].map(([value, label]) => el('option', {value}, label)))),
    el('label', {}, 'Explanation', el('textarea', {name: 'explanation', rows: 3, maxlength: 2000})), el('button', {type: 'submit'}, 'Report event'));
  section.append(el('details', {}, el('summary', {}, 'Report a problem'), formAction(form, fields => api('discovery', `/api/events/${id}/report/`, {method: 'POST', data: Object.fromEntries(fields), signal}))));
}
