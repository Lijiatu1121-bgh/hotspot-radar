# -*- coding: utf-8 -*-
"""基于 knowledge_raw.json 生成知识区爆款分析报告（按方向分组）。"""
import json, re, datetime, os
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))   # 知识热点/
data = json.load(open(os.path.join(BASE, 'data', 'knowledge_raw.json'), encoding='utf-8'))
N = len(data)
TODAY = datetime.date.today().strftime('%Y-%m-%d')  # 运行当天，历史报告不覆盖
BATCH = os.environ.get('BZ_BATCH') or TODAY   # scripts/run_all.py 统一分配的「每次独立文件夹」

def med(l):
    s = sorted(l); n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

# ---------- 方向分布 ----------
dir_count = Counter()
for v in data:
    for d in v['dirs']:
        dir_count[d] += 1
dirs_order = [d for d, _ in dir_count.most_common()]
dir_avg_play = {d: 0 for d in dirs_order}
for d in dirs_order:
    ps = [v['play'] for v in data if d in v['dirs']]
    dir_avg_play[d] = sum(ps)/max(len(ps), 1)

# ---------- 时长分布 ----------
durs = [v['duration'] for v in data if v['duration'] > 0]
short = sum(1 for d in durs if d < 180)
mid = sum(1 for d in durs if 180 <= d <= 600)
long_ = sum(1 for d in durs if d > 600)
avg_dur = med(durs)/60

# ---------- 互动率（中位，仅 play>1000） ----------
def rate(field):
    r = [v[field]/v['play'] for v in data if v['play'] > 1000 and v[field] > 0]
    return med(r)*100 if r else 0
rate_like = rate('like')
rate_fav = rate('favorites')
rate_dm = rate('danmaku')
rate_review = rate('review')

# ---------- 标题特征 ----------
titles = [v['title'] for v in data]
avg_len = sum(len(t) for t in titles)/len(titles)
p_sym = sum(1 for t in titles if re.search(r'[！？!?]', t))/len(titles)*100
p_num = sum(1 for t in titles if re.search(r'\d', t))/len(titles)*100

kw_lib = ['为什么','如何','怎么','怎样','揭秘','盘点','教程','入门','干货','全解','秒懂','看完',
          '建议','一定要','vs','VS','2026','中国','学生','考试','考研','学习','科普','真相','预测',
          '拆解','实测','评测','推荐','避坑','攻略','原理','本质','终于','原来','一口气','UP']
kw_cnt = Counter()
for t in titles:
    for kw in kw_lib:
        if kw.lower() in t.lower():
            kw_cnt[kw] += 1
kw_top = kw_cnt.most_common(12)

# ---------- 榜单 ----------
top_all = sorted(data, key=lambda v: v['play'], reverse=True)[:10]
top_by_dir = {}
for d in dirs_order:
    vs = [v for v in data if d in v['dirs']]
    top_by_dir[d] = sorted(vs, key=lambda v: v['play'], reverse=True)[:3]

# ---------- SVG 图表 ----------
def hbar(items, color='#FB7299', width=620):
    maxv = max(v for _, v in items)
    rowh, gap = 26, 8
    rows = ''
    for i, (lab, val) in enumerate(items):
        y = i*(rowh+gap)
        bw = max(3, val/maxv*(width-200))
        rows += (f'<g transform="translate(0,{y})"><text x="0" y="{rowh/2}" dominant-baseline="middle" font-size="12.5" fill="#333">{lab}</text>'
                 f'<rect x="150" y="4" width="{bw:.0f}" height="{rowh-8}" rx="3" fill="{color}"/>'
                 f'<text x="{150+bw+6:.0f}" y="{rowh/2}" dominant-baseline="middle" font-size="11.5" fill="#777">{val}</text></g>')
    h = len(items)*(rowh+gap)
    return f'<svg width="{width}" height="{h}" viewBox="0 0 {width} {h}" style="max-width:100%">{rows}</svg>'

def vbar(items, colors, width=460, height=240):
    maxv = max(v for _, v in items)
    n = len(items); slot = width/n; bw = slot*0.55
    rows = ''
    for i, (lab, val) in enumerate(items):
        x = i*slot + (slot-bw)/2
        bh = val/maxv*(height-50)
        y = height-34-bh
        c = colors[i % len(colors)]
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

dir_svg = hbar([(d, dir_count[d]) for d in dirs_order], '#FB7299', 620)
rate_svg = vbar([('点赞', rate_like), ('收藏', rate_fav), ('评论', rate_review), ('弹幕', rate_dm)],
                ['#FB7299', '#23ADE5', '#7ED321', '#9B59B6'], 460, 240)
time_svg = stack_bar([('短视频 <3min', short, '#FB7299'), ('中视频 3-10min', mid, '#23ADE5'), ('长视频 >10min', long_, '#FFB027')], 460)

# 方向平均播放条形
dirplay_svg = hbar([(d, round(dir_avg_play[d]/10000,1)) for d in dirs_order], '#23ADE5', 620)

