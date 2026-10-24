import { $, escape, toast } from '../../core/dom.js';
import { api } from '../../core/api.js';
import { state } from '../../core/state.js';
import { runtime } from '../../core/runtime.js';

export function showRewriteProposal(proposal) {
  let dialog=$('#rewrite-dialog');
  if (!dialog) {dialog=document.createElement('dialog');dialog.id='rewrite-dialog';dialog.className='rewrite-window';document.body.append(dialog);}
  dialog.innerHTML=`<h2>段落修改对比</h2><p class="hint">可继续编辑新段落。确认或点击窗口外，将保存修改。</p><div class="rewrite-columns"><section><h3>修改前</h3><textarea readonly aria-label="修改前">${escape(proposal.before)}</textarea></section><section><h3>修改后</h3><textarea id="proposal-text" aria-label="修改后">${escape(proposal.text)}</textarea></section></div><p class="hint" id="proposal-error"></p><div class="modal-actions"><button class="button secondary" id="discard-proposal">保留原段落</button><button class="button primary" id="apply-proposal">确认修改</button></div>`;
  const articleId=state.current.id;
  let saving=false;
  const apply=async()=>{
    if(saving)return;
    const text=$('#proposal-text').value;
    if(!text.trim()){$('#proposal-error').textContent='新段落不能为空';return;}
    saving=true;$('#apply-proposal').disabled=true;
    try {
      const article=await api(`/api/articles/${articleId}/paragraph/apply`,{method:'POST',body:JSON.stringify({proposal_id:proposal.proposal_id,revision:proposal.revision,text})});
      dialog.close();
      if(state.current?.id===articleId){state.current=article;state.dirty=false;state.editing=false;runtime.renderEditor();}
      toast('段落修改已保存，高亮处为本版修改');
    }catch(err){$('#proposal-error').textContent=err.message;toast(err.message);}finally{saving=false;$('#apply-proposal').disabled=false;}
  };
  $('#apply-proposal').onclick=apply;
  $('#discard-proposal').onclick=()=>dialog.close();
  dialog.onclick=e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)apply();}};
  dialog.oncancel=e=>{e.preventDefault();apply();};
  dialog.showModal();
}
