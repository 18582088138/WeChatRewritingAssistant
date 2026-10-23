# API 接口文档

本地基础地址 http://127.0.0.1:8000。FastAPI 交互文档位于 /docs，完整机器契约为 /openapi.json。所有业务请求使用 /api，同源 GUI 不需要另配服务器。请求和响应默认 JSON；文件上传使用 multipart/form-data。

配置 APP_TOKEN 后，除健康检查外所有业务 API 需 `Authorization: Bearer <token>`。密钥不返回浏览器。生成请求异步，返回后轮询文章详情直至 status 不为 Process；材料导入、融合、组图和投递同步返回，耗时取决于网络和模型。

## 对象约定

article 包含 id（32 位十六进制稳定标识）、url、title、archive_title、status、stage、revision、body、summary、keywords、sources、assets、review、events、error、deliveries 和 created_at/updated_at。详情额外返回 storage_path。title 是当前文案标题，archive_title 固定为原文标题；改稿不改变文章目录身份。

source 包含 title/url/text/retrieved_at，以及可获取的 published_at、author、storage_dir、images、videos、embedded_media、quality、media_downloads、reference_role。来源编号按数组顺序从 S1 起；manual 文件来源可能为 local://，不能当作公开网页链接。

asset 包含 id/type/path/alt/approved/watermark/rights/width/height/source_url/attribution，抓取素材有 sha256/bytes 等，生成卡片可有 derived_from。path 相对文章目录；浏览器通过素材文件 API 读取，不访问任意服务器文件。

review 包含 score、verdict、issues（category/severity/detail/suggestion）、strengths、fact_checks、checked_at、draft_revision。score 不代表平台通过，当前文案修改或素材变化后 review 可为 null。

## 接口清单

| 方法与路径 | 输入 | 返回 / 状态 |
| --- | --- | --- |
| GET /api/health | 无 | ok/version/requires_token，200 |
| GET /api/config | 无 | generation/research/platforms 当前非敏感配置 |
| GET /api/settings | 无 | 平台配置、服务能力与密钥是否配置，隐藏密钥值 |
| POST /api/settings | wechat 对象 | 更新后的平台设置 |
| GET /api/research/search?q=… | q 长度 2–240 | 结果、查询、尝试记录与 warnings，不生成文章 |
| GET /api/articles | 无 | 按更新时间排序的 article 数组 |
| POST /api/articles | url，可选 title/text | 创建文章，201；无 text 时启动抓取 |
| GET /api/articles/{id} | 无 | 详情，非 Process 时同步手工材料 |
| PATCH /api/articles/{id} | title/body/summary/keywords/revision | 保存新修订，清空审稿 |
| GET /api/articles/{id}/versions | 无 | 最新至多 30 个快照，附 version_id |
| POST /api/articles/{id}/generate | Options | Process 文章，202 |
| POST /api/articles/{id}/review | Options | Process 文章，202；只审稿 |
| POST /api/articles/{id}/paragraph | start/end/revision/instruction/provider | 替换选中正文后 article |
| POST /api/articles/{id}/references | url | 抓取用户补充来源与素材，返回 article |
| POST /api/articles/{id}/materials | file | 导入文本/图片/视频，返回 article |
| POST /api/articles/{id}/materials/sync | 无 | 同步 manual 文件夹，返回 article |
| POST /api/articles/{id}/fuse | selections/position/revision/instruction/provider | LLM 融合插入后的 article |
| POST /api/articles/{id}/assets | file | 旧图片上传入口，12 MB 上限 |
| PATCH /api/articles/{id}/assets/{asset_id} | approved/alt | 更新素材确认状态，返回 article |
| GET /api/articles/{id}/assets/{asset_id}/file | 无 | 本地文件，真实 MIME |
| POST /api/articles/{id}/stock | query | Pixabay 搜索下载素材后 article |
| POST /api/articles/{id}/cards | 无 | 生成分页组图后的 article |
| GET /api/articles/{id}/render | 无 | html 和 pages 数组 |
| GET /api/articles/{id}/preview | 无 | 完整排版 HTML |
| GET /api/articles/{id}/export/{platform} | 平台路径参数 | ZIP：draft.md/caption.txt/preview.html/sources.json/assets |
| POST /api/articles/{id}/deliver | platforms 数组 | 各平台的独立投递结果 |

