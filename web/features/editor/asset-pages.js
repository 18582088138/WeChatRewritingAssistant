import { $, } from '../../core/dom.js';
import { hydrateImages } from '../../core/media.js';
import { assetTile, bindAssets } from '../../components/assets.js';
import { state } from '../../core/state.js';

export function assetPages(el) {
  let index=0; const size=6;
  function draw(){
    const article=state.current, assets=article.assets;
    const pages=Math.max(1,Math.ceil(assets.length/size));index=Math.min(index,pages-1);
    el.innerHTML=`<div class="page-controls"><button class="button secondary small" id="assets-prev" ${index===0?'disabled':''}>上一页素材</button><span>${index+1} / ${pages} · ${assets.length} 项</span><button class="button secondary small" id="assets-next" ${index+1===pages?'disabled':''}>下一页素材</button></div><div class="asset-grid">${assets.slice(index*size,(index+1)*size).map(a=>assetTile(article,a)).join('')||'<p class="hint">暂无素材</p>'}</div>`;
    $('#assets-prev').onclick=()=>{index--;draw();};$('#assets-next').onclick=()=>{index++;draw();};
    bindAssets(el);hydrateImages(el);
  }
  draw();
}
