#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把一篇推文/长文渲染成小红书 3:4 竖版图片笔记（1080×1440），并导出 PNG。

用法：
    python3 render.py --spec cards.json --out ./out [--style glass] [--scale 2] [--html-only]

spec 是一个 JSON，描述每一页的内容（由 AI 从推文提炼，见 SKILL.md 的 spec 格式）。
脚本只负责「排版 + 出图」，不负责理解文章。

依赖：本机 Google Chrome（headless 截图），零 Python 第三方依赖。
"""
import argparse
import html
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
CSS_PATH = SKILL_DIR / "assets" / "card.css"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("chromium"),
    shutil.which("google-chrome"),
]

FIT_JS = """
<script>
(function(){
  var stage = document.querySelector('.stage');
  var els = [].slice.call(document.querySelectorAll('[data-fit]'));
  if(!stage || !els.length) return;
  var parse = function(el){
    var p = (el.dataset.fit||'').split(':').map(Number);
    return {min: p[0]||20, max: p[1]||80, step: p[2]||2};
  };
  var cfg = els.map(parse);
  var cur = cfg.map(function(c){return c.max;});
  var apply = function(){ els.forEach(function(el,i){ el.style.fontSize = cur[i] + 'px'; }); };
  apply();
  var guard = 0;
  while(stage.scrollHeight > stage.clientHeight + 2 && guard++ < 400){
    var idx = -1, best = -1;
    els.forEach(function(el,i){
      if(cur[i] > cfg[i].min && cur[i] > best){ best = cur[i]; idx = i; }
    });
    if(idx < 0) break;
    cur[idx] -= cfg[idx].step;
    apply();
  }
})();
</script>
"""


def esc(s):
    return html.escape("" if s is None else str(s), quote=False)


def find_chrome():
    for c in CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


# ---------------------------------------------------------------- 页面模板

def head_foot(kicker, source, page_no, total, footnote=""):
    """页眉：左 kicker / 右 页码。页脚：左 source / 右 footnote。

    footnote 由 spec 的 `footnote` 字段控制，**缺省就不渲染右侧那格** ——
    技能不替用户预设页脚内容（曾硬编码过占位符，发出去就是废信息）。
    """
    kicker_html = f'<span class="kicker">{esc(kicker)}</span>' if kicker else "<span></span>"
    pageno = f'<span class="pageno">{page_no:02d} / {total:02d}</span>'
    head = f'<div class="pg-head">{kicker_html}{pageno}</div>'
    right = f'<span>{esc(footnote)}</span>' if footnote else ""
    foot = f'<div class="pg-foot"><span>{esc(source)}</span>{right}</div>' if source else ""
    return head, foot


def build_cover(card, ctx):
    head, foot = head_foot(ctx["kicker"], ctx["source"], 1, ctx["total"], ctx.get("footnote", ""))
    sub = f'<p class="cover-sub">{esc(card.get("subtitle",""))}</p>' if card.get("subtitle") else ""
    # 封面底部通栏图（话题标签已不再在图上渲染，这里改放推文封面图）
    img = (f'<img class="cover-img" src="{ctx["img"](card["img"])}" alt="">'
           if card.get("img") else "")
    return f"""{head}
<div class="stage">
  <h1 class="cover-title" data-fit="52:132:2">{esc(card.get("title",""))}</h1>
  <div class="cover-rule"></div>
  {sub}
  {img}
</div>
{foot}"""


def build_points(card, ctx, i):
    head, foot = head_foot(ctx["kicker"], ctx["source"], i, ctx["total"], ctx.get("footnote", ""))
    idx = card.get("index") or f"{i-1:02d}"
    title = f'<h2 class="card-title" data-fit="38:76:2">{esc(card.get("title",""))}</h2>' if card.get("title") else ""
    pts = "".join(f"<li>{esc(p)}</li>" for p in card.get("points", []))
    ul = f'<div class="mid"><ul class="points" data-fit="24:42:1">{pts}</ul></div>' if pts else ""
    note = f'<p class="note">{esc(card.get("note",""))}</p>' if card.get("note") else ""
    return f"""{head}
<div class="stage">
  <div class="idx">{esc(idx)}</div>
  {title}
  {ul}
  {note}
</div>
{foot}"""


def build_quote(card, ctx, i):
    head, foot = head_foot(ctx["kicker"], ctx["source"], i, ctx["total"], ctx.get("footnote", ""))
    by = f'<div class="by">— {esc(card.get("by",""))}</div>' if card.get("by") else ""
    return f"""{head}
