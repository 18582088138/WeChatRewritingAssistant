import { $, escape, heading, toast } from '../core/dom.js';
import { connectionConfig, saveConnection, api } from '../core/api.js';
import { state, platformNames } from '../core/state.js';
import { runtime } from '../core/runtime.js';

export function renderSettings() {
  const settings = state.settings;
  $('#main').innerHTML =
    heading('', '设置与连接', '配置服务连接与草稿投递，密钥保存在后端。') +
    `<div class="settings-sections">
    <section class="settings-section">
      <div class="settings-description">
      <h2>后端服务</h2>
      <p>连接你的内容工作台，文章、素材和修订保存在这里。</p>
      <span class="pill ${state.online ? '' : 'warning'}">${state.online ? '已连接' : '未连接'}</span>
      <p class="hint">双击 Start.cmd 启动完整应用，界面和 API 使用同一地址。手机可使用电脑的局域网地址。</p>
      </div>
      <div class="panel">
      <form id="connection-form">
      <label>后端地址<input type="url" name="api" value="${escape(connectionConfig.base)}" placeholder="http://127.0.0.1:8000" required>
      </label>
      <label>访问令牌<input type="password" name="token" value="${escape(connectionConfig.token)}" placeholder="与后端 APP_TOKEN 一致" autocomplete="off">
      </label>
      <p class="hint">访问令牌仅保留在当前浏览器会话。</p>
      <div class="form-actions">
      <button class="button primary" type="submit">保存并连接</button>
      </div>
      </form>
      </div>
      </section>
    <section class="settings-section">
      <div class="settings-description">
      <h2>写作与审稿模型</h2>
      <p>同一模型服务分别承担写作和独立审稿，两次结果均会保存。</p>
      <p class="hint">在后端 .env 修改 API_KEY、BASE_URL 和 MODEL，重启服务后生效。</p>
      </div>
      <div class="panel">${['deepseek', 'openrouter']
        .map((p) => {
          const item = settings?.providers.find((x) => x.id === p);
          return `<div class="settings-platform">
      <div class="platform-text">
      <strong>${p === 'deepseek' ? 'DeepSeek' : 'OpenRouter'}</strong>
      <p>${escape(item?.model || '连接后端后读取配置')}</p>
      </div>
      <span class="pill ${item?.configured ? '' : 'warning'}">${item?.configured ? '已配置' : '未配置'}</span>
      </div>`;
        })
        .join('')}</div>
      </section>
    <section class="settings-section">
      <div class="settings-description">
      <h2>平台草稿工作流</h2>
      <p>先准备草稿，再到平台确认和发送。</p>
      <p class="hint">公众号支持官方草稿接口。其他平台提供文案和素材包，需手动保存到草稿箱。</p>
      </div>
      <div class="panel">${Object.entries(platformNames)
        .map(
          ([id, name]) =>
            `<div class="settings-platform">
      <div class="platform-text">
      <strong>${name}</strong>
      <p>${id === 'wechat' ? '官方接口写入草稿箱，需账号权限与 IP 白名单' : '导出图文素材包，在平台手动保存草稿'}</p>
      </div>
      <span class="pill ${id === 'wechat' && !settings?.wechat_configured ? 'warning' : ''}">${id === 'wechat' ? (settings?.wechat_configured ? '凭据已配置' : '待配置') : '图文包'}</span>
      </div>`,
        )
        .join('')}</div>
      </section>
    <section class="settings-section">
      <div class="settings-description">
      <h2>微信公众号</h2>
      <p>设置草稿署名与封面素材。</p>
      <p class="hint">App ID 和 App Secret 在后端 .env 配置。封面为空时，会上传文章的第一张已确认图片。</p>
      <div class="draft-mini">
      <span>草稿示例</span>
      <strong>行业要闻解读</strong>
      <p>${escape(settings?.wechat?.author || '未设置署名')} · ${settings?.wechat?.thumb_media_id ? '使用指定封面' : '使用已确认的文章配图'}</p>
      </div>
      </div>
      <div class="panel">
      <form id="wechat-form">
      <label>署名（最多 8 字）<input name="author" maxlength="8" value="${escape(settings?.wechat?.author || '')}" placeholder="例如：科技观察">
      </label>
      <label>封面 thumb_media_id（可选）<input name="thumb_media_id" value="${escape(settings?.wechat?.thumb_media_id || '')}" placeholder="留空时使用文章配图">
      </label>
      <p class="hint">${state.online ? '配置保存后用于新增公众号草稿。' : '请先连接后端，再保存平台配置。'}</p>
      <div class="form-actions">
      <button class="button secondary" type="submit" ${!state.online ? 'disabled' : ''}>保存平台配置</button>
      </div>
      </form>
      </div>
      </section>
    </div>`;
  $('#connection-form').onsubmit = async (e) => {
    e.preventDefault();
    const fields = new FormData(e.target);
    const address = String(fields.get('api')).replace(/\/$/, '');
    const parsed = new URL(address);
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      toast('后端地址需要使用 HTTP 或 HTTPS');
      return;
    }
    saveConnection(address, String(fields.get('token')));
    await runtime.refresh();
    toast(state.online ? '后端连接成功' : '连接失败，请检查服务与令牌');
  };
  $('#wechat-form').onsubmit = async (e) => {
    e.preventDefault();
    try {
      state.settings = await api('/api/settings', {
        method: 'POST',
        body: JSON.stringify({ wechat: Object.fromEntries(new FormData(e.target)) }),
      });
      toast('公众号草稿配置已保存');
    } catch (err) {
      toast(err.message);
    }
  };
}
