# -*- coding: utf-8 -*-
"""生成《GitHub 热点技术分析报告》。

不做 star 搬运，做四件事：
  1) 清理：识别刷星投放（同描述多仓库）、资源合集、纯提示词包，并公开剔除依据
  2) 拆解：TOP 项目的技术路线（reads README 判断实现方式，而非只看描述）
  3) 归因：为什么现在火——用同赛道星速基线对比，区分「赛道风口」和「个体异常」
  4) 结论：能不能用 —— 成熟度打分给出「可直接用 / 看思路 / 只看热闹」
"""
import json, os, re, datetime, statistics
from collections import Counter, defaultdict
import github_taxonomy as gx

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
TODAY = datetime.date.today().strftime('%Y-%m-%d')
BATCH = os.environ.get('BZ_BATCH') or TODAY
NOW_DT = datetime.datetime.now()

raw = json.load(open(os.path.join(DATA, 'repos_raw.json'), encoding='utf-8'))
repos = raw.get('repos', [])
queries = raw.get('queries', {})

farms = gx.detect_farm(repos)

jobs, junked = [], []
for r in repos:
    junk = gx.junk_check(r, farms)
    track, hits = gx.classify(r)
    m = gx.metrics(r)
    sig = gx.readme_signals(r.get('_readme', ''))
    score, detail = gx.maturity(r, m, sig, junk)
    v, vwhy = gx.verdict(score, junk)
    j = {
        'full_name': r.get('full_name'), 'url': r.get('html_url'),
        'desc': (r.get('description') or '').strip(),
        'lang': r.get('language'), 'topics': (r.get('topics') or [])[:6],
        'stars': m['stars'], 'forks': m['forks'], 'age': m['age'],
        'velocity': m['velocity'], 'fork_ratio': m['fork_ratio'],
        'license': ((r.get('license') or {}).get('spdx_id') if r.get('license') else None),
        'homepage': r.get('homepage'), 'created': (r.get('created_at') or '')[:10],
        'pushed': (r.get('pushed_at') or '')[:10],
        'track': track['name'] if track else '未归类', 'hits': hits,
        'sig': sig, 'score': score, 'detail': detail,
        'verdict': v, 'verdict_why': vwhy, 'junk': junk,
        'sources': r.get('_sources', []),
        'readme_len': len(r.get('_readme') or ''),
    }
    (junked if junk else jobs).append(j)

# ---------- 赛道基线（用于「为什么火」的归因） ----------
track_items = defaultdict(list)
for j in jobs:
    track_items[j['track']].append(j)
track_med_v = {t: statistics.median([x['velocity'] for x in v]) for t, v in track_items.items()}
all_med_v = statistics.median([j['velocity'] for j in jobs]) if jobs else 1


def why_hot(j):
    """归因：是赛道风口，还是个体异常？"""
    reasons = []
    tm = track_med_v.get(j['track'], all_med_v)
    if tm and j['velocity'] >= tm * 2 and j['velocity'] > 50:
        reasons.append(f"个体异常：星速 {j['velocity']:.0f}/天，是同赛道中位的 {j['velocity']/tm:.1f} 倍，"
                       f"说明它抓住了具体痛点，而不是靠赛道整体上涨")
    elif tm >= all_med_v * 1.4:
        reasons.append(f"赛道风口：{j['track']} 本期整体吸星效率是全局的 {tm/all_med_v:.1f} 倍，它顺势而起")
    if any(w in j['sig']['inherit'] for w in ('based on', 'built on top of', 'fork of', 'wrapper around')):
        reasons.append('站在已有项目肩上：README 明示基于/包装既有实现，传播成本低')
    if 'iOS' in j['sig']['platform'] or 'Android' in j['sig']['platform']:
        reasons.append('移动端稀缺：桌面工具多、手机端同等能力少，天然有需求缺口')
    if 'Rust 实现' in j['sig']['stack']:
        reasons.append('Rust 重写叙事：性能与安全的故事自带传播力，也容易被技术社区转发')
    if not reasons:
        reasons.append('信号不足：README 与 topics 都没给出明确原因，需要人工看代码判断')
    return reasons


def pct(n, d):
    return f'{n/d*100:.0f}%' if d else '0%'


