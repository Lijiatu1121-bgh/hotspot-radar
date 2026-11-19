# -*- coding: utf-8 -*-
"""把知识区爆款视频按「知识点」聚类，生成「爆款背后的知识点」报告（替换原统计视角）。"""
import json, re, os, datetime
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))   # 知识热点/
data = json.load(open(os.path.join(BASE, 'data', 'knowledge_raw.json'), encoding='utf-8'))
TODAY = datetime.date.today().strftime('%Y-%m-%d')  # 运行当天，历史报告不覆盖
BATCH = os.environ.get('BZ_BATCH') or TODAY   # scripts/run_all.py 统一分配的「每次独立文件夹」
N = len(data)

def text(v):
    return (v.get('title','') + ' ' + v.get('tag','') + ' ' + v.get('description','')).lower()

# ---------- 知识点分类体系（方向 -> 知识点列表） ----------
# 每个知识点：name 名称 / kw 命中关键词 / explain 一句话定义+为什么火
TAX = {
'传统理论科目': [
 {'name':'微积分与极限','kw':['微积分','极限','导数','微分','积分','微分方程','牛顿-莱布尼茨'],
  'explain':'研究“变化率与累积”的数学分支，核心是导数与积分。爆款多集中在“直观理解极限/导数几何意义/微积分到底用来干嘛”。'},
 {'name':'线性代数与矩阵','kw':['线性代数','矩阵','向量','特征值','行列式','方程组','张量'],
  'explain':'用向量和矩阵研究线性变换，是 AI、图形学、工程计算的共同地基，常被吐槽“学了不知道干嘛”于是成为讲解热点。'},
 {'name':'经典力学','kw':['牛顿','力学','运动','引力','能量','动量','圆周','天体力学'],
  'explain':'以牛顿三定律为核心的物体运动规律，含能量守恒、引力、动量，是物理入门第一座大山。'},
 {'name':'电磁学','kw':['电磁','电场','磁场','电路','麦克斯韦','电流','电压','电磁感应'],
  'explain':'电场、磁场及其相互作用，麦克斯韦方程组统一了电与磁，也是现代一切电气设备的原理根。'},
 {'name':'量子力学','kw':['量子','波函数','薛定谔','纠缠','叠加','测不准','量子力学'],
  'explain':'微观粒子的概率性物理规律，含波粒二象性、叠加、纠缠，反直觉却支撑了半导体与 AI 算力。'},
 {'name':'有机化学与分子','kw':['有机','官能团','化学键','反应','分子','化学','催化'],
  'explain':'碳化合物结构与反应规律，官能团决定性质，是生命化学与材料化学的核心难点。'},
 {'name':'遗传与进化','kw':['基因','dna','遗传','进化','细胞','自然选择','达尔文'],
  'explain':'基因如何传递、物种如何演化，含 DNA、自然选择，解释“我们从哪来、生命怎么运作”。'},
 {'name':'哲学与逻辑','kw':['哲学','逻辑','存在','意识','辩证法','思考','思维'],
  'explain':'对存在、认知、推理的系统性反思，含逻辑学与思维方法，是“开窍类”长尾内容。'},
],
'AI/人工智能': [
 {'name':'大语言模型与 Transformer','kw':['大模型','transformer','gpt','llama','预训练','语言模型','基座模型'],
  'explain':'以 Transformer 架构预训练的大规模语言模型（GPT/通义/智谱等），是当前 AI 热潮的底层底座。'},
 {'name':'提示词工程','kw':['提示词','prompt','咒语','指令','提示'],
  'explain':'通过设计指令(Prompt)引导模型输出，是零代码撬动模型能力的最高性价比入口。'},
 {'name':'微调与对齐','kw':['微调','fine','对齐','lora','蒸馏','训练','rlhf'],
  'explain':'在预训练模型上用特定数据继续训练(LoRA等)或对齐人类偏好(RLHF)，让通用模型变“专用”。'},
 {'name':'RAG 与知识库','kw':['rag','检索','知识库','向量','嵌入','embedding'],
  'explain':'检索增强生成：让模型先查资料再回答，缓解幻觉、接入私有知识，是当前落地最稳的架构。'},
 {'name':'AI Agent 智能体','kw':['agent','智能体','工作流','自动化','自主','智能体'],
  'explain':'能自主规划、调用工具完成任务的 AI 系统，被视为从“聊天”走向“干活”的关键形态。'},
 {'name':'扩散模型与 AIGC','kw':['扩散','文生图','stable diffusion','midjourney','sora','视频生成','生图','绘图'],
  'explain':'通过逐步去噪生成图像/视频(SD、Midjourney、Sora等)，引爆了 AI 内容创作浪潮。'},
 {'name':'多模态与推理','kw':['多模态','推理','o1','思维链','视觉理解','推理模型','深度思考'],
  'explain':'模型同时理解图文等多模态信息，并以链式推理(o1类)提升数学/代码等复杂任务表现。'},
 {'name':'大模型应用提效','kw':['编程','办公','copilot','效率','助手','应用','生产力'],
  'explain':'用 AI 助手做编程、写作、办公、数据分析，是离普通人最近的“生产力”落地方向。'},
],
'电子设备': [
 {'name':'显卡 / GPU','kw':['显卡','gpu','显存','光追','架构','4090','5090','核显','显卡'],
  'explain':'负责图形与并行计算的芯片，显存容量/位宽、架构、光追是选购与评测的核心参数，也是 AI 算力的载体。'},
 {'name':'CPU 与制程','kw':['cpu','处理器','制程','核心','架构','npu','芯片制程'],
  'explain':'中央处理器，制程(nm)、核心数、架构决定性能；NPU 兴起让端侧 AI 成为新卖点。'},
 {'name':'笔记本 / 整机选购','kw':['笔记本','笔电','整机','轻薄','游戏本','台式','选购'],
  'explain':'按需求选轻薄本/游戏本/台式整机，平衡性能、续航、价格，是“避坑指南”类常青内容。'},
 {'name':'手机与新机评测','kw':['手机','iphone','华为','小米','旗舰','发布','安卓','影像'],
  'explain':'旗舰新机发布季的实测对比，影像、性能、续航、信号是焦点，更新节奏最快。'},
 {'name':'散热与装机','kw':['散热','装机','电源','机箱','水冷','风冷','超频'],
  'explain':'DIY 装机里的散热、电源、机箱搭配，直接决定稳定性与超频上限。'},
 {'name':'外设与配件','kw':['耳机','键盘','鼠标','显示器','相机','平板','手表','外设'],
  'explain':'耳机、键鼠、显示器、相机等体验与生产力外设，客单价低、决策频次高。'},
 {'name':'芯片与算力','kw':['芯片','算力','半导体','晶圆','光刻','制程'],
  'explain':'半导体芯片与算力供给，是 AI 与整机升级的底层约束，也是地缘政治焦点。'},
],
'科学科普': [
 {'name':'宇宙与天体','kw':['宇宙','黑洞','星系','恒星','引力波','膨胀','暗物质'],
  'explain':'黑洞、星系、恒星演化、引力波，回答“宇宙从哪来、到哪去”，是科普顶流题材。'},
 {'name':'量子与微观','kw':['量子','粒子','原子','原子核','微观','对撞'],
  'explain':'原子、基本粒子、量子现象，窥探物质最底层的规律，反直觉最吸睛。'},
 {'name':'生命与进化','kw':['进化','物种','恐龙','基因','大脑','意识','生命','达尔文'],
  'explain':'进化论、恐龙、大脑与意识，理解生命的来龙去脉，天然带故事性。'},
 {'name':'地球与气候','kw':['地球','气候','地质','海洋','板块','地震'],
  'explain':'地球内部结构、地质变迁、气候变化与海洋，连接当下气候议题。'},
 {'name':'数学之美','kw':['数学','数论','分形','拓扑','几何','素数'],
  'explain':'数论、分形、拓扑等，展示数学的结构与趣味，是“高级感”科普方向。'},
],
'人文历史': [
 {'name':'中国历史与王朝','kw':['中国','王朝','唐朝','秦汉','明清','古代','皇帝'],
  'explain':'秦汉、唐宋、明清等王朝兴衰与制度变迁，是最稳的历史基本盘。'},
 {'name':'世界文明与战争','kw':['罗马','二战','战争','文明','帝国','世界史','拿破仑'],
  'explain':'罗马、二战、帝国兴衰等世界史关键节点，叙事张力强、受众广。'},
 {'name':'考古与文物','kw':['考古','文物','遗址','博物馆','发掘','墓葬'],
  'explain':'遗址、文物、博物馆，用实物还原历史，近年随文博热持续走高。'},
 {'name':'哲学与思想','kw':['哲学','思想','儒家','道家','西方哲学','启蒙','诸子'],
  'explain':'中西方哲学流派与思想史，儒道、启蒙等，满足“认知升级”需求。'},
 {'name':'文化与艺术','kw':['文化','艺术','文学','诗词','书法','美学'],
  'explain':'文学、诗词、艺术流变，理解文化表达与审美。'},
],
}

