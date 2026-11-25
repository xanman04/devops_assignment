import {api, currentUser} from './api.js';
import {el, link, heading, message, button, field, formAction, date} from './dom.js';
import {requireAccount, action} from './accounts.js';

const groupLink = group => el('article', {class: 'ui-row'}, el('div', {}, el('h2', {}, link(group.name, `#group/${group.id}`)),
  el('p', {}, group.description), el('p', {}, `${group.member_count}/${group.capacity} · ${group.joining_mode === 'public' ? 'Public' : 'Private'}`)), link('Event', `#event/${group.event_id}`));

export async function eventGroups(root, id, signal) {
  root.append(heading('Go together'), link('← Event', `#event/${id}`));
  const data = await api('groups', `/api/events/${id}/groups/`, {signal});
  if (signal.aborted) return;
  root.append(...(data.groups.length ? data.groups.map(groupLink) : [message('No groups yet. Start one and find people to attend with.')]));
  if (currentUser()) root.append(link('Create a group', `#create-group/${id}`, {class: 'button'}));
  else root.append(link('Log in to join or create a group', '#login'));
}
export async function mine(root, signal) {
  if (!requireAccount(root)) return;
  const data = await api('groups', '/api/groups/mine/', {signal});
  if (signal.aborted) return;
  root.append(heading('Groups'), el('h2', {}, 'My groups'), ...(data.groups.length ? data.groups.map(groupLink) : [message('No groups yet. Find an event and choose Go together.')]),
    el('h2', {}, 'Requests'), ...(data.requests.length ? data.requests.map(r => el('article', {class: 'ui-row'},
      el('p', {}, link(r.group_name, `#group/${r.group_id}`), ` · ${r.status}`),
      r.status === 'approved' && action('Accept offer', async () => {
        await api('groups', `/api/requests/${r.id}/accept/`, {method: 'POST', data: {confirm_switch: true}, signal});
        location.hash = `group/${r.group_id}`;
      }, 'Accept this offer? If you belong to another group for this event, you will leave it.'),
      ['pending', 'approved'].includes(r.status) && action('Cancel request', () => api('groups', `/api/requests/${r.id}/cancel/`, {method: 'POST', data: {}, signal}))
    )) : [message('No requests yet.')]));
}

export async function groupForm(root, eventId, id, signal) {
  if (!requireAccount(root)) return;
  const initial = id ? await api('groups', `/api/groups/${id}/`, {signal}) : {};
  if (signal.aborted) return;
  const form = el('form', {class: 'ui-form'}, field('Group name', 'name', 'text', {required: true, maxlength: 120, value: initial.name || ''}),
    el('label', {}, 'Description', el('textarea', {name: 'description', required: true, rows: 4}, initial.description || '')),
    field('Capacity (including you)', 'capacity', 'number', {required: true, min: 1, value: initial.capacity || 6}),
    el('label', {}, 'Who can join?', el('select', {name: 'joining_mode', 'aria-label': 'Who can join?'}, el('option', {value: 'public', selected: initial.joining_mode !== 'approval_required'}, 'Public — join directly'), el('option', {value: 'approval_required', selected: initial.joining_mode === 'approval_required'}, 'Private — owner approval'))),
    el('button', {type: 'submit'}, id ? 'Save group' : 'Create group'));
  const key = crypto.randomUUID(); // Stable across failed retries of this form.
  root.append(heading(id ? 'Edit group' : 'Create group'), formAction(form, async fields => {
    const data = Object.fromEntries(fields); data.capacity = Number(data.capacity);
    if (!id) data.event_id = Number(eventId);
    const result = await api('groups', id ? `/api/groups/${id}/edit/` : '/api/groups/', {
      method: id ? 'PUT' : 'POST', data, headers: {'Idempotency-Key': key}, signal,
    });
    location.hash = `group/${result.id}`;
  }));
}

