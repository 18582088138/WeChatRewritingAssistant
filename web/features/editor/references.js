import { $, $$, escape, toast, safeUrl } from '../../core/dom.js';
import { api } from '../../core/api.js';
import { hydrateImages } from '../../core/media.js';
import { state } from '../../core/state.js';
import { runtime } from '../../core/runtime.js';
import { saveDraft } from './draft.js';

let basket = [], sourceIndex = 0, pageIndex = 0, insertion = 0, kind = 'text';
let pageSize = 650;
let importing = false;

function importState(value) {
  importing = value;
  ['reference-upload','sync-materials','add-reference-url'].forEach(id=>{if($('#'+id))$('#'+id).disabled=value;});
}

export function openReferences() {
  pageSize = state.config?.platforms?.preview_chars || 650;
  insertion = $('#draft-body')?.selectionStart ?? state.current.body.length;
  if (insertion < 0) insertion = 0;
  basket = []; sourceIndex = 0; pageIndex = 0; kind = 'text';
  let dialog = $('#references-dialog');
  if (!dialog) {
    dialog = document.createElement('dialog');
    dialog.id = 'references-dialog'; dialog.className = 'reference-window';
    document.body.append(dialog);
  }
  renderReferences();
  dialog.show();
}

function renderReferences() {
  const article = state.current;
  const source = article.sources[sourceIndex];
  const text = source?.text || '';
  const count = Math.max(1, Math.ceil(text.length / pageSize));
  pageIndex = Math.min(pageIndex,count-1);
  $('#references-dialog').innerHTML = `<header class="reference-header"><div><h2>参考资料包</h2><p>${article.sources.length} 篇资料 · ${article.assets.length} 项素材</p></div><button class="button secondary small" id="close-references">关闭</button></header>
    <nav class="reference-tabs">${[['text','文章'],['image','图片'],['video','视频']].map(([value,label])=>`<button class="button ${kind===value?'primary':'secondary'} small" data-reference-kind="${value}">${label}</button>`).join('')}</nav>
    <div class="reference-body">${kind==='text'?`<label>选择参考文章<select id="reference-source">${article.sources.map((s,i)=>`<option value="${i}" ${i===sourceIndex?'selected':''}>[S${i+1}] ${escape(s.title)}</option>`).join('')}</select></label>
    ${source?`<p class="hint">原文链接：<a href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.url)}</a><br>${escape(source.published_at||'日期未知')} · ${escape(source.reference_role?.kind||'原始新闻')}</p>`:''}
    <textarea id="reference-text" readonly aria-label="参考文章正文">${escape(text.slice(pageIndex*pageSize,(pageIndex+1)*pageSize))}</textarea>
    <div class="page-controls"><button class="button secondary small" id="reference-prev" ${pageIndex===0?'disabled':''}>上一页</button><span>${pageIndex+1} / ${count}</span><button class="button secondary small" id="reference-next" ${pageIndex+1===count?'disabled':''}>下一页</button></div>
    <div class="desktop-fusion"><button class="button secondary small" id="add-selection">加入选中段落</button><div class="reference-basket">${basket.map((s,i)=>`<p>[S${s.source_id}] ${escape(s.label)} <button data-remove-selection="${i}" class="sample-link">移除</button></p>`).join('')||'<p class="hint">可从不同资料页选择多段。融合稿将插入打开浮窗前的正文光标位置。</p>'}</div><label>融合要求<input id="fusion-instruction" value="自然衔接，保留技术细节和出处"></label><button class="button primary" id="fuse-selections" ${!basket.length?'disabled':''}>融合改写并插入正文</button></div><p class="mobile-fusion-note hint">多段资料融合请在电脑端操作。</p>`:
    `<div class="reference-media-grid">${article.assets.filter(a=>a.type===kind&&!a.id.startsWith('card-')).map(a=>`<article>${kind==='image'?`<img data-asset="${article.id}/${a.id}" alt="${escape(a.alt)}">`:`<video controls data-asset="${article.id}/${a.id}"></video>`}<p>${escape(a.alt)}${!a.approved?' · 待确认':''}</p><button class="button secondary small" data-reference-media="${a.id}">插入${kind==='image'?'图片':'视频'}</button></article>`).join('')||'<p class="hint">暂无本地素材，可在下方添加。</p>'}</div>${kind==='video'?article.sources.flatMap(s=>s.embedded_media||[]).map(v=>`<p><a href="${safeUrl(v.url)}" target="_blank" rel="noopener noreferrer">外部播放器（未下载）</a></p>`).join(''):''}`}</div>
    <section class="reference-import"><label class="button secondary small">添加文件<input id="reference-upload" type="file" multiple accept=".md,.txt,.pdf,.html,.png,.jpg,.jpeg,.gif,.webp,.mp4,.mov,.webm" hidden></label><button class="button secondary small" id="sync-materials">同步文件夹</button><details><summary>添加文章链接 / 查看目录</summary><input id="reference-url" type="url" placeholder="https://…"><button class="button secondary small" id="add-reference-url">抓取并加入资料包</button><p class="hint storage-path">${escape(article.storage_path||'文章目录')}/manual/{images,videos,texts}</p></details></section>`;
  $('#close-references').onclick = () => $('#references-dialog').close();
  $$('[data-reference-kind]').forEach(b=>b.onclick=()=>{kind=b.dataset.referenceKind;renderReferences();});
  $('#reference-source')?.addEventListener('change',e=>{sourceIndex=Number(e.target.value);pageIndex=0;renderReferences();});
  $('#reference-prev')?.addEventListener('click',()=>{pageIndex--;renderReferences();});
  $('#reference-next')?.addEventListener('click',()=>{pageIndex++;renderReferences();});
  $('#add-selection')?.addEventListener('click',()=>{
    const area=$('#reference-text'), start=area.selectionStart, end=area.selectionEnd;
    if(start===end){toast('先在参考正文中选择一段内容');return;}
    const prefix=text.slice(0,pageIndex*pageSize);
    basket.push({source_id:sourceIndex+1,start:[...prefix+area.value.slice(0,start)].length,end:[...prefix+area.value.slice(0,end)].length,label:area.value.slice(start,end).slice(0,80)});
    renderReferences();
  });
  $$('[data-remove-selection]').forEach(b=>b.onclick=()=>{basket.splice(Number(b.dataset.removeSelection),1);renderReferences();});
  $('#fuse-selections')?.addEventListener('click',async()=>{
    const button=$('#fuse-selections'), instruction=$('#fusion-instruction').value;
    const area=$('#draft-body');
    const position=[...(area?.value||article.body).slice(0,insertion)].length;
    if(!(await saveDraft(true)))return;
    button.disabled=true;button.textContent='正在融合改写';
    try{
      state.current=await api(`/api/articles/${article.id}/fuse`,{method:'POST',body:JSON.stringify({selections:basket.map(({label,...s})=>s),position,revision:state.current.revision,instruction,provider:state.current.options?.provider||state.config?.generation.provider||'deepseek'})});
      state.dirty=false;$('#references-dialog').close();runtime.renderEditor();toast('参考内容已融合插入并保存，等待复审');
    }catch(err){toast(err.message);button.disabled=false;button.textContent='融合改写并插入正文';}
  });
  $$('[data-reference-media]').forEach(b=>b.onclick=()=>{
    const asset=article.assets.find(a=>a.id===b.dataset.referenceMedia), area=$('#draft-body');
    if(!area){toast('切换到文案编辑后插入素材');return;}
    const label=String(asset.alt || (asset.type==='video'?'参考视频':'参考配图')).replace(/[\[\]\n]/g,'');
    const path=`/api/articles/${article.id}/assets/${asset.id}/file`;
    const content=asset.type==='image'?`![${label}](${path})`:`[视频：${label}](${path})`;
    area.value=area.value.slice(0,insertion)+'\n\n'+content+'\n\n'+area.value.slice(insertion);
    state.dirty=true;$('#references-dialog').close();toast('素材已插入，请保存修改');
  });
  $('#reference-upload').onchange=async e=>{
    if(importing)return;
    const files=[...e.target.files];importState(true);
    try{for(const file of files){const form=new FormData();form.append('file',file);const updated=await api(`/api/articles/${article.id}/materials`,{method:'POST',body:form});if(state.current?.id===article.id)state.current=updated;}if(state.current?.id===article.id)renderReferences();toast('补充材料已归档');}catch(err){toast(err.message);}finally{importState(false);}
  };
  $('#sync-materials').onclick=async()=>{if(importing)return;importState(true);try{const updated=await api(`/api/articles/${article.id}/materials/sync`,{method:'POST'});if(state.current?.id===article.id){state.current=updated;renderReferences();}toast('文件夹同步完成');}catch(err){toast(err.message);}finally{importState(false);}};
  $('#add-reference-url').onclick=async()=>{
    if(importing)return;importState(true);
    const url=$('#reference-url').value;const b=$('#add-reference-url');b.disabled=true;b.textContent='正在抓取';
    try{const updated=await api(`/api/articles/${article.id}/references`,{method:'POST',body:JSON.stringify({url})});if(state.current?.id===article.id){state.current=updated;renderReferences();}toast('参考资料已加入');}catch(err){toast(err.message);b.textContent='抓取并加入资料包';}finally{importState(false);}
  };
  importState(importing);
  hydrateImages($('#references-dialog'));
}
