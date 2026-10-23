import { $, toast } from '../../core/dom.js';
import { api } from '../../core/api.js';
import { state } from '../../core/state.js';
import { runtime } from '../../core/runtime.js';

export function editorPayload() {
  return {
    title: $('#draft-title')?.value ?? state.current.title,
    body: $('#draft-body')?.value ?? state.current.body,
    summary: $('#draft-summary')?.value ?? state.current.summary,
    keywords: ($('#draft-keywords')?.value ?? state.current.keywords.join('，'))
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean),
    revision: state.current.revision,
  };
}

export async function saveDraft(silent = false) {
  if (!state.dirty) return true;
  try {
    state.current = await api('/api/articles/' + state.current.id, {
      method: 'PATCH',
      body: JSON.stringify(editorPayload()),
    });
    state.dirty = false;
    if (!silent) {
      runtime.renderEditor();
      toast('修改已保存，审稿结果已重置');
    }
    return true;
  } catch (err) {
    toast(err.message);
    return false;
  }
}

export function options() {
  const previous = state.current.options || {};
  return {
    word_count: Number($('#word-count')?.value || previous.word_count || state.config?.generation.word_count || 1800),
    style: $('#writing-style')?.value || previous.style || state.config?.generation.style || '专业、自然、克制的中文科技解读',
    platform: $('#target-platform')?.value || previous.platform || 'wechat',
    provider: $('#model-provider')?.value || previous.provider || state.config?.generation.provider || 'deepseek',
    research: $('#research')?.checked ?? true,
    related_urls: ($('#related-urls')?.value || '')
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
  };
}

export async function generate(revise) {
  if (!(await saveDraft(true))) return;
  const opts = options();
  opts.revise = revise;
  try {
    state.current = await api(`/api/articles/${state.current.id}/generate`, {
      method: 'POST',
      body: JSON.stringify(opts),
    });
    runtime.renderEditor();
    toast(revise ? '已启动按审稿意见修改与复审' : '已启动写作与审稿，结果会自动保存');
  } catch (err) {
    toast(err.message);
  }
}

export async function reviewCurrent() {
  if (!(await saveDraft(true))) return;
  try {
    state.current = await api(`/api/articles/${state.current.id}/review`, {
      method: 'POST',
      body: JSON.stringify(options()),
    });
    runtime.renderEditor();
  } catch (err) {
    toast(err.message);
  }
}

export async function rewriteSelection() {
  const area = $('#draft-body'),
    selected = state.selection || { start: area.selectionStart, end: area.selectionEnd };
  if (selected.start === selected.end) {
    toast('请先在正文中选择要重写的段落');
    return;
  }
  // JavaScript selection offsets use UTF-16; the Python API counts Unicode code points.
  const start = [...area.value.slice(0, selected.start)].length,
    end = [...area.value.slice(0, selected.end)].length;
  const instruction = $('#rewrite-instruction').value,
    provider = options().provider;
  if (!(await saveDraft(true))) return;
  const b = $('#rewrite-selection');
  b.disabled = true;
  b.textContent = '正在重写';
  try {
    state.current = await api(`/api/articles/${state.current.id}/paragraph`, {
      method: 'POST',
      body: JSON.stringify({ start, end, instruction, provider, revision: state.current.revision }),
    });
    state.selection = null;
    runtime.renderEditor();
    toast('选中段落已重写并保存，其余正文已保留');
  } catch (err) {
    toast(err.message);
    b.disabled = false;
    b.textContent = '重写选中段落';
  }
}
