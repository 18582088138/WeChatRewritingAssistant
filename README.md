# Signal Studio · WeChatRewritingAssistant

本地中文科技内容工作台：从新闻或论文链接出发，抓取图文视频、检索参考资料、融合生成含配图的原创解读，独立审稿、人工修订，并准备多平台草稿。

前后端代码分离，完整应用由同一个 Python 服务提供 GUI、API 和存储。本轮只做本地验收；后续部署选择支持 Python 的统一平台。

## 一键安装和启动

Windows 本机已有 conda/Miniforge 时：

1. 双击 [Install.cmd](Install.cmd)，使用或创建 xkd_env_py312 并安装依赖；保留已有 .env。
2. 在 .env 配置 DeepSeek 等模型密钥，已有配置可直接使用。
3. 双击 [Start.cmd](Start.cmd)，同时启动前端和后端，打开 http://127.0.0.1:8000。

再次启动会检测已有服务。终端入口：

```powershell
conda run --no-capture-output -n xkd_env_py312 python scripts/launch.py
```

Linux 提供 install.sh/start.sh，本轮实测环境是 Windows/conda。服务地址、端口和自动打开浏览器行为在 config/app.json。手机同局域网访问可把 host 改为 0.0.0.0 并重启，通过电脑局域网 IP 和相同端口打开。

## 工作流程

1. 导入公开文章/论文链接，正文、图片、视频按原文标题和资源类型落盘；原文 Markdown 开头保留链接。
2. 搜索新闻发布日期前后 3 天的强关联材料。日期窗口可配置，直接相关的旧论文/基础科普标为背景，用户补充标为人工资料。
3. 写作 Agent 融合资料包，生成标题、摘要、关键词、含配图及 [S1] 出处的原创稿；审稿 Agent 检查技术细节、证据、排版、原创性和语言表达。一次写作与一次审稿分别保存。
4. 人工编辑、按反馈修改或选区重写。PC 参考浮窗支持跨来源选择多段，调用 LLM 融合后插入正文；图片/视频可从资料库插入。GUI 上传和直接复制 manual 文件夹均可补充素材。
5. 查看手机分页预览，生成 1080×1440 多页组图，核对来源媒体的授权/水印。待确认媒体可用于内部草稿；导出只包含已确认素材。
6. 准备平台草稿，最终发布自行在平台操作。New/Process/Done 表示处理阶段，Done 仍可能有待人工处理的审稿意见。

## 文档

| 文档 | 内容 |
| --- | --- |
| [产品设计](docs/product-design.md) | 页面、流程、状态、研究策略、图文和验收范围 |
| [接口文档](docs/api-reference.md) | API 清单、对象、选区位置、示例和错误 |
| [使用手册](docs/user-guide.md) | 安装、编辑、素材、手机、配置和故障处理 |
| [语言风格调参指南](docs/prompt-style-guide.md) | 正负例、控制变量、固定样本与迭代方法 |
| [应用架构](docs/architecture.md) | 模块边界、统一运行、标题归档与规模约束 |
| [本地产品实测](docs/local-product-validation.md) | 本轮真实 E2E、GUI 和素材验证结果 |
| [GUI 设计记录](docs/gui-design.md) | taste-skill 方向、检查与视觉取舍 |

交互 API 文档：http://127.0.0.1:8000/docs；完整契约：http://127.0.0.1:8000/openapi.json。

## 配置和数据

config/app.json、research.json、generation.json、platforms.json 管理应用、检索、两个 Agent 基础参数和图文分页。config/prompts 保存写作、审稿、统一语言风格、选区融合和压缩提示词。生成保存配置指纹及 config-history 快照。API 密钥仅放 .env，不返回浏览器、不提交 Git。

```text
data/articles/原文标题/（同名追加短 ID）
  article.json                 当前状态和文案
  source/原文标题/             标题 Markdown，text/images/videos
  references/参考文章标题/     标题 Markdown，text/images/videos
  manual/images,videos,texts/   手动补充资料库
  drafts/                      当前稿及标题修订稿
  versions/                    每阶段/人工编辑快照
  generated/                   分页组图、信息图、模型尝试稿
  config-history/              使用过的配置副本
  exports/                     平台图文包
```

旧 UUID 目录启动时备份并迁移，保留旧素材以维持历史版本引用。article.json 是当前文案状态；修改落盘 Markdown 不会自动回写应用，修稿请通过 GUI 保存。当前使用单进程任务锁与文件存储，运行一个 Uvicorn worker。

## 平台能力边界

| 平台 | 当前行为 |
| --- | --- |
| 微信公众号 | 配置账号与接口权限后调用草稿接口，仅新增草稿 |
| X / 小红书 / 微博 | 准备本地图文素材包，由用户手动保存到平台草稿 |

没有直接发布接口。公众号远程投递本轮未使用真实账号验收，素材包导出不代表远程草稿写入。待确认图片会阻止公众号草稿投递。

抓取支持公开 HTML/PDF、图片、直接视频和播放器发现；不支持通用动态渲染、登录/验证码处理或受保护流媒体。下载失败与未纳入参考的原因保留。图片水印/授权需人工确认；审稿不代表独立技术实验或平台审核通过。

## 验证和后续部署

```powershell
conda run --no-capture-output -n xkd_env_py312 python -m pytest -q
conda run --no-capture-output -n xkd_env_py312 python scripts/check_architecture.py
# 会使用真实网络和模型额度
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_user_e2e.py --output test-results/product-revision-e2e --resume --revise
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_product_ui.py
```

浏览器验证需 requirements-dev.txt 和本机 Chrome。源码单文件限制为 350 行/16 KB，检查模块依赖与前端循环；测试数据、截图、密钥不提交。

GitHub Pages 的旧静态 GUI 部署保留作历史记录；本轮移除 push 自动部署，只保留手动触发，不进行线上调试。完整应用后续部署到 Python 平台。Dockerfile/compose.yaml 是统一打包起点，本轮未构建验收。先前实测可参考 [搜索抓取记录](docs/research-validation.md)、[三篇旧版 E2E](docs/user-e2e-validation.md) 和 [Pages 历史记录](docs/pages-deployment-validation.md)。
