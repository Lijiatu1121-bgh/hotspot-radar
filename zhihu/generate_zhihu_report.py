# -*- coding: utf-8 -*-
"""生成《知乎有价值议题分析报告》。

报告立场：不做热榜搬运，只做三件事
  1) 判定：哪些条目有分析价值，哪些是营销/八卦/情绪，并说明理由
  2) 拆解：每条有价值议题的知识内核、分析视角、争议类型、该问的问题
  3) 归因：热度 ≠ 价值，用散点图把「高热度低价值」和「低热度高价值」分开

所有结论由 zhihu_taxonomy.py 的规则引擎生成，可复现、可审计；
末尾明确标注方法与局限，不假装是人工判断。
"""
import json, os, re, datetime
from collections import Counter, defaultdict
import zhihu_taxonomy as tx

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
TODAY = datetime.date.today().strftime('%Y-%m-%d')
BATCH = os.environ.get('BZ_BATCH') or TODAY
NOW_DT = datetime.datetime.now()

raw = json.load(open(os.path.join(DATA, 'zhihu_raw.json'), encoding='utf-8'))
hot = raw.get('hot', [])
daily = raw.get('daily', [])

# ---------- 分类 ----------
kept, dropped = [], []
for it in hot:
    ex = tx.excluded(it)
    if ex:
        kind, words = ex
        it2 = dict(it)
        it2['drop_kind'] = kind
        it2['drop_words'] = words
        dropped.append(it2)
        continue
    a = tx.analyze(it)
    it2 = dict(it)
    it2.update(a)
    kept.append(it2)

kept.sort(key=lambda x: x['score']['total'], reverse=True)

# 软剔除：价值分过低（<30）说明既不属于营销八卦，也确实拆不出可验证的东西
SOFT_CUT = 30
low_value = [k for k in kept if k['score']['total'] < SOFT_CUT]
kept = [k for k in kept if k['score']['total'] >= SOFT_CUT]

dropped_kind = Counter(d['drop_kind'] for d in dropped)

# ---------- 统计 ----------
dom_cnt = Counter(k['domain'] for k in kept)
dom_score = defaultdict(list)
for k in kept:
    dom_score[k['domain']].append(k['score']['total'])
dom_avg = {d: sum(v) / len(v) for d, v in dom_score.items()}

