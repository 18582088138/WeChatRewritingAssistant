# 真实搜索与抓取验证

本文件保留基础抓取测试记录。当前完整应用的 ±3 天检索、标题归档、参考素材库与三篇真实生成复测见 [本地产品实测](local-product-validation.md)。

测试日期：2026-10-23；环境：Windows、conda `xkd_env_py312`，使用项目配置的代理。测试只运行搜索、抓取、素材保存与浏览器查看，不调用写作或审稿模型。

## 结果与证据

最终固定测试集包含 12 个真实链接和 6 组搜索词。10 个链接通过正文锚点、篇幅、素材发现与文件校验；2 个记录为访问受限。6 组搜索均找到预期来源。这里的“通过”表示达到已声明的检查条件，并不意味着网页上每一张图片、每一个视频都已下载。

| 真实来源 | 保存正文字符 | 图片：发现 / 保存 | 视频或播放器 | 核查结果 |
| --- | ---: | ---: | --- | --- |
| [Claude Sonnet 4.5](https://www.anthropic.com/news/claude-sonnet-4-5) | 13,821 | 23 / 10 | 5 个外部视频来源 | 发布信息、评测内容、脚注；小尺寸品牌图未采用 |
| [DeepSeek Terminus 公告](https://api-docs.deepseek.com/news/news250922) | 680 | 1 / 1 | 无 | 正文短但完整，评测图片可解码 |
| [Qwen3](https://qwenlm.github.io/blog/qwen3/) | 16,026 | 7 / 7 | 1 个 MOV 未下载 | MOV 超过 25 MB，明确记录原因 |
| [Qwen2.5-VL](https://qwenlm.github.io/blog/qwen2.5-vl/) | 33,629 | 27 / 12 | 11 个直链，保存 2 个 MP4 | 第 3 个视频超限，余下超过本轮配置数量 |
| [DeepSeek-V3 PDF](https://arxiv.org/pdf/2412.19437) | 187,372 | 12 / 12 | 无 | 53/53 页，包含附录末尾；图片是含图表页面的整页渲染 |
| [DeepSeek-V3 HTML](https://arxiv.org/html/2412.19437v2) | 140,186 | 15 / 12 | 无 | 全文、图注、SVG 图表，章节末尾锚点保留 |
| [Qwen3 摘要入口](https://arxiv.org/abs/2505.09388) | 119,763 | 5 / 3 | 无 | 自动转向论文全文；两个小尺寸图标未采用 |
| [NVIDIA DGX Spark 报道](https://developer.nvidia.com/blog/running-frontier-class-ai-models-across-8-nvidia-dgx-spark-nodes/) | 11,085 | 1 / 1 | 无 | 近期硬件报道正文、表格及资源链接 |
| [NVIDIA Sentry 报道](https://developer.nvidia.com/blog/inside-nvidia-sentry-secure-ai-agents-at-runtime/) | 15,133 | 3 / 3 | 无 | 近期 Agent 安全技术报道及架构图 |
| [SmolVLA 镜像](https://hf-mirror.com/blog/smolvla) | 19,589 | 21 / 8 | 动图受 8 MB 限制 | 镜像可用，但不自动替换官方来源；小头像被尺寸过滤 |
| [SmolVLA 官方](https://huggingface.co/blog/smolvla) | — | — | — | 当前网络 HTTP 504，部分尝试为 TLS 连接失败 |
| [GPT-5 官方](https://openai.com/index/introducing-gpt-5/) | — | — | — | HTTP 403，未绕过访问限制 |

上述字符数是固定验证运行的输出；页面和网络条件变化会导致后续数据不同。后续优化保留 GIF 动画、过滤 Hugging Face 作者头像行，并扩大失败候选后的继续尝试范围。镜像追加在线复测出现 TLS 握手超时，因此另用已保存的真实 HTML 回放正文提取，并再次联网下载素材；回放测试与完整在线测试分开记录。

Qwen2.5-VL 的两个视频用 `ffprobe` 验证：H.264 720×1280、10.828 秒（含 AAC）；H.264 1080×1920、11.345 秒。浏览器已实际加载 MP4 元数据，确认视频宽度 720。配图拼图已人工检查：包含评测柱状图、模型结构图、机器人示意图及论文图表。SmolVLA 真实网页回放加联网素材测试另外成功保存 GIF 动图，未转换为静态首帧。

搜索词为 Qwen3 technical report、Claude Sonnet 4.5 announcement benchmarks、DeepSeek V3.1 Terminus、NVIDIA Isaac GR00T N1 humanoid robots、具身智能 SmolVLA、NVIDIA DGX Spark nodes。每组检查预期域名或论文路径，并保存全部候选、检索服务尝试与失败原因。

原始网页、论文、正文、metadata、素材、哈希和逐项结果保存在 `test-results/research-final-verified/`；总报告为 `report.json`。这些第三方全文与素材仅在本地保存，不提交 Git。`test-results/material-contact-sheet.jpg` 是配图抽查拼图。浏览器截图为 `research-source-desktop.png` 与 `research-source-mobile.png`。

## 修复内容

原实现把 Google JavaScript 提示页解析成空结果，缺少可观测失败信息。现使用 Bing 自然结果、官方 sitemap/feed/index 与 arXiv 论文检索，过滤不相关版本、型号和重复来源。原论文正文在 65,000 字符处静默截断，模型只读取开头 18,000 字符；现完整文本落盘，模型上下文分布取样并明确标记省略内容，保留章节及抓取警告。有限上下文仍不能保证每个事实都已进入模型输入。

HTML 提取按正文容器选择，保留正文标题、表格、图注和发布日期；图片识别 srcset、懒加载、picture 和 SVG 图表，优先尝试高清候选，失败后继续备选。PDF 提取最多 150 页并报告不完整或文字稀少页。下载保留来源、大小、SHA-256、尺寸、授权待确认状态；视频验证容器文件头、保留真实 MOV/MP4/WebM 格式。来源页可查看完整正文、素材数量、逐项失败说明及外部播放器地址。

## 已知限制

默认每个来源最多保存 12 张图片、尝试 3 个视频；图片下载上限 8 MB、视频 25 MB。没有把超限视频截成不完整文件。外部播放器、YouTube、Bilibili 和流媒体播放列表只记录地址，不声称下载成功。PDF 图表页面包含正文，尚未自动裁剪单图；扫描 PDF 不执行 OCR。动态渲染、付费墙、验证页及站点访问限制仍可能阻止获取。

尝试了 [DeepSeek 官方 Search/Fetch](https://api-docs.deepseek.com/guides/search) 的 4 次搜索与 2 次抓取；当前配置均返回 HTTP 404。接口适配保留为可选功能，`SEARCH_PROVIDER=free` 为默认；`deepseek` 模式失败时继续公共检索。没有把接口文档存在视为接口实测成功。

后续已使用用户提供的两篇公众号文章和一篇智东西文章进行真实抓取、关联搜索、DeepSeek 写作与审稿、浏览器编辑、反馈修改、组图和四平台素材包导出。正文及 GIF 均保存成功；腾讯视频仍仅保留播放器引用。逐项证据、修复与外部草稿写入限制见 [用户三篇文章完整 E2E 实测](user-e2e-validation.md)。

## 复测方法

```powershell
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_research.py
# 用自己的测试集；输出目录与正常文章目录隔离
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_research.py --cases my-cases.json --output test-results/user-retest
conda run -n xkd_env_py312 python -m pytest -q
```

测试集格式见 `scripts/research_cases.json`：文章有 `name`、`url`、正文锚点 `anchors` 和可选最低篇幅/素材数量；搜索有 `query` 与 `expected_url`。脚本逐项写报告，意外失败返回非零退出码，预计访问受限来源记录为 `limited`。默认脚本不运行生成 Agent；可独立用 `/api/research/search?q=...` 检查搜索响应和诊断信息，适用相同访问令牌。