# ---------- 聚类：每个知识点匹配视频 ----------
for d, kps in TAX.items():
    for kp in kps:
        matches = [v for v in data if d in v['dirs'] and any(k.lower() in text(v) for k in kp['kw'])]
        kp['videos'] = sorted(matches, key=lambda v: v['play'], reverse=True)
        kp['cov'] = len(matches)
        kp['play_sum'] = sum(v['play'] for v in matches)

# 全知识区最热知识点 TOP10（按覆盖视频数）
all_kp = [(d, kp) for d, kps in TAX.items() for kp in kps if kp['cov'] > 0]
all_kp.sort(key=lambda x: x[1]['cov'], reverse=True)
top10 = all_kp[:10]

# 当下热门具体词/新词（在标题中出现的频次）
HOT_TERMS = ['deepseek','qwen','通义','智谱','glm','claude','gpt-5','gpt5','gemini','llama','文心','kimi','豆包',
             'rtx 5090','5090','骁龙','鸿蒙','m4','玄戒','麒麟','相对论','量子计算','sora','midjourney','stable diffusion']
term_cnt = Counter()
for v in data:
    t = v['title'].lower()
    for term in HOT_TERMS:
        if term in t:
            term_cnt[term] += 1
hot_terms = [(k, c) for k, c in term_cnt.most_common() if c > 0]

