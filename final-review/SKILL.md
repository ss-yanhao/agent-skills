---
name: final-review
display_name: "一键审阅 AI 产物"
version: 1.0.0
description: 输入一批 AI 产物清单（文案/配图/规则文件等最终交付物）→ 输出一个可自由圈点批注、一键导出意见 JSON 的离线审阅 HTML，供用户目检后由主理人逐条回收修改。独立通用技能，不依赖任何专家包。当用户说「把产物放一个 HTML 里让我标注 / 做个审阅件 / review 一下 / 生成可圈点批注的页面」，或任何「多份交付物需用户目检 + 逐条反馈后我再改」的场景时使用。
agent_created: true
---

# final-review · 一键审阅 AI 产物

**输入**一批 AI 产物清单（manifest 描述）→ **输出**一个可自由圈点批注、一键导出意见 JSON 的离线审阅 HTML。

把模型交付的所有「最终成品」收进一个单文件页面，用户在浏览器里选中文字就能批注、在图上拖框就能圈注，点一下导出固定文件名 `review-comments.json`，主理人据此逐条回收修改。

本技能**只产出审阅件与回收流程**，不修改被审阅的文件本身；被审阅内容只是一份 `manifest.json` 数据，与任何专家包解耦。

## 何时用
用户说以下任意一种时启用：
- 「把产物放一个 HTML 里让我标注 / 做审阅件 / review 一下」
- 「生成一个可以圈点批注的页面」
- 任何「多份交付物需要用户目检 + 逐条反馈后我再改」的场景

## 铁律：产物 = 最终交付物，不是我的过程文件
用户定义的「产物」是**交付给人的最终东西**（如让我写朋友圈文案，文案本身就是产物），**不是生成它的脚本/过程文件**。
写 manifest 时：
- ✅ 放：推文终稿、朋友圈文案、小红书文案、更新日志条目、配图成稿等消费者面向的成品。
- ❌ 不放：生成脚本（qa-check.py / gen-illustrations.py / purify-silhouette.py 等）、`pipeline.json`、`PROMPT-MAP.md`、QA 报告、提示词草稿、构建/渲染脚本等内部过程文件。
- 例：某次任务交付物是「写进专家团的规则」，那 7 个规则文件本身就是该任务的最终产物，可放；但同 run 里的生图脚本/状态机 json 只是过程，不放。

## 依赖
- `python3` + `markdown`：`pip install markdown`（已装进受管 venv 可直接用）
- 内联 JS 产出前会用 `node --check` 校验（找不到 node 则跳过并告警，不阻断产出）

## 用法（两步）
1. **写 manifest.json**：描述要审阅的批次与文件。格式见下。每条文件带 `realpath`（真文件绝对路径），供回收时主理人定位修改。
2. **跑生成器**：
   ```
   python <skill>/gen_review.py --manifest manifest.json --out review.html
   ```
   输出单文件、自包含（CSS/JS 内联）、可离线打开的 `review.html`。

## manifest.json 格式
```json
{
  "title": "审阅件标题",
  "defaultBatch": "batch-a",
  "batches": [
    { "id":"batch-a", "label":"批次A说明", "default":true,
      "root":"/绝对/根目录",
      "files":[ {"src":"相对root的文件路径","docid":"a1","title":"显示标题","realpath":"/绝对/真文件路径"} ] },
    { "id":"batch-b", "label":"批次B说明", "default":false, "root":"...", "files":[ ... ] }
  ]
}
```
- `realpath` 留空字符串 `""` 的项是「自助添加、无真文件对应」，回收时主理人会追问目标文件。
- `default:true` 的批次默认展开，其余折叠（页面顶部可一键展开）。
- 文件类型：`.md`（富文本）/ `.json/.py/.js/.cjs/.txt`（代码围栏）/ 图片（`.png/.jpg/.jpeg/.gif/.webp/.bmp`，自动 base64 内联、可圈注）。
- 样例见 `<skill>/assets/example-manifest.json`。

## HTML 内用户能做什么
- 左侧目录跳转到可见批次的章节
- **选中正文任意文字 → 浮条「💬 标注 / 🖍 高亮」** → 标注弹框写意见，自动存浏览器本地
- **在图片上拖框（单击=整图）→ 圈注**，图上标编号，导出带 `region`（0~1 比例坐标）
- 顶栏「➕ 自助添加」：上传文件 / 粘贴文本，离线新增一节（无 realpath）
- 顶栏「⬇ 保存并下载」：把全部标注导出为 **固定文件名 `review-comments.json`** 并下载，同时弹出可复制的 JSON
- 右侧面板列出所有标注（含来源章节、原文引用、realpath），可定位/删除；「⬆ 导入」可回贴标注

## 回收循环（用户在 HTML 标注完、说「写完了」后，主理人执行）
1. `Read` 约定路径下的 `review-comments.json`。
2. 遍历 `annotations`：按 `realpath` 定位真文件；`realpath` 为空 → 问用户目标文件。
3. 逐条编辑对应 .md/.json/.py 等。
4. 若改的是专家包文件 → 同步 源 + 缓存多版本三副本并核 sha256（沿用双副本规则；这是对「被审阅内容」的常规修改，不改变本技能）。
5. 回执：每条怎么改、改了哪个文件；有歧义的标出。

## 导出 JSON 结构（每条 annotation）
```json
{ "id":"a...", "batchId":"batch-a", "batchLabel":"...", "doc":"a1",
  "title":"显示标题", "realpath":"/绝对/真文件路径",
  "quote":"被选中原文（≤400字）", "comment":"用户意见",
  "type":"note|hl|img", "region":{ "x":0.1,"y":0.2,"w":0.3,"h":0.25 }, "ts":"ISO时间" }
```

## 注意事项
- `gen_review.py` 落盘前会用 `node --check` 校验内联 JS，失败即报错不产出（无 node 时降级为告警跳过）。
- 浏览器本地存储仅同浏览器有效；跨设备/换浏览器以导出的 JSON 为准交回主理人。
- 文件名建议用 ascii（如 `review.html`），避免中文路径编码坑。
- 本技能与任何专家包解耦：被审阅内容只是数据（manifest），技能代码不写进专家包。