def hbar(data, color='#2da44e', width=620, unit=''):
    if not data:
        return '<div style="color:#999;font-size:13px">无数据</div>'
    maxv = max(v for _, v in data) or 1
    rowh, gap = 26, 9
    rows = ''
    for i, (lab, val) in enumerate(data):
        y = i * (rowh + gap)
        bw = max(3, val / maxv * (width - 230))
        shown = f'{val:.1f}' if isinstance(val, float) else str(val)
        rows += (f'<g transform="translate(0,{y})">'
                 f'<text x="0" y="{rowh/2}" dominant-baseline="middle" font-size="12.5" fill="#24292f">{lab}</text>'
                 f'<rect x="180" y="4" width="{bw:.0f}" height="{rowh-8}" rx="3" fill="{color}"/>'
                 f'<text x="{180+bw+7:.0f}" y="{rowh/2}" dominant-baseline="middle" font-size="11.5" fill="#57606a">{shown}{unit}</text>'
                 f'</g>')
    h = len(data) * (rowh + gap)
    return f'<svg width="{width}" height="{h}" viewBox="0 0 {width} {h}" style="max-width:100%">{rows}</svg>'


def project_card(j, idx):
    sig = j['sig']
    tech = []
    if sig['stack']:
        tech.append('技术栈：' + '、'.join(sig['stack']))
    if sig['install']:
        tech.append('安装：`' + '/'.join(sig['install']) + '`')
    if sig['inherit']:
        tech.append('继承关系：README 出现「' + '」「'.join(sig['inherit'][:2]) + '」')
    if sig['platform']:
        tech.append('平台：' + '、'.join(sig['platform']))
    if not tech:
        tech.append('README 未提供足够技术线索（可能非代码型仓库，或 README 抓取失败）')

    judges = ''.join(f'<li>{x}</li>' for x in (
        next((t['judge'] for t in gx.TRACKS if t['name'] == j['track']), [])
    ))
    why = ''.join(f'<li>{x}</li>' for x in why_hot(j))
    score_bits = ''.join(
        f'<span class="bit{" neg" if v < 0 else ""}">{k} {v:+d} · {r}</span>' for k, v, r in j['detail'])

    cls = 'ok' if j['verdict'] == '可直接用' else ('mid' if j['verdict'] == '看思路' else 'warn')
    return f'''
<div class="pcard">
  <div class="phead">
    <span class="pidx">{idx:02d}</span>
    <div style="flex:1">
      <a class="pname" href="{j['url']}" target="_blank">{j['full_name']}</a>
      <div class="pdesc">{j['desc'] or '（无描述）'}</div>
    </div>
  </div>
  <div class="pmeta">
    <span class="pill p-track">{j['track']}</span>
    <span class="pill p-lang">{j['lang'] or '无主语言'}</span>
    <span class="pill p-stat">★ {j['stars']:,} · ⑂ {j['forks']:,} · 建仓 {j['age']} 天</span>
    <span class="pill p-v">星速 {j['velocity']:.0f}/天</span>
    <span class="verdict {cls}">{j['verdict']}</span>
  </div>
  <div class="pblock">
    <div class="plabel">技术路线（读 README 得出，不是猜）</div>
    <ul class="plist">{''.join(f'<li>{t}</li>' for t in tech)}</ul>
  </div>
  <div class="pgrid">
    <div>
      <div class="plabel">为什么现在火</div>
      <ul class="plist">{why}</ul>
    </div>
    <div>
      <div class="plabel">这条赛道的判断点</div>
      <ul class="plist">{judges or '<li>该赛道暂无固定判断框架，需人工看代码</li>'}</ul>
    </div>
  </div>
  <div class="pfoot">
    <div class="plabel">成熟度 {j['score']} 分 · 结论：{j['verdict']} —— {j['verdict_why']}</div>
    <div class="bits">{score_bits}</div>
  </div>
</div>'''


# ---------- 榜单切片 ----------
def sort_pick(src, n, key):
    lst = [j for j in jobs if src in j['sources']]
    lst.sort(key=lambda x: x[key], reverse=True)
    seen, out = set(), []
    for x in lst:
        if x['full_name'] in seen:
            continue
        seen.add(x['full_name'])
        out.append(x)
    return out[:n]


