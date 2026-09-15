# final-review · 一键审阅 AI 产物

> **输入**一批 AI 产物清单（文案 / 配图 / 规则文件）→ **输出**一个可自由圈点批注、一键导出意见 JSON 的离线审阅 HTML。

把模型交付给你的所有「最终成品」收进一个单文件 HTML，你在浏览器里选中文字就能批注、在图上拖框就能圈注，点一下导出成固定文件名 `review-comments.json`，丢回主理人，它逐条帮你改。

不依赖任何专家包、不修改被审阅的文件，被审阅内容只是一份 `manifest.json` 数据。

---

## ✨ 它解决什么

- 模型一轮给你一堆文件（推文、朋友圈文案、小红书文案、配图、规则 md），你看完要逐条反馈，但反馈散在聊天里、改完又得来回对。
- 这个技能把**所有最终产物**装进一个页面，标注和原文绑定（自动记录「谁、哪段、什么意见」），导出结构化的意见清单，回收时主理人按图索骥，不用来回问。

> 📌 **产物 = 最终交付物，不是过程文件。**
> 让你写朋友圈文案，文案本身就是产物；生成它的脚本、`pipeline.json`、QA 报告、提示词草稿都**不放**进审阅件。

---

## 🚀 快速开始

```bash
# 1. 写一份 manifest.json（见下），列出要审阅的产物
# 2. 跑生成器，吐出一个自包含、可离线打开的 review.html
python <skill 目录>/gen_review.py --manifest manifest.json --out review.html
# 3. 浏览器打开 review.html → 选中文字批注 / 在图上拖框圈注
# 4. 顶栏「⬇ 保存并下载」→ 导出 review-comments.json
# 5. 把 json 给主理人，说「写完了」→ 它逐条回收修改
```

依赖：`python3` + `markdown`（`pip install markdown`）。内联 JS 会在产出前用 `node --check` 校验（找不到 node 则跳过并告警）。

---

## 📝 manifest.json 格式

```json
{
  "title": "审阅件标题",
  "defaultBatch": "batch-current",
  "batches": [
    {
      "id": "batch-current",
      "label": "本轮交付",
      "default": true,
      "root": "/绝对/根目录",
      "files": [
        {
          "src": "相对 root 的文件路径",
          "docid": "a1",
          "title": "页面里显示的标题",
          "realpath": "/绝对/真文件路径（回收时主理人据此定位修改）"
        }
      ]
    },
    {
      "id": "batch-prev",
      "label": "上一轮（默认折叠）",
      "default": false,
      "root": "/绝对/根目录2",
      "files": [ "..." ]
    }
  ]
}
```

- `realpath` 留空字符串 `""` 表示「自助添加、无真文件对应」，回收时主理人会追问目标文件。
- `default: true` 的批次默认展开，其余折叠；页面顶部可一键展开全部。
- 文件类型支持：`.md`（渲染为富文本）、`.json/.py/.js/.cjs/.txt`（代码围栏）、图片（`.png/.jpg/.jpeg/.gif/.webp/.bmp`，自动 base64 内联，可圈注）。
- 一份可直接改路径用的样例见 [`assets/example-manifest.json`](./assets/example-manifest.json)。

---

## 🖱️ 在 HTML 里能做什么

| 操作 | 说明 |
|------|------|
| 选中正文文字 → 💬 标注 / 🖍 高亮 | 弹框写意见，自动存浏览器本地 + 记录原文引用 |
| 在图片上拖框（单击=整图） | 生成带区域坐标的圈注，图上标编号 |
| 顶栏「➕ 自助添加」 | 上传文件 / 粘贴文本，离线新增一节（无 realpath） |
| 顶栏「⬇ 保存并下载」 | 全部标注导出为固定名 `review-comments.json` 并下载 |
| 右侧面板 | 列出所有标注（来源章节 / 原文引用 / realpath），可定位、删除 |
| 顶栏「⬆ 导入」 | 把 json 回贴进页面，圈注按坐标重建 |

> 浏览器本地存储仅同浏览器有效；跨设备 / 换浏览器以导出的 JSON 为准。

---

## 🔁 回收循环（主理人视角）

1. `Read` 约定路径下的 `review-comments.json`。
2. 遍历 `annotations`：按 `realpath` 定位真文件；`realpath` 为空 → 问用户目标文件。
3. 逐条编辑对应 `.md / .json / .py` 等。
4. 回执：每条怎么改、改了哪个文件；有歧义的标出。

导出 JSON 每条结构：

```json
{
  "id": "a...",
  "batchId": "batch-current",
  "batchLabel": "本轮交付",
  "doc": "a1",
  "title": "显示标题",
  "realpath": "/绝对/真文件路径",
  "quote": "被选中原文（≤400字）",
  "comment": "用户意见",
  "type": "note | hl | img",
  "region": { "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.25 },
  "ts": "ISO 时间"
}
```

`type:"img"` 的条目带 `region`（0~1 比例坐标），用于定位图上的具体区域。

---

## 📦 与专家包解耦

本技能是独立通用技能，去掉了放进任何专家包的设计：被审阅的内容只是 `manifest` 数据，技能代码不写进专家包。谁都能用，用来审自己的任何产物。
