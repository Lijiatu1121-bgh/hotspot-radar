# -*- coding: utf-8 -*-
"""把各渠道的报告汇总成一个静态站点（docs/），供 GitHub Pages 直接发布。

产物结构：
  docs/index.html                     ← 首页：按批次倒序列出三个渠道的报告
  docs/<channel>/<batch>/*.html       ← 报告副本（由各渠道 reports/ 复制）
  docs/.nojekyll                      ← 关掉 Jekyll，否则下划线开头的文件会被忽略

为什么复制而不是直接发布 */reports/：
  GitHub Pages 只支持从「仓库根目录」或「/docs」发布，不能指定任意子目录。
  复制一份到 docs/ 换来的好处是：零 Actions、零构建，push 完就自动生效。
"""
import os, re, json, shutil, datetime, html as htmlmod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')

CHANNELS = [
    ('bilibili', 'B站', '#FB7299', '综合爆款 · 知识区 · AI+硬件 · 知识点'),
    ('zhihu', '知乎', '#0084FF', '有价值议题筛选 · 知识内核 · 争议拆解'),
    ('github', 'GitHub', '#2da44e', '刷星识别 · 技术路线 · 成熟度评级'),
]

# 报告文件名 -> 卡片上的短标题（按关键字匹配，取不到就用文件名）
SHORT_NAMES = [
    ('b站爆款分析报告', '综合爆款分析'),
    ('知识区爆款背后的知识点报告', '知识点拆解'),
    ('知识区爆款分析报告', '知识区爆款'),
    ('人工智能与硬件更新爆款报告', 'AI + 硬件'),
    ('知乎有价值议题分析报告', '价值议题分析'),
    ('GitHub热点技术分析报告', '技术分析'),
]


def short_name(fn):
    for key, name in SHORT_NAMES:
        if key in fn:
            return name
    return re.sub(r'_?\d{4}-\d{2}-\d{2}(_\d+)?\.html$', '', fn).replace('.html', '')


def collect():
    """扫描各渠道 reports/，返回 {batch: {channel: [(file, short)]}} 和批次列表。"""
    data, batches = {}, set()
    for ch, _, _, _ in CHANNELS:
        base = os.path.join(ROOT, ch, 'reports')
        if not os.path.isdir(base):
            continue
        for batch in sorted(os.listdir(base)):
            d = os.path.join(base, batch)
            if not os.path.isdir(d):
                continue
            files = [f for f in sorted(os.listdir(d)) if f.lower().endswith('.html')]
            if not files:
                continue
            batches.add(batch)
            data.setdefault(batch, {})[ch] = [(f, short_name(f)) for f in files]
    return data, sorted(batches, reverse=True)


def build():
    data, batches = collect()
    if not batches:
        print('没有找到任何报告，先跑 scripts/run_all.py')
        return 1

    # 重建 docs/（这是纯生成目录，整体覆盖）
    if os.path.isdir(DOCS):
        shutil.rmtree(DOCS)
    os.makedirs(DOCS)
    open(os.path.join(DOCS, '.nojekyll'), 'w').close()

    # 复制报告
    copied = 0
    for batch, chs in data.items():
        for ch, files in chs.items():
            dst = os.path.join(DOCS, ch, batch)
            os.makedirs(dst, exist_ok=True)
            for fn, _ in files:
                shutil.copy2(os.path.join(ROOT, ch, 'reports', batch, fn),
                             os.path.join(dst, fn))
                copied += 1

    # 读状态文件（记录某渠道本期是否失败）
    status_map = {}
    for batch in batches:
        p = os.path.join(ROOT, 'reports', batch, 'status.json')
        if os.path.exists(p):
            try:
                status_map[batch] = json.load(open(p, encoding='utf-8'))
            except Exception:
                pass

    # ---------- 首页 ----------
    blocks = ''
    for i, batch in enumerate(batches):
        chs = data.get(batch, {})
        st = status_map.get(batch, {}).get('channels', {})
        latest = ' latest' if i == 0 else ''
        tag = '<span class="badge">最新</span>' if i == 0 else ''
        rows = ''
        for ch, label, color, desc in CHANNELS:
            if ch in chs:
                links = ' · '.join(
                    f'<a href="{ch}/{batch}/{f}" style="--c:{color}">{nm}</a>'
                    for f, nm in chs[ch])
                rows += (f'<div class="row">'
                         f'<span class="ch" style="--c:{color}">{label}</span>'
                         f'<span class="links">{links}</span></div>')
            else:
                err = st.get(ch, {}).get('error', '本期未运行')
                rows += (f'<div class="row missing">'
                         f'<span class="ch" style="--c:{color}">{label}</span>'
                         f'<span class="links">未生成 <i>{htmlmod.escape(err[:60])}</i></span></div>')
        blocks += f'<section class="batch{latest}"><h2>{batch}{tag}</h2>{rows}</section>'

    total_reports = sum(len(f) for chs in data.values() for f in chs.values())
    # 不写精确构建时间：否则每次运行都会产生一个仅时间不同的 diff，污染提交历史
    newest = batches[0] if batches else '—'

    page = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>热点雷达 · 三渠道热点分析</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  background:#f5f7fa;color:#1f2328;line-height:1.65;
  background-image:radial-gradient(circle at 15% 0%,rgba(0,132,255,.07),transparent 45%),
                   radial-gradient(circle at 85% 8%,rgba(45,164,78,.06),transparent 42%);}}
