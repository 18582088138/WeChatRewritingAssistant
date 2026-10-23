# Signal Studio · WeChatRewritingAssistant

一个本地优先的中文科技内容工作台：从文章或论文链接出发，研究多个来源，生成原创解读，独立审稿，编辑图文并准备各平台草稿。

GUI 已按 [taste-skill](https://github.com/leonxlnx/taste-skill) 的应用界面规范优化，使用 Editorial greeting / Open plane 方向。具体设计取舍、检查结果与截图自评见 [GUI 优化记录](docs/gui-design.md)。支持文章、设置与单篇编辑的 hash 入口，刷新后恢复当前页面。

## 启动

```powershell
conda create -n xkd_env_py312 python=3.12 pip -y
conda run -n xkd_env_py312 python -m pip install -r requirements.txt
# 已有 .env 时不要覆盖；新环境从模板创建并填写模型密钥
Copy-Item .env.example .env
conda run --no-capture-output -n xkd_env_py312 python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。也可执行 `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`。同一局域网手机操作使用 `scripts/start.ps1 -Lan`，访问电脑的局域网 IP 和 8000 端口，按需配置 Windows 防火墙与 `.env` 中的 `CORS_ORIGINS`。本机默认不开放外网；对外部署时设置 `APP_TOKEN` 并启用 HTTPS。令牌在界面“设置与连接”填写，只保存在浏览器当前会话。

代理可在 `.env` 中设置 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`。`HF_ENDPOINT` 为预留配置，当前没有下载本地 Hugging Face 模型。API 密钥从后端读取，不返回浏览器，不提交 Git。

## 工作流程

1. 导入公开报道、模型发布页面或 PDF 论文。需要登录、反爬或动态渲染的来源可粘贴原文，仍保留原始链接。
2. 文章目录以 New / Process / Done 显示状态。选择平台、目标字数、风格和 DeepSeek / OpenRouter，开启关联搜索或手动补充来源。
3. 写作 Agent 提炼来源，重新组织论述、标注 `[S1]` 等事实出处，输出标题、正文、关键词和一句话总结；审稿 Agent 核对证据、技术细节、排版、自然表达和原创性风险。
4. 一轮写作和一轮审稿构成一次生成，两个阶段分别落盘。按审稿意见修改会开启新一轮写作和复审。Done 表示本轮完成，高风险意见仍会显示“待人工确认”。
5. 编辑 Markdown 并保存，或选中段落后局部重写。修改正文会使旧审稿失效，避免旧反馈被误用于新版本。来源与素材页支持本地上传、Pixabay 图库检索（需 `PIXABAY_API_KEY`）、授权和水印确认，编辑页选择素材插入或替换图片。
6. 生成 1080×1440 PNG 组图，可下载文案、排版 HTML、来源与已确认素材的 ZIP 包。图片是本地排版生成，不需要图片生成 API。
7. 选择平台准备草稿：公众号真正写入草稿箱；X、小红书、微博生成图文包，由用户在平台保存草稿和最终发布。

## 已实现的平台边界

| 平台 | 本项目行为 | 必要配置 |
| --- | --- | --- |
| 微信公众号 | stable_token → 素材上传 → draft/add，仅新增草稿 | `.env` 的 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`；公众号接口权限和 IP 白名单；界面配置作者与可选 `thumb_media_id` |
| X | 保存适配文案与素材包，打开创作平台自行存草稿 | 暂无需 API key；长文需按账号权限与实际限额处理 |
| 小红书 | 导出 3:4 图文组图和文案，手动存草稿 | 暂无需 API key |
| 微博 | 导出图文包，手动存草稿 | 暂无需 API key |

未找到可统一使用的官方远程草稿接口的平台不会显示“远程草稿写入成功”。未实现浏览器登录自动化，也不调用直接发帖接口。公众号真实投递需要用户账号配置，未配置时返回清晰失败原因；不会伪造成功。

## 存储与接口

前后端按职责分层，入口、路由、页面、编辑操作与样式均已模块化。目录结构、依赖规则、文件规模限制及独立运行方式见 [应用架构](docs/architecture.md)。

```text
data/
  settings.json
  articles/<id>/
    article.json          # 状态、文案、审稿、素材和投递记录
    draft.md              # 当前正文
    versions/*.json       # 每阶段及人工保存的历史版本
    materials/source-N/text/  # 原始 HTML/PDF、正文与来源元数据
    materials/source-N/images/
    materials/source-N/videos/
    materials/local/images/
    generated/cards-rN/   # 本地生成组图
    exports/              # 平台图文包
```

FastAPI 接口文档：http://127.0.0.1:8000/docs 。文件写入使用临时文件替换；正文编辑带修订号检查；同一文章的任务互斥；服务重启后中断任务可重新启动。当前任务在单进程内执行，请使用单个 Uvicorn worker，后续生产部署可以迁移数据库和任务队列。

来源抓取支持公开 HTML 与 PDF，关联检索尽力从搜索结果提取公开页面，可能受网络、搜索服务、反爬、付费墙影响。检索失败会保留已有来源并记录提示，可手动补充一手资料链接。HTML 不具备动态浏览器渲染能力。来源图片和直接视频链接按类型落盘，视频限 25 MB，不支持受保护流媒体或 DRM。来源图片的授权、水印由人工确认；没有自动视觉鉴权，也不能保证所有来源图片无水印。

目标字数是对模型的写作约束，超过宽松上限会返回失败，最终字数在编辑页可见；不同平台字数、账号能力和审核规则变化，需要用户发布前核对。审稿依据抓取到的来源，不代表独立实验或审核通过保证。

## GitHub Pages

`.github/workflows/pages.yml` 将 `web/` 部署到 GitHub Pages。仓库 Settings → Pages 的 Source 选择 GitHub Actions，然后推送 main 或手动运行工作流。

Pages 只能托管静态前端，不能运行 Python、保存服务器文件或安全存放 API 密钥。在线前端的“设置与连接”中填写独立部署的 HTTPS 后端地址，并在后端配置 Pages 域名的 `CORS_ORIGINS`。后端未连接时可以查看界面示例，示例明确标注，不代表真实生成内容。HTTPS Pages 不能连接普通 HTTP 后端；局域网使用本地后端自带前端。

## 验证

搜索与抓取已进行多轮真实图文、视频和论文验证，结果、访问限制与自定义链接复测方式见 [真实搜索与抓取验证](docs/research-validation.md)。

用户提供的两篇公众号文章和一篇智东西文章也已进行真实 DeepSeek 与 Chrome 的完整链路测试，覆盖按审稿意见修改、段落重写、配图替换、组图和四平台素材包导出，见 [三篇文章 E2E 实测](docs/user-e2e-validation.md)。流程通过与文案审稿结论分别记录，平台素材包导出不代表外部草稿箱写入成功。

```powershell
conda run -n xkd_env_py312 python -m pytest -q
```

测试覆盖来源地址隔离、访问令牌、HTML 清理、生成审稿落盘、版本冲突、局部重写、素材确认、组图、导出和模型失败恢复，模型请求使用替身，避免消耗密钥额度。

本次开发验证：8 项后端测试通过，桌面和 390px 手机浏览器完成目录、设置、编辑保存、预览、版本、组图和下载检查，无脚本错误。真实 DeepSeek 验证使用历史论文 [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437)，已完成抓取、写作、独立审稿并保存，结果 88 分。验证样稿保存在本地文章目录，明确说明是历史论文，不代表最新要闻。600 字短篇输出曾超限，已加压缩重试和超限保护，最终篇幅仍需人工核对。

浏览器验证可安装 `requirements-dev.txt` 后运行 `scripts/verify_browser.py`。`scripts/verify_editor.py` 使用真实验证样稿，`scripts/verify_live.py` 会消耗模型调用额度并把结果存到 `test-results/live-data/`。截图和验证数据均不提交 Git。

GitHub Actions 和 Pages 已配置完成，测试及部署工作流均成功。线上地址：[Signal Studio](https://18582088138.github.io/WeChatRewritingAssistant/)。已实测全部 39 个前端文件与本地内容一致、正确 MIME 类型、桌面/平板/手机导航与设置；详情和复测命令见 [Pages 部署验证](docs/pages-deployment-validation.md)。Pages 托管静态前端，联网抓取、Agent 和文件存储仍需要连接 Python 后端。

接口参考：[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode)、[微信公众号开发文档](https://developers.weixin.qq.com/doc/service/)、[X API 文档](https://docs.x.com/)。应用定位为有来源的原创整理与解读，保留事实出处和人工确认流程。
