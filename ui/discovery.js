import {api, base} from './api.js';
import {el, link, external, heading, message, date, button} from './dom.js';

function bundled(path) {
  return path && !path.startsWith('/') && !path.split('/').includes('..') && /^[a-zA-Z0-9_./-]+$/.test(path) ? `assets/${path}` : '';
}
function artwork(event) {
  return event.has_poster ? `${base('discovery')}/api/events/${event.id}/poster/` : bundled(event.demo_poster);
}
export function cards(events) {
  return el('div', {class: 'ui-events'}, events.map(event => {
    const image = artwork(event);
    return el('article', {class: 'ui-event'}, image && link(el('img', {src: image, alt: '', loading: 'lazy'}), `#event/${event.id}`),
      el('div', {}, el('p', {class: 'ui-meta'}, date(event.starts_at, event.venue.timezone)),
        el('h2', {}, link(event.title, `#event/${event.id}`)), el('p', {}, event.venue.name),
        el('div', {class: 'ui-tags'}, event.categories.map(c => link(c.name, `#genre/${c.slug}`)))));
  }));
}
function recordingList(records) {
  return el('ul', {class: 'ui-recordings'}, records.map(r => el('li', {}, external(r.title, r.url), r.artist_credit && el('small', {}, r.artist_credit))));
}
function artistCards(artists) {
  return el('div', {class: 'ui-artists'}, artists.map(a => link([
    bundled(a.photo) && el('img', {src: bundled(a.photo), alt: '', loading: 'lazy'}), el('strong', {}, a.name), el('span', {}, a.origin),
  ].filter(Boolean).reduce((wrap, item) => {wrap.append(item); return wrap;}, el('div')), `#artist/${a.id}`)));
}

export async function discover(root, query, signal) {
  root.append(heading('Discover', 'Find your next night. Explore the music behind it.'));
  const [content, genres, artists] = await Promise.all([
    api('discovery', `/api/browse/?q=${encodeURIComponent(query || '')}`, {signal}),
    api('discovery', '/api/genres/', {signal}), api('discovery', '/api/artists/', {signal}),
  ]);
  if (signal.aborted) return;
  root.append(el('h2', {}, query ? `Results for “${query}”` : 'Upcoming events'), content.events.length ? cards(content.events) : message('No upcoming events match. Try another search or create an event after signing in.'),
    el('h2', {}, 'Explore genres'), el('div', {class: 'ui-genres'}, genres.categories.map(c => {
      const item = link(c.name, `#genre/${c.slug}`); item.style.borderInlineStartColor = c.color; return item;
    })), el('h2', {}, 'Artists & DJs'), artistCards(artists.artists));
}

export async function eventDetail(root, id, signal) {
  const event = await api('discovery', `/api/events/${id}/content/`, {signal});
  if (signal.aborted) return;
  const image = artwork(event);
  root.append(link('← Discover', '#discover'), el('div', {class: 'ui-event-hero'}, image && el('img', {src: image, alt: `${event.title} poster`}),
    el('div', {}, heading(event.title, `${date(event.starts_at, event.venue.timezone)} · ${event.venue.timezone}`),
      event.cancelled && message('This event has been cancelled.'), el('h2', {}, event.venue.name), el('p', {}, event.venue.address),
      el('p', {}, `Until ${date(event.ends_at, event.venue.timezone)}`), el('p', {}, event.tempo),
      el('div', {class: 'ui-tags'}, event.categories.map(c => link(c.name, `#genre/${c.slug}`))),
      event.ticket_url && external('Tickets ↗', event.ticket_url))),
    el('section', {}, el('h2', {}, 'About this night'), el('p', {class: 'ui-prose'}, event.description)),
    el('section', {}, el('h2', {}, 'Lineup'), event.performers.length ? el('div', {class: 'ui-tags'}, event.performers.map(a => link(a.name, `#artist/${a.id}`))) : el('p', {}, 'Lineup to be announced.')),
    el('section', {}, el('h2', {}, 'The sound'), recordingList(event.samples)),
    event.references.length ? el('section', {}, el('h2', {}, 'Organizer listening links'), recordingList(event.references)) : null,
    el('section', {id: 'event-participation'}, el('h2', {}, 'Go together'), link('View attendance groups →', `#event-groups/${event.id}`)));
}

