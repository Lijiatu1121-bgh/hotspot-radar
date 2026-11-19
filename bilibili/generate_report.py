# -*- coding: utf-8 -*-
import json, re, datetime, os
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))   # 总热点/
DATA = os.path.join(ROOT, 'data')
TODAY = datetime.date.today().strftime('%Y-%m-%d')  # 运行当天，历史报告不覆盖
BATCH = os.environ.get('BZ_BATCH') or TODAY   # scripts/run_all.py 统一分配的「每次独立文件夹」
NOW_DT = datetime.datetime.now()
items = json.load(open(os.path.join(DATA, 'popular.json'), encoding='utf-8'))

# ---------- 工具 ----------
def dur2sec(d):
    if isinstance(d, int):
        return d
    p = [int(x) for x in str(d).split(':')]
    if len(p) == 3:
        return p[0]*3600 + p[1]*60 + p[2]
    if len(p) == 2:
        return p[0]*60 + p[1]
    return p[0]

def med(l):
    s = sorted(l); n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

# ---------- 统计 ----------
tn = Counter(v.get('tname', '?') for v in items)
top_cat = tn.most_common(15)

durs = [dur2sec(v.get('duration', 0)) for v in items]
short = sum(1 for d in durs if d < 180)
mid = sum(1 for d in durs if 180 <= d <= 600)
long_ = sum(1 for d in durs if d > 600)
avg_dur = sum(durs)/len(durs)/60

rates = {}
for k, f in [('点赞', 'like'), ('投币', 'coin'), ('收藏', 'favorite'), ('分享', 'share'), ('弹幕', 'danmaku')]:
    r = [v['stat'].get(f, 0)/max(v['stat'].get('view', 1), 1) for v in items if v['stat'].get('view', 0) > 1000]
    rates[k] = med(r)*100

titles = [v.get('title', '') for v in items]
avg_len = sum(len(t) for t in titles)/len(titles)
p_sym = sum(1 for t in titles if re.search(r'[！？!?]', t))/len(titles)*100
p_num = sum(1 for t in titles if re.search(r'\d', t))/len(titles)*100
p_br  = sum(1 for t in titles if re.search(r'[【】《》"]', t))/len(titles)*100

top = sorted(items, key=lambda v: v['stat'].get('view', 0), reverse=True)[:10]
now = NOW_DT.timestamp()
ages = [(now - v.get('pubdate', now))/86400 for v in items if v.get('pubdate')]
age_med = med(ages)

# ---------- SVG 图表 ----------
def hbar(data, color='#FB7299', width=600):
    maxv = max(v for _, v in data)
    rowh, gap = 24, 8
    rows = ''
    for i, (lab, val) in enumerate(data):
        y = i*(rowh+gap)
        bw = max(3, val/maxv*(width-180))
        rows += (f'<g transform="translate(0,{y})">'
                 f'<text x="0" y="{rowh/2}" dominant-baseline="middle" font-size="12.5" fill="#333">{lab}</text>'
                 f'<rect x="130" y="3" width="{bw:.0f}" height="{rowh-6}" rx="3" fill="{color}"/>'
                 f'<text x="{130+bw+6:.0f}" y="{rowh/2}" dominant-baseline="middle" font-size="11.5" fill="#777">{val}</text>'
                 f'</g>')
    h = len(data)*(rowh+gap)
    return f'<svg width="{width}" height="{h}" viewBox="0 0 {width} {h}" style="max-width:100%">{rows}</svg>'

def vbar(data, colors, width=460, height=240):
    maxv = max(v for _, v in data)
    n = len(data)
    slot = width/n
    bw = slot*0.55
    rows = ''
    for i, (lab, val) in enumerate(data):
        x = i*slot + (slot-bw)/2
        bh = val/maxv*(height-50)
        y = height-34-bh
        c = colors[i % len(colors)]
        rows += (f'<g><rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{bh:.0f}" rx="3" fill="{c}"/>'
                 f'<text x="{x+bw/2:.0f}" y="{y-6:.0f}" text-anchor="middle" font-size="11.5" fill="#333">{val:.1f}%</text>'
                 f'<text x="{x+bw/2:.0f}" y="{height-12:.0f}" text-anchor="middle" font-size="11.5" fill="#666">{lab}</text></g>')
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%">{rows}</svg>'

cat_svg = hbar(top_cat, '#FB7299', 620)
rate_svg = vbar([(k, rates[k]) for k in ['点赞', '收藏', '投币', '分享', '弹幕']],
                ['#FB7299', '#23ADE5', '#FFB027', '#7ED321', '#9B59B6'], 460, 240)

# 时长分布堆叠条
def stack_bar(segs, width=460):
    total = sum(s[1] for s in segs)
    x = 0
    rows = ''
    for lab, val, c in segs:
        w = val/total*width
        rows += f'<rect x="{x:.0f}" y="0" width="{w:.0f}" height="34" fill="{c}"/>'
        rows += f'<text x="{x+w/2:.0f}" y="21" text-anchor="middle" font-size="12" fill="#fff">{lab} {val}</text>'
        x += w
    return (f'<svg width="{width}" height="34" viewBox="0 0 {width} 34" style="max-width:100%">{rows}</svg>'
            f'<div style="font-size:12px;color:#888;margin-top:6px">共 {total} 条 · 平均时长 {avg_dur:.1f} 分钟</div>')

