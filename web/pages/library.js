import { articleCard } from '../components/article-card.js';
import { icon } from '../icons.js';
import { $, $$, escape, heading, empty } from '../core/dom.js';
import { hydrateImages } from '../core/media.js';
import { openImport } from '../features/import.js';
import { state, statusNames } from '../core/state.js';
import { runtime } from '../core/runtime.js';

const demoArticles = [
  {
    title: '从模型到行动：具身智能真正需要解决什么？',
    summary: '理解机器人从感知、决策到执行的技术链路，找到值得持续关注的行业信号。',
    keywords: ['具身智能', '行业观察'],
    status: 'Done',
    cover: 'Embodied AI',
  },
  {
    title: '读懂大模型发布：参数之外，哪些指标更重要',
    summary: '从评测方法、推理成本和实际使用场景出发，建立一套读懂新模型的框架。',
    keywords: ['大模型', '技术解读'],
    status: 'Process',
    cover: 'Beyond LLMs',
  },
  {
    title: 'AI 硬件的下一步：让算力走到用户身边',
    summary: '芯片、终端和软件生态共同影响体验，值得先把产品的真实能力讲清楚。',
    keywords: ['AI 硬件', '产业洞察'],
    status: 'New',
    cover: 'AI × Hardware',
  },
];

export function renderLibrary() {
  const articles = state.demo
    ? demoArticles.map((a, i) => ({
        ...a,
        id: 'demo-' + i,
        created_at: '2026-10-23T08:00:00Z',
        sources: [],
        assets: [],
        body: '',
        stage: statusNames[a.status],
      }))
    : state.articles;
  const counts = (s) => articles.filter((a) => s === 'All' || a.status === s).length;
  const visible = articles.filter(
    (a) =>
      (state.filter === 'All' || a.status === state.filter) &&
      (a.title + ' ' + a.keywords.join(' ')).toLowerCase().includes(state.query.toLowerCase()),
  );
  const needsAttention = articles.filter(
    (a) => a.status === 'New' || a.error || a.review?.issues.some((i) => i.severity === 'high'),
  );
  const finding = state.demo
    ? '示例内容 · 用于预览界面，不会保存到你的文章目录。'
    : !state.online
      ? '连接后端后，可导入来源并开始创作。'
      : needsAttention.length
        ? `${needsAttention.length} 篇内容等待处理，打开文章继续创作。`
        : articles.length
          ? '文案已保存。打开文章，检查来源并继续编辑。'
          : '从一篇报道或论文开始，整理你的第一篇行业解读。';
  const lead = needsAttention[0] || articles[0];
  $('#main').innerHTML =
    heading(
      '',
      '文章工作台',
      finding,
      `<button class="button primary" id="new-article">${icon('plus')}导入文章</button>`,
    ) +
    `<div class="stats" aria-label="文章状态统计">${[
      ['全部文章', 'All'],
      ['待创作', 'New'],
      ['处理中', 'Process'],
      ['已完成', 'Done'],
    ]
      .map(
        ([label, s]) =>
          `<button class="stat ${state.filter === s ? 'selected' : ''}" data-filter="${s}">
      <span class="stat-label">${label}</span>
      <span class="stat-value">${counts(s)}<small>篇</small>
      </span>
      </button>`,
      )
      .join('')}</div>
    <div class="library-workflow">
      <div class="workflow-copy">
      <strong>从来源到草稿，每一步可核对</strong>
      <p>研究来源 → 原创撰写 → 独立审稿 → 人工确认</p>
      </div>${lead ? `<button class="button secondary" data-article="${lead.id}">${icon('edit')}${lead.status === 'New' ? '开始创作' : '继续编辑'}</button>` : `<span class="workflow-note">保留出处与修订记录</span>`}</div>
    <div class="section-title">
      <h2>我的文章 <span>${visible.length} 篇${state.query ? '匹配内容' : ''}</span>
      </h2>
      <div class="section-actions">
      <span class="hint">最近更新优先</span>${!state.demo ? '<button class="sample-link" id="show-demo">查看界面示例</button>' : ''}</div>
      </div>
    ${state.demo ? '<div class="demo-badge">界面示例，不代表真实抓取或生成结果。<button id="exit-demo">退出示例</button></div>' : ''}
    <div class="toolbar">
      <div class="tabs" aria-label="文章状态筛选">${[
        ['All', '全部'],
        ['New', '待创作'],
        ['Process', '处理中'],
        ['Done', '已完成'],
      ]
        .map(
          ([s, label]) =>
            `<button class="tab ${state.filter === s ? 'active' : ''}" data-filter="${s}" aria-pressed="${state.filter === s}">${label}<span>${counts(s)}</span>
      </button>`,
        )
        .join('')}</div>
      <label class="search">${icon('search')}<input id="search" placeholder="搜索标题或关键词" value="${escape(state.query)}" aria-label="搜索文章">
      </label>
      </div>
    <div class="article-grid" data-count="${visible.length}">${visible.length ? visible.map((a, i) => articleCard(a, i)).join('') : empty(state.query ? '没有匹配的内容' : state.filter !== 'All' ? '当前没有' + statusNames[state.filter] + '的文章' : '导入你的第一个行业信号', state.query ? '试试其他关键词，或切换文章状态。' : state.filter !== 'All' ? '切换到全部文章，或导入新的来源。' : '保存原始资料，整理核心事实，再把你的观点写出来。', state.query || state.filter !== 'All' ? '' : '<div class="section-actions"><button class="button primary" id="empty-import">导入第一篇文章</button></div>')}</div>`;
  $('#new-article').onclick = openImport;
  $('#empty-import')?.addEventListener('click', openImport);
  $('#show-demo')?.addEventListener('click', () => {
    state.demo = true;
    runtime.render();
  });
  $('#exit-demo')?.addEventListener('click', () => {
    state.demo = false;
    runtime.render();
  });
  $$('[data-filter]').forEach(
    (b) =>
      (b.onclick = () => {
        state.filter = b.dataset.filter;
        renderLibrary();
      }),
  );
  $('#search').oninput = (e) => {
    const at = e.target.selectionStart;
    state.query = e.target.value;
    renderLibrary();
    $('#search').focus();
    $('#search').setSelectionRange(at, at);
  };
  $$('[data-article]').forEach(
    (el) => (el.onclick = () => runtime.openArticle(el.dataset.article)),
  );
  hydrateImages();
}