.wrap{{max-width:860px;margin:0 auto;padding:52px 20px 80px}}
header{{margin-bottom:38px}}
h1{{font-size:29px;letter-spacing:-.4px;margin-bottom:9px}}
h1 .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;background:#2da44e;
  margin-right:10px;vertical-align:middle;box-shadow:0 0 0 4px rgba(45,164,78,.15)}}
.sub{{color:#5c6b7a;font-size:14px}}
.stats{{display:flex;gap:26px;margin-top:18px;font-size:13px;color:#8a94a0;flex-wrap:wrap}}
.stats b{{color:#1f2328;font-size:17px;font-weight:800;margin-right:4px}}
section.batch{{background:#fff;border:1px solid #e6eaf0;border-radius:14px;
  padding:20px 22px;margin-bottom:14px;box-shadow:0 1px 3px rgba(16,24,40,.04)}}
section.latest{{border-color:#cfe0f5;box-shadow:0 3px 16px rgba(0,132,255,.08)}}
h2{{font-size:16px;font-weight:800;letter-spacing:.2px;margin-bottom:14px;
  display:flex;align-items:center;gap:9px;font-variant-numeric:tabular-nums}}
.badge{{font-size:10.5px;font-weight:700;color:#0066cc;background:#e8f3ff;
  border-radius:20px;padding:2px 9px;letter-spacing:.3px}}
.row{{display:flex;gap:14px;align-items:baseline;padding:8px 0;border-top:1px dashed #eef1f5}}
.row:first-of-type{{border-top:none}}
.ch{{flex:0 0 58px;font-size:12.5px;font-weight:700;color:var(--c)}}
.links{{flex:1;font-size:13.5px;color:#9aa5b1}}
.links a{{color:#37474f;text-decoration:none;border-bottom:1px solid transparent;
  transition:.15s;padding:1px 0}}
.links a:hover{{color:var(--c);border-bottom-color:var(--c)}}
.row.missing .links{{color:#b0b8c1}}
.row.missing i{{font-style:normal;font-size:12px;color:#c4ccd4}}
footer{{margin-top:34px;text-align:center;color:#b0b8c1;font-size:12px;line-height:1.9}}
footer code{{font-family:ui-monospace,Consolas,monospace;background:#eef1f5;
  border-radius:4px;padding:1px 6px;font-size:11.5px}}
</style></head>
<body><div class="wrap">
<header>
  <h1><span class="dot"></span>热点雷达</h1>
  <div class="sub">B站 · 知乎 · GitHub 三渠道热点分析，每周更新。每个渠道都做了营销/低质内容剔除，并给出可执行的分析框架。</div>
  <div class="stats">
    <span><b>{len(batches)}</b>周次</span>
    <span><b>{total_reports}</b>份报告</span>
    <span><b>3</b>个渠道</span>
    <span>最新数据 {newest}</span>
  </div>
</header>
{blocks}
<footer>
  由 GitHub Actions 之外的本地脚本生成 · 数据全部来自公开接口<br>
  重新构建：<code>python scripts/build_site.py</code>
</footer>
</div></body></html>'''

    with open(os.path.join(DOCS, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)

    print(f'站点已生成：docs/')
    print(f'  批次 {len(batches)} 个，报告 {copied} 份')
    print(f'  最新：{batches[0] if batches else "—"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(build())
