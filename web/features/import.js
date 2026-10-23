import { $, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { state } from '../core/state.js';
import { runtime } from '../core/runtime.js';

export function openImport() {
  $('#import-dialog').showModal();
}

export function bindImportDialog() {
  $('#cancel-import').onclick = () => $('#import-dialog').close();
  $('#import-form').onsubmit = async (e) => {
    e.preventDefault();
    const button = $('button[type=submit]', e.target);
    button.disabled = true;
    try {
      const fields = Object.fromEntries(new FormData(e.target));
      const a = await api('/api/articles', { method: 'POST', body: JSON.stringify(fields) });
      state.demo = false;
      $('#import-dialog').close();
      e.target.reset();
      await runtime.refresh(false);
      await runtime.openArticle(a.id);
      toast('文章已导入，来源正在准备');
    } catch (err) {
      toast(err.message);
    } finally {
      button.disabled = false;
    }
  };
}
