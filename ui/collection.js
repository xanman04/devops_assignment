import {api} from './api.js';
import {el, link, heading, message, date} from './dom.js';

const count = (number, word) => `${number} ${word}${number === 1 ? '' : 's'}`;
const safeColor = value => /^#[0-9a-f]{6}$/i.test(value) ? value : '#8d95a6';

function svg(tag, attrs, ...children) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  node.append(...children);
  return node;
}

// One spoke per genre, reaching further out the more often it appears, relative to the most frequent genre.
export function genreChart(genres, cards) {
  const counts = genres.map(genre => cards.filter(card => card.genre === genre.name).length);
  const top = Math.max(0, ...counts);
  if (!top) return '';
  const centre = 160, radius = 112;
  const point = (index, fraction) => {
    const angle = -Math.PI / 2 + 2 * Math.PI * index / genres.length;
    return [centre + radius * fraction * Math.cos(angle), centre + radius * fraction * Math.sin(angle)];
  };
  const points = fraction => genres.map((_, i) => point(i, fraction(i)).map(n => n.toFixed(1)).join(',')).join(' ');
  const spokes = genres.map((genre, i) => {
    const [x, y] = point(i, 1);
    return [svg('line', {x1: centre, y1: centre, x2: x, y2: y, stroke: safeColor(genre.color), 'stroke-opacity': 0.45}),
      svg('circle', {cx: x, cy: y, r: 3.5, fill: safeColor(genre.color)},
        svg('title', {}, `${genre.name}: ${counts[i]}`))];
  }).flat();
  const favourites = genres.map((genre, i) => ({name: genre.name, total: counts[i]})).filter(g => g.total)
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name)).slice(0, 3);
  const summary = favourites.map(g => `${g.name} (${g.total})`).join(', ');
  return el('figure', {class: 'ui-chart'},
    svg('svg', {viewBox: '22 22 276 276', role: 'img', 'aria-label': `Genre chart. Most collected: ${summary}`},
      ...[0.25, 0.5, 0.75, 1].map(ring => svg('polygon', {points: points(() => ring), fill: 'none', stroke: '#555'})),
      ...spokes,
      svg('polygon', {points: points(i => Math.max(counts[i] / top, 0.05)), fill: '#d4d4d4', 'fill-opacity': 0.25, stroke: '#f1f1f1', 'stroke-width': 1.5})),
    el('figcaption', {}, el('strong', {}, 'Music taste: '), summary));
}

// Loaded after the profile form, with its own error message, so a failure here leaves the form usable.
export async function collectionSection(root, signal) {
  const section = el('section', {class: 'ui-collection', 'aria-label': 'Collection'}, message('Loading your collection…'));
  root.append(section);
  let data, genres;
  try {[data, genres] = await Promise.all([api('discovery', '/api/account/collection/', {signal}),
    api('discovery', '/api/genres/', {signal})]);}
  catch (error) {if (!signal.aborted) section.replaceChildren(message(error.message)); return;}
  if (signal.aborted) return;
  const events = new Map(data.cards.map(card => [card.event_id, card]));
  const eventLink = card => link(card.title, `#event/${card.event_id}`);
  const tile = (kind, color, ...content) => {
    const item = el('li', {class: `ui-card ui-card-${kind}`}, ...content);
    if (/^#[0-9a-f]{6}$/i.test(color)) item.style.borderTopColor = color;
    return item;
  };
  const badges = data.achievements.map(badge => tile(badge.tier.toLowerCase(), '',
    el('p', {class: 'ui-meta'}, badge.tier), el('h3', {}, badge.title),
    el('details', {}, el('summary', {}, `Earned from ${count(badge.event_ids.length, 'event')}`),
      el('ul', {}, badge.event_ids.map(id => el('li', {}, events.get(id).title))))));
  const cards = data.cards.map(card => tile('event', card.color,
    el('p', {class: 'ui-meta'}, card.genre), el('h3', {}, eventLink(card)),
    el('p', {}, `${card.venue} · ${date(card.starts_at, card.timezone)}`)));
  const locked = Math.max(data.total_slots - badges.length - cards.length, 0);
  section.replaceChildren(el('h2', {}, data.name),
    el('p', {}, `${count(data.followed, 'followed event')} · ${count(data.cards.length, 'event card')} · ${count(data.achievements.length, 'achievement')}`),
    !cards.length ? message('No event cards yet. Cards come from verified attendance, and check-in is not available yet.') : '',
    genreChart(genres.categories, data.cards),
    el('ul', {class: 'ui-cards'}, badges, cards,
      Array.from({length: locked}, () => el('li', {class: 'ui-card ui-card-locked'}, 'Locked'))));
}
