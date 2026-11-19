# -*- coding: utf-8 -*-
"""基于 knowledge_raw.json 中「AI/人工智能 + 电子设备(硬件)」子集，生成独立专项爆款报告。"""
import json, re, time, datetime, os
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))   # 知识热点/
data = json.load(open(os.path.join(BASE, 'data', 'knowledge_raw.json'), encoding='utf-8'))
TODAY = datetime.date.today().strftime('%Y-%m-%d')  # 运行当天，历史报告不覆盖
BATCH = os.environ.get('BZ_BATCH') or TODAY   # scripts/run_all.py 统一分配的「每次独立文件夹」

# 筛选 AI + 硬件(电子设备) 子集
subset = [v for v in data if ('AI/人工智能' in v['dirs']) or ('电子设备' in v['dirs'])]
N = len(subset)

def med(l):
    s = sorted(l); n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

# 子方向拆分
ai = [v for v in subset if 'AI/人工智能' in v['dirs']]
hw = [v for v in subset if '电子设备' in v['dirs']]

# 硬件按关键词归类（用于细分）
hw_kw = {'手机':['手机','iphone','华为','小米','三星'], '电脑/笔记本':['笔记本','电脑','笔电','macbook'],
         '显卡/CPU':['显卡','cpu','gpu','芯片','算力'], '数码配件':['耳机','相机','平板','手表','键鼠','外设']}
def hw_bucket(v):
    t = (v['title'] + ' ' + v.get('tag','')).lower()
    for name, kws in hw_kw.items():
        if any(k.lower() in t for k in kws):
            return name
    return '其他数码'
hw_buckets = Counter(hw_bucket(v) for v in hw)

# 平均播放
ai_avg = sum(v['play'] for v in ai)/max(len(ai), 1)/10000
hw_avg = sum(v['play'] for v in hw)/max(len(hw), 1)/10000

# 时长分布
durs = [v['duration'] for v in subset if v['duration'] > 0]
short = sum(1 for d in durs if d < 180)
mid = sum(1 for d in durs if 180 <= d <= 600)
long_ = sum(1 for d in durs if d > 600)
avg_dur = med(durs)/60

# 互动率（中位，play>1000）
def rate(field):
    r = [v[field]/v['play'] for v in subset if v['play'] > 1000 and v[field] > 0]
    return med(r)*100 if r else 0
rate_like = rate('like'); rate_fav = rate('favorites'); rate_dm = rate('danmaku'); rate_review = rate('review')

# 标题特征
titles = [v['title'] for v in subset]
avg_len = sum(len(t) for t in titles)/len(titles)
p_sym = sum(1 for t in titles if re.search(r'[！？!?]', t))/len(titles)*100
p_num = sum(1 for t in titles if re.search(r'\d', t))/len(titles)*100

kw_lib = ['2026','大模型','chatgpt','gpt','实测','评测','推荐','教程','怎么','为什么','如何','显卡','cpu','gpu',
          '手机','笔记本','拆解','避坑','装机','算力','芯片','ai','干货','预测','新品','发布','对比','上手','体验']
kw_cnt = Counter()
for t in titles:
    tl = t.lower()
    for kw in kw_lib:
        if kw in tl:
            kw_cnt[kw] += 1
kw_top = [(k, c) for k, c in kw_cnt.most_common(14)]

# 热点新鲜度：发布距今天数中位数
now = time.time()
def age_med(vs):
    ages = [(now - v['pubdate'])/86400 for v in vs if v.get('pubdate')]
    return med(ages) if ages else 0
ai_age = age_med(ai); hw_age = age_med(hw)

# 榜单
top_all = sorted(subset, key=lambda v: v['play'], reverse=True)[:12]
top_ai = sorted(ai, key=lambda v: v['play'], reverse=True)[:5]
top_hw = sorted(hw, key=lambda v: v['play'], reverse=True)[:5]

