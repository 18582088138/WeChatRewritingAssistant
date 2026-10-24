export function formatKeywords(keywords, platform) {
  const tags=keywords.map(k=>k.replace(/^#+|#+$/g,'').trim()).filter(Boolean);
  return platform==='wechat'?tags.join('，'):tags.map(k=>platform==='weibo'?`#${k.replace(/\s+/g,'')}#`:`#${k.replace(/\s+/g,'')}`).join(' ');
}