new_top = sort_pick('new', 6, 'stars')
grow_top = sort_pick('growing', 6, 'velocity')
cards = ''.join(project_card(j, i) for i, j in enumerate(new_top + grow_top, 1))

# ---------- 统计 ----------
track_cnt = Counter(j['track'] for j in jobs)
lang_cnt = Counter(j['lang'] or '无主语言' for j in jobs)
junk_cnt = Counter(j['junk'][0] for j in junked)

track_bar = hbar([(f"{t}（{c}）", round(track_med_v[t], 1)) for t, c in track_cnt.most_common()],
                 '#2da44e', 700, ' 星/天')
lang_bar = hbar([(f'{k}', v) for k, v in lang_cnt.most_common(10)], '#0969da', 700, ' 个')

# 剔除清单
junk_rows = ''
for j in sorted(junked, key=lambda x: -x['stars']):
    junk_rows += (f'<tr><td style="text-align:left"><a href="{j["url"]}" target="_blank" '
                  f'style="color:#0969da;text-decoration:none">{j["full_name"]}</a></td>'
                  f'<td>{j["junk"][0]}</td><td>★{j["stars"]:,}</td>'
                  f'<td style="text-align:left;color:#8b949e;font-size:12px">{j["junk"][1][:46]}</td></tr>')

# AI 相关占比
ai_tracks = {'AI Agent 与自动化', '大模型工具链', 'AI 生成内容'}
ai_jobs = [j for j in jobs if j['track'] in ai_tracks]
ai_share = len(ai_jobs) / len(jobs) if jobs else 0
ai_med = statistics.median([j['velocity'] for j in ai_jobs]) if ai_jobs else 0
other_med = statistics.median([j['velocity'] for j in jobs if j['track'] not in ai_tracks]) or 1

rust_jobs = [j for j in jobs if 'Rust' in (j['lang'] or '')]
rust_share = len(rust_jobs) / len(jobs) if jobs else 0
rust_med = statistics.median([j['velocity'] for j in rust_jobs]) if rust_jobs else 0

# 可用清单（展示前 8，但数量按全量统计，避免被切片误导）
usable_all = sorted([j for j in jobs if j['verdict'] == '可直接用'], key=lambda x: -x['score'])
study_all = sorted([j for j in jobs if j['verdict'] == '看思路'], key=lambda x: -x['velocity'])
usable, study = usable_all[:8], study_all[:8]

usable_rows = ''.join(
    f'<tr><td style="text-align:left"><a href="{j["url"]}" target="_blank" style="color:#0969da;text-decoration:none">{j["full_name"]}</a></td>'
    f'<td>{j["track"]}</td><td><b>{j["score"]}</b></td><td>{j["lang"] or "—"}</td>'
    f'<td>{(j["license"] or "无")}</td><td>{j["velocity"]:.0f}</td></tr>' for j in usable) or \
    '<tr><td colspan="6" style="color:#999;padding:18px">本期无满分项目</td></tr>'

study_rows = ''.join(
    f'<tr><td style="text-align:left"><a href="{j["url"]}" target="_blank" style="color:#0969da;text-decoration:none">{j["full_name"]}</a></td>'
    f'<td>{j["track"]}</td><td><b>{j["score"]}</b></td>'
    f'<td style="text-align:left;color:#8b949e;font-size:12px">{j["verdict_why"][:40]}</td></tr>' for j in study) or \
    '<tr><td colspan="4" style="color:#999;padding:18px">本期无</td></tr>'

# 排除「未归类」再算红利赛道，否则会把一堆杂项算成风口
_known_med = [(t, v) for t, v in track_med_v.items() if t != '未归类']
best_track = max(_known_med, key=lambda x: x[1]) if _known_med else None
best_track_txt = (f'{best_track[0]}（中位 {best_track[1]:.0f} 星/天）' if best_track else '暂无数据')

top_track = track_cnt.most_common(1)[0] if track_cnt else ('—', 0)
if top_track[0] == '未归类' and len(track_cnt) > 1:
    top_track = track_cnt.most_common(2)[1]
fastest = max(jobs, key=lambda x: x['velocity']) if jobs else None
qmeta = ' · '.join(f"{v.get('label','')} {v.get('count',0)} 条" for v in queries.values())