<div class="stage center">
  <div class="quote-mark">&ldquo;</div>
  <blockquote class="quote" data-fit="30:72:2">{esc(card.get("text",""))}</blockquote>
  {by}
</div>
{foot}"""


def build_stat(card, ctx, i):
    head, foot = head_foot(ctx["kicker"], ctx["source"], i, ctx["total"], ctx.get("footnote", ""))
    cells = "".join(
        f'<div><div class="stat-num">{esc(s.get("num",""))}</div>'
        f'<div class="stat-lab">{esc(s.get("label",""))}</div></div>'
        for s in card.get("items", [])
    )
    title = f'<h2 class="card-title" data-fit="38:68:2">{esc(card.get("title",""))}</h2>' if card.get("title") else ""
    return f"""{head}
<div class="stage">
  {title}
  <div class="mid"><div class="stat-grid">{cells}</div></div>
</div>
{foot}"""


def build_ending(card, ctx, i):
    head, foot = head_foot(ctx["kicker"], ctx["source"], i, ctx["total"], ctx.get("footnote", ""))
    # 话题标签与 cta 文案都不再上图，腾出的空间改放一张收尾插画
    img = (f'<img class="end-float" src="{ctx["img"](card["img"])}" alt="">'
           if card.get("img") else "")
    return f"""{head}
<div class="stage">
  <div class="endbox">
    <h2 class="end-title" data-fit="40:92:2">{esc(card.get("title",""))}</h2>
  </div>
  {img}
</div>
{foot}"""


def build_product(card, ctx, i):
    """场景卡：一张插画当底图，把产品图叠在底图的左下 / 右下角。

    产品图是 RGBA 透明底的"漂浮罐体"，底边锚定在底图下缘 —— 因为产品图
    自身的罐体底部在原图里就是被裁掉的，底边对齐正好把切口藏在画面边界。

    spec 字段：
      base / product        底图与产品图文件名
      title / caption       图上文字
      base_fit              cover（默认）| contain（竖版底图用，避免重裁主体）
      prod_anchor           right（默认）| left
      prod_w / prod_x       产品图宽度（占画布宽 %）与距锚点边内缩（%）
    """
    head, foot = head_foot(ctx["kicker"], ctx["source"], i, ctx["total"], ctx.get("footnote", ""))
    base = ctx["img"](card.get("base", ""))
    prod = ctx["img"](card.get("product", "")) if card.get("product") else ""

    cls = []
    if card.get("base_fit") == "contain":
        cls.append("base-contain")
    if card.get("prod_anchor") == "left":
        cls.append("left")
    cls = (" " + " ".join(cls)) if cls else ""

    style = []
    if card.get("prod_w"):
        style.append(f"--pw:{card['prod_w']}%")
    if card.get("prod_x") is not None:
        style.append(f"--px:{card['prod_x']}%")
    style = f' style="{";".join(style)}"' if style else ""

    prod_html = f'<img class="prod-img" src="{prod}" alt=""{style}>' if prod else ""

    title = f'<h2 class="card-title" data-fit="34:64:2">{esc(card["title"])}</h2>' if card.get("title") else ""
    cap = f'<p class="img-caption">{esc(card.get("caption",""))}</p>' if card.get("caption") else ""
    textbox = f'<div class="textbox">{title}{cap}</div>' if (title or cap) else ""

    return f"""{head}
<div class="stage">
  <div class="productcard{cls}">
    <div class="collage">
      <img class="base-img" src="{base}" alt="">
      {prod_html}
    </div>
    {textbox}
  </div>
</div>
{foot}"""


def build_image(card, ctx, i):
    """图片卡：一张图 + 可选标题/要点/说明。

    layout:
      top     —— 图上文下（默认）
      imgonly —— 只有图，铺满
    """
    head, foot = head_foot(ctx["kicker"], ctx["source"], i, ctx["total"], ctx.get("footnote", ""))
    src = ctx["img"](card.get("img", ""))
    layout = card.get("layout", "top")

    title = ""
    if card.get("title"):
        title = f'<h2 class="card-title" data-fit="34:64:2">{esc(card["title"])}</h2>'
    pts = "".join(f"<li>{esc(p)}</li>" for p in card.get("points", []))
    ul = f'<ul class="points img-points" data-fit="22:34:1">{pts}</ul>' if pts else ""
    cap = f'<p class="img-caption">{esc(card.get("caption",""))}</p>' if card.get("caption") else ""
    textbox = f'<div class="textbox">{title}{ul}{cap}</div>' if (title or ul or cap) else ""

    cls = "imgcard imgonly" if layout == "imgonly" else "imgcard"
    return f"""{head}
