import {api} from './api.js';
import {el, link, heading, message, date} from './dom.js';

const count = (number, word) => `${number} ${word}${number === 1 ? '' : 's'}`;

// Loaded after the profile form, with its own error message, so a failure here leaves the form usable.
export async function collectionSection(root, signal) {
  const section = el('section', {class: 'ui-collection', 'aria-label': 'Collection'}, message('Loading your collection…'));
  root.append(section);
  let data;
  try {data = await api('discovery', '/api/account/collection/', {signal});}
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
    el('ul', {class: 'ui-cards'}, badges, cards,
      Array.from({length: locked}, () => el('li', {class: 'ui-card ui-card-locked'}, 'Locked'))));
}
