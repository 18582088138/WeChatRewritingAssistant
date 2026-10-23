import { icon } from '../icons.js';
import { $, $$, escape, date, heading, empty } from '../core/dom.js';
import { state, platformNames } from '../core/state.js';
import { runtime } from '../core/runtime.js';

export function renderDeliveries() {
  const rows = state.articles
    .flatMap((a) => a.deliveries.map((d) => ({ a, d })))
    .sort((x, y) => y.d.at.localeCompare(x.d.at));
  $('#main').innerHTML =
    heading(
      'READY FOR YOUR AUDIENCE',
      '草稿投递',
      '查看草稿写入结果与素材包记录，最终发送在各平台完成。',
    ) +
    `<div class="panel">${
      rows.length
        ? rows
            .map(
              ({ a, d }) => `<div class="delivery-row">
      <div class="platform-logo">${icon('send')}</div>
      <div class="platform-text">
      <strong>${escape(a.title)}</strong>
      <p>${platformNames[d.platform]} · ${escape(d.message)}</p>
      <small>${date(d.at, true)}${d.media_id ? ' · media_id: ' + escape(d.media_id) : ''}</small>
      </div>
      <span class="pill ${d.status === 'failed' ? 'warning' : ''}">${d.status === 'draft_saved' ? '草稿已写入' : d.status === 'export_ready' ? '素材包就绪' : '失败'}</span>
      <button class="button secondary small" data-open-delivery="${a.id}">打开文章</button>
      </div>`,
            )
            .join('')
        : empty(
            '内容准备好了，再出发',
            '完成文案后，在编辑页面选择目标平台。<br>公众号写入草稿箱，其他平台导出图文素材包。',
          )
    }</div>`;
  $$('[data-open-delivery]').forEach(
    (b) => (b.onclick = () => runtime.openArticle(b.dataset.openDelivery)),
  );
}
