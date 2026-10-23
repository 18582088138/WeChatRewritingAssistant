import { icon } from '../icons.js';
import { $, $$, escape, date, safeUrl, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { hydrateImages, hydratePreview } from '../core/media.js';
import { rewriteSelection } from '../features/editor/draft.js';
import { makeCards, uploadAsset, openAssetPicker } from '../features/editor/assets.js';
import { showVersion } from '../features/editor/preview.js';
import { assetTile, bindAssets } from '../components/assets.js';
import { state } from '../core/state.js';
import { runtime } from '../core/runtime.js';

export async function renderEditorContent() {
  const a = state.current,
    el = $('#editor-content');
  if (state.tab === 'edit') {
    el.innerHTML = `<input class="editor-title" id="draft-title" value="${escape(a.title)}" aria-label="文章标题" ${a.status === 'Process' ? 'disabled' : ''}>
      <label>一句话总结<input id="draft-summary" value="${escape(a.summary)}" placeholder="生成后展示一句话总结">
      </label>
      <label>关键词（逗号分隔）<input id="draft-keywords" value="${escape(a.keywords.join('，'))}" placeholder="大模型，AI 硬件，行业观察">
      </label>
      <textarea class="editor-body" id="draft-body" placeholder="正文将在这里生成。也可以先手动编写 Markdown，再交给审稿 Agent。" ${a.status === 'Process' ? 'disabled' : ''}>${escape(a.body)}</textarea>
      <div class="editor-toolbar">
      <button class="button secondary small" id="rewrite-selection">${icon('edit')} 重写选中段落</button>
      <button class="button secondary small" id="replace-image">${icon('image')} 插入 / 替换图片</button>
      <button class="button secondary small" id="make-cards" ${!a.body ? 'disabled' : ''}>${icon('grid')} 生成 3:4 组图</button>
      <span class="hint" id="save-state">${a.body.length} 字 · Markdown 编辑</span>
      </div>
      <label>局部重写要求<input id="rewrite-instruction" placeholder="例如：简短一点，保留数据与来源" value="让表达更自然简洁，保留事实与来源">
      </label>
      <p class="hint">电脑：在正文中选中文字后重写。手机：长按文字选择，再点重写按钮。选择原图片的 Markdown 后，可在素材库中替换。</p>`;
    ['draft-title', 'draft-summary', 'draft-keywords', 'draft-body'].forEach(
      (id) =>
        ($('#' + id).oninput = () => {
          state.dirty = true;
          $('#save-state').textContent = '有未保存修改';
        }),
    );
    $('#draft-body').onselect = () => {
      state.selection = {
        start: $('#draft-body').selectionStart,
        end: $('#draft-body').selectionEnd,
      };
    };
    $('#rewrite-selection').onclick = rewriteSelection;
    $('#replace-image').onclick = openAssetPicker;
    $('#make-cards').onclick = makeCards;
  } else if (state.tab === 'preview') {
    el.innerHTML = '<div class="loading">正在排版</div>';
    try {
      const data = await api(`/api/articles/${a.id}/render`);
      if (state.current?.id !== a.id || state.tab !== 'preview') return;
      el.innerHTML = `<div class="preview-prose">
      <h1>${escape(a.title)}</h1>${data.html}</div>`;
      await hydratePreview(el);
    } catch (err) {
      el.textContent = err.message;
    }
  } else if (state.tab === 'sources') {
    el.innerHTML = `<div class="panel-title">
      <h3>事实与出处</h3>
      <span>${a.sources.length} 个来源</span>
      </div>
      <div class="sources-list">${
        a.sources
          .map(
            (s, i) => `<div class="source-item">
      <strong>[S${i + 1}] ${escape(s.title)}</strong>
      <a href="${safeUrl(s.url)}" target="_blank" rel="noopener noreferrer">${escape(s.url)} ${icon('external')}</a>
      <p>${escape(s.text.slice(0, 240))}…</p>
      <span class="hint">抓取于 ${date(s.retrieved_at, true)} · 完整正文已保存在本地</span>
      </div>`,
          )
          .join('') || '<p class="hint">来源仍在抓取，或尚未导入。</p>'
      }</div>
      <div class="panel-title" style="margin-top:28px">
      <h3>文章素材</h3>
      <label class="button secondary small" style="margin:0">${icon('plus')} 上传本地图片<input type="file" id="upload-asset" accept="image/png,image/jpeg,image/webp" hidden style="display:none">
      </label>
      </div>
      <div class="notice">来源素材需人工确认授权与水印，确认后才会用于正文。图片可从编辑页插入或替换。</div>
      <div class="asset-grid">${a.assets.map((asset) => assetTile(a, asset)).join('') || '<p class="hint">暂无素材，上传你的配图开始编辑。</p>'}</div>`;
    const stockBar = document.createElement('div');
    stockBar.className = 'notice';
    stockBar.innerHTML = `<label>图库关键词<input id="stock-query" placeholder="例如 artificial intelligence / semiconductor">
      </label>
      <button class="button secondary small" id="search-stock">${icon('search')} 搜索 Pixabay 素材并保存</button>
      <p class="hint">使用后端 Pixabay 密钥，素材保留作者与许可来源，使用前仍需确认。</p>`;
    el.querySelector('.asset-grid').before(stockBar);
    $('#search-stock').onclick = async () => {
      const query = $('#stock-query').value.trim();
      if (!query) {
        toast('请输入素材关键词');
        return;
      }
      const b = $('#search-stock');
      b.disabled = true;
      try {
        state.current = await api(`/api/articles/${a.id}/stock`, {
          method: 'POST',
          body: JSON.stringify({ query }),
        });
        runtime.renderEditor();
        toast('图库检索完成，匹配素材已保存');
      } catch (err) {
        toast(err.message);
        b.disabled = false;
      }
    };
    bindAssets(el);
    $('#upload-asset').onchange = uploadAsset;
    hydrateImages(el);
  } else {
    el.innerHTML = '<div class="loading">正在读取修订记录</div>';
    try {
      const versions = await api(`/api/articles/${a.id}/versions`);
      if (state.tab !== 'versions' || state.current?.id !== a.id) return;
      el.innerHTML = versions.length
        ? versions
            .map(
              (v, i) =>
                `<div class="version">
      <div>修订 ${v.revision} · ${escape(v.stage)}<br>
      <small>${date(v.updated_at, true)} · ${v.body.length} 字${v.review ? ' · 审稿 ' + v.review.score + ' 分' : ''}</small>
      </div>
      <button class="button secondary small" data-version="${i}">阅览此版本</button>
      </div>`,
            )
            .join('')
        : '<p class="hint">生成或保存文案后，这里会记录历史版本。</p>';
      $$('[data-version]').forEach(
        (b) => (b.onclick = () => showVersion(versions[Number(b.dataset.version)])),
      );
    } catch (err) {
      el.textContent = err.message;
    }
  }
}