# ---------- SVG ----------
def hbar(items, color='#FB7299', width=620):
    maxv = max(v for _, v in items) or 1; rowh, gap = 26, 8; rows = ''
    for i, (lab, val) in enumerate(items):
        y = i*(rowh+gap); bw = max(3, val/maxv*(width-220))
        rows += (f'<g transform="translate(0,{y})"><text x="0" y="{rowh/2}" dominant-baseline="middle" font-size="12.5" fill="#333">{lab}</text>'
                 f'<rect x="170" y="4" width="{bw:.0f}" height="{rowh-8}" rx="3" fill="{color}"/>'
                 f'<text x="{170+bw+6:.0f}" y="{rowh/2}" dominant-baseline="middle" font-size="11.5" fill="#777">{val}</text></g>')
    return f'<svg width="{width}" height="{len(items)*(rowh+gap)}" viewBox="0 0 {width} {len(items)*(rowh+gap)}" style="max-width:100%">{rows}</svg>'

DIR_COLOR = {'传统理论科目':'#23ADE5','AI/人工智能':'#FB7299','电子设备':'#7ED321','科学科普':'#9B59B6','人文历史':'#FFB027'}
DIR_EMOJI = {'传统理论科目':'📐','AI/人工智能':'🤖','电子设备':'🔧','科学科普':'🔭','人文历史':'🏛️'}

def video_list(vs, n=3):
    r = ''
    for i, v in enumerate(vs[:n], 1):
        r += (f'<li><a href="https://www.bilibili.com/video/{v.get("bvid")}" target="_blank" style="color:#23ADE5;text-decoration:none">{v["title"][:34]}</a>'
               f' <span style="color:#999">· {v["author"][:8]} · {v["play"]/10000:.0f}万</span></li>')
    return r

# 最热 TOP10 图
top10_svg = hbar([(f'{kp["name"]}', kp['cov']) for _, kp in top10], '#FB7299', 620)

# 方向区块
dir_sections = ''
total_kp_cov = 0
for d, kps in TAX.items():
    covered = [kp for kp in kps if kp['cov'] > 0]
    total_kp_cov += len(covered)
    cards = ''
    for kp in sorted(covered, key=lambda x: x['cov'], reverse=True):
        cards += f'''<div class="kpcard">
          <div class="kptop"><span class="kpname">{kp['name']}</span>
            <span class="badge">🔥 {kp['cov']} 个热门视频 · 总播放 {kp['play_sum']/10000:.0f}万</span></div>
          <div class="kpex">{kp['explain']}</div>
          <ul class="kpvideos">{video_list(kp['videos'],3)}</ul>
        </div>'''
    dir_sections += f'''<section>
      <h2>{DIR_EMOJI[d]} {d} <span style="font-size:13px;color:#999;font-weight:400">· 覆盖 {len(covered)} 个知识点</span></h2>
      <div class="kpwrap">{cards}</div>
    </section>'''

hot_terms_html = ''.join(f'<span class="tag">{k} {c}</span>' for k, c in hot_terms) or '<span class="tag">（标题中未检出显著高频新词）</span>'

