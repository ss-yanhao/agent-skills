# agent-skills

> 给 AI 用的技能库 —— 每个目录一个技能，复制过去就能用，零构建零依赖。

![Skills](https://img.shields.io/badge/skills-1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-WorkBuddy-orange)

---

## ✨ 技能一览

| 技能 | 干什么 | 输入 → 输出 | 首次要配资料 |
|------|--------|-------------|:----:|
| 📖 [**moments-copy**](./moments-copy/) | 海报 → 朋友圈文案 | 一张海报 + 参考资料 → 三版互斥文案 + 配图与发布建议 | ✅ |

---

## 📦 安装

```bash
git clone https://github.com/ss-yanhao/agent-skills.git
cd agent-skills
./install.sh                 # 装全部
./install.sh moments-copy    # 只装某一个
```

脚本把技能复制到 `~/.workbuddy/skills/`，已存在的会先问你要不要覆盖。
**装完重开一次会话**，WorkBuddy 才会扫到新技能。

---

## 📖 moments-copy · 海报朋友圈文案

> 丢一张海报和一份资料进去，出三条**能直接复制发出去**的朋友圈文案。

**什么时候用** — 拿到门店开业图 / 活动主视觉 / 产品海报 / 宣传单，要配一段发圈文案时。

### ✨ 它和别的文案工具不一样在哪

- 📏 **按朋友圈真实规格写** — 超 6 行会被折叠成「全文」，一个 emoji 占 4 字符，全都算进字符预算，交付时逐版报行数与字符数
- 🎲 **多样性优先于合规** — 朋友圈不是报批物料，平庸比出格更致命。只守 5 条会真出事的底线，极限词不做处理
- 🌾 **会联网借势** — 先查当天准确日期（节气节日绝不靠推算），再搜当下的节气 / 节日 / 热点，沾得上才用，硬蹭不如不蹭
- 🧩 **三版角度互斥** — 不是同一段话的三种长度，是三个不同的思路，角度、卖点、钩子全错开

### 🎯 产出什么

| 项目 | 说明 |
|------|------|
| **三版文案** | 短促 / 场景 / 卖点，每版末尾标注角度、卖点、借势、关键词，方便你挑 |
| **配图建议** | 第几张放什么，按朋友圈九宫格的排布规律给 |
| **发布时段** | 推荐 1-2 个时段，并说明为什么 |
| **防折叠提醒** | 复制去发之前要做的操作（不操作会被压成一行） |

### 📝 首次使用要填资料

技能目录下 `user/` 里有 4 个模板：

| 文件 | 填什么 |
|------|--------|
| `brand-brief.md` | 品牌与产品（卖点、人群、口径） |
| `sample-copy.md` | 3-5 条你认可的往期文案 |
| `style-profile.md` | 风格偏好（emoji 用法、行数、人称） |
| `ima-config.md` | 可选，接知识库用 |

填完它照**你的手感**写，而不是照通用模板写。
不填也能跑，只是出来的东西更"通用"，没那么像你。

### 🔌 可选增强

接上 ima 知识库后可从中取品牌口径和往期素材，**不接也能正常跑**。
配置方法见 [references/ima-setup.md](./moments-copy/references/ima-setup.md)。

---

## 🗂️ 目录结构

```
agent-skills/
├── README.md              # 你在看的这个
├── install.sh             # 一键安装脚本
├── moments-copy/          # 一个技能 = 一个目录
│   ├── SKILL.md           # 主流程，AI 读这个
│   ├── references/        # 参考资料（AI 按需读取）
│   └── user/              # 使用者填的资料（模板已备好）
└── (新的技能直接加在顶层)
```

**约定** — 顶层目录里只要有 `SKILL.md`，就会被 `install.sh` 认成一个技能，新增不用改脚本。

---

## ➕ 怎么加一个新技能

1. 顶层建一个目录，目录名就是技能名（小写 + 连字符，例如 `wechat-title`）
2. 里面放 `SKILL.md`，开头写 frontmatter：
   ```yaml
   ---
   name: wechat-title
   display_name: "公众号标题"
   description: "什么时候该触发这个技能，一句话说清"
   version: 1.0.0
   ---
   ```
3. 需要参考资料就建 `references/`，需要使用者填资料就建 `user/`
4. 在 README 的**技能一览**表里加一行

---

## 🔒 隐私提醒

`user/` 里的模板是空的，但**填完之后**它们就变成私人资料了（品牌信息、往期文案）。

- `.onboarded` 标记和 `user/archive/` 下的存档已被 `.gitignore` 排除
- 如果你 clone 后填了资料，又不想被 git 盯上，跑这条让它假装没看见：

  ```bash
  git update-index --skip-worktree moments-copy/user/brand-brief.md
  ```

  换掉文件名可以保护其他几个。要恢复跟踪把 `--skip-worktree` 换成 `--no-skip-worktree`。

---

## 📄 License

MIT © 2025

---

<p align="center">
  <sub>Made with ❤️ for 品牌运营</sub>
</p>
