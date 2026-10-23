# GitHub Pages 部署验证（历史记录）

本文件记录先前静态 GUI 部署。当前产品方案是同平台提供前端和 Python 后端，本轮只验收本地完整应用，不继续 Pages 部署；详见 [本地产品验证](local-product-validation.md)。Pages 工作流已移除 push 自动部署，仅保留手动触发。

测试日期：2026-10-23；线上地址：[Signal Studio 科技内容工作台](https://18582088138.github.io/WeChatRewritingAssistant/)。测试访问实际 GitHub Pages 页面，没有使用本地前端替代，也没有模拟网络响应。

此前首次配置 Pages 时的权限问题已解除。提交 `4641bb2` 的测试和部署均成功；本次新增部署测试后的 `d02f6e6` 也已自动完成 [测试工作流](https://github.com/18582088138/WeChatRewritingAssistant/actions/runs/39967647770)（25 秒）和 [Pages 部署](https://github.com/18582088138/WeChatRewritingAssistant/actions/runs/39967647500)（27 秒）。

## 线上检查

| 检查 | 结果 |
| --- | --- |
| HTTPS 线上首页 | HTTP 200，应用正常启动 |
| 项目子路径 `/WeChatRewritingAssistant/` | JS 模块和 CSS 相对路径加载正常 |
| 全部 39 个 HTML / JS / CSS 文件 | HTTP 200；与本地 `web/` 文件逐字节一致（统一换行符），报告保留 SHA-256 |
| 文件 MIME 类型 | HTML、JavaScript、CSS 类型符合浏览器要求 |
| 后端文件隔离 | `.env`、`backend/app.py`、`data/articles/`、`.git/config` 均 HTTP 404 |
| 默认无后端配置 | 显示“后端未连接”，没有把示例数据当作真实文章 |
| 示例与筛选 | 3 篇明确标注的示例，New / Process / Done 各 1 篇；关键词无匹配时正确显示空结果 |
| 导入缺少后端 | 显示配置后端提示，保留导入表单，不创建虚假文章 |
| 页面导航 | 文章工作台、素材库、草稿投递、设置均可打开 |
| 设置页刷新 | `#settings` 刷新后仍显示设置页；访问令牌输入框为 password 类型 |
| 1440 / 768 / 390px | 无横向溢出；手机导航可打开，选择页面后关闭 |
| 浏览器运行 | 无脚本异常、无失败的静态资源请求 |

Chrome 使用真实代理访问线上 Pages，截图和逐项报告在本地 `test-results/pages-deployment/`，不提交 Git。截图包括桌面文章目录、桌面/平板/手机设置页及手机文章目录。

## 部署范围

线上已部署静态前端。Python 后端、文章、原始素材、模型 API 密钥没有部署到 Pages。公网完整使用仍需独立部署 HTTPS API，并在设置页配置服务地址与访问令牌；后端 `CORS_ORIGINS` 应允许 `https://18582088138.github.io`，不包含仓库路径。

额外真实联动测试也已通过：线上 Pages 设置页连接本机 `http://127.0.0.1:8000` 后显示“后端已连接”，读取日常文章目录，并打开真实 E2E 测试稿编辑页。这个测试只验证当前电脑上的 API 联动，不代表部署了公网后端。手机上的 `127.0.0.1` 指向手机自身，不能使用该地址访问电脑服务。

## 复测

```powershell
# 检查当前 HEAD 的测试/部署工作流、实际线上文件、真实 Chrome 页面
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_pages.py
# 额外检查线上前端连接已运行的真实本地后端，仅阅读文章
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_pages.py --api-base http://127.0.0.1:8000
# 工作流尚未结束时，仅检查已上线页面；之后仍应核对 Actions
conda run --no-capture-output -n xkd_env_py312 python scripts/verify_pages.py --skip-actions
```

检查不调用写作模型，不导入真实来源，不投递平台草稿，也不执行公开发布。浏览器脚本与线上 HTTP/工作流检查分为独立模块，符合项目源码规模约束。Linux 可先运行 `python -m playwright install chromium`；其他浏览器路径可用 `--browser-executable` 指定。

公共 GitHub API 曾在共享代理下返回 HTTP 403 限流。脚本此时读取 GitHub 官方 Actions 页面中的结构化运行记录，核对完整提交 SHA 与 success 结论，并在报告记录证据渠道；不会把 API 限流误报为部署失败。