scores = [k['score']['total'] for k in kept]
avg_score = sum(scores) / len(scores) if scores else 0
heat_vals = [k['heat'] for k in kept if k.get('heat')]
med_heat = sorted(heat_vals)[len(heat_vals) // 2] if heat_vals else 0
drop_rate = (len(dropped) + len(low_value)) / len(hot) * 100 if hot else 0

low_rows = ''
for k in low_value:
    low_rows += (f'<tr><td style="text-align:left;color:#666">{k["title"][:40]}</td>'
                 f'<td><span class="pill p-warn">价值分不足</span></td>'
                 f'<td style="text-align:left;color:#aaa;font-size:12px">'
                 f'{k["score"]["total"]} 分 · 归类「{k["domain"]}」但缺乏可验证的知识底盘</td></tr>')


# ---------- SVG ----------
def hbar(data, color='#0084FF', width=620, unit=''):
    data = [(str(l), v) for l, v in data]
    if not data:
        return '<div style="color:#999;font-size:13px">无数据</div>'
    maxv = max(v for _, v in data) or 1
    rowh, gap = 26, 9
    rows = ''
    for i, (lab, val) in enumerate(data):
        y = i * (rowh + gap)
        bw = max(3, val / maxv * (width - 200))
        rows += (f'<g transform="translate(0,{y})">'
                 f'<text x="0" y="{rowh/2}" dominant-baseline="middle" font-size="12.5" fill="#333">{lab}</text>'
                 f'<rect x="150" y="4" width="{bw:.0f}" height="{rowh-8}" rx="3" fill="{color}"/>'
                 f'<text x="{150+bw+7:.0f}" y="{rowh/2}" dominant-baseline="middle" font-size="11.5" fill="#777">{val}{unit}</text>'
                 f'</g>')
    h = len(data) * (rowh + gap)
    return f'<svg width="{width}" height="{h}" viewBox="0 0 {width} {h}" style="max-width:100%">{rows}</svg>'


def scatter(items, width=680, height=380):
    """象限图：横轴=热度排名百分位，纵轴=价值分。

    为什么不用真实热度做横轴：热榜热度都在百万量级（59 万 ~ 1595 万），
    对数轴上跨度不到半个数量级，点会全挤在一起，看不出结构。
    改用排名百分位后，四象限的语义非常干净：
      右上 又热又有料 / 右下 热但空 / 左上 冷但有料（套利区）/ 左下 冷且空
    """
    pts = [i for i in items if i.get('heat')]
    if not pts:
        return '<div style="color:#999;font-size:13px">热度数据缺失，无法绘制</div>'

    order = sorted(pts, key=lambda p: p['heat'])
    n = len(order)
    for idx, p in enumerate(order):
        p['_xr'] = (idx + 0.5) / n          # 0~1，热度排名百分位

    pad_l, pad_b, pad_t, pad_r = 54, 46, 22, 22
    W, H = width - pad_l - pad_r, height - pad_t - pad_b
    rows = ''

    # 网格
    for gv in (0, 25, 50, 75, 100):
        y = pad_t + H - gv / 100 * H
        rows += f'<line x1="{pad_l}" y1="{y:.0f}" x2="{pad_l+W}" y2="{y:.0f}" stroke="#eef0f2"/>'
        rows += (f'<text x="{pad_l-8}" y="{y:.0f}" text-anchor="end" '
                 f'dominant-baseline="middle" font-size="11" fill="#9aa5b1">{gv}</text>')

    # 中位分割线
    ym = pad_t + H - avg_score / 100 * H
    xm = pad_l + W * 0.5
    rows += (f'<line x1="{pad_l}" y1="{ym:.0f}" x2="{pad_l+W}" y2="{ym:.0f}" '
             f'stroke="#b9c6d3" stroke-dasharray="5 4"/>')
    rows += (f'<line x1="{xm:.0f}" y1="{pad_t}" x2="{xm:.0f}" y2="{pad_t+H}" '
             f'stroke="#b9c6d3" stroke-dasharray="5 4"/>')

    # 象限标注
    qlab = [
        (pad_l + 10, pad_t + 14, '冷门但有料 · 套利区', '#1a7f37', 'start'),
        (pad_l + W - 10, pad_t + 14, '又热又有料', '#0066cc', 'end'),
        (pad_l + 10, pad_t + H - 8, '冷且空', '#9aa5b1', 'start'),
        (pad_l + W - 10, pad_t + H - 8, '热但空', '#c25b1a', 'end'),
    ]
    for x, y, t, c, anc in qlab:
        rows += (f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anc}" font-size="11.5" '
                 f'font-weight="700" fill="{c}" opacity="0.72">{t}</text>')

    # 数据点
    for p in pts:
        x = pad_l + p['_xr'] * W
        y = pad_t + H - p['score']['total'] / 100 * H
        c = '#0084FF' if p['score']['total'] >= avg_score else '#C9D6E3'
        r = 5 + min(6, (p.get('answer_count') or 0) / 120)
        rows += (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{c}" '
                 f'fill-opacity="0.7" stroke="#fff" stroke-width="1.2"/>')

    # 只标 5 条，且做过重叠规避（同列靠得太近就下移）
    marked = sorted(pts, key=lambda p: p['score']['total'], reverse=True)[:3]
    marked += [p for p in sorted(pts, key=lambda p: p['heat'], reverse=True)[:2] if p not in marked]
    used = []
    for p in marked:
        x = pad_l + p['_xr'] * W
        y = pad_t + H - p['score']['total'] / 100 * H - 11
        while any(abs(x - ux) < 78 and abs(y - uy) < 13 for ux, uy in used):
            y += 13
        used.append((x, y))
        rows += (f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="middle" font-size="9.5" '
                 f'fill="#37474f">{p["title"][:10]}</text>')

    rows += (f'<text x="{pad_l+W/2:.0f}" y="{height-8}" text-anchor="middle" font-size="11" '
             f'fill="#9aa5b1">热度排名（左冷 → 右热）</text>')
    rows += (f'<text x="14" y="{pad_t+8}" font-size="11" fill="#9aa5b1">价值分</text>')
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%">{rows}</svg>'


