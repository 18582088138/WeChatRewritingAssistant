import { escape } from '../core/dom.js';

export function reviewHtml(a) {
  if (!a.review)
    return '<p class="hint">等待审稿，或编辑后重新审稿。审稿结果用于辅助判断，最终内容由你确认。</p>';
  const r = a.review;
  return `${a.review_current === false ? '<p class="notice">文案或资料已修改。下面保留最近一次审稿，需重新审稿。</p>' : ''}<div class="review-score">
      <div class="score-ring">${r.score}</div>
      <p>${escape(r.verdict)}<br>
      <span class="hint">基于已抓取来源核对</span>
      </p>
      </div>${r.issues
        .map(
          (i) => `<div class="issue ${i.severity}">
      <strong>${escape(i.category)} · ${i.severity === 'high' ? '需修改' : i.severity === 'medium' ? '建议优化' : '提示'}</strong>
      <p>${escape(i.detail)}</p>${escape(i.suggestion)}</div>`,
        )
        .join('')}${
        r.fact_checks.length
          ? `<details>
      <summary>查看事实核对</summary>${r.fact_checks.map((f) => `<p class="hint">${escape(f.claim)}<br>${escape(f.source_id)} · ${escape(f.status)}<br>${escape(f.reason)}</p>`).join('')}</details>`
          : ''
      }<p class="hint">审稿仅覆盖已提供证据；不代表平台审核或版权投诉结果。</p>`;
}
