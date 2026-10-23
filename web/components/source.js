import { escape, date, safeUrl } from '../core/dom.js';
import { icon } from '../icons.js';

export function sourceItem(source, index) {
  const quality = source.quality || {};
  const reports = source.media_downloads || [];
  const problems = reports.filter((item) => item.status !== 'saved');
  const embeds = source.embedded_media || [];
  return `<div class="source-item">
    <strong>[S${index + 1}] ${escape(source.title)}</strong>
    <a href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.url)} ${icon('external')}</a>
    <p>${escape(source.text.slice(0, 240))}…</p>
    <span class="hint">抓取于 ${date(source.retrieved_at, true)} · ${(quality.full_text_chars ?? Array.from(source.text).length).toLocaleString()} 字符已保存${source.published_at ? ' · 原文发布 ' + escape(source.published_at) : ''}</span>
    ${source.quality ? `<p class="hint">图片 ${quality.saved_images || 0}/${quality.discovered_images || 0} · 视频 ${quality.saved_videos || 0}/${quality.discovered_videos || 0} · 外部播放器 ${embeds.length}</p>` : ''}
    ${(quality.warnings || []).map((warning) => `<p class="hint">${escape(warning)}</p>`).join('')}
    ${problems.length ? `<details><summary>素材抓取说明（${problems.length} 项）</summary>${problems.map((item) => `<p class="hint">${item.type === 'video' ? '视频' : '图片'} · ${escape(item.reason || item.status)}<br><a href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">查看素材来源</a></p>`).join('')}</details>` : ''}
    ${embeds.length ? `<details><summary>外部视频来源（未下载文件）</summary>${embeds.map((item) => `<p class="hint"><a href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">${escape(item.title || item.url)}</a></p>`).join('')}</details>` : ''}
    <details><summary>查看已保存全文</summary><pre class="source-full-text">${escape(source.text)}</pre></details>
  </div>`;
}