time_svg = stack_bar([('短视频 <3min', short, '#FB7299'),
                      ('中视频 3-10min', mid, '#23ADE5'),
                      ('长视频 >10min', long_, '#FFB027')], 460)

# Top10 表格
rows = ''
for i, v in enumerate(top, 1):
    st = v['stat']
    view = st.get('view', 0)/10000
    like = st.get('like', 0)/10000
    rows += (f'<tr><td style="color:#FB7299;font-weight:700">{i}</td>'
             f'<td style="text-align:left"><a href="https://www.bilibili.com/video/av{st.get("aid")}" target="_blank" style="color:#23ADE5;text-decoration:none">{v.get("title","")[:32]}</a></td>'
             f'<td>{v.get("tname","")}</td>'
             f'<td>{view:.0f}万</td><td>{like:.1f}万</td>'
             f'<td>{v.get("owner",{}).get("name","")[:10]}</td></tr>')

# ---------- 组装 HTML ----------
html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>B站爆款内容分析报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f7;color:#222;line-height:1.6}}
.wrap{{max-width:920px;margin:0 auto;padding:28px 18px 60px}}
header{{background:linear-gradient(135deg,#FB7299,#ff9bbb);color:#fff;border-radius:16px;padding:30px 28px;margin-bottom:22px}}
header h1{{font-size:26px;margin-bottom:8px}}
header p{{opacity:.92;font-size:14px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}}
.card{{flex:1;min-width:160px;background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
.card .n{{font-size:26px;font-weight:800;color:#FB7299}}
.card .l{{font-size:13px;color:#888;margin-top:4px}}
section{{background:#fff;border-radius:14px;padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
section h2{{font-size:18px;margin-bottom:4px;color:#222}}
section .desc{{font-size:13px;color:#999;margin-bottom:16px}}
.chart{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:9px 8px;border-bottom:1px solid #f0f0f0;text-align:center}}
th{{background:#fafafa;color:#666;font-weight:600}}
.note{{background:#fff7fb;border-left:4px solid #FB7299;border-radius:0 10px 10px 0;padding:14px 18px;margin:14px 0;font-size:14px}}
.note b{{color:#FB7299}}
.tips li{{margin:10px 0;list-style:none;padding-left:26px;position:relative}}
.tips li:before{{content:"▸";position:absolute;left:6px;color:#23ADE5;font-weight:700}}
.tag{{display:inline-block;background:#fdeef4;color:#FB7299;border-radius:6px;padding:2px 8px;font-size:12px;margin:3px}}
</style></head>
<body><div class="wrap">

<header>
  <h1>📊 B站爆款内容分析报告</h1>
  <p>数据抓取于 {TODAY} {NOW_DT.strftime('%H:%M')} · 样本 = {len(items)} 条全站热门 + 全站/游戏/科技/动画/影视 分区排行榜 · 全部来自公开接口，无需登录</p>
</header>

<div class="cards">
  <div class="card"><div class="n">{len(items)}</div><div class="l">分析样本（条）</div></div>
  <div class="card"><div class="n">{avg_dur:.1f}′</div><div class="l">平均视频时长</div></div>
  <div class="card"><div class="n">{rates["点赞"]:.1f}%</div><div class="l">点赞率中位（每百播放）</div></div>
  <div class="card"><div class="n">{age_med:.1f}天</div><div class="l">上榜视频发布距今中位（热点新鲜度）</div></div>
</div>

<section>
  <h2>1 · 哪些内容最容易爆？</h2>
  <div class="desc">下图按二级分区统计热门榜视频数量。游戏类（电竞/单机/手机/网游）合计占比最高，"日常/生活"是最大单一类目。</div>
  <div class="chart">{cat_svg}</div>
  <div class="note">💡 <b>规律：</b>热门榜是"游戏 + 日常/生活 + 搞笑/影视二创"三足鼎立。游戏靠赛事与二次元PV，生活靠共鸣与治愈，搞笑靠情绪释放。想入局，优先从这三类里找一个你能持续产出的切口。</div>
</section>

<section>
  <h2>2 · 视频做多长合适？</h2>
  <div class="desc">时长分布相当均衡，并非越短越好——长视频（>10min）也占了三分之一。</div>
  <div class="chart">{time_svg}</div>
  <div class="note">💡 <b>规律：</b>短视频（<3min）负责"刷到就点"，占 {short/len(durs)*100:.0f}%；但长视频（>10min）仍有 {long_/len(durs)*100:.0f}%，说明<strong>深度/故事型内容照样能爆</strong>。建议新手用短视频试水、用中长视频立人设，两条腿走路。</div>
</section>

<section>
  <h2>3 · 用户看完会怎么互动？</h2>
  <div class="desc">互动率中位（仅统计播放>1000 的视频，避免新片干扰）。</div>
  <div class="chart" style="display:flex;justify-content:center">{rate_svg}</div>
  <div class="note">💡 <b>规律：</b>点赞率 ~{rates["点赞"]:.1f}%（基准线），但<strong>收藏率（{rates["收藏"]:.1f}%）{'高于' if rates["收藏"] > rates["投币"] else '低于'}投币率（{rates["投币"]:.1f}%）</strong>——观众更愿意"存起来以后用"，而不是"打钱"。做<strong>有用、可复盘、可收藏</strong>的内容（盘点/教程/清单），比纯娱乐更容易被长期推流。</div>
</section>

<section>
  <h2>4 · 标题怎么起？</h2>
  <div class="desc">对 {len(items)} 条热门标题的统计。</div>
  <div class="chart">
    <div style="display:flex;gap:18px;flex-wrap:wrap">
      <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666;margin-bottom:4px">平均标题长度</div><div style="font-size:24px;font-weight:800;color:#FB7299">{avg_len:.0f} 字</div></div>
      <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666;margin-bottom:4px">含 ！/？ 情绪符</div><div style="font-size:24px;font-weight:800;color:#23ADE5">{p_sym:.0f}%</div></div>
      <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666;margin-bottom:4px">含 【】《》 强调符</div><div style="font-size:24px;font-weight:800;color:#FFB027">{p_br:.0f}%</div></div>
      <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666;margin-bottom:4px">含 数字/年份</div><div style="font-size:24px;font-weight:800;color:#7ED321">{p_num:.0f}%</div></div>
    </div>
  </div>
  <div class="note">💡 <b>规律：</b>爆款标题平均 {avg_len:.0f} 字，{p_sym:.0f}% 带情绪符、{p_br:.0f}% 带【】强调框。好标题≈<strong>"情绪/疑问 + 具体信息（数字、时间、人名）+ 视觉强调"</strong>。别做"低调标题党"，要"信息明确的强情绪"。</div>
</section>

<section>
  <h2>5 · 当前最火的 10 条</h2>
  <div class="desc">按播放量排序（点击标题可跳转原视频）。</div>
  <table>
    <tr><th>#</th><th style="text-align:left">标题</th><th>分区</th><th>播放</th><th>点赞</th><th>UP主</th></tr>
    {rows}
  </table>
</section>

<section>
  <h2>6 · 爆款规律一句话总结</h2>
  <div style="font-size:14px">
    <span class="tag">赛道集中</span><span class="tag">游戏/生活/搞笑三足鼎立</span>
    <span class="tag">长度两极</span><span class="tag">短试水·长立人设</span>
    <span class="tag">收藏>投币</span><span class="tag">做"有用"的内容</span>
    <span class="tag">强情绪标题</span><span class="tag">{avg_len:.0f}字·带符号</span>
    <span class="tag">热点窗口短</span><span class="tag">上榜中位仅 {age_med:.1f} 天</span>
  </div>
  <div class="note">⚡ <b>最关键的一条：</b>上榜视频发布距今中位数仅 <b>{age_med:.1f} 天</b>。B站热门榜轮换极快，<strong>追热点要在 48 小时内出内容</strong>，错过窗口基本没戏。</div>
</section>

<section>
  <h2>7 · 给你的选题行动清单</h2>
  <ul class="tips" style="font-size:14px;color:#333">
    <li><b>选赛道：</b>从「游戏二创 / 日常治愈 / 搞笑盘点 / 知识科普」里挑一个你真感兴趣、能持续做的，别贪多。</li>
    <li><b>定形式：</b>先用 1–3 分钟短视频追热点试水，再用 8–12 分钟中长视频做"有观点/有信息量"的内容立人设。</li>
    <li><b>练标题：</b>套公式——「情绪词/疑问 + 具体数字或时间点 +【】强调」。例：<i>"3 分钟看懂 XX：为什么年轻人都在聊它？【深度】"</i></li>
    <li><b>提收藏：</b>每期都想清楚"观众为什么要存"——清单、教程、对比表、避坑指南，都是高收藏形态。</li>
    <li><b>拼速度：</b>刷到热点立刻记下来，48 小时内出片；热点类内容不求完美，求快和角度新。</li>
    <li><b>看数据：</b>每周回看自己视频的点赞率/收藏率，对标这份基准（点赞 ~{rates["点赞"]:.1f}%、收藏 ~{rates["收藏"]:.1f}%），低于均值就调标题或开头。</li>
  </ul>
</section>

<div style="text-align:center;color:#bbb;font-size:12px;margin-top:30px">
  本报告由 WorkBuddy 基于 B站公开排行榜/热门接口自动生成 · 数据仅反映抓取时点，不构成流量承诺
</div>

</div></body></html>'''

outdir = os.path.join(ROOT, 'reports', BATCH)
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, f'b站爆款分析报告_{TODAY}.html')
_i = 2
while os.path.exists(out):          # 同日重跑自动加序号，绝不覆盖旧文档
    out = os.path.join(outdir, f'b站爆款分析报告_{TODAY}_{_i}.html')
    _i += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('生成成功:', out)
print('数字标题比例: %.0f%%' % p_num)