def clean_excerpt(t, n=130):
    """摘要清洗：去掉原文里的推广链接与多余空白，超长截断。"""
    t = re.sub(r'https?://\S+', '', t or '')
    t = re.sub(r'\s+', ' ', t).strip()
    return (t[:n] + '…') if len(t) > n else t


def card(k, idx):
    sc = k['score']
    lens = ''.join(f'<li>{x}</li>' for x in k['lens'][:3])
    asks = ''.join(f'<li>{x}</li>' for x in k['ask'][:3])
    hits = '、'.join(k['hits'][:4]) if k['hits'] else '—'
    ex = clean_excerpt(k.get('excerpt'))
    # 同一知识域的框架文字是共性的，所以每条必须补一段「它自己在说什么」，
    # 否则一个领域出 6 条时，6 张卡会一字不差，读起来就是模板。
    ex_block = (f'''<div class="iblock iquote">
    <div class="ilabel">这条在说什么（知乎原文摘要）</div>
    <p>{ex}</p>
  </div>''' if ex else '')
    return f'''
<div class="icard">
  <div class="ihead">
    <span class="irank">{idx:02d}</span>
    <a class="ititle" href="{k['url']}" target="_blank">{k['title']}</a>
  </div>
  <div class="imeta">
    <span class="pill p-blue">{k['domain']}</span>
    <span class="pill p-gray">{k['debate']}</span>
    <span class="pill p-score">价值 {sc['total']} 分</span>
    <span class="heat">🔥 {k.get('heat_text') or '热度未公开'} · {k.get('answer_count',0)} 回答</span>
  </div>
  {ex_block}
  <div class="iblock">
    <div class="ilabel">知识内核 · 这类问题该怎么看</div>
    <p>{k['frame']}</p>
  </div>
  <div class="igrid">
    <div>
      <div class="ilabel">要拆这条，得用这些视角</div>
      <ul class="ilist">{lens}</ul>
    </div>
    <div>
      <div class="ilabel">做内容必须回答的问题</div>
      <ul class="ilist">{asks}</ul>
    </div>
  </div>
  <div class="ifoot">
    <b>论证方式：</b>{k['debate_tip']}　<b>命中依据：</b>{hits}
  </div>
</div>'''


# ---------- 领域级洞察 ----------
dom_insight = []
for d, cnt in dom_cnt.most_common():
    items = [k for k in kept if k['domain'] == d]
    top = max(items, key=lambda x: x['score']['total'])
    dm = next((x for x in tx.DOMAINS if x['name'] == d), None)
    dom_insight.append({
        'name': d, 'cnt': cnt, 'avg': dom_avg[d], 'top': top,
        'frame': dm['frame'] if dm else '',
        'gap': dm['ask'][0] if dm else '',
    })

dom_bar = hbar([(f"{d['name']}（{d['cnt']}）", round(d['avg'], 1)) for d in dom_insight],
               '#0084FF', 620, ' 分')
scat_svg = scatter(kept)

# 高热度低价值 / 低热度高价值（这是最有用的两个名单）
heat_rank = sorted([k for k in kept if k.get('heat')], key=lambda x: x['heat'], reverse=True)
overhyped = [k for k in heat_rank if k['score']['total'] < avg_score][:3]
underrated = sorted(kept, key=lambda x: x['score']['total'], reverse=True)
underrated = [k for k in underrated if (k.get('heat') or 0) < med_heat][:3]

# 日报归类
daily_rows = ''
for s in daily:
    d, hits = tx.classify({'title': s['title'], 'excerpt': s.get('hint', '')})
    daily_rows += (f'<tr><td style="text-align:left"><a href="{s["url"]}" target="_blank" '
                   f'style="color:#0084FF;text-decoration:none">{s["title"]}</a></td>'
                   f'<td>{d["name"] if d else "未归类"}</td>'
                   f'<td style="text-align:left;color:#888;font-size:12px">{s.get("hint","")}</td></tr>')

