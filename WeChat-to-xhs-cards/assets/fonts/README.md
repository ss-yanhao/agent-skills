# 内置字体

本目录的 `.woff2` 是**子集化后的开源字体**，随技能一起分发，保证任何机器出图字形一致。

## 用了什么

| 文件 | 字体 | 字重 | 用途 |
|---|---|---|---|
| `NotoSansSC-400.woff2` | 思源黑体 / Noto Sans SC | 400 | 正文 |
| `NotoSansSC-500.woff2` | 思源黑体 | 500 | 次级标题 |
| `NotoSansSC-600.woff2` | 思源黑体 | 600 | 页眉小标签 |
| `NotoSansSC-700.woff2` | 思源黑体 | 700 | 小标题 |
| `NotoSansSC-800.woff2` | 思源黑体 | 800 | 大字标题 |
| `NotoSerifSC-700.woff2` | 思源宋体 / Noto Serif SC | 700 | 金句页的装饰引号 |

## 为什么是这两款

**授权干净，且允许随软件再分发。**

- 思源黑体 = Source Han Sans（Adobe） = Noto Sans SC（Google），同一套字形两个名字
- 思源宋体 = Source Han Serif = Noto Serif SC
- 两者均为 **SIL Open Font License 1.1**，协议正文明确允许"与任何软件捆绑再分发"
  （"bundled, redistributed and/or sold with any software"），所以放进本仓库合规

**对比其他免费商用中文字体**：阿里巴巴普惠体、MiSans、HarmonyOS Sans 虽然也能免费商用，
但都是厂商自有协议，且**明确禁止再分发字体文件**（如普惠体协议："未经授权，任何人不得
上传、发布、转载阿里巴巴字体文件"）。它们可以装在你自己机器上用，但不能随开源仓库分发 ——
所以本技能不采用。

**也刻意避开了系统商业字体**：早期版本用 `-apple-system` / `PingFang SC`（苹方），
在 macOS 上出图会命中苹果的商业字体，且换到 Windows 会变成别的字形，结果不可控。
现在字体栈的首位是内置思源黑体，系统字体只做子集外生僻字的兜底。

## 子集包含什么

7556 个字符，覆盖日常中文 99.9%+：

- ASCII 可打印字符（U+0020–U+007E）
- **GB2312 全部汉字**（6763 字）
- 常用全角标点与符号（`　·—…‰′″※℃→←↑↓●○◆◇■□★☆×÷±≈≠≤≥…` 等）

**不在子集里的字**（生僻字、罕见异体字、emoji）会回退到系统字体渲染 —— 一般笔记用不到，
但如果你写了生僻字发现字形不统一，就是命中了这条。

## 怎么重新构建

字体来自 Google Fonts。注意：拿**完整 TTF** 要带一个老 User-Agent，
否则返回的是切成一百多片、按 unicode-range 加载的 woff2，不便本地打包。

```bash
# 1. 取字体 URL（老 UA → 返回完整 TTF）
curl -A "Mozilla/5.0 (Windows NT 6.1; WOW64)" \
  "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700;800&display=swap"

# 2. 以后面任一字重为例，下载 TTF 后子集化 + 转 woff2
python3 -m fontTools.subset w700.ttf \
  --text-file=subset_chars.txt \
  --output-file=NotoSansSC-700.woff2 \
  --flavor=woff2 --layout-features='*' --drop-tables+=DSIG
```

`subset_chars.txt` 的生成方式（GB2312 全字 + ASCII + 常用标点）：

```python
chars = set(chr(c) for c in range(0x20, 0x7F))          # ASCII
for b1 in range(0xA1, 0xFF):                             # GB2312 全字
    for b2 in range(0xA1, 0xFF):
        try:
            chars.add(bytes([b1, b2]).decode('gb2312'))
        except UnicodeDecodeError:
            pass
chars |= set("　·—…‰′″※℃℉№→←↑↓●○◆◇■□★☆♡♥✓✔✕✖×÷±≈≠≤≥∞％＄￥€£§¶†‡•‘’“”„…")
open("subset_chars.txt", "w", encoding="utf-8").write("".join(sorted(chars)))
```

依赖：`pip install fonttools brotli`（woff2 压缩需要 brotli）。

**体积参考**：完整 TTF 单字重约 10 MB，子集化 + woff2 后约 1 MB。本目录 6 个字重合计约 6 MB。

## 许可

- 字体版权归于 Adobe / Google，见 `OFL.txt`
- 保留字体名为 `'Source'`，本子集版本未使用该名称
- 许可证正文随字体一同分发（`OFL.txt`），符合 OFL 第 2 条
- 字体文件**不得单独出售**（OFL 第 1 条）；随本技能一起使用、再分发均无限制
