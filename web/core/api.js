export const connectionConfig = {
  base:
    localStorage.getItem('signal.api') ||
    (location.hostname.endsWith('github.io') ? '' : location.origin),
  token: sessionStorage.getItem('signal.token') || '',
};
export function saveConnection(base, token) {
  connectionConfig.base = base;
  connectionConfig.token = token;
  localStorage.setItem('signal.api', base);
  sessionStorage.setItem('signal.token', token);
}
export function authHeaders() {
  return connectionConfig.token ? { Authorization: 'Bearer ' + connectionConfig.token } : {};
}

export async function api(path, options = {}) {
  if (!connectionConfig.base)
    throw new Error(
      '请在设置中配置后端地址。GitHub Pages 提供前端，AI 与文件服务由 Python 后端运行。',
    );
  const headers = {
    ...authHeaders(),
    ...(options.body && !(options.body instanceof FormData)
      ? { 'Content-Type': 'application/json' }
      : {}),
    ...options.headers,
  };
  let response;
  try {
    response = await fetch(connectionConfig.base.replace(/\/$/, '') + path, {
      ...options,
      headers,
    });
  } catch {
    throw new Error('无法连接后端，请检查服务地址、HTTPS 与网络');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === 'string' ? data.detail : `请求失败（${response.status}），请检查输入`,
    );
  }
  return response.headers.get('content-type')?.includes('json') ? response.json() : response.blob();
}
