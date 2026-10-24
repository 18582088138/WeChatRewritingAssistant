import { icon } from './icons.js';
import { $, $$ } from './core/dom.js';
import { connectionConfig } from './core/api.js';
import { closeNavigation, toggleNavigation } from './core/navigation.js';
import { setView, openArticle, boot } from './application/router.js';
import { render, refresh } from './application/workspace.js';
import { bindImportDialog } from './features/import.js';
import { saveDraft } from './features/editor/draft.js';
import { bindAssetDialog } from './features/editor/assets.js';
import { renderLibrary } from './pages/library.js';
import { renderEditor } from './pages/editor.js';
import { state } from './core/state.js';
import { configureRuntime } from './core/runtime.js';

let pollBusy = false;
configureRuntime({ render, refresh, renderEditor, renderLibrary, setView, openArticle });
$$('.nav-item').forEach((b) => (b.onclick = () => setView(b.dataset.view)));
$('#mobile-menu').onclick = toggleNavigation;
$('#refresh').onclick = () => refresh();
$('.brand').onclick = (e) => {
  e.preventDefault();
  setView('library');
};
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's' && state.current) {
    e.preventDefault();
    saveDraft();
  }
  if (['Enter', ' '].includes(e.key) && e.target.matches('[data-article]')) {
    e.preventDefault();
    openArticle(e.target.dataset.article);
  }
});
window.addEventListener('beforeunload', (e) => {
  if (state.dirty) {
    e.preventDefault();
    e.returnValue = '';
  }
});
setInterval(async () => {
  if (pollBusy || state.dirty || document.hidden || !connectionConfig.base) return;
  pollBusy = true;
  try {
    const wasBusy =
      state.articles.some((a) => a.status === 'Process') || state.current?.status === 'Process';
    if (wasBusy) {
      const currentId = state.current?.id,
        tab = state.tab;
      await refresh(false);
      if (state.current?.id === currentId) state.tab = tab;
      if (!document.querySelector('dialog[open]')) render();
    }
  } finally {
    pollBusy = false;
  }
}, 4000);
$$('[data-icon]').forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeNavigation();
    $('#mobile-menu').focus();
  }
  if (e.key === 'Tab' && document.body.classList.contains('nav-open')) {
    const controls = [$('#mobile-menu'), $('.brand'), ...$$('.nav-item')];
    const index = controls.indexOf(document.activeElement);
    if ((e.shiftKey && index <= 0) || (!e.shiftKey && index === controls.length - 1)) {
      e.preventDefault();
      controls[e.shiftKey ? controls.length - 1 : 0].focus();
    }
  }
});
bindImportDialog();
bindAssetDialog();
boot();