export async function detail(root, id, signal) {
  const group = await api('groups', `/api/groups/${id}/`, {signal});
  if (signal.aborted) return;
  const count = el('p', {}, `${group.member_count}/${group.capacity} members · ${group.joining_mode === 'public' ? 'Public' : 'Private'}`);
  root.append(heading(group.name, group.description), link(group.event_title, `#event/${group.event_id}`),
    count);
  if (!requireAccount(root)) return;
  const owned = group.owner_id === currentUser().id;
  const membership = await api('groups', '/api/groups/mine/', {signal});
  if (signal.aborted) return;
  const member = membership.groups.some(g => g.id === Number(id));
  if (!member) {
    const existing = membership.groups.find(g => g.event_id === group.event_id);
    if (group.joining_mode === 'public') root.append(action(existing ? 'Switch to this group' : 'Join group', async () => {
      await api('groups', `/api/groups/${id}/join/`, {method: 'POST', data: {confirm_switch: Boolean(existing)}, signal});
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }, existing ? `Leave ${existing.name} and join ${group.name}?` : 'Join this group?'));
    else root.append(action('Request to join', () => api('groups', `/api/groups/${id}/request/`, {method: 'POST', data: {}, signal})));
    return;
  }
  root.append(action('Leave group', async () => {
    await api('groups', `/api/groups/${id}/leave/`, {method: 'POST', data: {}, signal}); location.hash = 'groups';
  }, owned ? 'Leave this group? Ownership passes to the longest-standing member, or the empty group is deleted.' : 'Leave this group?'));
  if (owned) root.append(link('Edit group', `#edit-group/${id}`));
  const canDelete = currentUser().permissions?.some(p => ['groups.*', 'groups.delete_attendancegroup'].includes(p));
  if (owned && canDelete) root.append(action('Delete group', async () => {
    await api('groups', `/api/groups/${id}/delete/`, {method: 'DELETE', signal}); location.hash = 'groups';
  }, 'Delete this group and its chat? This cannot be undone.'));
  if (owned) {
    const data = await api('groups', `/api/groups/${id}/requests/`, {signal});
    if (signal.aborted) return;
    root.append(el('h2', {}, 'Join requests'), ...data.requests.filter(r => r.status === 'pending').map(r => {
      const row = el('article', {class: 'ui-row'}, el('p', {}, `Applicant #${r.applicant_id}`));
      row.append(...[true, false].map(approve => action(approve ? 'Approve' : 'Decline', async () => {
        await api('groups', `/api/requests/${r.id}/review/`, {method: 'POST', data: {approve}, signal});
        if (!signal.aborted) row.replaceChildren(message(approve ? 'Request approved.' : 'Request declined.'));
      })));
      return row;
    }));
  }
  const messages = el('div', {class: 'ui-chat', role: 'log', 'aria-label': 'Group messages', 'aria-live': 'polite'});
  const status = message('Loading chat…');
  const members = el('section', {'aria-label': 'Group members'});
  root.append(el('h2', {}, 'Chat'), status, messages);
  const form = el('form', {class: 'ui-form'}, el('label', {}, 'Message', el('textarea', {name: 'body', required: true, maxlength: 2000, rows: 3})), el('button', {type: 'submit'}, 'Send message'));
  root.append(formAction(form, async data => {
    await api('groups', `/api/groups/${id}/messages/`, {method: 'POST', data: {body: data.get('body')}, signal}); form.reset(); await poll();
  }), members);
  let signature = '', timer;
  const bans = el('section', {'aria-label': 'Banned people'});
  if (owned) root.append(bans);
  async function showBans() {
    const data = await api('groups', `/api/groups/${id}/bans/`, {signal});
    if (signal.aborted) return;
    bans.replaceChildren(el('h2', {}, 'Banned people'), data.bans.length ? el('div', {}, data.bans.map(b => el('div', {class: 'ui-row'},
      el('span', {}, `${b.display_name} · ${date(b.issued_at)}${b.reason ? ` · ${b.reason}` : ''}`),
      action('Lift ban', async () => {
        await api('groups', `/api/bans/${b.id}/lift/`, {method: 'POST', data: {}, signal}); await showBans();
      }, 'Allow this person to join the group again?')))) : message('Nobody is banned from this group.'));
  }
  async function poll() {
    clearTimeout(timer);
    if (signal.aborted || !currentUser()) return;
    try {
      const data = await api('groups', `/api/groups/${id}/chat/`, {signal});
      if (signal.aborted) return;
      status.hidden = true;
      count.textContent = `${data.members.length}/${group.capacity} members · ${group.joining_mode === 'public' ? 'Public' : 'Private'}`;
      if (signature !== data.signature) {
        signature = data.signature;
        const names = new Map(data.members.map(m => [m.user_id, m.user__display_name]));
        messages.replaceChildren(...data.messages.map(m => el('article', {class: 'ui-chat-message'},
          el('small', {}, `${names.get(m.author_id) || 'Former member'} · ${date(m.created_at)}${m.edited_at ? ' · edited' : ''}`),
          el('p', {class: 'ui-prose'}, m.deleted_at ? 'Message deleted' : m.body),
          !m.deleted_at && m.author_id === currentUser().id && editMessage(m, signal, poll),
          !m.deleted_at && (owned || m.author_id === currentUser().id) && action('Delete message', async () => {
            await api('groups', `/api/messages/${m.id}/`, {method: 'DELETE', signal}); signature = ''; await poll();
          }, 'Delete this message?'))), ...data.notices.map(n => el('p', {class: 'ui-meta'}, n.text)));
        members.replaceChildren(el('h2', {}, 'Members'), ...data.members.map(m => el('div', {class: 'ui-row'}, el('span', {}, m.user__display_name),
          owned && m.user_id !== currentUser().id && action('Remove member', async () => {
            await api('groups', `/api/groups/${id}/members/${m.user_id}/remove/`, {method: 'POST', data: {}, signal}); signature = ''; await poll();
          }, 'Remove this member from the group?'),
          owned && m.user_id !== currentUser().id && action('Remove and ban', async () => {
            await api('groups', `/api/groups/${id}/members/${m.user_id}/remove/`, {method: 'POST', data: {ban: true, reason: 'Removed by the group owner'}, signal}); signature = ''; await poll();
          }, 'Remove this member and stop them from rejoining until you lift the ban?'))));
        if (owned) await showBans();
      }
    } catch (error) {
      if (!signal.aborted) {status.hidden = false; status.textContent = `${error.message} Chat will retry shortly.`;}
    }
    if (!signal.aborted) timer = setTimeout(poll, 3000);
  }
  signal.addEventListener('abort', () => clearTimeout(timer), {once: true});
  await poll();
}

function editMessage(record, signal, refresh) {
  const form = el('form', {class: 'ui-form'}, el('label', {}, 'Edit message', el('textarea', {name: 'body', required: true, rows: 2, maxlength: 2000}, record.body)), el('button', {type: 'submit'}, 'Save message'));
  return el('details', {}, el('summary', {}, 'Edit message'), formAction(form, async data => {
    await api('groups', `/api/messages/${record.id}/`, {method: 'PUT', data: {body: data.get('body')}, signal}); await refresh();
  }));
}
