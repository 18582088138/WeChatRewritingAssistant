import { icon } from '../icons.js';
import { escape } from '../core/dom.js';
import { platformNames } from '../core/state.js';

export function deliveryPanel(a) {
  return `<div class="panel">
      <div class="panel-title">
      <h3>${icon('external')} 多平台草稿投递</h3>
      <span>最终发布由你决定</span>
      </div>
      <p class="hint">公众号写入官方草稿箱；其他平台生成适配素材包，在平台中手动保存草稿。</p>
      <div class="platform-select">${Object.entries(platformNames)
        .map(
          ([id, n]) =>
            `<label>
      <input type="checkbox" value="${id}" name="publish-platform" ${id === 'wechat' ? 'checked' : ''}>${n}</label>`,
        )
        .join('')}</div>
      <div class="section-actions">
      <button class="button primary" id="deliver" ${!a.body || a.status === 'Process' ? 'disabled' : ''}>准备 / 投递所选平台</button>
      <button class="button secondary" id="export-draft" ${!a.body ? 'disabled' : ''}>下载图文包</button>
      </div>${a.deliveries
        .slice(-4)
        .map(
          (d) =>
            `<div class="delivery-row">
      <div class="platform-text">
      <strong>${platformNames[d.platform]} · ${d.status === 'draft_saved' ? '已存入草稿箱' : d.status === 'export_ready' ? '素材包就绪' : '投递失败'}</strong>
      <p>${escape(d.message)}</p>
      </div>${d.status === 'export_ready' ? `<button class="button secondary small" data-export="${d.platform}">下载素材包</button>` : ''}</div>`,
        )
        .join('')}</div>`;
}