# 剔除清单
drop_rows = ''
for d in dropped:
    drop_rows += (f'<tr><td style="text-align:left;color:#666">{d["title"][:40]}</td>'
                  f'<td><span class="pill p-warn">{d["drop_kind"]}</span></td>'
                  f'<td style="text-align:left;color:#aaa;font-size:12px">{"、".join(d["drop_words"][:3])}</td></tr>')

cards_html = ''.join(card(k, i) for i, k in enumerate(kept[:10], 1))
rest_rows = ''
for k in kept[10:]:
    rest_rows += (f'<tr><td style="text-align:left"><a href="{k["url"]}" target="_blank" '
                  f'style="color:#0084FF;text-decoration:none">{k["title"][:38]}</a></td>'
                  f'<td>{k["domain"]}</td><td>{k["debate"]}</td>'
                  f'<td><b>{k["score"]["total"]}</b></td><td>{k.get("heat_text") or "—"}</td></tr>')

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>知乎有价值议题分析报告 · {TODAY}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f4f6f8;color:#1a1a1a;line-height:1.68}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 18px 70px}}
header{{background:linear-gradient(135deg,#0084FF,#4da3ff);color:#fff;border-radius:16px;padding:32px 30px;margin-bottom:22px}}
header h1{{font-size:26px;margin-bottom:8px;letter-spacing:.5px}}
header p{{opacity:.93;font-size:13.5px}}
.cards{{display:flex;gap:13px;flex-wrap:wrap;margin-bottom:24px}}
.card{{flex:1;min-width:150px;background:#fff;border-radius:14px;padding:17px 18px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
.card .n{{font-size:25px;font-weight:800;color:#0084FF}}
.card .l{{font-size:12.5px;color:#888;margin-top:3px;line-height:1.4}}
section{{background:#fff;border-radius:14px;padding:26px;margin-bottom:18px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
section h2{{font-size:18px;margin-bottom:4px}}
section h2 .num{{color:#0084FF;margin-right:6px}}
section .desc{{font-size:13px;color:#8a94a0;margin-bottom:16px}}
.chart{{overflow-x:auto;margin:6px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:9px 8px;border-bottom:1px solid #f1f3f5;text-align:center}}
th{{background:#fafbfc;color:#666;font-weight:600;font-size:12.5px}}
.note{{background:#f0f7ff;border-left:4px solid #0084FF;border-radius:0 10px 10px 0;padding:14px 18px;margin:14px 0;font-size:13.8px}}
.note b{{color:#0066cc}}
.icard{{border:1px solid #e8edf2;border-radius:12px;padding:18px 20px;margin-bottom:14px;background:#fff}}
.ihead{{display:flex;gap:10px;align-items:flex-start;margin-bottom:9px}}
.irank{{flex:0 0 30px;font-size:15px;font-weight:800;color:#c8d3de;line-height:1.5}}
.ititle{{font-size:15.5px;font-weight:700;color:#111;text-decoration:none;line-height:1.45}}
.ititle:hover{{color:#0084FF}}
.imeta{{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:13px;font-size:12px}}
.pill{{display:inline-block;border-radius:6px;padding:2px 8px;font-size:11.5px;white-space:nowrap}}
.p-blue{{background:#e8f3ff;color:#0066cc}}
.p-gray{{background:#f0f2f5;color:#5c6b7a}}
.p-score{{background:#eafaf0;color:#12864b;font-weight:700}}
.p-warn{{background:#fff2e8;color:#c25b1a}}
.heat{{color:#9aa5b1;font-size:11.5px}}
.iblock{{background:#fafbfc;border-radius:9px;padding:12px 14px;margin-bottom:11px}}
.iblock p{{font-size:13.5px;color:#33414f}}
.iquote{{background:#f7fbff;border-radius:0 9px 9px 0;border-left:3px solid #9dc7ff;padding:11px 15px}}
.iquote p{{font-size:12.8px;color:#5c6b7a;line-height:1.62}}
.ilabel{{font-size:11.5px;font-weight:700;color:#8a94a0;letter-spacing:.4px;margin-bottom:6px;text-transform:uppercase}}
.igrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:11px}}
.ilist{{list-style:none;font-size:13px;color:#41505f}}
.ilist li{{position:relative;padding-left:14px;margin:5px 0;line-height:1.55}}
.ilist li:before{{content:"";position:absolute;left:0;top:9px;width:5px;height:5px;border-radius:50%;background:#9dc7ff}}
.ifoot{{font-size:11.5px;color:#9aa5b1;border-top:1px dashed #eaeff4;padding-top:9px}}
.ifoot b{{color:#5c6b7a}}
.domcard{{border-left:3px solid #0084FF;padding:2px 0 2px 14px;margin-bottom:16px}}
.domcard h4{{font-size:14.5px;margin-bottom:5px}}
.domcard h4 span{{font-weight:400;color:#8a94a0;font-size:12px;margin-left:6px}}
.domcard p{{font-size:13px;color:#4a5a6a}}
.domcard .q{{font-size:12.5px;color:#c25b1a;margin-top:6px}}
.tips li{{margin:9px 0;list-style:none;padding-left:24px;position:relative;font-size:13.8px}}
.tips li:before{{content:"▸";position:absolute;left:4px;color:#0084FF;font-weight:700}}
.mono{{font-family:ui-monospace,Consolas,monospace;background:#f5f7f9;border-radius:5px;padding:1px 5px;font-size:12px}}
@media(max-width:640px){{.igrid{{grid-template-columns:1fr}}}}
</style></head>
<body><div class="wrap">

<header>
  <h1>知乎有价值议题分析报告</h1>
  <p>抓取于 {raw.get('fetched_at', TODAY)} · 热榜 {len(hot)} 条 + 知乎日报 {len(daily)} 条 ·
  已剔除营销/八卦/情绪类 {len(dropped)} 条，保留 {len(kept)} 条可分析议题 ·
  全部来自公开接口，不涉及账号登录</p>
</header>

<div class="cards">
  <div class="card"><div class="n">{len(kept)}</div><div class="l">有价值议题<br>（筛后保留）</div></div>
  <div class="card"><div class="n">{drop_rate:.0f}%</div><div class="l">热搜被剔除比例<br>（营销/八卦/情绪）</div></div>
  <div class="card"><div class="n">{avg_score:.0f}</div><div class="l">保留议题平均价值分<br>（满分 100）</div></div>
  <div class="card"><div class="n">{len(dom_cnt)}</div><div class="l">覆盖知识领域</div></div>
</div>

<section>
  <h2><span class="num">1</span>先剔除：这 {len(dropped) + len(low_value)} 条为什么不算「有价值」</h2>
  <div class="desc">热榜是流量榜，不是知识榜。剔除分两道：<b>硬剔除</b>（规则命中营销/八卦/情绪/琐事）、<b>软剔除</b>（价值分不足 30，虽不低俗但拆不出可验证的东西）。每条都标了依据，可逐条复核——如果你觉得某条被误杀，说明规则该调。</div>

  <div style="font-size:12.5px;font-weight:700;color:#8a94a0;margin:14px 0 6px;letter-spacing:.4px">硬剔除 · {len(dropped)} 条</div>
  <table>
    <tr><th style="text-align:left">被剔除条目</th><th style="width:110px">判定</th><th style="text-align:left;width:34%">触发词</th></tr>
    {drop_rows or '<tr><td colspan="3" style="color:#999;padding:18px">本期无硬剔除项</td></tr>'}
  </table>

  <div style="font-size:12.5px;font-weight:700;color:#8a94a0;margin:16px 0 6px;letter-spacing:.4px">软剔除 · {len(low_value)} 条</div>
  <table>
    <tr><th style="text-align:left">被剔除条目</th><th style="width:110px">判定</th><th style="text-align:left;width:34%">原因</th></tr>
    {low_rows or '<tr><td colspan="3" style="color:#999;padding:18px">本期无软剔除项</td></tr>'}
  </table>

  <div class="note">💡 <b>判定标准（写在前面，避免黑箱）：</b>
    营销导购 = 指向购买行为；娱乐八卦 = 讨论对象是明星私生活或影视剧情；
    情感树洞 = 无可验证事实、只讨论个人感受；生活琐事 = 经验性日常，无知识增量。
    四类共同点：<b>看完之后你无法获得任何可迁移的判断力</b>。
    软剔除则是「有讨论、但讨论不出硬东西」——留着会稀释报告价值。</div>
</section>

<section>
  <h2><span class="num">2</span>热度 ≠ 价值：一张图看清</h2>
  <div class="desc">横轴是<b>热度排名</b>（左冷右热），纵轴是<b>价值分</b>，点越大表示回答越多（争论越激烈）。两条虚线是中位分割线，把议题分成四个象限。</div>
  <div class="chart">{scat_svg}</div>
  <div class="note">💡 <b>四个象限怎么用：</b>
    <b>右上（又热又有料）</b>——当天就该做，有流量也有信息增量；
    <b>右下（热但空）</b>——传播广但拆开是空的，跟风只会消耗信任；
    <b>左上（冷门但有料）</b>——<b>这才是内容创作者的套利空间</b>，竞争小、信息增量大；
    <b>左下（冷且空）</b>——直接跳过。
    {('本期典型的「热但空」：' + '；'.join(k['title'][:20] + '…' for k in overhyped)) if overhyped else ''}
  </div>
</section>

<section>
  <h2><span class="num">3</span>价值议题分布在哪些领域</h2>
  <div class="desc">按每个领域的平均价值分排序（括号内为该领域议题数）。分数越高，说明该领域的议题越「可拆、可验证、可延展」。</div>
  <div class="chart">{dom_bar}</div>
  <div class="note">💡 <b>判断：</b>数量多 ≠ 值得做。某个领域条数多但均分低，说明它只是当天热闹；
    条数少但均分高的领域，往往是<b>当天的真问题被埋没在热搜尾部</b>。</div>
</section>

<section>
  <h2><span class="num">4</span>逐条拆解：本期最值得做的 {min(10,len(kept))} 条</h2>
  <div class="desc">每条给出「知识内核 → 分析视角 → 论证方式 → 必答问题」。这不是摘要，是拆解路径：照着这几步走，内容才有信息增量。</div>
  {cards_html or '<div style="color:#999;padding:20px">本期无可拆解议题</div>'}
</section>
'''

if rest_rows:
    html += f'''
<section>
  <h2><span class="num">5</span>其余有价值议题（简表）</h2>
  <div class="desc">价值分达标但未进前 {min(10,len(kept))}，可作为备选选题池。</div>
  <table>
    <tr><th style="text-align:left">议题</th><th style="width:130px">领域</th><th style="width:90px">争议类型</th><th style="width:70px">价值分</th><th style="width:100px">热度</th></tr>
    {rest_rows}
  </table>
</section>'''

html += f'''
<section>
  <h2><span class="num">{6 if rest_rows else 5}</span>领域级洞察：每个领域本期在问什么</h2>
  <div class="desc">把同一领域的议题放在一起看，会发现它们共享同一个知识缺口。这才是「热点背后的东西」。</div>
  {''.join(f"""<div class="domcard">
    <h4>{d['name']}<span>本期 {d['cnt']} 条 · 均分 {d['avg']:.0f} · 代表议题「{d['top']['title'][:26]}」</span></h4>
    <p>{d['frame']}</p>
    <div class="q">⚑ 该领域本期最该回答的问题：{d['gap']}</div>
  </div>""" for d in dom_insight) or '<div style="color:#999">无</div>'}
</section>

<section>
  <h2><span class="num">{7 if rest_rows else 6}</span>知乎日报补充（编辑精选，天然低营销）</h2>
  <div class="desc">热榜是算法排序，日报是人工筛选。两者对照可以看出「大众关心什么」和「编辑认为什么值得读」的差。</div>
  <table>
    <tr><th style="text-align:left">标题</th><th style="width:130px">归类</th><th style="text-align:left;width:30%">作者/阅读</th></tr>
    {daily_rows or '<tr><td colspan="3" style="color:#999;padding:20px">本期日报接口未返回数据</td></tr>'}
  </table>
  <div class="note">💡 <b>用法：</b>日报里命中「科学与工程 / 医学与健康 / 历史与人文」的条目，通常是可以长期做、不怕过期的选题；
    热榜里的高价值条目则是「现在做就有时效红利」的选题。<b>两类交替发，账号既有流量又有厚度。</b></div>
</section>

<section>
  <h2><span class="num">{8 if rest_rows else 7}</span>本期行动清单</h2>
  <ul class="tips">
    <li><b>今天就能做：</b>「{kept[0]['title'][:26] if kept else '—'}」——它的价值分 {kept[0]['score']['total'] if kept else 0}，属于{kept[0]['debate'] if kept else '—'}型，
        按「机制 → 证据 → 边界」三段写，别站队。</li>
    {''.join(f'<li><b>值得埋伏：</b>「{k["title"][:26]}」热度只有 {k.get("heat_text") or "偏低"}，但价值分 {k["score"]["total"]}——'
             f'热度低意味着竞争小，信息增量大，适合做深度而非快讯。</li>' for k in underrated[:2])}
    <li><b>不要碰：</b>{'、'.join(d['drop_kind'] for d in dropped[:3]) if dropped else '本期无'} 类条目虽然热度高，但拆开后没有可验证的事实，
        做这类内容短期有播放、长期掉粉。</li>
    <li><b>建素材库：</b>把本期 {len(dom_cnt)} 个领域的「必答问题」抄进笔记，下次遇到同类热点直接套框架，
        不用从零想角度。</li>
  </ul>
</section>

<section>
  <h2>方法与局限（必读）</h2>
  <div style="font-size:13px;color:#5c6b7a">
    <p style="margin-bottom:8px"><b>数据口径：</b>热榜来自 <span class="mono">api.zhihu.com/topstory/hot-list</span>，固定 30 条，
    是平台当下快照；日报来自 <span class="mono">news-at.zhihu.com/api/4/news/latest</span>，人工编辑筛选。两者都是公开接口，不含任何账号数据。</p>
    <p style="margin-bottom:8px"><b>分类方法：</b>关键词命中式归类（12 个知识域 / 4 类排除规则），<b>属于启发式，不是语义理解</b>。
    长句、反讽、隐喻容易误判，报告内已列出命中依据供复核。真正的语义级判断需要人工过一遍。</p>
    <p style="margin-bottom:8px"><b>价值分含义：</b>100 分制，由知识密度（40）+ 讨论空间（30）+ 时效性（20）+ 可延展性（10）相加。
    它衡量的是「这条议题能拆出多少可验证的东西」，<b>不代表内容一定火</b>。热度是平台给的，价值是自己判断的，两者不是一回事。</p>
    <p><b>不做什么：</b>不做立场表态，不评价具体人物，不预测政治走向。本报告只提供分析路径。</p>
  </div>
</section>

<div style="text-align:center;color:#b8c2cc;font-size:12px;margin-top:28px">
  由 WorkBuddy 基于知乎公开接口生成 · 抓取时点 {raw.get('fetched_at', TODAY)} · 分类为机器启发式判定，请结合人工判断
</div>

</div></body></html>'''

outdir = os.path.join(ROOT, 'reports', BATCH)
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, f'知乎有价值议题分析报告_{TODAY}.html')
_i = 2
while os.path.exists(out):
    out = os.path.join(outdir, f'知乎有价值议题分析报告_{TODAY}_{_i}.html')
    _i += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'生成成功: {out}')
print(f'  热榜 {len(hot)} 条 → 保留 {len(kept)} 条 / 剔除 {len(dropped)} 条')
print(f'  领域分布: ' + ' / '.join(f'{d}({c})' for d, c in dom_cnt.most_common()))
print(f'  最高价值: [{kept[0]["score"]["total"]}分] {kept[0]["title"][:34]}' if kept else '  无保留议题')
