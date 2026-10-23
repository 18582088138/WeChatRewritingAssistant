import { $ } from '../core/dom.js';
import { api } from '../core/api.js';
import { releaseMedia } from '../core/media.js';
import { renderLibrary } from '../pages/library.js';
import { renderEditor } from '../pages/editor.js';
import { renderMaterials } from '../pages/materials.js';
import { renderDeliveries } from '../pages/deliveries.js';
import { renderSettings } from '../pages/settings.js';
import { state } from '../core/state.js';

export function render() {
  document.body.dataset.view = state.current ? 'editor' : state.view;
  releaseMedia();
  if (state.current) renderEditor();
  else
    ({
      library: renderLibrary,
      materials: renderMaterials,
      deliveries: renderDeliveries,
      settings: renderSettings,
    })[state.view]();
  $('#nav-count').textContent = state.articles.length;
}

export async function refresh(redraw = true) {
  try {
    const [articles, settings, config] = await Promise.all([api('/api/articles'), api('/api/settings'), api('/api/config')]);
    state.articles = articles;
    state.settings = settings;
    state.config = config;
    state.online = true;
    if (state.current && !state.dirty) {
      const current = articles.find((a) => a.id === state.current.id);
      if (current) state.current = current;
    }
  } catch {
    state.online = false;
  }
  connection();
  if (redraw) render();
}

export function connection() {
  $('#connection-dot').style.background = state.online ? '#77ab67' : '#c7ac7a';
  $('#connection-text').textContent = state.online ? '后端已连接' : '后端未连接';
}
