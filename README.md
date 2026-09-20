# 悦来越AI · 小红书爆款雷达

AI 小红书图文爆款雷达。自动聚合 ChatGPT、Claude、Gemini、AI 图片、AI 办公和 AI 工具相关热门图文，并提供原创仿写入口。

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yue995666/ai-xhs-radar)

## 当前功能
- 近 24 小时 AI 图文雷达
- GPT / Claude / Gemini / AI图片 / AI办公 / AI工具
- 点赞、收藏、评论、推荐度
- 原帖跳转
- 原创仿写
- TikHub Token 通过服务器环境变量读取，不写进前端

## Render 部署
项目根目录已经包含 `render.yaml`。

部署时只需要填写一个环境变量：

- Key: `TIKHUB_TOKEN`
- Value: 你的 TikHub Token

健康检查地址：

`/healthz`
