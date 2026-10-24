import { $, $$, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { closeNavigation } from '../core/navigation.js';
import { render, refresh } from './workspace.js';
import { renderEditor } from '../pages/editor.js';
import { state } from '../core/state.js';

export function setView(view) {
  if (state.dirty && !confirm('正文有未保存修改，离开会丢失这些修改。确定离开？')) return;
  history.replaceState(null, '', '#' + view);
  state.dirty = false;
  state.view = view;
  state.current = null;
  state.tab = 'edit';
  $$('.nav-item').forEach((el) => el.classList.toggle('active', el.dataset.view === view));
  $('#crumb').textContent = {
    library: '文章工作台',
    materials: '素材库',
    deliveries: '草稿投递',
    settings: '设置与连接',
  }[view];
  closeNavigation();
  render();
}

export async function openArticle(id) {
  if (id.startsWith('demo-')) {
    toast('这是界面示例。请导入真实来源开始创作。');
    return;
  }
  if (state.dirty && !confirm('有未保存修改，确定切换文章？')) return;
  try {
    state.current = await api('/api/articles/' + id);
    history.replaceState(null, '', '#article/' + id);
    state.tab = 'edit';
    state.editing = false;
    state.dirty = false;
    closeNavigation();
    renderEditor();
    $('#crumb').textContent = '文章编辑';
    window.scrollTo({ top: 0 });
  } catch (err) {
    toast(err.message);
  }
}

export async function boot() {
  render();
  await refresh();
  const route = location.hash.slice(1);
  if (['library', 'materials', 'deliveries', 'settings'].includes(route)) setView(route);
  else if (/^article\/[a-f0-9]{32}$/.test(route)) await openArticle(route.slice(8));
}
