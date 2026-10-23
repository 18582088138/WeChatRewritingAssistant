import { icon } from '../icons.js';
import { $, $$, escape, safeUrl, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { download } from '../core/media.js';
import { state } from '../core/state.js';

export function assetTile(article, asset, picker = false) {
  return `<div class="asset-tile">${
    asset.type === 'video'
      ? `<video controls data-asset="${article.id}/${asset.id}">
      </video>`
      : `<img data-asset="${article.id}/${asset.id}" alt="${escape(asset.alt)}">`
  }<div class="asset-content">
      <p>${asset.width || ''}${asset.width ? ' × ' + asset.height : ''} · ${escape(asset.rights)}</p>${
        asset.attribution
          ? `<p>
      <a href="${safeUrl(asset.attribution)}" target="_blank" rel="noopener noreferrer">查看来源 ${icon('external')}</a>
      </p>`
          : ''
      }<label>图片描述<input type="text" data-alt="${asset.id}" value="${escape(asset.alt || '配图')}">
      </label>
      <label class="checkbox">
      <input type="checkbox" data-approve="${article.id}/${asset.id}" ${asset.approved ? 'checked' : ''}>已确认授权且无水印</label>${picker ? `<button class="button primary small" data-pick="${asset.id}" ${!asset.approved ? 'disabled' : ''}>使用这张图片</button>` : `<button class="button secondary small" data-download-asset="${article.id}/${asset.id}">下载素材</button>`}</div>
      </div>`;
}

export function bindAssets(root) {
  $$('[data-approve]', root).forEach(
    (input) =>
      (input.onchange = async () => {
        const [id, assetId] = input.dataset.approve.split('/');
        try {
          const article = await api(`/api/articles/${id}/assets/${assetId}`, {
            method: 'PATCH',
            body: JSON.stringify({
              approved: input.checked,
              alt: $(`[data-alt="${assetId}"]`, root).value,
            }),
          });
          if (state.current?.id === id) state.current = article;
          else state.articles = state.articles.map((a) => (a.id === id ? article : a));
          const pick = $(`[data-pick="${assetId}"]`, root);
          if (pick) pick.disabled = !input.checked;
          toast(input.checked ? '素材已确认，可用于正文' : '素材已移回待确认区');
        } catch (err) {
          input.checked = !input.checked;
          toast(err.message);
        }
      }),
  );
  $$('[data-download-asset]', root).forEach(
    (b) =>
      (b.onclick = async () => {
        try {
          const [id, asset] = b.dataset.downloadAsset.split('/');
          download(
            await api(`/api/articles/${id}/assets/${asset}/file`),
            asset + '.' + (b.closest('.asset-tile').querySelector('video') ? 'mp4' : 'jpg'),
          );
        } catch (err) {
          toast(err.message);
        }
      }),
  );
}
