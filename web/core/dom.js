export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const escape = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
export function date(value, detailed = false) {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    ...(detailed ? { hour: '2-digit', minute: '2-digit' } : {}),
  });
}

export function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return ['https:', 'http:'].includes(parsed.protocol) ? escape(parsed.href) : '#';
  } catch {
    return '#';
  }
}

export function heading(context, title, description, action = '') {
  return `<div class="page-heading">
      <div>
      <h1>${title}</h1>
      <p>${description}</p>
      </div>${action}</div>`;
}

export function empty(title, text, action = '') {
  return `<div class="empty-state">
      <h3>${title}</h3>
      <p>${text}</p>${action}</div>`;
}

export function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $('#toast').classList.remove('visible'), 4500);
}
