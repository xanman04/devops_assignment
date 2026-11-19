// DOM text is always text, including user-controlled titles and chat messages.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value !== undefined && value !== null && value !== false) node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
export const link = (label, href, attrs = {}) => el('a', {...attrs, href}, label);
export function external(label, url) {
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return el('span', {}, label);
    return link(label, parsed.href, {target: '_blank', rel: 'noopener noreferrer'});
  } catch { return el('span', {}, label); }
}
export const message = text => el('p', {role: 'status', class: 'ui-message'}, text);
export function heading(title, description = '') {
  return el('header', {class: 'ui-heading'}, el('h1', {}, title), description && el('p', {}, description));
}
export function date(value, zone = 'Europe/Paris') {
  return new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short', timeZone: zone}).format(new Date(value));
}
export const button = (text, action, attrs = {}) => el('button', {type: 'button', ...attrs, onclick: action}, text);
export function field(label, name, type = 'text', attrs = {}) {
  return el('label', {}, label, el('input', {name, type, ...attrs}));
}
export function formAction(form, action) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = form.querySelector('[type=submit]');
    if (submit.disabled) return;
    submit.disabled = true;
    let status = form.querySelector('[role=status]');
    if (!status) { status = message(''); form.append(status); }
    status.textContent = 'Saving…';
    try { await action(new FormData(form)); status.textContent = 'Saved.'; }
    catch (error) { status.textContent = error.message; }
    finally { submit.disabled = false; }
  });
  return form;
}