total_cov_kp = len(all_kp)
html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>知识区爆款背后的知识点</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f7;color:#222;line-height:1.6}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 18px 60px}}
header{{background:linear-gradient(135deg,#23ADE5,#9B59B6);color:#fff;border-radius:16px;padding:30px 28px;margin-bottom:22px}}
header h1{{font-size:26px;margin-bottom:8px}} header p{{opacity:.92;font-size:14px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}}
.card{{flex:1;min-width:140px;background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
.card .n{{font-size:24px;font-weight:800;color:#9B59B6}} .card .l{{font-size:13px;color:#888;margin-top:4px}}
section{{background:#fff;border-radius:14px;padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
section h2{{font-size:18px;margin-bottom:16px}}
.note{{background:#eef9ff;border-left:4px solid #23ADE5;border-radius:0 10px 10px 0;padding:14px 18px;margin:14px 0;font-size:14px}}
.note b{{color:#23ADE5}}
.kpwrap{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.kpcard{{border:1px solid #eee;border-radius:12px;padding:14px 16px;background:#fcfcfd}}
.kptop{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap}}
.kpname{{font-size:15px;font-weight:700;color:#333}}
.badge{{font-size:11.5px;color:#FB7299;background:#fdeef5;border-radius:6px;padding:2px 8px;white-space:nowrap}}
.kpex{{font-size:13px;color:#555;margin:8px 0}}
.kpvideos{{margin:6px 0 0;padding-left:18px;font-size:12.5px;line-height:1.8}}
.kpvideos li{{margin:2px 0}}
.tag{{display:inline-block;background:#eafaf0;color:#1a9e4b;border-radius:6px;padding:3px 9px;font-size:12px;margin:3px}}
@media(max-width:680px){{.kpwrap{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

<header>
  <h1>📚 知识区爆款「背后的知识点」报告</h1>
  <p>数据抓取于 {TODAY} · 样本 {N} 条（公开搜索接口，按「方向关键词 + 播放量排序」抓取、去重）· 本报告从"爆款统计"转向"知识点梳理"：把热门视频按知识点聚类，每个知识点讲清"是什么、谁在讲、有多热"</p>
</header>

<div class="cards">
  <div class="card"><div class="n">{N}</div><div class="l">有效样本（条）</div></div>
  <div class="card"><div class="n">5</div><div class="l">覆盖方向</div></div>
  <div class="card"><div class="n">{total_cov_kp}</div><div class="l">命中的知识点</div></div>
  <div class="card"><div class="n">{top10[0][1]['name'] if top10 else '—'}</div><div class="l">最热知识点</div></div>
</div>

<section>
  <h2>🌟 全知识区最热知识点 TOP10</h2>
  <div class="desc" style="font-size:13px;color:#999;margin-bottom:14px">按"覆盖的热门视频数"排序——数字越大，说明越多爆款在讲这个知识点。</div>
  <div class="chart" style="overflow-x:auto">{top10_svg}</div>
  <div class="note">💡 这张图直接回答"大家现在在学什么"：排名越靠前，越是当下被集中讨论、值得你优先做内容的知识点。</div>
</section>

{dir_sections}

<section>
  <h2>🔥 当下热门具体词 / 新词</h2>
  <div class="desc" style="font-size:13px;color:#999;margin-bottom:14px">在热门视频标题中出现频次最高的具体实体/新概念——反映正在被集中讨论的"具体事物"。</div>
  <div>{hot_terms_html}</div>
  <div class="note">💡 这些词是"知识点"的具象化：比如 DeepSeek / 5090 / Sora 一旦出现，就对应一个大知识点风口，可据此快速定位选题。</div>
</section>

<div style="text-align:center;color:#bbb;font-size:12px;margin-top:30px">
  本报告由 WorkBuddy 基于 B站公开搜索接口自动生成 · 知识点聚类基于标题/标签/简介关键词匹配，定义为辅助理解用；数据为「关键词+播放排序」样本，非官方排行榜
</div>
</div></body></html>'''

outdir = os.path.join(BASE, 'reports', BATCH)
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, f'知识区爆款背后的知识点报告_{TODAY}.html')
_i = 2
while os.path.exists(out):          # 同日重跑自动加序号，绝不覆盖旧文档
    out = os.path.join(outdir, f'知识区爆款背后的知识点报告_{TODAY}_{_i}.html')
    _i += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('生成成功:', out)
print(f'样本 {N} 条，命中知识点 {total_cov_kp} 个')
print('各方向命中:', {d: sum(1 for kp in kps if kp["cov"]>0) for d, kps in TAX.items()})
print('\n最热知识点 TOP10:')
for d, kp in top10:
    print(f'  [{d}] {kp["name"]}: {kp["cov"]}视频 / {kp["play_sum"]/10000:.0f}万播放')
print('\n热门具体词:', hot_terms[:12])
