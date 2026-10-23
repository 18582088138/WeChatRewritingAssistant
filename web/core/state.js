export const state = {
  view: 'library',
  filter: 'All',
  query: '',
  articles: [],
  current: null,
  tab: 'edit',
  settings: null,
  online: false,
  dirty: false,
  selection: null,
  demo: false,
};
export const platformNames = { wechat: '微信公众号', x: 'X', xiaohongshu: '小红书', weibo: '微博' };
export const statusNames = { New: '待创作', Process: '处理中', Done: '已完成' };