export async function genre(root, id, signal, subgenre) {
  const data = await api('discovery', /^\d+$/.test(id) ? `/api/genres/${id}/` : `/api/genres/slug/${id}/`, {signal});
  if (signal.aborted) return;
  root.append(link('← Discover', '#discover'), heading(data.name, data.description), el('p', {}, data.tempo),
    el('h2', {}, 'Start listening'), recordingList(data.samples.filter(s => !s.tag_ids.length)),
    el('h2', {}, 'Subgenres'), ...data.tags.map(t => el('details', {open: t.slug === subgenre}, el('summary', {}, t.name), el('p', {}, t.description),
      t.bpm_min && el('p', {}, `${t.bpm_min}–${t.bpm_max} BPM`), recordingList(data.samples.filter(s => s.tag_ids.includes(t.id))),
      el('p', {}, link('Link to this subgenre', `#genre/${data.slug}/${t.slug}`)))),
    el('h2', {}, 'Artists & DJs'), artistCards(data.artists));
  root.querySelector('details[open]')?.scrollIntoView({block: 'start'});
}

export async function artist(root, id, signal) {
  const data = await api('discovery', `/api/artists/${id}/`, {signal});
  if (signal.aborted) return;
  root.append(link('← Discover', '#discover'), el('div', {class: 'ui-event-hero'}, bundled(data.photo) && el('figure', {},
    el('img', {src: bundled(data.photo), alt: data.name}), el('figcaption', {}, data.photo_credit, ' · ', data.photo_license, ' ', external('Source', data.photo_source_url))),
    el('div', {}, heading(data.name, data.description), el('p', {}, data.origin), data.active_since && el('p', {}, `Active since ${data.active_since}`),
      data.labels && el('p', {}, data.labels), data.official_url && external('Official website ↗', data.official_url),
      el('div', {class: 'ui-tags'}, data.links.map(l => external(l.platform, l.url))))),
    el('h2', {}, 'Tracks & sets'), recordingList(data.recordings), el('h2', {}, 'Upcoming appearances'),
    data.events.length ? cards(data.events) : message('No upcoming appearances listed.'));
}