<div class="stage">
  <div class="{cls}">
    <div class="photo-box"><img src="{src}" alt=""></div>
    {textbox}
  </div>
</div>
{foot}"""


BUILDERS = {
    "points": build_points,
    "quote": build_quote,
    "stat": build_stat,
    "image": build_image,
    "product": build_product,
}


def build_pages(spec):
    style = spec.get("style", "ink")
    ctx = {
        "kicker": spec.get("kicker", ""),
        "source": spec.get("source", ""),
        "footnote": spec.get("footnote", ""),
        # HTML 在 out/html/ 下，图片统一放 out/images/，所以要多退一层
        "img": lambda name: "../images/" + os.path.basename(str(name)),
    }
    cover = spec.get("cover") or {}
    cards = spec.get("cards", [])
    ending = spec.get("ending")
    total = 1 + len(cards) + (1 if ending else 0)

    pages = []
    # 封面
    pages.append(("01-cover", f"封面 · {cover.get('title','')}", build_cover(cover, {**ctx, "total": total})))
    # 正文
    for n, c in enumerate(cards, start=2):
        kind = c.get("kind", "points")
        builder = BUILDERS.get(kind, build_points)
        name = f"{n:02d}-{kind}"
        label = f"{kind} · {c.get('title') or c.get('text','')}"[:40]
        pages.append((name, label, builder(c, {**ctx, "total": total}, n)))
    # 结尾
    if ending:
        n = len(cards) + 2
        pages.append((f"{n:02d}-ending", f"结尾 · {ending.get('title','')}",
                      build_ending(ending, {**ctx, "total": total}, n)))
    return style, pages


def wrap_html(body_inner, css, style, accent):
    accent_css = f"body{{--accent:{accent};}}" if accent else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>{css}
{accent_css}
</style></head>
<body class="theme-{style}">
{body_inner}
{FIT_JS}
</body></html>"""


# ---------------------------------------------------------------- 出图

def screenshot(chrome, html_path, png_path, scale):
    """出图一次。

    注意两个 macOS 上的坑：
    1. Chrome 152+ 的 headless 截图写完 PNG 后进程不会退出（macOS 上
       CVDisplayLink 报错后一直挂着），所以不能等它自己结束 —— 改成轮询
       产物文件，尺寸稳定后直接杀掉整个进程组。
    2. 同一个 user-data-dir 复用会被上一次的残留进程锁住，所以每次都用
       全新的临时 profile。
    """
    if os.path.exists(png_path):
        os.remove(png_path)
    profile = tempfile.mkdtemp(prefix="xhs-chrome-")
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",          # 外层沙箱 + Chrome 自带 seatbelt 会互相打架，必须关掉
        "--disable-gpu",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-background-networking",
        "--hide-scrollbars",
        "--force-device-scale-factor=%s" % scale,
        "--window-size=1080,1440",
        "--virtual-time-budget=4000",
        f"--screenshot={png_path}",
        f"file://{html_path}",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + 40
    last_size, stable_since = -1, None
    ok = False
    try:
        while time.time() < deadline:
            if os.path.exists(png_path):
                size = os.path.getsize(png_path)
                if size > 1024 and size == last_size:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since > 0.4:
                        ok = True
                        break
                else:
                    stable_since = None
                last_size = size
            time.sleep(0.15)
    finally:
        _kill_tree(proc)
        shutil.rmtree(profile, ignore_errors=True)

    if not ok or not os.path.exists(png_path):
        raise RuntimeError(f"截图失败，40s 内没等到产物：{html_path}")
    return png_path


