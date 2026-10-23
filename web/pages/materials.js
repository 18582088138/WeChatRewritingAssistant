import { icon } from '../icons.js';
import { $, heading, empty } from '../core/dom.js';
import { hydrateImages } from '../core/media.js';
import { openImport } from '../features/import.js';
import { assetTile, bindAssets } from '../components/assets.js';
import { state } from '../core/state.js';

export function renderMaterials() {
  const assets = state.articles.flatMap((a) => a.assets.map((asset) => ({ article: a, asset })));
  $('#main').innerHTML =
    heading('YOUR VISUAL RESOURCES', '素材库', '按文章归档的图片、视频与本地生成组图。') +
    `<div class="asset-grid">${assets.length ? assets.map(({ article, asset }) => assetTile(article, asset)).join('') : empty('给内容一个更好的视觉表达', '导入文章后，来源素材会自动归档。<br>也可以在文章编辑页上传图片、生成组图。', `<button class="button primary" id="material-import">${icon('plus')} 导入文章</button>`)}</div>`;
  $('#material-import')?.addEventListener('click', openImport);
  bindAssets($('#main'));
  hydrateImages();
}
