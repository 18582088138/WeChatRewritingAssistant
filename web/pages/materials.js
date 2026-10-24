import { icon } from '../icons.js';
import { $, heading, empty, escape, toast } from '../core/dom.js';
import { hydrateImages } from '../core/media.js';
import { openImport } from '../features/import.js';
import { assetTile, bindAssets } from '../components/assets.js';
import { state } from '../core/state.js';
import { api } from '../core/api.js';

export async function renderMaterials() {
  let library;
  try {library=await api('/api/materials/public');}catch(err){toast(err.message);library={sources:[],assets:[]};}
  if(state.view!=='materials')return;
  $('#main').innerHTML =
    heading('YOUR VISUAL RESOURCES', '素材库', '本篇文章独立归档，公共资料可供不同文章选用。') +
    `<section class="panel material-group"><h2>公共素材库</h2><div class="section-actions"><label class="button secondary">添加文档 / 图片 / 视频<input id="public-upload" type="file" multiple accept=".md,.txt,.pdf,.docx,.html,.png,.jpg,.jpeg,.gif,.webp,.mp4,.mov,.webm" hidden></label><button class="button secondary" id="sync-public">同步文件夹</button></div><label>添加参考网址<input id="public-url" type="url" placeholder="https://…"></label><button class="button secondary small" id="public-fetch">抓取网址</button><p class="hint storage-path">${escape(library.storage_path||'data/public-materials')}/manual/{texts,images,videos}</p><div>${library.sources.map(s=>`<p>${icon('articles')} ${escape(s.title)}<br><small>${escape(s.url)}</small></p>`).join('')}</div><div class="asset-grid">${library.assets.map(a=>`<article class="asset-tile">${a.type==='video'?`<video controls data-asset="public/${a.id}"></video>`:`<img data-asset="public/${a.id}" alt="${escape(a.alt)}">`}<p>${escape(a.alt)}</p></article>`).join('')||'<p class="hint">暂无公共媒体。可上传文件或直接复制到公共目录。</p>'}</div></section><h2>文章素材库</h2>${state.articles.length?state.articles.map(a=>`<details class="panel material-group"><summary>${escape(a.title)} · ${a.sources.length} 篇参考 · ${a.assets.length} 项素材</summary><div>${a.sources.map(s=>`<p>${escape(s.title)}</p>`).join('')}</div><div class="asset-grid">${a.assets.map(asset=>assetTile(a,asset)).join('')||'<p class="hint">暂无媒体素材</p>'}</div></details>`).join(''):empty('给内容一个更好的视觉表达', '导入文章后，来源素材会自动归档。', `<button class="button primary" id="material-import">${icon('plus')} 导入文章</button>`)}`;
  $('#material-import')?.addEventListener('click', openImport);
  bindAssets($('#main'));
  hydrateImages();
  $('#sync-public').onclick=renderMaterials;
  $('#public-upload').onchange=async e=>{const b=e.target;b.disabled=true;try{for(const file of e.target.files){const form=new FormData();form.append('file',file);await api('/api/materials/public',{method:'POST',body:form});}await renderMaterials();toast('公共资料已保存');}catch(err){toast(err.message);b.disabled=false;}};
  $('#public-fetch').onclick=async()=>{const b=$('#public-fetch');b.disabled=true;b.textContent='正在抓取';try{await api('/api/materials/public/references',{method:'POST',body:JSON.stringify({url:$('#public-url').value})});await renderMaterials();toast('公共参考资料已保存');}catch(err){toast(err.message);b.disabled=false;b.textContent='抓取网址';}};
}