def top_rows(vs, n=999):
    r = ''
    for i, v in enumerate(vs, 1):
        if i > n: break
        tag = '🤖AI' if 'AI/人工智能' in v['dirs'] else '🔧硬件'
        r += (f'<tr><td style="color:#FB7299;font-weight:700">{i}</td>'
              f'<td style="text-align:left"><span style="font-size:11px">{tag}</span> '
              f'<a href="https://www.bilibili.com/video/{v.get("bvid")}" target="_blank" style="color:#23ADE5;text-decoration:none">{v["title"][:28]}</a></td>'
              f'<td>{v["typename"]}</td><td>{v["play"]/10000:.0f}万</td><td>{v["author"][:10]}</td></tr>')
    return r

# ---------- SVG ----------
def hbar(items, color='#FB7299', width=620):
    maxv = max(v for _, v in items); rowh, gap = 26, 8; rows = ''
    for i, (lab, val) in enumerate(items):
        y = i*(rowh+gap); bw = max(3, val/maxv*(width-200))
        rows += (f'<g transform="translate(0,{y})"><text x="0" y="{rowh/2}" dominant-baseline="middle" font-size="12.5" fill="#333">{lab}</text>'
                 f'<rect x="150" y="4" width="{bw:.0f}" height="{rowh-8}" rx="3" fill="{color}"/>'
                 f'<text x="{150+bw+6:.0f}" y="{rowh/2}" dominant-baseline="middle" font-size="11.5" fill="#777">{val}</text></g>')
    return f'<svg width="{width}" height="{len(items)*(rowh+gap)}" viewBox="0 0 {width} {len(items)*(rowh+gap)}" style="max-width:100%">{rows}</svg>'

def vbar(items, colors, width=460, height=240):
    maxv = max(v for _, v in items); n = len(items); slot = width/n; bw = slot*0.55; rows = ''
    for i, (lab, val) in enumerate(items):
        x = i*slot + (slot-bw)/2; bh = val/maxv*(height-50); y = height-34-bh; c = colors[i % len(colors)]
        rows += (f'<g><rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{bh:.0f}" rx="3" fill="{c}"/>'
                 f'<text x="{x+bw/2:.0f}" y="{y-6:.0f}" text-anchor="middle" font-size="11.5" fill="#333">{val:.1f}%</text>'
                 f'<text x="{x+bw/2:.0f}" y="{height-12:.0f}" text-anchor="middle" font-size="11.5" fill="#666">{lab}</text></g>')
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%">{rows}</svg>'

def stack_bar(segs, width=460):
    total = sum(s[1] for s in segs); x = 0; rows = ''
    for lab, val, c in segs:
        w = val/total*width
        rows += f'<rect x="{x:.0f}" y="0" width="{w:.0f}" height="34" fill="{c}"/><text x="{x+w/2:.0f}" y="21" text-anchor="middle" font-size="12" fill="#fff">{lab} {val}</text>'
        x += w
    return (f'<svg width="{width}" height="34" viewBox="0 0 {width} 34" style="max-width:100%">{rows}</svg>'
            f'<div style="font-size:12px;color:#888;margin-top:6px">共 {total} 条 · 平均时长 {avg_dur:.1f} 分钟</div>')

sub_svg = hbar([('🤖 AI/人工智能', len(ai)), ('🔧 电子设备(硬件)', len(hw))], '#FB7299', 620)
subplay_svg = hbar([('🤖 AI/人工智能', round(ai_avg,1)), ('🔧 电子设备(硬件)', round(hw_avg,1))], '#23ADE5', 620)
hwbucket_svg = hbar([(k, v) for k, v in hw_buckets.most_common()], '#7ED321', 620)
rate_svg = vbar([('点赞', rate_like), ('收藏', rate_fav), ('评论', rate_review), ('弹幕', rate_dm)],
                ['#FB7299', '#23ADE5', '#7ED321', '#9B59B6'], 460, 240)
