# 本地完整应用实测

日期：2026-10-23。环境：Windows、conda xkd_env_py312、本机 Chrome、项目代理、真实 DeepSeek API。只测试本地完整应用；本轮未部署或调试 GitHub Pages，没有真实账号发帖。

## 三篇用户文章

| 原文 | 主文字符 | 原文图片保存 | 最终资料包 | 初稿/复审分数 | 流程 |
| --- | ---: | ---: | ---: | ---: | --- |
| [Qwen Audio](https://mp.weixin.qq.com/s/ckMmkZ7tQNHpruTUTeuV_g) | 3874 | 8 | 2 份 | 84 / 84 | 生成、浏览器编辑、按反馈修改与导出通过 |
| [Opus 游戏逆向](https://mp.weixin.qq.com/s/MDTp3gFMLZzCPoFlJTqQ0w) | 2426 | 11 | 2 份 | 84 / 78 | 同上；2 张 GIF 保留 13/16 帧 |
| [智东西 MiniMax H3](https://zhidx.com/p/581841.html) | 3496 | 5 | 3 份 | 82 / 84 | 同上；官方来源另保存 2 张图片、3 个视频 |

分数不是平台审核通过或文案无误的证明。游戏案例复审分数下降也保留原样，不把流程通过解释成质量必然提升。目标正文 1800 字符，正文计数不含来源列表和图片链接，并有配置容差；文件总字符数包含 Markdown 和 URL，分别约 3196/2813/3282。最终生成的组图各 20 张，全部 1080×1440；长稿应按实际平台场景进一步精简或分批使用。

覆盖步骤：真实抓取 → 关联搜索/正文筛选 → 写作 Agent → 审稿 Agent → GUI 保存 → 真模型选区重写 → 图片替换 → 图文预览 → 修订记录 → 多页组图 → 四平台 ZIP → 按审稿意见再写作和复审 → 新修订预览/导出。未确认的来源素材应被 ZIP 排除，已确认并插入的素材应在导出 HTML 中指向包内真实文件。

## 参考资料和日期

Qwen Audio 主文发布日期为 2026-09-10，补充 FLASepformer 原始论文并标 background；论文正文页未返回可解析日期，保留日期未知，不伪称同期新闻。

游戏主文发布日期为 2026-10-12，实际项目说明文章发布日期为 10 月 9 日，按 -3 天纳入。搜索模型版本统一空格匹配，修复 Opus5.5 被误截为 Opus5 的问题。

智东西发布日期为 2026-08-03，关联报道与 MiniMax 官方发布页均为 7 月 31 日，按 -3 天纳入。之前仅依赖搜索引擎时漏掉官方文章，并出现 H3 化学论文候选；正文筛选拒绝这些候选后，又补入官方博客索引并收紧品牌与模型匹配。最终资料包有主文、同期报道和官方发布页；没有把较晚的非官方教程当成同期资料。

检索仍是尽力召回，不能宣称覆盖所有相关报道。官方索引配置在 config/research.json 的 publisher_indexes，索引提取真实链接，再抓取正文验证日期和相关性，不硬编码猜测文章 URL。

## 图片和视频质量

图片逐个解码、检查尺寸及哈希；GIF 检查多帧且原始与保存哈希一致。智东西图片曾全部遭遇临时 504，增加正常浏览器请求头与最多一次瞬时错误重试后，最终 5 张原文图完整保存。403 等访问限制不按临时错误重试。

MiniMax 官方视频经过 ffprobe 检查，记录文件哈希、流和时长：

| 视频 | 编码 | 尺寸 | 时长 |
| --- | --- | --- | ---: |
| s3-video-0 | HEVC | 1920×1080 | 2.09 秒 |
| s3-video-1 | H.264 | 2560×1440 | 6.584 秒 |
| s3-video-2 | H.264 | 2560×1440 | 6.583 秒 |

浏览器实测参考库视频读取元数据和插入预览。播放器链接或不支持的流媒体仍保留诊断，不计入已下载视频。

## 人工编辑与本地运行

额外 GUI 产品测试使用真实智东西正文、官方参考文本、已抓取图片和视频：直接复制到 manual 后同步、GUI 上传 Markdown、两个来源选区加入待融合列表、真实 DeepSeek 融合后插入且完整保留未选中稿件、图片/视频插入保存、分页切换、390px 手机无横向溢出并隐藏 PC 专属融合、组图素材每页不超过 6 项，浏览器脚本错误为 0。该操作验证稿约 4500 字符，生成 27 页，作为功能测试保留，不作为单次发布推荐篇幅。

融合曾因模型省略 [S编号] 被拒绝，原稿保持不变；加强 prompt 并增加最多一次格式纠正重试后真实插入通过，重试次数配置为 fusion_retries。上传与文件夹同步的响应竞争也被发现，现将导入操作串行并在处理中禁用重复操作。

Install.cmd 对应安装脚本已在 xkd_env_py312 实际运行，依赖安装成功。完整服务由 scripts/launch.py 启动；同一地址提供 GUI 与 /api，再次启动检测已有实例。原有 4 篇文章标题迁移完成，备份保留；历史素材路径继续可用。Windows 安装需本机已有 conda；新建环境分支、Linux 安装、容器与外部部署未在本轮机器完整实测。

本轮最终三篇样稿已复制回本地 GUI，原有稿件保留。新稿归档名包含“实测”和短 ID，记录 validation_label。样稿仍需人工核对技术表述、来源图授权和水印，不能直接当成已发布稿。

## 检查与证据位置

38 项后端测试通过，覆盖标题迁移、日期与背景、选区位置、融合出处失败保留原稿及格式重试、手工同步、临时下载重试、模型篇幅预算、GIF/视频格式、导出、组图标点换行和公众号本地视频阻断。架构检查通过：源码单文件不超过 350 行/16 KB，前端无循环依赖；JavaScript 语法检查通过。

taste-skill 应用检查在 1440/768/390px 完成，目录与调整后的编辑页均 0 FAIL / 0 WARN；已阅览截图，参考浮窗、手机预览和组图使用真实本地资料。设计取舍见 gui-design.md。

本地证据（test-results 不提交 Git）：

- test-results/product-revision-e2e/e2e-report.json：三篇完整流程、反馈修订、媒体证据和各平台导出。
- test-results/product-revision-e2e/product-summary.json：最终样稿 ID、来源角色、媒体检查和 GUI 归档路径。
- test-results/product-ui/report.json：真实 LLM 融合、文件添加、视频和手机分页。
- test-results/product-ui/*.png：参考资料浮窗、桌面/手机预览。
- .taste-skill/inspect、.taste-skill/editor-final：三种宽度的测量报告与截图。
- 文章目录 versions、generated/attempts、config-history：每阶段稿件、失败尝试和配置快照。

复测命令：

```powershell
conda run --no-capture-output -n xkd_env_py312 python -m pytest -q
conda run --no-capture-output -n xkd_env_py312 python scripts/check_architecture.py
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_user_e2e.py --output test-results/product-revision-e2e --resume --revise
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_product_ui.py
```

resume 复用已通过案例；需要完整新一轮可指定新输出目录或 --regenerate-case 案例名。真实 E2E 和 GUI 融合会消耗模型额度。GUI 产品测试需本地服务和原有智东西样稿，脚本中的源样稿 ID 需与实际本地数据对应。

## 未验收的外部能力

没有调用真实公众号账号的 draft/add，本轮只验证缺少凭据时提示失败和素材准备。X、小红书、微博仍是本地图文包加人工存草稿，没有统一远程草稿写入。没有直接发布、平台审核通过保证、自动水印鉴定或图片授权保证。Pages 仅保留历史静态部署记录，本轮未部署。
