import { $, escape } from '../../core/dom.js';
import { hydratePreview } from '../../core/media.js';

export function pagedPreview(el, title, pages) {
  let index=0;
  function draw(){
    el.innerHTML=`<div class="page-controls"><button class="button secondary small" id="preview-prev" ${index===0?'disabled':''}>上一页</button><span>第 ${index+1} / ${pages.length} 页</span><button class="button secondary small" id="preview-next" ${index===pages.length-1?'disabled':''}>下一页</button></div><article class="preview-prose paged-article"><h1>${escape(title)}</h1>${pages[index]}</article>`;
    $('#preview-prev').onclick=()=>{index--;draw();};$('#preview-next').onclick=()=>{index++;draw();};
    hydratePreview(el);
  }
  draw();
}
