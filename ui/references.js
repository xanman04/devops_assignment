import {api} from './api.js';
import {el, link, heading, message, field, formAction} from './dom.js';
import {requireAccount, action} from './accounts.js';

const kinds = [['track', 'Track'], ['set', 'Set'], ['artist_page', 'Artist page']];
const reload = () => window.dispatchEvent(new HashChangeEvent('hashchange'));

function referenceForm(legend, submit, value, save) {
  const kind = el('select', {name: 'kind', 'aria-label': 'Kind'},
    kinds.map(([id, label]) => el('option', {value: id, selected: value.kind === id}, label)));
  const form = el('form', {class: 'ui-form'}, el('fieldset', {}, el('legend', {}, legend),
    field('Title', 'title', 'text', {required: true, maxlength: 200, value: value.title}),
    field('Artist or DJ', 'artist_credit', 'text', {required: true, maxlength: 200, value: value.artist_credit}),
    field('Link address', 'url', 'url', {required: true, maxlength: 2048, value: value.url}),
    el('label', {}, 'Kind', kind),
    field('Position (lower numbers come first)', 'display_order', 'number', {required: true, min: 0, max: 2147483647, step: 1, value: value.display_order}),
    el('button', {type: 'submit'}, submit)));
  return formAction(form, async data => {
    const fields = Object.fromEntries(data);
    await save({...fields, display_order: Number(fields.display_order)});
    reload();
  });
}

export async function listeningLinks(root, id, signal) {
  if (!requireAccount(root)) return;
  const base = `/api/events/${id}/references/`;
  const data = await api('discovery', base, {signal});
  if (signal.aborted) return;
  const next = data.references.reduce((top, r) => Math.max(top, r.display_order + 1), 0);
  root.append(link('← My events', '#my-events'),
    heading('Listening links', `Shown on the public page for ${data.event.title}.`),
    data.references.length ? '' : message('No listening links yet.'),
    ...data.references.map(reference => el('div', {},
      referenceForm(reference.title, 'Save link', reference,
        fields => api('discovery', `${base}${reference.id}/`, {method: 'PUT', data: fields, signal})),
      action('Remove link', async () => {
        await api('discovery', `${base}${reference.id}/delete/`, {method: 'POST', data: {}, signal});
        reload();
      }, `Remove the link “${reference.title}”?`))),
    referenceForm('Add a link', 'Add link', {title: '', artist_credit: '', url: '', kind: 'track', display_order: next},
      fields => api('discovery', base, {method: 'POST', data: fields, signal})));
}