export async function near(root, filters, signal) {
  root.classList.add('ui-map-page');
  const status = message('Loading events…');
  const canvas = el('div', {class: 'ui-map', 'aria-label': 'Map of upcoming events'});
  const list = el('section', {class: 'ui-map-results', 'aria-label': 'Events in this area'});
  const artists = el('section', {'aria-label': 'Artists playing in this area'});
  root.append(canvas, el('div', {class: 'ui-map-toolbar'}, heading('Near me'), status), list);
  const genres = await api('discovery', '/api/genres/', {signal});
  if (signal.aborted) return;
  const select = el('select', {'aria-label': 'Genre'}, el('option', {value: ''}, 'All genres'), genres.categories.map(c => el('option', {value: c.id}, c.name)));
  const tagSelect = el('select', {'aria-label': 'Subgenre', disabled: true}, el('option', {value: ''}, 'All subgenres'));
  const windowSelect = el('select', {'aria-label': 'When'}, el('option', {value: ''}, 'Any date'),
    el('option', {value: '7'}, 'Next 7 days'), el('option', {value: '30'}, 'Next 30 days'));
  const mode = button('Show list', () => { list.hidden = !list.hidden; mode.textContent = list.hidden ? 'Show list' : 'Hide list'; });
  const locate = button('Use my location', () => navigator.geolocation?.getCurrentPosition(position => {
    if (!signal.aborted && map) map.flyTo({center: [position.coords.longitude, position.coords.latitude], zoom: 12});
  }, () => { status.textContent = 'Location unavailable. You can move the map or browse the list.'; }, {timeout: 7000}));
  filters.append(el('label', {class: 'ui-filter'}, 'Music', select), el('label', {class: 'ui-filter'}, 'Subgenre', tagSelect),
    el('label', {class: 'ui-filter'}, 'When', windowSelect), mode, locate);
  function fillTags() {
    const tags = genres.tags.filter(t => String(t.category_id) === select.value);
    tagSelect.replaceChildren(el('option', {value: ''}, 'All subgenres'), tags.map(t => el('option', {value: t.id}, t.name)));
    tagSelect.disabled = !tags.length;
  }
  let map, markers = [], events = [], timer, generation = 0;
  // Everyone billed on the listed events, busiest first, so the list follows the map and filters.
  function showArtists(shown) {
    const playing = new Map();
    for (const event of shown) {
      for (const person of event.performers) {
        const entry = playing.get(person.id) || {name: person.name, count: 0};
        entry.count += 1; playing.set(person.id, entry);
      }
    }
    const ranked = [...playing].sort((a, b) => b[1].count - a[1].count || a[1].name.localeCompare(b[1].name));
    artists.hidden = !ranked.length;
    artists.replaceChildren(el('h2', {}, 'Artists playing here'), el('div', {class: 'ui-tags'},
      ranked.map(([id, a]) => link(a.count > 1 ? `${a.name} (${a.count})` : a.name, `#artist/${id}`))));
  }
  function render() {
    if (signal.aborted) return;
    const bounds = map?.getBounds();
    const visible = events.filter(e => !bounds || bounds.contains([e.venue.longitude, e.venue.latitude]));
    status.textContent = `${visible.length} upcoming event${visible.length === 1 ? '' : 's'} in this area`;
    showArtists(visible);
    list.replaceChildren(visible.length ? cards(visible) : message('No upcoming events here. Move the map or try another genre.'), artists);
    markers.forEach(m => m.remove()); markers = [];
    if (!map) return;
    const venues = new Map();
    for (const event of visible) {
      if (!venues.has(event.venue.id)) venues.set(event.venue.id, []);
      venues.get(event.venue.id).push(event);
    }
    for (const group of venues.values()) {
      const e = group[0];
      const pin = button(String(group.length), () => {
        showArtists(group);
        list.hidden = false; mode.textContent = 'Hide list'; list.replaceChildren(cards(group), artists);
      }, {class: 'ui-pin', 'aria-label': `${e.venue.name}: ${group.length} events`});
      pin.style.backgroundColor = e.categories[0]?.color || '#999';
      markers.push(new window.maplibregl.Marker({element: pin}).setLngLat([e.venue.longitude, e.venue.latitude]).addTo(map));
    }
  }
  async function load() {
    const version = ++generation;
    try {
      const query = new URLSearchParams();
      if (select.value) query.set('category', select.value);
      if (tagSelect.value) query.set('tag', tagSelect.value);
      if (windowSelect.value) {
        const day = offset => new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10);
        query.set('from', day(0)); query.set('to', day(Number(windowSelect.value)));
      }
      const data = await api('discovery', `/api/browse/?${query}`, {signal});
      if (version !== generation || signal.aborted) return;
      events = data.events; render();
    } catch (error) { if (!signal.aborted) status.textContent = error.message; }
  }
  select.addEventListener('change', () => { fillTags(); load(); });
  tagSelect.addEventListener('change', load);
  windowSelect.addEventListener('change', load);
  signal.addEventListener('abort', () => {clearTimeout(timer); map?.remove();}, {once: true});
  await load();
  try {
    // Same pinned renderer as the original Bassline interface; network failure leaves the list usable.
    const module = await import('https://unpkg.com/maplibre-gl@6.3.0/dist/maplibre-gl.mjs');
    if (signal.aborted) return;
    window.maplibregl = module;
    map = new module.Map({container: canvas, style: 'https://tiles.openfreemap.org/styles/dark', center: [-3.7038, 40.4168], zoom: 11});
    map.addControl(new module.NavigationControl(), 'top-right');
    map.on('moveend', () => {clearTimeout(timer); timer = setTimeout(render, 150);});
    map.on('load', render);
    map.on('error', () => {status.textContent = 'Map tiles unavailable. The event list is still usable.'; list.hidden = false;});
  } catch {
    status.textContent = 'The map could not load. Browse upcoming events below.'; list.hidden = false;
  }
}