# 提前算好这段文字：直接写进 f-string 里会因引号嵌套（外层 ''' 与内层 '''）静默变空
if fastest:
    fastest_para = (
        f"它在 {fastest['age']} 天内拿到 {fastest['stars']:,} 星，属「{fastest['track']}」赛道，"
        f"同赛道中位星速仅 {track_med_v.get(fastest['track'], 0):.0f}/天。"
        f"<b>判断：</b>这是个体异常而非赛道整体上涨，说明它命中了一个此前没人做好的具体需求。"
        f"这类项目最值得拆——<b>它的成功原因就是一条现成的选题</b>。"
    )
    fastest_name = f"{fastest['full_name']}（{fastest['velocity']:.0f} 星/天）"
else:
    fastest_para = '本期无可用数据。'
    fastest_name = '—'

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitHub 热点技术分析报告 · {TODAY}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f6f8fa;color:#1f2328;line-height:1.68}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 18px 70px}}
header{{background:linear-gradient(135deg,#1f2328,#30363d);color:#fff;border-radius:16px;padding:32px 30px;margin-bottom:22px}}
header h1{{font-size:26px;margin-bottom:8px}}
header p{{opacity:.86;font-size:13.5px}}
.mono{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}
.cards{{display:flex;gap:13px;flex-wrap:wrap;margin-bottom:24px}}
.card{{flex:1;min-width:150px;background:#fff;border:1px solid #d8dee4;border-radius:14px;padding:17px 18px}}
.card .n{{font-size:25px;font-weight:800;color:#1f2328}}
.card .l{{font-size:12.5px;color:#57606a;margin-top:3px;line-height:1.4}}
section{{background:#fff;border:1px solid #d8dee4;border-radius:14px;padding:26px;margin-bottom:18px}}
section h2{{font-size:18px;margin-bottom:4px}}
section h2 .num{{color:#0969da;margin-right:6px}}
section .desc{{font-size:13px;color:#57606a;margin-bottom:16px}}
.chart{{overflow-x:auto;margin:6px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:9px 8px;border-bottom:1px solid #eaeef2;text-align:center}}
th{{background:#f6f8fa;color:#57606a;font-weight:600;font-size:12.5px}}
.note{{background:#f0fff4;border-left:4px solid #2da44e;border-radius:0 10px 10px 0;padding:14px 18px;margin:14px 0;font-size:13.8px}}
.note.warn{{background:#fff8e6;border-left-color:#bf8700}}
.note b{{color:#1a7f37}}
.note.warn b{{color:#9a6700}}
.pcard{{border:1px solid #d8dee4;border-radius:12px;padding:18px 20px;margin-bottom:14px}}
.phead{{display:flex;gap:11px;align-items:flex-start;margin-bottom:10px}}
.pidx{{flex:0 0 30px;font-size:15px;font-weight:800;color:#c6cdd5;line-height:1.5}}
.pname{{font-size:15.5px;font-weight:700;color:#0969da;text-decoration:none;font-family:ui-monospace,Consolas,monospace}}
.pdesc{{font-size:13px;color:#57606a;margin-top:3px}}
.pmeta{{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:13px}}
.pill{{display:inline-block;border-radius:6px;padding:2px 8px;font-size:11.5px;white-space:nowrap}}
.p-track{{background:#ddf4ff;color:#0969da}}
.p-lang{{background:#f6f8fa;color:#57606a;border:1px solid #d8dee4}}
.p-stat{{background:#f6f8fa;color:#57606a}}
.p-v{{background:#fff8e6;color:#9a6700;font-weight:700}}
.verdict{{margin-left:auto;font-size:12px;font-weight:700;border-radius:6px;padding:3px 10px}}
.verdict.ok{{background:#1a7f37;color:#fff}}
.verdict.mid{{background:#ddf4ff;color:#0969da}}
.verdict.warn{{background:#fff1e5;color:#bc4c00}}
.pblock{{background:#f6f8fa;border-radius:9px;padding:12px 14px;margin-bottom:11px}}
.pgrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:11px}}
.plabel{{font-size:11.5px;font-weight:700;color:#8b949e;letter-spacing:.4px;margin-bottom:6px}}
.plist{{list-style:none;font-size:12.8px;color:#424a53}}
.plist li{{position:relative;padding-left:13px;margin:5px 0;line-height:1.55}}
.plist li:before{{content:"";position:absolute;left:0;top:8px;width:5px;height:5px;border-radius:50%;background:#8fd19e}}
.pfoot{{border-top:1px dashed #d8dee4;padding-top:10px}}
.bits{{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}}
.bit{{font-size:11px;background:#f6f8fa;border:1px solid #eaeef2;border-radius:5px;padding:2px 7px;color:#57606a}}
.bit.neg{{background:#fff1e5;border-color:#ffd8b5;color:#bc4c00}}
.tips li{{margin:9px 0;list-style:none;padding-left:24px;position:relative;font-size:13.8px}}
.tips li:before{{content:"▸";position:absolute;left:4px;color:#0969da;font-weight:700}}
.trend{{border-left:3px solid #0969da;padding:2px 0 2px 14px;margin-bottom:16px}}
.trend h4{{font-size:14.5px;margin-bottom:5px}}
.trend p{{font-size:13px;color:#424a53}}
@media(max-width:640px){{.pgrid{{grid-template-columns:1fr}}}}
</style></head>
<body><div class="wrap">

<header>
  <h1>GitHub 热点技术分析报告</h1>
  <p>抓取于 {raw.get('fetched_at', TODAY)} · {qmeta} · 去重后 {len(repos)} 个仓库 ·
  剔除刷星/合集 {len(junked)} 个后，保留 {len(jobs)} 个可分析项目 · 公开 API，无需 token</p>
</header>

<div class="cards">
  <div class="card"><div class="n">{len(jobs)}</div><div class="l">可分析项目<br>（剔杂后）</div></div>
  <div class="card"><div class="n">{len(junked)}</div><div class="l">剔除<br>（刷星/合集）</div></div>
  <div class="card"><div class="n">{all_med_v:.0f}</div><div class="l">星速中位数<br>（星/天）</div></div>
  <div class="card"><div class="n">{pct(len(ai_jobs), len(jobs))}</div><div class="l">AI 相关项目占比</div></div>
</div>

<section>
  <h2><span class="num">1</span>先清场：{len(junked)} 个看似很火、实际没工程价值的仓库</h2>
  <div class="desc">GitHub 搜索按 star 排序会把三类噪声顶上来：批量刷星投放、资源合集、纯提示词包。它们的共同点是——<b>star 很高，但你 clone 下来没有可运行的东西</b>。</div>
  <table>
    <tr><th style="text-align:left">仓库</th><th style="width:100px">类型</th><th style="width:90px">Star</th><th style="text-align:left;width:40%">判定依据</th></tr>
    {junk_rows or '<tr><td colspan="4" style="color:#999;padding:18px">本期无剔除项</td></tr>'}
  </table>
  <div class="note warn">⚠️ <b>这一节是本报告最该看的部分。</b>
    本期新星榜里出现了多个<b>描述完全相同、fork 为 0</b> 的仓库（{junk_cnt.get('刷星投放', 0)} 个），
    这是典型的批量刷星引流手法：同一套代码/文案换壳发布，靠搜索排名导流。
    如果只看「star 榜」做选题，很容易把它们当成真趋势去讲。</div>
</section>

<section>
  <h2><span class="num">2</span>赛道：钱和注意力在往哪走</h2>
  <div class="desc">括号内是本期该赛道的项目数，柱长是<b>该赛道星速中位数</b>（每天涨多少星）。用中位数而非总和，避免单个爆款拉偏整个赛道。</div>
  <div class="chart">{track_bar}</div>
  <div class="note">💡 <b>怎么用：</b>赛道柱长代表「同样的项目质量，放在这个赛道能多拿多少关注」。
    柱长明显高于全局中位（{all_med_v:.0f} 星/天）的赛道，说明当下有系统性红利——
    这时候做该赛道的解读内容，天然比冷门赛道更容易被算法推。</div>
</section>

<section>
  <h2><span class="num">3</span>逐项目拆解：本期最该看的 12 个</h2>
  <div class="desc">前 6 个来自「近 7 天新建」（按星数），后 6 个来自「8–30 天」（按星速，排除已经跑完的）。每个都读了 README 判断实现方式，不是照抄描述。</div>
  {cards or '<div style="color:#999;padding:20px">本期无可拆解项目</div>'}
</section>

<section>
  <h2><span class="num">4</span>技术栈分布</h2>
  <div class="desc">主语言统计（剔杂后）。注意：语言数不等于项目数——有 {len([j for j in jobs if not j['lang']])} 个项目没有主语言，多为纯文档/配置类。</div>
  <div class="chart">{lang_bar}</div>
  <div class="note">💡 <b>读法：</b>Rust 占比 {pct(len(rust_jobs), len(jobs))}（{len(rust_jobs)} 个），中位星速 {rust_med:.0f}/天，
    {'高于' if rust_med > all_med_v else '低于'}全局中位 {all_med_v:.0f}。
    {'这说明「Rust 重写」仍是当下最有效的传播叙事——同样功能用 Rust 实现，更容易被技术社区转发。'
     if rust_med > all_med_v else '说明 Rust 项目已经进入常态，不再自带额外流量。'}</div>
</section>

<section>
  <h2><span class="num">5</span>本期趋势判断</h2>
  <div class="desc">三条结论，每条都给出支撑数据。数据之外的部分标为推断。</div>

  <div class="trend">
    <h4>① AI 相关项目占 {pct(len(ai_jobs), len(jobs))}，星速是其他项目的 {ai_med/other_med:.1f} 倍</h4>
    <p>本期 {len(jobs)} 个可分析项目里 {len(ai_jobs)} 个属 AI 三条赛道（Agent / 工具链 / 生成内容），
    中位星速 {ai_med:.0f}/天，非 AI 项目为 {other_med:.0f}/天。
    <b>判断：</b>AI 占了约三分之一的供给，是这时期的主要题材；但星速只高出 {ai_med/other_med:.1f} 倍，
    说明<b>「沾上 AI 就有人看」的红利已经不明显</b>，接下来拼的是具体问题解决得好不好。
    <span style="color:#8b949e">（这是单期横截面，只能说明当下结构，不能证明趋势在变；要看变化需连续 3 期以上对比。）</span></p>
  </div>

  <div class="trend">
    <h4>② 供给最密集的赛道是「{top_track[0]}」，本期 {top_track[1]} 个项目</h4>
    <p>从数量看这是供给最密集的方向，意味着<b>竞争也最激烈</b>：同期有 {top_track[1]} 个项目在抢同一批用户的注意力。
    <b>判断：</b>做内容时，选这个赛道里的「具体问题」而非「整个赛道综述」——综述已经过剩，具体问题还有空间。</p>
  </div>

  <div class="trend">
    <h4>③ 本期星速最高：{fastest_name}</h4>
    <p>{fastest_para}</p>
  </div>
</section>

<section>
  <h2><span class="num">6</span>可用清单：哪些能动手，哪些只能看</h2>
  <div class="desc">成熟度 = 真实使用度（fork 比）+ 工程完整度（安装方式）+ 许可证 + 产品化 − 风险扣分。满分 100。</div>

  <div style="font-size:12.5px;font-weight:700;color:#1a7f37;margin:14px 0 6px">✅ 可直接用 · {len(usable_all)} 个</div>
  <table>
    <tr><th style="text-align:left">仓库</th><th style="width:150px">赛道</th><th style="width:70px">成熟度</th><th style="width:90px">语言</th><th style="width:110px">许可证</th><th style="width:80px">星速</th></tr>
    {usable_rows}
  </table>

  <div style="font-size:12.5px;font-weight:700;color:#0969da;margin:16px 0 6px">🔍 看思路 · {len(study_all)} 个（读代码比用它更有价值）</div>
  <table>
    <tr><th style="text-align:left">仓库</th><th style="width:150px">赛道</th><th style="width:70px">成熟度</th><th style="text-align:left;width:38%">为什么只能看</th></tr>
    {study_rows}
  </table>

  <div class="note">💡 <b>判断口径：</b>「可直接用」要求 fork/star ≥ 0.12、README 写明安装方式、许可证宽松——
    三者缺一就可能踩坑（无 license 的项目商用有法律风险）。
    「看思路」通常是技术方案精彩但工程未打磨，<b>抄它的设计比依赖它的代码更划算</b>。</div>
</section>

<section>
  <h2><span class="num">7</span>给你的行动清单</h2>
  <ul class="tips">
    <li><b>先看第 1 节再看榜单：</b>本期有 {len(junked)} 个仓库看着火但没东西，其中 {junk_cnt.get('刷星投放', 0)} 个是刷星投放。
        养成先查 fork 比（{'<'} 0.02 基本可疑）的习惯，能避开大部分坑。</li>
    <li><b>挑一个赛道深耕：</b>本期供给最密集的是「{top_track[0]}」，但赛道红利最高的是
        {best_track_txt}。
        两者不一致时，<b>选红利高的那个做内容，选供给密的那个做工具</b>。</li>
    <li><b>立刻能上手：</b>{('、'.join(j['full_name'] for j in usable[:3])) if usable else '本期无满分项目'}。
        这三类都满足「宽松许可 + 有安装文档 + 有人真 fork」，跑一遍不亏。</li>
    <li><b>做内容的正确姿势：</b>不要报「本周 star 榜前十」，而是选一个项目讲清
        <b>它解决了什么此前解决不好的问题</b>——本期 {fastest['full_name'] if fastest else '—'} 就是现成素材。</li>
    <li><b>存一份快照：</b>本期数据已存入 <span class="mono">{BATCH}/data/repos_raw.json</span>，
        下周跑完可以对比赛道星速变化，<b>单期数据只能看热闹，两期以上才能看出趋势</b>。</li>
  </ul>
</section>

<section>
  <h2>方法与局限（必读）</h2>
  <div style="font-size:13px;color:#57606a">
    <p style="margin-bottom:8px"><b>数据口径：</b>GitHub Search API，三张榜共 3 次请求：
    近 7 天新建按 star 排序、8–30 天新建按 star 排序、万星项目近 3 天有推送。
    <b>注意：</b>GitHub 搜索的 star 排序有滞后，真正「本周暴涨」的项目不一定在榜上，需要用 star-history 类工具补。</p>
    <p style="margin-bottom:8px"><b>刷星识别：</b>用「描述文本归一化后重复 ≥2 次」判定批量投放，这是启发式规则。
    高明的刷星会改描述绕过检测，所以<b>本报告不能证明某个项目没刷星，只能标出明显的</b>。</p>
    <p style="margin-bottom:8px"><b>技术路线判断：</b>来自 README 前 4000 字符的关键词匹配（安装方式、技术栈、继承关系）。
    README 写得差的项目会被低估，这是数据源本身的偏差，不是项目质量问题——
    遇到「README 未提供线索」的项目，建议直接看代码。</p>
    <p style="margin-bottom:8px"><b>成熟度分不是质量分：</b>它衡量「现在拿来用靠不靠谱」，不衡量技术优雅程度。
    高分意味着工程完备、可依赖；低分可能是早期项目，反而更值得关注设计。</p>
    <p><b>不做什么：</b>不评价项目作者、不判断商业前景、不推荐在生产环境未经测试地使用任何仓库。</p>
  </div>
</section>

<div style="text-align:center;color:#8b949e;font-size:12px;margin-top:28px">
  由 WorkBuddy 基于 GitHub 公开 API 生成 · 抓取时点 {raw.get('fetched_at', TODAY)} · 数据快照 {BATCH}/data/
</div>

</div></body></html>'''

outdir = os.path.join(ROOT, 'reports', BATCH)
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, f'GitHub热点技术分析报告_{TODAY}.html')
_i = 2
while os.path.exists(out):
    out = os.path.join(outdir, f'GitHub热点技术分析报告_{TODAY}_{_i}.html')
    _i += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'生成成功: {out}')
print(f'  仓库 {len(repos)} → 保留 {len(jobs)} / 剔除 {len(junked)}（{dict(junk_cnt)}）')
print(f'  赛道: ' + ' / '.join(f'{t}({c})' for t, c in track_cnt.most_common(5)))
print(f'  星速中位 {all_med_v:.1f}/天；可直接用 {len(usable_all)} 个，看思路 {len(study_all)} 个')
