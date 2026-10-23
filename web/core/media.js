import { $$ } from './dom.js';
import { api } from './api.js';

let blobUrls = [];
export function releaseMedia() {
  blobUrls.forEach(URL.revokeObjectURL);
  blobUrls = [];
}
export async function hydrateImages(root = document) {
  await Promise.allSettled(
    $$('[data-asset]', root).map(async (el) => {
      const [article, id] = el.dataset.asset.split('/');
      try {
        const blob = await api(`/api/articles/${article}/assets/${id}/file`);
        if (!el.isConnected) return;
        const url = URL.createObjectURL(blob);
        blobUrls.push(url);
        el.src = url;
      } catch {
        el.alt = '素材加载失败';
      }
    }),
  );
}

export async function hydratePreview(root) {
  const imgs = $$('img', root);
  await Promise.allSettled(
    imgs.map(async (img) => {
      const match = img
        .getAttribute('src')
        ?.match(/^\/api\/articles\/([a-f0-9]{32})\/assets\/([^/]+)\/file$/);
      if (match) {
        img.dataset.asset = match[1] + '/' + match[2];
      } else {
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
      }
    }),
  );
  await hydrateImages(root);
}

export function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export function blobDataUrl(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(blob);
  });
}
