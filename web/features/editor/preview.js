import { $$, escape, date, toast } from '../../core/dom.js';
import { api } from '../../core/api.js';
import { blobDataUrl } from '../../core/media.js';
import { saveDraft } from './draft.js';
import { state } from '../../core/state.js';

export async function openPreview() {
  if (!(await saveDraft(true))) return;
  const w = window.open('about:blank', '_blank');
  if (!w) {
    toast('浏览器拦截了阅览窗口，请允许弹窗');
    return;
  }
  try {
    const blob = await api(`/api/articles/${state.current.id}/preview`);
    const text = await blob.text();
    const doc = new DOMParser().parseFromString(text, 'text/html');
    for (const img of $$('img', doc)) {
      const match = img
        .getAttribute('src')
        ?.match(/^\/api\/articles\/([a-f0-9]{32})\/assets\/([^/]+)\/file$/);
      if (match) {
        const b = await api(`/api/articles/${match[1]}/assets/${match[2]}/file`);
        img.src = await blobDataUrl(b);
      }
    }
    w.document.open();
    w.document.write('<!doctype html>' + doc.documentElement.outerHTML);
    w.document.close();
  } catch (err) {
    w.close();
    toast(err.message);
  }
}

export function showVersion(v) {
  const w = window.open('about:blank', '_blank');
  if (!w) return;
  w.document.open();
  w.document.write(
    `<!doctype html>
      <meta charset="utf-8">
      <title>${escape(v.title)}</title>
      <body style="max-width:760px;margin:40px auto;padding:25px;font-family:system-ui">
      <h1>${escape(v.title)}</h1>
      <p>历史版本 · ${date(v.updated_at, true)} · 修订 ${v.revision}</p>
      <pre style="white-space:pre-wrap;line-height:1.9">${escape(v.body)}</pre>
      </body>`,
  );
  w.document.close();
}