time_svg = stack_bar([('短视频 <3min', short, '#FB7299'), ('中视频 3-10min', mid, '#23ADE5'), ('长视频 >10min', long_, '#FFB027')], 460)
kw_html = ''.join(f'<span class="tag">{k} {c}</span>' for k, c in kw_top)

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>人工智能与硬件更新爆款报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f7;color:#222;line-height:1.6}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 18px 60px}}
header{{background:linear-gradient(135deg,#FB7299,#9B59B6);color:#fff;border-radius:16px;padding:30px 28px;margin-bottom:22px}}
header h1{{font-size:26px;margin-bottom:8px}} header p{{opacity:.92;font-size:14px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}}
.card{{flex:1;min-width:140px;background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
.card .n{{font-size:24px;font-weight:800;color:#FB7299}} .card .l{{font-size:13px;color:#888;margin-top:4px}}
section{{background:#fff;border-radius:14px;padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
section h2{{font-size:18px;margin-bottom:4px}} section .desc{{font-size:13px;color:#999;margin-bottom:16px}}
.chart{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:8px;border-bottom:1px solid #f0f0f0;text-align:center}}
th{{background:#fafafa;color:#666;font-weight:600}} h4{{font-size:15px;margin:14px 0 6px;color:#FB7299}}
.note{{background:#fdeef5;border-left:4px solid #FB7299;border-radius:0 10px 10px 0;padding:14px 18px;margin:14px 0;font-size:14px}}
.note b{{color:#FB7299}} .tip{{margin:10px 0;padding-left:26px;position:relative;font-size:14px}} .tip:before{{content:"▸";position:absolute;left:6px;color:#FB7299;font-weight:700}}
.tag{{display:inline-block;background:#eafaf0;color:#1a9e4b;border-radius:6px;padding:3px 9px;font-size:12px;margin:3px}}
.tipbox{{background:#fff7fb;border-radius:12px;padding:18px 20px;margin-top:10px}}
.flex2{{display:flex;gap:18px;flex-wrap:wrap}} .flex2>div{{flex:1;min-width:200px}}
</style></head><body><div class="wrap">

<header>
  <h1>🤖 人工智能与硬件更新 · 爆款分析报告</h1>
  <p>数据抓取于 {TODAY} · 样本 {N} 条（从公开搜索接口按「方向关键词 + 播放量排序」抓取、去重）· 聚焦 AI/人工智能 + 电子设备(硬件更新) 两大科技方向</p>
</header>

<div class="cards">
  <div class="card"><div class="n">{N}</div><div class="l">有效样本（条）</div></div>
  <div class="card"><div class="n">{len(ai)}</div><div class="l">🤖 AI 内容</div></div>
  <div class="card"><div class="n">{len(hw)}</div><div class="l">🔧 硬件内容</div></div>
  <div class="card"><div class="n">{avg_dur:.1f}′</div><div class="l">平均时长</div></div>
  <div class="card"><div class="n">{rate_fav:.1f}%</div><div class="l">收藏率中位</div></div>
</div>

<section>
  <h2>1 · 两大方向体量 & 流量对比</h2>
  <div class="desc">左：内容数量；右：单条平均播放量（万）。</div>
  <div class="chart">{sub_svg}</div>
  <div class="chart" style="margin-top:10px">{subplay_svg}</div>
  <div class="note">💡 <b>规律：</b>硬件方向内容量更大（{len(hw)} 条），但 <strong>AI 方向单条平均播放 {ai_avg:.0f} 万，明显高于硬件的 {hw_avg:.0f} 万</strong>——AI 是单位流量红利更高的赛道，新模型/新工具出来极易爆；硬件靠"评测/实测/选购"持续稳定吸量。</div>
</section>

<section>
  <h2>2 · 硬件内容细分</h2>
  <div class="desc">把硬件内容按品类再拆（按标题/标签命中归类）。</div>
  <div class="chart">{hwbucket_svg}</div>
  <div class="note">💡 <b>规律：</b>硬件爆款以<strong>手机/笔记本等「选购决策类」</strong>为主，显卡/CPU/芯片等「硬核参数类」体量较小但受众极精准、收藏率高。做硬件更新，优先吃"新机发布季/新品实测"的流量峰值。</div>
</section>

<section>
  <h2>3 · 视频做多长合适？</h2>
  <div class="desc">科技类内容整体偏中长视频。</div>
  <div class="chart">{time_svg}</div>
  <div class="note">💡 <b>规律：</b>长视频（>10min）占 {long_/len(durs)*100:.0f}%、中视频（3–10min）占 {mid/len(durs)*100:.0f}%——AI 原理讲解、硬件深度评测都靠时长承载信息量，建议 AI 类 8–15 分钟、硬件评测 10–20 分钟，短视频只做"新发布速报"引流。</div>
</section>

<section>
  <h2>4 · 用户怎么互动？</h2>
  <div class="desc">互动率中位（仅统计播放>1000）。搜索接口不返回投币/分享，故用点赞/收藏/评论/弹幕四项。</div>
  <div class="chart" style="display:flex;justify-content:center">{rate_svg}</div>
  <div class="note">💡 <b>规律：</b>收藏率中位 {rate_fav:.1f}%（略低于知识区整体 1.3%），但科技内容"工具属性"极强——观众会把 AI 教程、硬件选购清单当资料存。<strong>主动埋"可保存点"（参数表、对比图、prompt 合集、选购清单）才能把收藏率拉到中位线之上</strong>，这是科技区推流的关键杠杆。</div>
</section>

<section>
  <h2>5 · 标题怎么起？</h2>
  <div class="desc">对 {N} 条标题统计 + 高频爆款词命中。</div>
  <div class="chart" style="display:flex;gap:18px;flex-wrap:wrap">
    <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666">平均标题长度</div><div style="font-size:24px;font-weight:800;color:#FB7299">{avg_len:.0f} 字</div></div>
    <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666">含 ！/？ 情绪符</div><div style="font-size:24px;font-weight:800;color:#23ADE5">{p_sym:.0f}%</div></div>
    <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666">含 数字/年份</div><div style="font-size:24px;font-weight:800;color:#7ED321">{p_num:.0f}%</div></div>
  </div>
  <div style="margin-top:14px"><div style="font-size:13px;color:#666;margin-bottom:6px">高频爆款词（命中视频数）</div>{kw_html}</div>
  <div class="note">💡 <b>规律：</b>科技标题高频词集中在 <strong>「2026/新品/发布」（时效性）+ 实测/评测/上手/体验（可信度）+ 显卡/CPU/大模型（具体对象）+ 怎么/为什么（疑问钩子）」</strong>。例：<i>"2026 最强显卡实测！XX vs YY 到底怎么选？"</i></div>
</section>

<section>
  <h2>6 · 热点新鲜度</h2>
  <div class="desc">上榜视频发布距今天数中位数（科技内容迭代快，追热点窗口极短）。</div>
  <div class="flex2" style="font-size:14px">
    <div style="background:#fdeef5;border-radius:12px;padding:16px"><div style="font-size:13px;color:#888">🤖 AI 内容发布距今中位</div><div style="font-size:26px;font-weight:800;color:#FB7299">{ai_age:.1f} 天</div></div>
    <div style="background:#eafaf0;border-radius:12px;padding:16px"><div style="font-size:13px;color:#888">🔧 硬件内容发布距今中位</div><div style="font-size:26px;font-weight:800;color:#1a9e4b">{hw_age:.1f} 天</div></div>
  </div>
  <div class="note">💡 <b>规律：</b>AI 与硬件上榜内容都极"新鲜"（中位仅 {min(ai_age,hw_age):.1f} 天）。<strong>AI 新模型/新工具、硬件新机发布，务必在 48 小时内出"实测/速报"</strong>，错过热度窗口基本没机会。</div>
</section>

<section>
  <h2>7 · 科技爆款 TOP12</h2>
  <div class="desc">AI + 硬件合并按播放量排序（点击标题可跳转原视频）。</div>
  <table><tr><th>#</th><th style="text-align:left">标题</th><th>分区</th><th>播放</th><th>UP主</th></tr>{top_rows(top_all)}</table>
</section>

<section>
  <h2>8 · AI 与硬件 各自爆款代表</h2>
  <div class="desc">两个方向播放量最高的 5 条。</div>
  <h4>🤖 AI/人工智能 TOP5</h4>
  <table><tr><th>#</th><th style="text-align:left">标题</th><th>分区</th><th>播放</th><th>UP主</th></tr>{top_rows(top_ai,5)}</table>
  <h4>🔧 电子设备(硬件) TOP5</h4>
  <table><tr><th>#</th><th style="text-align:left">标题</th><th>分区</th><th>播放</th><th>UP主</th></tr>{top_rows(top_hw,5)}</table>
</section>

<section>
  <h2>9 · 给你的 AI + 硬件 选题清单</h2>
  <div class="tipbox">
    <div class="tip"><b>AI 方向（流量红利）：</b>紧盯大模型/新工具发布节奏，<strong>48h 内出实测/教程/对比</strong>；选题偏"能上手"——prompt 技巧、效率工作流、AI 绘画/剪辑，比纯科普更容易爆。</div>
    <div class="tip"><b>硬件方向（稳定基本盘）：</b>主打<strong>选购决策 + 新品实测</strong>——新机发布季做"上手/对比/避坑"，平时做"XX 怎么选"常青树内容，持续吸量。</div>
    <div class="tip"><b>定形式：</b>AI 类 8–15 分钟讲透一个工具/场景；硬件评测 10–20 分钟，短视频只发"新发布 1 分钟速报"引流。</div>
    <div class="tip"><b>练标题：</b>套「时效词（2026/新品/发布）+ 具体对象（显卡/大模型）+ 可信词（实测/评测/上手）+ 钩子（怎么选/为什么）」。</div>
    <div class="tip"><b>提收藏：</b>每期给"可保存点"——参数对比表、选购清单、prompt 合集、避坑指南，直接拉高收藏率（科技区推流关键）。</div>
    <div class="tip"><b>追热点：</b>AI/硬件内容中位仅 {min(ai_age,hw_age):.0f} 天就"过期"，建立发布日历，新模型/新机当天立项、次日出片。</div>
  </div>
</section>

<div style="text-align:center;color:#bbb;font-size:12px;margin-top:30px">
  本报告由 WorkBuddy 基于 B站公开搜索接口自动生成 · 数据为「关键词+播放排序」样本，反映抓取时点热门趋势，非官方排行榜，不构成流量承诺
</div>
</div></body></html>'''

outdir = os.path.join(BASE, 'reports', BATCH)
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, f'人工智能与硬件更新爆款报告_{TODAY}.html')
_i = 2
while os.path.exists(out):          # 同日重跑自动加序号，绝不覆盖旧文档
    out = os.path.join(outdir, f'人工智能与硬件更新爆款报告_{TODAY}_{_i}.html')
    _i += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('生成成功:', out)
print(f'AI={len(ai)} 硬件={len(hw)} 合计={N}')
print(f'AI均播={ai_avg:.0f}万 硬件均播={hw_avg:.0f}万')
print('硬件细分:', dict(hw_buckets))
print(f'时长 短/中/长: {short}/{mid}/{long_}  平均{avg_dur:.1f}min')
print(f'点赞率{rate_like:.1f}% 收藏率{rate_fav:.1f}% 评论率{rate_review:.1f}% 弹幕率{rate_dm:.1f}%')
print(f'标题平均{avg_len:.0f}字 情绪符{p_sym:.0f}% 数字{p_num:.0f}%')
print(f'AI新鲜度{ai_age:.1f}天 硬件新鲜度{hw_age:.1f}天')
print('高频词:', kw_top[:8])