platform 为 wechat/x/xiaohongshu/weibo。provider 为 deepseek/openrouter。发表功能没有直接发布路由。

## 常用请求

导入 URL：

```json
{"url":"https://zhidx.com/p/581841.html"}
```

手动原文导入使用相同请求增加 title/text（text 至少 150 字符），仍保存 url。抓取不会读取内网、带账号密码 URL 或非标准端口。

Options 示例；字段可省略，字数/风格/provider 默认从 config/generation.json 读取：

```json
{
  "word_count":1800,
  "style":"专业、自然、克制的中文科技解读，保留关键技术细节",
  "platform":"wechat",
  "provider":"deepseek",
  "research":true,
  "related_urls":[],
  "revise":false
}
```

word_count 为 300–6000，related_urls 至多 4 项。revise=true 将当前审稿意见交给写作 Agent；research=false 复用现有资料包。字数是正文字符目标，不含末尾来源链接列表；超过配置容差并压缩失败时当前稿保留，尝试稿归档。

保存请求必须携带当前 revision 和完整文案字段：

```json
{"title":"模型发布解读","body":"正文 [S1]","summary":"一句话总结","keywords":["AI"],"revision":2}
```

选区重写以零起始 Unicode 码点范围 [start,end) 替换：

```json
{"start":12,"end":120,"revision":3,"instruction":"压缩句子，保留测试条件","provider":"deepseek"}
```

多段资料融合按来源全文选区，position 是当前正文插入位置；不是参考文章页内位置：

```json
{
  "selections":[{"source_id":1,"start":100,"end":260},{"source_id":2,"start":0,"end":180}],
  "position":180,
  "revision":3,
  "instruction":"解释两份材料一致和不同的技术条件",
  "provider":"deepseek"
}
```

source_id 从 1 起，最多 12 个选区。模型输出需 text 字段并含实际选中来源的 [S编号]，不能引用未选中来源。失败不修改正文；成功增加 revision 并清空审稿。前端 UTF-16 位置需先转换码点，emoji 按一个码点处理。

平台准备请求：

```json
{"platforms":["wechat","x","xiaohongshu","weibo"]}
```

响应是逐平台结果：draft_saved 表示公众号远程草稿已写入；export_ready 表示本地素材包已生成；failed 带 message。HTTP 200 不代表每个平台成功。投递会产生记录，重试公众号可能创建额外草稿。

## 文件与错误

materials 支持 md/txt/pdf/html/png/jpg/jpeg/gif/webp/mp4/mov/webm，上传上限 25 MB。原文抓取图片/视频上限和数量来自 research 配置；超过、播放列表或格式无效的媒体只记录诊断。未确认素材不进入导出 HTML/ZIP。公众号存在未确认正文图片时拒绝投递。

| 状态码 | 处理方法 |
| --- | --- |
| 401 | 填写正确应用令牌 |
| 404 | 文章或素材不存在，刷新列表 |
| 409 | 任务忙或 revision 冲突，读取最新稿后重试 |
| 413 | 文件过大，压缩或拆分 |
| 422 | 参数、选区、来源或模型配置不符合约束 |
| 502 | 模型/图库调用或输出验证失败，检查提示，原稿保留 |

异步任务失败通常体现在 article.error/stage，而非原始 202 请求的状态码。同步调用返回 detail 提示；并发编辑必须以服务端 revision 为准。当前文件存储和任务锁要求单进程，不能直接添加多个 worker。