def _kill_tree(proc):
    """Chrome 会拉一群子进程，必须杀整个进程组。"""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="推文 → 小红书 3:4 图片笔记")
    ap.add_argument("--spec", required=True, help="内容 spec JSON 路径")
    ap.add_argument("--out", default="./xhs-out", help="输出目录")
    ap.add_argument("--img-base", help="配图所在目录（spec 里 img 只写文件名）")
    ap.add_argument("--style", help="覆盖 spec 里的主题：ink / glass / bold")
    ap.add_argument("--accent", help="覆盖主色，如 #C1440E")
    ap.add_argument("--scale", type=int, default=2, help="导出倍率，默认 2（即 2160×2880）")
    ap.add_argument("--html-only", action="store_true", help="只生成 HTML，不截图（快速调样式）")
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    css = CSS_PATH.read_text(encoding="utf-8")
    style = args.style or spec.get("style", "ink")
    accent = args.accent or spec.get("accent")

    style, pages = build_pages(spec)
    if args.style:
        style = args.style

    out = pathlib.Path(args.out).expanduser().resolve()
    html_dir = out / "html"
    # 注意：某些运行环境下 mkdir(exist_ok=True) 遇到已存在目录仍会抛 EEXIST，
    # 所以一律先判断存在再建 —— 否则第二次渲染必挂在"重新出图"这一步。
    for d in (out, html_dir):
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)

    # 把用到的配图收集到 out/images/，HTML 用相对路径引用
    img_base = args.img_base or spec.get("img_base") or ""
    need = []
    if spec.get("cover", {}).get("img"):
        need.append(spec["cover"]["img"])
    if spec.get("ending", {}).get("img"):
        need.append(spec["ending"]["img"])
    for c in spec.get("cards", []):
        for key in ("img", "base", "product"):
            if c.get(key):
                need.append(c[key])
    # 去重，保持顺序
    need = list(dict.fromkeys(need))
    if need:
        if not img_base:
            sys.exit("spec 里用了配图，但没给 --img-base 或 spec.img_base")
        src_dir = pathlib.Path(img_base).expanduser()
        img_dir = out / "images"
        if not img_dir.exists():
            img_dir.mkdir(parents=True, exist_ok=True)
        for name in need:
            src = src_dir / os.path.basename(str(name))
            if not src.exists():
                sys.exit(f"配图不存在：{src}")
            shutil.copy2(src, img_dir / src.name)
        print(f"已复制 {len(need)} 张配图 → {img_dir}")

    # 内置字体复制到 out/fonts/ —— card.css 里的 @font-face 用 ../fonts/ 引用，
    # 整个 out 目录因此可以独立搬走，换台机器出图也是同一套字形。
    font_src = CSS_PATH.parent / "fonts"
    if font_src.is_dir():
        font_dir = out / "fonts"
        if not font_dir.exists():
            font_dir.mkdir(parents=True, exist_ok=True)
        n_font = 0
        for f in sorted(font_src.iterdir()):
            if f.is_file() and f.suffix.lower() in (".woff2", ".txt", ".md"):
                shutil.copy2(f, font_dir / f.name)
                n_font += 1
        print(f"已复制 {n_font} 个字体文件 → {font_dir}")
    else:
        sys.stderr.write(f"警告：没找到内置字体目录 {font_src}，出图会退回系统字体\n")

    written_html = []
    for name, label, inner in pages:
        p = html_dir / f"{name}.html"
        p.write_text(wrap_html(inner, css, style, accent), encoding="utf-8")
        written_html.append((name, label, p))

    if args.html_only:
        print(f"已生成 {len(written_html)} 个 HTML（未截图）：{html_dir}")
        return

    chrome = find_chrome()
    if not chrome:
        sys.exit("没找到 Chrome/Chromium，无法截图。可先跑 --html-only，或手动在浏览器里打开 html/ 下的文件。")

    pngs = []
    labels = {}
    for name, label, p in written_html:
        png = out / f"{name}.png"
        screenshot(chrome, p, png, args.scale)
        pngs.append(png)
        labels[name] = label
        print(f"  ✓ {png.name}")

    # 预览页：把所有卡片并排摆出来，本地直接看效果
    items = "".join(
        f'<figure><img src="{p.name}" alt="{esc(labels.get(p.stem, ""))}">'
        f'<figcaption>{esc(labels.get(p.stem, ""))}</figcaption></figure>'
        for p in pngs
    )
    preview = out / "preview.html"
    preview.write_text(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>小红书图片笔记预览</title>
<style>
body{{margin:0;padding:48px;background:#F2F2F5;font-family:system-ui,sans-serif;
display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:32px}}
figure{{margin:0}} img{{width:100%;border-radius:16px;box-shadow:0 12px 32px rgba(0,0,0,.14);display:block}}
figcaption{{margin-top:12px;font-size:14px;color:#666;text-align:center}}
</style></head><body>{items}</body></html>""", encoding="utf-8")

    print(f"\n共 {len(pngs)} 张，输出目录：{out}")
    print(f"预览页：{preview}")


if __name__ == "__main__":
    main()
