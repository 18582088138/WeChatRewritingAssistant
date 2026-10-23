# 应用架构

前端是可独立托管的静态 ES Modules 应用，后端是 Python FastAPI API 服务。两者通过 `/api` HTTP 接口通信；模型密钥、来源抓取、Agent、文件保存与平台投递均在后端执行。

```text
backend/
  app.py                 应用工厂、生命周期、CORS、路由注册
  schemas.py             请求结构与输入约束
  dependencies.py        访问令牌与文章读取依赖
  routes/                articles / generation / assets / preview / settings / delivery
  tasks.py               文章任务互斥、后台执行与重启恢复
  workflow.py            抓取、写作与审稿流程编排
  agents.py              写作 Agent、审稿 Agent 与模型请求
  research.py, network.py 来源研究、抓取与网络约束
  materials.py, render.py 素材、排版、组图和导出
  publishing.py           平台草稿投递
  store.py               文章、素材与历史版本文件存储
  settings_store.py       非敏感平台配置读取
web/
  app.js                 组合模块、注册事件、启动应用
  application/           路由、页面调度、数据刷新
  core/                  状态、API、DOM、媒体、导航、runtime 命令接口
  pages/                 目录、编辑、素材、投递、设置页面
  features/              导入、文案操作、局部重写、图片操作、投递
  components/            文章卡片、素材卡片、审稿反馈、投递面板
  styles/                基础变量、框架、控件、各功能区、响应式样式
  taste.css              按顺序导入样式模块
```

后端入口只组装应用。路由完成请求校验与响应转换，业务流程放在领域模块，存储放在 `store.py`。增加平台应扩展投递模块；增加 Agent 能力应扩展 Agent 与工作流，而不是追加到入口文件。

前端依赖方向为 `app → application → pages → features/components → core`。基础模块不导入页面或业务操作。页面与操作需要刷新或导航时，通过 `core/runtime.js` 的命令接口调用；真实实现由入口注入，避免相互导入产生循环依赖。状态由 `core/state.js` 集中维护，网络与连接配置由 `core/api.js` 管理。

## 独立运行

默认 `SERVE_FRONTEND=true`，后端附带托管 `web/`，便于本地和手机访问。设置 `SERVE_FRONTEND=false` 可只提供 API，不挂载前端。两种模式使用相同业务代码和接口。

```powershell
# 终端一：API 服务
$env:SERVE_FRONTEND = 'false'
$env:CORS_ORIGINS = 'http://127.0.0.1:8080'
conda run --no-capture-output -n xkd_env_py312 python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# 终端二：静态前端
conda run --no-capture-output -n xkd_env_py312 python -m http.server 8080 --bind 127.0.0.1 --directory web
```

打开 `http://127.0.0.1:8080`，在设置中填写后端地址 `http://127.0.0.1:8000`。GitHub Pages 同样只部署 `web/`；线上需 HTTPS API 与对应的 `CORS_ORIGINS`。API key 只写后端 `.env`，浏览器仅配置 API 地址及应用访问令牌。

当前文件存储和任务互斥使用单进程模式，运行一个 Uvicorn worker。多进程部署需要先迁移任务锁、队列与存储协调。

## 模块规模与验证

源码单文件限制为 350 行、16 KB。超出时按职责拆分，不压缩为长行绕过限制。`scripts/check_architecture.py` 检查规模、Python 语法、前端模块存在性、依赖边界与循环导入；CI 同时检查 JavaScript 语法。新增页面应放到 `pages/`，复用视图放到 `components/`，用户操作放到 `features/`。

```powershell
conda run -n xkd_env_py312 python scripts/check_architecture.py
conda run -n xkd_env_py312 python -m pytest -q
conda run -n xkd_env_py312 python scripts/verify_browser.py
conda run -n xkd_env_py312 python scripts/verify_editor.py
conda run -n xkd_env_py312 python scripts/verify_separation.py
```

浏览器脚本依赖 `requirements-dev.txt` 与本机 Chrome。前两个浏览器脚本检查已启动的本地服务；独立部署脚本临时启动 API 与静态服务器，使用隔离数据目录，结束后关闭服务器。以上验证不调用模型服务。
