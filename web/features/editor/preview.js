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
    for (const img of $$('img,video', doc)) {
      const match = img
        .getAttribute('src')
        ?.match(/^\/api\/articles\/([a-f0-9]{32})\/assets\/([^/]+)\/file$/);
      if (match) {
        const b = await api(`/api/articles/${match[1]}/assets/${match[2]}/file`);
        img.src = await blobDataUrl(b);
      }
      const poster=img.getAttribute('poster');
      if(poster?.startsWith('/api/articles/'))img.poster=await blobDataUrl(await api(poster));
    }
    w.document.open();
    w.document.write('<!doctype html>' + doc.documentElement.outerHTML);
    w.document.close();
  } catch (err) {
    w.close();
    toast(err.message);
  }
}

export async function showVersion(v) {
  const w = window.open('about:blank', '_blank');
  if (!w) return;
  try {
    const blob=await api(`/api/articles/${v.id}/versions/${v.version_id}/preview`);
    const doc=new DOMParser().parseFromString(await blob.text(),'text/html');
    await Promise.all($$('img,video',doc).map(async el=>{
      const src=el.getAttribute('src');
      if(src?.startsWith(`/api/articles/${v.id}/versions/${v.version_id}/assets/`))el.src=await blobDataUrl(await api(src));
      const poster=el.getAttribute('poster');
      if(poster?.startsWith(`/api/articles/${v.id}/versions/${v.version_id}/assets/`))el.poster=await blobDataUrl(await api(poster));
    }));
    w.document.open();w.document.write('<!doctype html>'+doc.documentElement.outerHTML);w.document.close();
  }catch(err){w.close();toast(err.message);}
}
