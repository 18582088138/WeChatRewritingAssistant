# 应用架构

前端是静态 ES Modules 应用，后端是 Python FastAPI API 服务，代码按职责分离。产品部署为同一个完整应用：一个 Python 服务同时提供 `web/` 和 `/api`，一键安装、一键启动。模型密钥、抓取、Agent、保存与投递均在后端执行。本轮只做本地验收，后续统一部署到支持 Python 和持久化存储的平台。

```text
backend/
  app.py                 应用工厂、生命周期、CORS、路由注册
  schemas.py             请求结构与输入约束
  dependencies.py        访问令牌与文章读取依赖
  routes/                articles / generation / assets / preview / settings / delivery / research / references
  tasks.py               文章任务互斥、后台执行与重启恢复
  workflow.py            抓取、写作与审稿流程编排
  agents.py              写作 Agent、审稿 Agent 与模型请求
  research.py            来源提取入口，search/download 的稳定调用接口
  research_*.py          HTML/PDF、媒体发现、下载、搜索、官方索引、质量与模型上下文
  network.py             网络约束与有界下载
  materials.py, render.py 素材、HTML 排版和导出
  card_layout.py         3:4 图文分页、真实配图与字号约束
  pagination.py          HTML 逐页预览
  archive.py             标题目录、原文链接、来源文件组织
  manual_materials.py    GUI 文件和文件夹补充资料同步
  draft_media.py         原创稿配图补足
  configuration.py       JSON、prompts、配置验证与指纹快照
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
config/                  app / research / generation / platforms JSON
  prompts/               写作、审稿、语言风格、融合、压缩 prompts
scripts/local.ps1        Windows 安装和启动统一入口
scripts/launch.py        同源应用启动、旧数据迁移、浏览器打开
```

后端入口只组装应用。路由完成请求校验与响应转换，业务流程放在领域模块，存储放在 `store.py`。增加平台应扩展投递模块；增加 Agent 能力应扩展 Agent 与工作流，而不是追加到入口文件。

前端依赖方向为 `app → application → pages → features/components → core`。基础模块不导入页面或业务操作。页面与操作需要刷新或导航时，通过 `core/runtime.js` 的命令接口调用；真实实现由入口注入，避免相互导入产生循环依赖。状态由 `core/state.js` 集中维护，网络与连接配置由 `core/api.js` 管理。

## 完整应用运行

默认 `SERVE_FRONTEND=true`，同源托管前端和 API。Windows 双击 Install.cmd 安装（本机已有 conda），双击 Start.cmd 启动完整应用。底层入口如下：

```powershell
conda run --no-capture-output -n xkd_env_py312 python scripts/launch.py
```

打开 http://127.0.0.1:8000，无需另配后端。config/app.json 控制监听与浏览器行为，config 其他文件控制研究、生成与排版；密钥只写 .env。SERVE_FRONTEND=false 保留为架构验证接口，不是产品部署方案。GitHub Pages 历史工作流只保留手动触发，本轮不部署；它不能运行完整 Python 应用。

当前文件存储和任务互斥使用单进程模式，运行一个 Uvicorn worker。多进程部署需要先迁移任务锁、队列与存储协调。

## 数据组织

data/articles/原文标题/ 保存稳定 UUID 元数据 article.json；同名任务追加短 ID。source/原文标题/ 与 references/参考标题/ 分别保存标题 Markdown、text 原始 HTML/PDF 和元数据、images、videos。原文 Markdown 第一行是原文链接。manual/images、videos、texts 接收 GUI 与文件夹添加的素材。drafts 保存当前和修订标题稿，versions 保存阶段快照，generated 保存组图、信息图和模型尝试稿，config-history 保存配置版本。

本轮增加 branches/vNNNN.json 作为用户编号版本，branches/media 保存不可变媒体副本。revision 与 version_number 独立；revisions.py 负责累计 >30% 的新版本规则与变动范围。draft_presentation.py 清理人工稿并保留 agent_evidence；review_state.py 判断上次审稿是否仍匹配当前文案。局部重写拆成提案生成与确认两个接口。

data/public-materials/library.json、manual 和 references 是独立公共素材库；public_materials.py 负责共享资料与选择复制。research_x.py 负责 X 长帖/媒体提取及真实渠道诊断。video_posters.py 在 FFmpeg 可用时提取视频封面帧；document_text.py 提取有大小限制的 DOCX 正文。

两个 Agent 的详细输入输出、控制流程、Prompt 与代码修改入口见 [agents-design.md](agents-design.md)。

首次启动迁移旧 UUID 目录，迁移前备份到 data/backups/title-migration。保留旧 materials 文件供历史快照路径使用。数据读取始终使用 UUID，不通过文章标题作 API 身份；修改生成标题不移动归档目录。

自动检索候选由 research_related 发现，research_temporal 按正文实体和 ±3 天日期筛选，原始论文/科普标为 background。人工补充不绕成自动审核资料，标为 manual。模型看到带编号的研究上下文，内部配图与导出授权分别管理；生成卡片记录所用素材并继承确认状态。

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
