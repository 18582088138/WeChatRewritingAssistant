import { $, $$, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { download } from '../core/media.js';
import { saveDraft, options } from './editor/draft.js';
import { state, platformNames } from '../core/state.js';
import { runtime } from '../core/runtime.js';

export function bindDelivery() {
  $('#deliver').onclick = async () => {
    if (!(await saveDraft(true))) return;
    const selected = $$('input[name=publish-platform]:checked').map((i) => i.value);
    if (!selected.length) {
      toast('请选择至少一个平台');
      return;
    }
    const b = $('#deliver');
    b.disabled = true;
    try {
      const result = await api(`/api/articles/${state.current.id}/deliver`, {
        method: 'POST',
        body: JSON.stringify({ platforms: selected }),
      });
      state.current = await api(`/api/articles/${state.current.id}`);
      runtime.renderEditor();
      for (const item of result.filter((r) => r.status === 'export_ready'))
        await exportDraft(item.platform);
      toast(
        result
          .map(
            (r) =>
              platformNames[r.platform] +
              (r.status === 'failed'
                ? '：' + r.message
                : r.status === 'draft_saved'
                  ? '：已写入草稿箱'
                  : '：素材包已生成'),
          )
          .join('；'),
      );
    } catch (err) {
      toast(err.message);
      b.disabled = false;
    }
  };
  $('#export-draft').onclick = async () => {
    if (await saveDraft(true)) exportDraft(options().platform);
  };
  $$('[data-export]').forEach((b) => (b.onclick = () => exportDraft(b.dataset.export)));
}

export async function exportDraft(platform) {
  try {
    download(
      await api(`/api/articles/${state.current.id}/export/${platform}`),
      `${platform}-draft.zip`,
    );
  } catch (err) {
    toast(err.message);
  }
}
