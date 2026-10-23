import { icon } from '../icons.js';
import { escape, date } from '../core/dom.js';
import { statusNames } from '../core/state.js';

export function articleCard(a) {
  const cover = a.assets.find((x) => x.type === 'image' && !x.id.startsWith('card-'));
  const key = a.keywords[0] || '行业要闻';
  const stage = a.error
    ? '处理失败，可重试'
    : a.review?.issues.some((i) => i.severity === 'high')
      ? '待人工确认'
      : a.status === 'Process'
        ? a.stage
        : statusNames[a.status];
  const action = a.status === 'New' ? '开始创作' : a.status === 'Process' ? '查看进度' : '编辑文案';
  const host = a.url ? new URL(a.url).hostname.replace(/^www\./, '') : '界面示例';
  return `<article class="article-card ${cover ? 'has-cover' : 'text-card'}" data-article="${a.id}" tabindex="0" role="button" aria-label="打开 ${escape(a.title)}">${
    cover
      ? `<div class="card-cover">
      <img data-asset="${a.id}/${cover.id}" alt="${escape(cover.alt)}" loading="lazy">
      </div>`
      : ''
  }<div class="card-body">
      <div class="card-tags">
      <span class="tag">${escape(key)}</span>
      <time class="card-date">${date(a.updated_at || a.created_at)}</time>
      </div>
      <h3>${escape(a.title)}</h3>
      <p>${escape(a.summary || a.error || '原始来源已导入。选择篇幅与风格，开始整理这条行业信号。')}</p>
      <div class="article-evidence">
      <span>${escape(host)}</span>
      <span>${a.sources.length} 个来源 · ${a.body.length} 字</span>
      </div>
      <div class="card-bottom">
      <span class="status ${a.error ? 'error' : a.status}">
      <i>
      </i>${escape(stage)}</span>
      <span class="article-action">${action}${icon('arrow')}</span>
      </div>
      </div>
      </article>`;
}
