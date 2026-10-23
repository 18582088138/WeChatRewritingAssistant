import { $, $$, toast } from '../../core/dom.js';
import { api } from '../../core/api.js';
import { hydrateImages } from '../../core/media.js';
import { saveDraft } from './draft.js';
import { assetTile, bindAssets } from '../../components/assets.js';
import { state } from '../../core/state.js';
import { runtime } from '../../core/runtime.js';

export async function makeCards() {
  if (!(await saveDraft(true))) return;
  const b = $('#make-cards');
  b.disabled = true;
  try {
    state.current = await api(`/api/articles/${state.current.id}/cards`, { method: 'POST' });
    state.tab = 'sources';
    runtime.renderEditor();
    toast('3:4 图文组图已生成，可预览并下载');
  } catch (err) {
    toast(err.message);
    b.disabled = false;
  }
}

export async function uploadAsset(e) {
  const file = e.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  try {
    state.current = await api(`/api/articles/${state.current.id}/assets`, {
      method: 'POST',
      body: form,
    });
    runtime.renderEditor();
    toast('本地图片已上传，请确认授权与水印');
  } catch (err) {
    toast(err.message);
  }
}

export function openAssetPicker() {
  const area = $('#draft-body');
  state.imageSelection = state.selection || { start: area.selectionStart, end: area.selectionEnd };
  const approved = state.current.assets.filter((a) => a.type === 'image');
  $('#asset-picker').innerHTML = approved.length
    ? approved.map((a) => assetTile(state.current, a, true)).join('')
    : '<p class="hint">暂无图片，请到“来源与素材”上传本地图片。</p>';
  bindAssets($('#asset-picker'));
  $$('[data-pick]').forEach(
    (b) =>
      (b.onclick = () => {
        const asset = state.current.assets.find((a) => a.id === b.dataset.pick);
        const { start, end } = state.imageSelection;
        const value = area.value;
        const caption = asset.alt.replace(/[\[\]\n]/g, '');
        const image = `![${caption}](/api/articles/${state.current.id}/assets/${asset.id}/file)`;
        area.value = value.slice(0, start) + image + value.slice(end);
        state.dirty = true;
        $('#save-state').textContent = '配图已替换，请保存';
        state.selection = null;
        $('#asset-dialog').close();
      }),
  );
  hydrateImages($('#asset-picker'));
  $('#asset-dialog').showModal();
}

export function bindAssetDialog() {
  $('#close-assets').onclick = () => $('#asset-dialog').close();
}
