# -*- coding: utf-8 -*-
"""抓取 GitHub 热点：三张榜 + TOP 项目 README（用于技术路线判断）。

三张榜（GitHub Search API，未认证限速 10 次/分钟，这里只用 3 次）：
  A 新星榜   created:>7天前        sort=stars   本周新建且飙升 → 真正的新鲜事
  B 成长榜   created:30..7天前      sort=stars   仍在新秀期，热度未退 → 看趋势是否持续
  C 活跃榜   stars:>5000 pushed:>3天前 sort=stars 长青项目的近期动作 → 看老赛道在动什么

为什么要抓 README（前 4000 字符）：
  只看 star 和描述分不清「原创工具」和「资源合集 / prompt 套壳」。
  README 里的安装方式、依赖栈、"built on top of" 之类表述，是判断技术路线的第一手材料。
"""
import urllib.request, urllib.parse, json, time, os, datetime, re, base64

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
TODAY = datetime.date.today()
TODAY_S = TODAY.strftime('%Y-%m-%d')
BATCH = os.environ.get('BZ_BATCH') or TODAY_S
SNAP = os.path.join(ROOT, 'reports', BATCH, 'data')
os.makedirs(DATA, exist_ok=True)
os.makedirs(SNAP, exist_ok=True)

HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/vnd.github+json',
}

D7 = (TODAY - datetime.timedelta(days=7)).isoformat()
D30 = (TODAY - datetime.timedelta(days=30)).isoformat()
D3 = (TODAY - datetime.timedelta(days=3)).isoformat()

QUERIES = [
    ('new', f'created:>{D7}', '新星榜 · 近 7 天新建', 100),
    ('growing', f'created:{D30}..{D7}', '成长榜 · 8–30 天', 100),
    ('active', f'stars:>5000 pushed:>{D3}', '活跃榜 · 万星项目近期动态', 50),
]


def fetch_json(url, tries=4, wait=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode('utf-8'))
                rem = r.headers.get('X-RateLimit-Remaining')
                if rem is not None:
                    print(f'    剩余配额 {rem}')
                return body
        except Exception as e:
            last = e
            time.sleep(wait * (i + 1))
    raise RuntimeError(f'抓取失败 {url}: {last}')


def fetch_readme(full_name):
    """取 README 原文（HEAD ref，免去判断默认分支）。失败返回空串，不阻断主流程。"""
    for fn in ('README.md', 'readme.md', 'README.MD'):
        try:
            url = f'https://raw.githubusercontent.com/{full_name}/HEAD/{fn}'
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode('utf-8', 'replace')[:4000]
        except Exception:
            continue
    return ''


repos = {}
meta = {}
for key, q, label, per in QUERIES:
    try:
        d = fetch_json(
            f'https://api.github.com/search/repositories'
            f'?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page={per}')
    except Exception as e:
        print(f'  [{key}] 失败: {e}')
        meta[key] = {'label': label, 'query': q, 'count': 0, 'error': str(e)}
        continue
    items = d.get('items') or []
    meta[key] = {'label': label, 'query': q, 'count': len(items)}
    for it in items:
        rid = it.get('id')
        if not rid:
            continue
        if rid not in repos:
            it['_sources'] = [key]
            repos[rid] = it
        else:
            repos[rid]['_sources'].append(key)
    print(f'  [{key}] {label}: {len(items)} 条（total_count={d.get("total_count")}）')
    time.sleep(2.5)     # 未认证搜索限速 10 次/分钟，留余量

if len(repos) < 100:
    raise SystemExit(f'错误：GitHub 仅取到 {len(repos)} 个仓库（预期 >=100），中止，避免残缺样本')

items = list(repos.values())

# README 只抓「本周热点」= 新星榜 + 成长榜各自的高星项目。
# 若按全库 star 排序，名额会被 linux / tensorflow 这类长青项目占满，读不到真正的新东西。
by_src = {'new': [], 'growing': [], 'active': []}
for it in items:
    for s in it.get('_sources', []):
        by_src.setdefault(s, []).append(it)

targets, seen_id = [], set()
for s in ('new', 'growing'):
    for it in sorted(by_src[s], key=lambda x: x.get('stargazers_count', 0), reverse=True)[:12]:
        if it.get('id') not in seen_id:
            seen_id.add(it.get('id'))
            targets.append(it)

for i, it in enumerate(targets, 1):
    it['_readme'] = fetch_readme(it['full_name'])
    print(f'    README {i}/{len(targets)}: {it["full_name"]} ({len(it["_readme"])} 字符)')
    time.sleep(0.2)
for it in items:
    it.setdefault('_readme', '')

payload = {
    'fetched_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'queries': meta,
    'repos': items,
}
text = json.dumps(payload, ensure_ascii=False, indent=2)
for d in (DATA, SNAP):
    with open(os.path.join(d, 'repos_raw.json'), 'w', encoding='utf-8') as f:
        f.write(text)

with_readme = sum(1 for it in items if it.get('_readme'))
print(f'  合计 {len(items)} 个仓库（去重后），{with_readme} 个取到 README')
print('数据快照:', SNAP)
