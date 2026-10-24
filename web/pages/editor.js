import { icon } from '../icons.js';
import { $, $$, escape, date } from '../core/dom.js';
import { saveDraft, generate, reviewCurrent } from '../features/editor/draft.js';
import { openPreview } from '../features/editor/preview.js';
import { bindDelivery } from '../features/delivery.js';
import { deliveryPanel } from '../components/delivery.js';
import { reviewHtml } from '../components/review.js';
import { renderEditorContent } from './editor-content.js';
import { state, platformNames, statusNames } from '../core/state.js';
import { runtime } from '../core/runtime.js';
import { openReferences } from '../features/editor/references.js';

export function renderEditor() {
  document.body.dataset.view = 'editor';
  const a = state.current,
    busy = a.status === 'Process',
    opts = { ...(state.config?.generation || {}), ...(a.options || {}) };
  $('#main').innerHTML =
    `<button class="back-link" id="back-library">${icon('back')}返回文章目录</button>
      <div class="editor-head">
      <div>
      <h1>${escape(a.title)}</h1>
      <p>${statusNames[a.status]} · ${escape(a.stage)} · ${a.sources.length} 个来源 · 第 ${a.version_number || 1} 版</p>
      </div>
      <div class="section-actions">
      <button class="button secondary" id="open-preview" ${!a.body ? 'disabled' : ''}>${icon('external')} 打开阅览</button>
      <button class="button primary" id="save-draft" ${busy ? 'disabled' : ''}>保存修改</button>
      <button class="button secondary" id="save-version" ${busy || !a.body ? 'disabled' : ''}>另存为新版本</button>
      </div>
      </div>${a.error ? `<div class="notice error-notice">${escape(a.error)}</div>` : ''}
    <div class="editor-layout">
      <div>
      <div class="panel">
      <div class="editor-tabs">${[
        ['edit', '文案编辑'],
        ['preview', '图文预览'],
        ['sources', '来源与素材'],
        ['versions', '修订记录'],
      ]
        .map(
          ([t, label]) =>
            `<button class="editor-tab ${state.tab === t ? 'active' : ''}" data-editor-tab="${t}">${label}</button>`,
        )
        .join('')}</div>
      <div id="editor-content">
      </div>
      </div><div class="panel source-textbox"><h3>参考来源</h3><p class="hint">出处独立保存，不计入正文篇幅。</p><textarea readonly aria-label="参考来源" rows="${Math.min(7,Math.max(3,a.sources.length*2))}">${escape(a.sources.map(s=>s.title+'\n'+s.url).join('\n\n'))}</textarea></div>${deliveryPanel(a)}</div>
      <aside class="editor-aside">
      <button class="button secondary full-width reference-launch" id="open-references">参考资料浮窗 · ${a.sources.length} 篇</button>
      <div class="panel">
      <div class="panel-title">
      <h3>${icon('edit')} 创作设置</h3>
      <span>写作 Agent</span>
      </div>
      <label>目标平台<select id="target-platform">${Object.entries(platformNames)
        .map(
          ([id, n]) =>
            `<option value="${id}" ${opts.platform === id ? 'selected' : ''}>${n}</option>`,
        )
        .join('')}</select>
      </label>
      <label>目标篇幅<select id="word-count">${(state.config?.generation.word_count_choices||[600,1000,1200,1800,2500,4000]).map((n) => `<option value="${n}" ${(opts.word_count || state.config?.generation.word_count || 1800) === n ? 'selected' : ''}>约 ${n} 字</option>`).join('')}</select>
      </label>
      <label>语言风格<input id="writing-style" value="${escape(opts.style || state.config?.generation.style || '专业、自然、克制的中文科技解读')}">
      </label>
      <label>模型服务<select id="model-provider">
      <option value="deepseek" ${opts.provider !== 'openrouter' ? 'selected' : ''}>DeepSeek</option>
      <option value="openrouter" ${opts.provider === 'openrouter' ? 'selected' : ''}>OpenRouter</option>
      </select>
      </label>
      <label class="checkbox">
      <input type="checkbox" id="research" ${opts.research !== false ? 'checked' : ''}>联网搜索关联来源</label>
      <details>
      <summary>补充关联来源</summary>
      <label>每行一个链接，最多 4 个<textarea id="related-urls" rows="3" placeholder="https://…">${escape((opts.related_urls || []).join('\n'))}</textarea>
      </label>
      </details>
      <button class="button primary full-width" id="generate" ${busy ? 'disabled' : ''}>${busy ? icon('refresh') + ' ' + escape(a.stage) : a.body ? icon('edit') + ' 重新生成 + 审稿' : icon('edit') + ' 开始创作 + 审稿'}</button>${a.review ? '<button class="button secondary full-width" id="revise" style="margin-top:10px">按审稿意见修改 + 复审</button>' : ''}<p class="hint">一轮写作 + 一轮独立审稿，生成与审稿结果分别保存。完成后由你确认内容。</p>
      </div>
      <div class="panel">
      <div class="panel-title">
      <h3>协作进度</h3>
      <span>${busy ? '进行中' : '已保存'}</span>
      </div>${[
        ['external', '研究来源', `${a.sources.length} 个已保存来源`],
        ['edit', '原创撰写', a.body ? `${a.prose_chars ?? a.body.length} 字 · 第 ${a.version_number || 1} 版` : '等待启动'],
        ['check', '独立审稿', a.review ? `${a.review.score} 分 · ${a.review.verdict}` : '等待审稿'],
      ]
        .map(
          ([iconName, t, text]) =>
            `<div class="progress-step">
      <span class="step-icon">${icon(iconName)}</span>
      <div>
      <strong>${t}</strong>
      <small>${escape(text)}</small>
      </div>
      </div>`,
        )
        .join('')}${
        a.events.length
          ? `<details>
      <summary>查看执行日志</summary>${a.events
        .slice(-12)
        .map(
          (e) =>
            `<p class="hint">${date(e.at, true)} · ${escape(e.stage)}<br>${escape(e.message)}</p>`,
        )
        .join('')}</details>`
          : ''
      }</div>
      <div class="panel">
      <div class="panel-title">
      <h3>${icon('check')} 审稿反馈</h3>
      <span>最近一次记录</span>
      </div><div class="review-scroll" tabindex="0" aria-label="审稿反馈">${reviewHtml(a)}</div><button class="button secondary full-width" id="review-only" ${busy || !a.body ? 'disabled' : ''}>${a.review_current ? '查看已保存审稿' : a.review ? '审稿修改后的文案' : '审稿当前文案'}</button>
      </div>
      </aside>
      </div>`;
  const aside = $('.editor-aside'), panels = aside.querySelectorAll(':scope > .panel');
  aside.insertBefore(panels[2], panels[1]);
  $('#back-library').onclick = () => runtime.setView('library');
  $('#save-draft').onclick = () => saveDraft();
  $('#save-version').onclick = () => saveDraft(false, true);
  $('#open-preview').onclick = openPreview;
  $$('[data-editor-tab]').forEach(
    (b) =>
      (b.onclick = async () => {
        if (!(await saveDraft(true))) return;
        state.tab = b.dataset.editorTab;
        renderEditor();
      }),
  );
  $('#generate').onclick = () => generate(false);
  $('#open-references').onclick = openReferences;
  $('#revise')?.addEventListener('click', () => generate(true));
  $('#review-only').onclick = reviewCurrent;
  bindDelivery();
  renderEditorContent();
}
