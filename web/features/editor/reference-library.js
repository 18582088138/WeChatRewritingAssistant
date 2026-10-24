import { api } from '../../core/api.js';
import { state } from '../../core/state.js';

let library={sources:[],assets:[]};
export async function loadPublic() { library=await api('/api/materials/public');return library; }
export function referenceLibrary() {return library;}
export function sourcesFor(article, scope='all') {
  return [...(scope==='public'?[]:article.sources.map((s,i)=>({...s,sourceIndex:i}))),...(scope==='article'?[]:library.sources.map((s,i)=>({...s,publicIndex:i})))];
}
export function mediaFor(article, scope='all') {
  return [...(scope==='public'?[]:article.assets.map(a=>({...a,libraryArticle:article.id}))),...(scope==='article'?[]:library.assets.map(a=>({...a,libraryArticle:'public'})))];
}
export async function attachPublic(item) {
  const result=await api(`/api/articles/${state.current.id}/materials/public`,{method:'POST',body:JSON.stringify(item)});
  state.current=result.article;
  return result;
}
