import {api} from './api.js';
import {el, link, heading, message, button, formAction} from './dom.js';
import {requireAccount} from './accounts.js';

const note = (label, name) => el('label', {}, label, el('textarea', {name, rows: 3, maxlength: 2000}));
function decision(label, choices) {
  return el('label', {}, label, el('select', {name: 'status', required: true, 'aria-label': label},
    el('option', {value: '', disabled: true, selected: true}, 'Choose a decision'),
    choices.map(([value, text]) => el('option', {value}, text))));
}

export async function moderation(root, signal) {
  if (!requireAccount(root)) return;
  const data = await api('discovery', '/api/moderation/', {signal});
  if (signal.aborted) return;
  root.append(heading('Moderation', 'Review venue proposals and reported events. Each action is checked against your current permissions.'),
    el('div', {class: 'ui-review-actions'}, link('← Profile', '#profile'),
      button('Refresh queues', () => window.dispatchEvent(new HashChangeEvent('hashchange')))));
  if (data.capabilities.venues) {
    const section = el('section', {'aria-label': 'Venue review queue'}, el('h2', {}, 'Pending venues'));
    root.append(section);
    if (!data.pending_venues.length) section.append(message('No venues awaiting review.'));
    for (const venue of data.pending_venues) {
      const row = el('article', {class: 'ui-row'}, el('div', {}, el('h3', {}, venue.name),
        el('p', {}, venue.address || 'No address supplied'), el('p', {}, venue.timezone),
        el('p', {}, `Coordinates: ${venue.latitude}, ${venue.longitude}`)));
      const form = el('form', {class: 'ui-form'}, decision('Venue decision', [['approved', 'Approve'], ['rejected', 'Reject']]),
        note('Review note', 'review_note'), el('button', {type: 'submit'}, 'Save venue review'));
      row.append(formAction(form, async fields => {
        const result = await api('discovery', `/api/moderation/venues/${venue.id}/review/`, {
          method: 'POST', data: Object.fromEntries(fields), signal,
        });
        if (!signal.aborted) row.replaceChildren(el('h3', {}, venue.name), message(`Venue ${result.status}.`));
      }));
      section.append(row);
    }
    if (data.pending_venues.length === 200) section.append(message('Showing the oldest 200 venues. Review these and refresh for the next batch.'));
  }
  if (data.capabilities.reports) {
    const section = el('section', {'aria-label': 'Event report queue'}, el('h2', {}, 'Pending event reports'));
    root.append(section);
    if (!data.pending_reports.length) section.append(message('No event reports awaiting review.'));
    for (const report of data.pending_reports) {
      const row = el('article', {class: 'ui-row'}, el('div', {}, el('h3', {}, report.event_title),
        link('View event', `#event/${report.event_id}`), el('p', {}, report.reason.replaceAll('_', ' ')),
        el('p', {class: 'ui-prose'}, report.explanation || 'No explanation supplied')));
      const form = el('form', {class: 'ui-form'}, decision('Report decision', [['dismissed', 'Dismiss'], ['actioned', 'Action taken']]),
        note('Resolution note', 'resolution_note'),
        data.capabilities.hide_events && el('label', {class: 'ui-checkbox'}, el('input', {type: 'checkbox', name: 'hide_event', value: 'yes'}), 'Hide this event from public discovery'),
        el('button', {type: 'submit'}, 'Save report review'));
      row.append(formAction(form, async fields => {
        const result = await api('discovery', `/api/moderation/reports/${report.id}/review/`, {
          method: 'POST', data: {status: fields.get('status'), resolution_note: fields.get('resolution_note'), hide_event: fields.get('hide_event') === 'yes'}, signal,
        });
        if (!signal.aborted) row.replaceChildren(el('h3', {}, report.event_title), message(`Report ${result.status}.`));
      }));
      section.append(row);
    }
    if (data.pending_reports.length === 200) section.append(message('Showing the oldest 200 reports. Review these and refresh for the next batch.'));
  }
}