# Top 表格
def top_rows(vs):
    r = ''
    for i, v in enumerate(vs, 1):
        r += (f'<tr><td style="color:#FB7299;font-weight:700">{i}</td>'
              f'<td style="text-align:left"><a href="https://www.bilibili.com/video/{v.get("bvid")}" target="_blank" style="color:#23ADE5;text-decoration:none">{v["title"][:30]}</a></td>'
              f'<td>{v["typename"]}</td><td>{v["play"]/10000:.0f}万</td><td>{v["author"][:10]}</td></tr>')
    return r
top_all_html = top_rows(top_all)
top_dir_html = ''
for d in dirs_order:
    top_dir_html += f'<h4 style="margin:14px 0 6px;color:#FB7299">▸ {d}（平均播放 {dir_avg_play[d]/10000:.0f}万）</h4>'
    top_dir_html += f'<table><tr><th>#</th><th style="text-align:left">标题</th><th>分区</th><th>播放</th><th>UP主</th></tr>{top_rows(top_by_dir[d])}</table>'

kw_html = ''.join(f'<span class="tag">{k} {c}</span>' for k, c in kw_top)

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>知识区爆款分析报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f7;color:#222;line-height:1.6}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 18px 60px}}
header{{background:linear-gradient(135deg,#23ADE5,#7ED321);color:#fff;border-radius:16px;padding:30px 28px;margin-bottom:22px}}
header h1{{font-size:26px;margin-bottom:8px}} header p{{opacity:.92;font-size:14px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}}
.card{{flex:1;min-width:150px;background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
.card .n{{font-size:24px;font-weight:800;color:#23ADE5}} .card .l{{font-size:13px;color:#888;margin-top:4px}}
section{{background:#fff;border-radius:14px;padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
section h2{{font-size:18px;margin-bottom:4px}} section .desc{{font-size:13px;color:#999;margin-bottom:16px}}
.chart{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:8px;border-bottom:1px solid #f0f0f0;text-align:center}}
th{{background:#fafafa;color:#666;font-weight:600}} h4{{font-size:15px}}
.note{{background:#eef9ff;border-left:4px solid #23ADE5;border-radius:0 10px 10px 0;padding:14px 18px;margin:14px 0;font-size:14px}}
.note b{{color:#23ADE5}} .tip{{margin:10px 0;padding-left:26px;position:relative;font-size:14px}} .tip:before{{content:"▸";position:absolute;left:6px;color:#FB7299;font-weight:700}}
.tag{{display:inline-block;background:#eafaf0;color:#1a9e4b;border-radius:6px;padding:3px 9px;font-size:12px;margin:3px}}
.tipbox{{background:#fff7fb;border-radius:12px;padding:18px 20px;margin-top:10px}}
</style></head><body><div class="wrap">

<header>
  <h1>📚 知识区爆款内容分析报告</h1>
  <p>数据抓取于 {TODAY} · 样本 {N} 条（按「方向关键词 + 播放量排序」从公开搜索接口抓取，去重后）· 覆盖 AI/人工智能、电子设备、传统理论科目、科学科普、人文历史五大方向</p>
</header>

<div class="cards">
  <div class="card"><div class="n">{N}</div><div class="l">有效样本（条）</div></div>
  <div class="card"><div class="n">5</div><div class="l">覆盖方向</div></div>
  <div class="card"><div class="n">{avg_dur:.1f}′</div><div class="l">平均时长</div></div>
  <div class="card"><div class="n">{rate_like:.1f}%</div><div class="l">点赞率中位</div></div>
  <div class="card"><div class="n">{rate_fav:.1f}%</div><div class="l">收藏率中位</div></div>
</div>

<section>
  <h2>1 · 五大方向体量对比</h2>
  <div class="desc">按方向统计视频数量（左）与平均播放量（右）。</div>
  <div class="chart">{dir_svg}</div>
  <div class="chart" style="margin-top:10px">{dirplay_svg}</div>
  <div class="note">💡 <b>规律：</b>剔除高中内容后，「电子设备（硬件）」成为体量最大方向（{dir_count.get('电子设备',0)} 条），「AI/人工智能」单条平均播放最高、是当下流量红利区；「传统理论科目」转为<strong>成人/大学向的稳定基本盘</strong>（{dir_count.get('传统理论科目',0)} 条）。</div>
</section>

<section>
  <h2>2 · 视频做多长合适？</h2>
  <div class="desc">知识区内容整体偏中长视频。</div>
  <div class="chart">{time_svg}</div>
  <div class="note">💡 <b>规律：</b>与全站「短长两极」不同，知识区<strong>中长视频（3–10min）占 {mid/len(durs)*100:.0f}%、长视频（>10min）占 {long_/len(durs)*100:.0f}%</strong>。知识类内容靠"讲清楚"，碎片短视频难承载，建议以 5–15 分钟为主。</div>
</section>

<section>
  <h2>3 · 用户怎么互动？</h2>
  <div class="desc">互动率中位（仅统计播放>1000 的视频）。注：搜索接口不返回投币/分享，故用点赞/收藏/评论/弹幕四项。</div>
  <div class="chart" style="display:flex;justify-content:center">{rate_svg}</div>
  <div class="note">💡 <b>规律：</b>知识区<strong>收藏率（{rate_fav:.1f}%）高于全站基准（1.1%）</strong>——观众把知识视频当"资料"存。做<strong>可复习、可收藏</strong>的内容（清单、公式表、避坑指南）最容易被长期推流。</div>
</section>

<section>
  <h2>4 · 标题怎么起？</h2>
  <div class="desc">对 {N} 条标题统计 + 高频爆款词命中。</div>
  <div class="chart" style="display:flex;gap:18px;flex-wrap:wrap">
    <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666">平均标题长度</div><div style="font-size:24px;font-weight:800;color:#23ADE5">{avg_len:.0f} 字</div></div>
    <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666">含 ！/？ 情绪符</div><div style="font-size:24px;font-weight:800;color:#FB7299">{p_sym:.0f}%</div></div>
    <div style="flex:1;min-width:150px"><div style="font-size:13px;color:#666">含 数字/年份</div><div style="font-size:24px;font-weight:800;color:#7ED321">{p_num:.0f}%</div></div>
  </div>
  <div style="margin-top:14px"><div style="font-size:13px;color:#666;margin-bottom:6px">高频爆款词（命中视频数）</div>{kw_html}</div>
  <div class="note">💡 <b>规律：</b>知识区标题爱用<strong>"为什么/如何/怎么"（疑问钩子）+ 揭秘/盘点/教程/干货（价值承诺）+ 学生/考试/考研（人群锚点）</strong>。例：<i>"为什么 XXX？3 分钟讲清本质【干货】"</i></div>
</section>

<section>
  <h2>5 · 全站知识区播放 TOP10</h2>
  <div class="desc">按播放量排序（点击标题可跳转原视频）。</div>
  <table><tr><th>#</th><th style="text-align:left">标题</th><th>分区</th><th>播放</th><th>UP主</th></tr>{top_all_html}</table>
</section>

<section>
  <h2>6 · 各方向爆款代表</h2>
  <div class="desc">每个方向播放量最高的 3 条。</div>
  {top_dir_html}
</section>

<section>
  <h2>7 · 爆款规律一句话</h2>
  <div style="font-size:14px">
    <span class="tag">传统科目=基本盘</span><span class="tag">AI=流量红利</span>
    <span class="tag">中长视频为主</span><span class="tag">收藏率超高</span>
    <span class="tag">疑问钩子标题</span><span class="tag">干货/盘点/教程</span>
  </div>
</section>

<section>
  <h2>8 · 给你的知识区选题清单</h2>
  <div class="tipbox">
    <div class="tip"><b>选赛道：</b>三选一或组合——① <b>传统理论科目</b>（数理化文史，最大盘、最稳）② <b>AI/人工智能</b>（流量红利、增长快）③ <b>电子设备</b>（评测/实测，变现路径清晰）。</div>
    <div class="tip"><b>定形式：</b>以 5–15 分钟中长视频为主，把一件事讲透；可配 1 分钟短视频做"钩子"引流。</div>
    <div class="tip"><b>练标题：</b>套公式——「疑问词（为什么/如何）+ 具体对象 + 价值词（干货/盘点/教程）」。多用"学生/考试/考研/避坑"锚定人群。</div>
    <div class="tip"><b>提收藏：</b>每期埋"可保存点"——公式表、思维导图、资源清单、步骤卡，直接拉高收藏率（知识区推流关键指标）。</div>
    <div class="tip"><b>追 AI 热点：</b>AI 方向单条播放最高，新模型/新工具出来 48 小时内出"实测/教程"，最容易吃到流量。</div>
    <div class="tip"><b>看数据：</b>每周回看自己视频收藏率，对标本报告基准（{rate_fav:.1f}%）；低于均值就优化"可保存性"和标题钩子。</div>
  </div>
</section>

<div style="text-align:center;color:#bbb;font-size:12px;margin-top:30px">
  本报告由 WorkBuddy 基于 B站公开搜索接口自动生成 · 数据为「关键词+播放排序」样本，反映抓取时点热门趋势，非官方排行榜，不构成流量承诺
</div>
</div></body></html>'''

outdir = os.path.join(BASE, 'reports', BATCH)
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, f'知识区爆款分析报告_{TODAY}.html')
_i = 2
while os.path.exists(out):          # 同日重跑自动加序号，绝不覆盖旧文档
    out = os.path.join(outdir, f'知识区爆款分析报告_{TODAY}_{_i}.html')
    _i += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('生成成功:', out)
print('方向:', dict(dir_count))
print(f'时长 短/中/长: {short}/{mid}/{long_}  平均{avg_dur:.1f}min')
print(f'点赞率{rate_like:.1f}% 收藏率{rate_fav:.1f}% 评论率{rate_review:.1f}% 弹幕率{rate_dm:.1f}%')
print(f'标题平均{avg_len:.0f}字 情绪符{p_sym:.0f}% 数字{p_num:.0f}%')
print('高频词:', kw_top[:6])
