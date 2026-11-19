# -*- coding: utf-8 -*-
"""抓取知乎热榜 + 知乎日报，刷新 data/ 当前副本，并在 <批次>/data/ 留存历史快照。

数据源（均为公开接口，无需登录）：
  - 热榜   https://api.zhihu.com/topstory/hot-list?limit=50   固定返回 30 条
  - 日报   https://news-at.zhihu.com/api/4/news/latest        编辑精选，天然偏「有价值」

设计取舍：
  热榜只有 30 条且娱乐化严重，单靠它做分析样本太薄、结论会失真；
  因此额外接入「知乎日报」（人工编辑筛选的深度内容），两类源分开存储、
  在报告里分别标注来源，避免把自己拼的数据说成平台官方榜单。
"""
import urllib.request, json, time, os, datetime, re

ROOT = os.path.dirname(os.path.abspath(__file__))   # 知乎热点/
DATA = os.path.join(ROOT, 'data')
TODAY = datetime.date.today().strftime('%Y-%m-%d')
BATCH = os.environ.get('BZ_BATCH') or TODAY
SNAP = os.path.join(ROOT, 'reports', BATCH, 'data')
os.makedirs(DATA, exist_ok=True)
os.makedirs(SNAP, exist_ok=True)

HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.zhihu.com/hot',
    'Accept': 'application/json, text/plain, */*',
}

HOT_URL = 'https://api.zhihu.com/topstory/hot-list?limit=50'
DAILY_URL = 'https://news-at.zhihu.com/api/4/news/latest'


def fetch_json(url, tries=4, wait=2):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:      # 网络抖动 / 偶发 403 都重试
            last = e
            time.sleep(wait * (i + 1))
    raise RuntimeError(f'抓取失败 {url}: {last}')


def parse_heat(txt):
    """'1595 万热度' -> 15950000；无法解析返回 None（报告里如实留空，不猜）。"""
    if not txt:
        return None
    m = re.search(r'([\d.]+)\s*(万|亿)?', str(txt))
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2)
    if unit == '亿':
        n *= 1e8
    elif unit == '万':
        n *= 1e4
    return int(n)


def qid_to_url(u):
    """api.zhihu.com/questions/xxx -> www.zhihu.com/question/xxx（给人点的链接）"""
    m = re.search(r'/(\d+)', u or '')
    return f'https://www.zhihu.com/question/{m.group(1)}' if m else (u or '')


# ---------- 1. 热榜 ----------
raw_hot = fetch_json(HOT_URL)
feeds = raw_hot.get('data', []) or []
hot = []
for rank, it in enumerate(feeds, 1):
    t = it.get('target') or {}
    if not t.get('title'):
        continue
    hot.append({
        'rank': rank,
        'id': t.get('id'),
        'title': t['title'].strip(),
        'url': qid_to_url(t.get('url')),
        'excerpt': (t.get('excerpt') or '').strip(),
        'answer_count': t.get('answer_count') or 0,
        'follower_count': t.get('follower_count') or 0,
        'comment_count': t.get('comment_count') or 0,
        'heat_text': it.get('detail_text') or '',
        'heat': parse_heat(it.get('detail_text')),
        'created': t.get('created'),
        'source': 'hot',
    })

if len(hot) < 20:
    raise SystemExit(f'错误：知乎热榜仅取到 {len(hot)} 条（预期 >=20），中止，避免用残缺样本出报告')

# ---------- 2. 知乎日报（补充深度内容） ----------
daily = []
try:
    d = fetch_json(DAILY_URL, tries=3, wait=2)
    for s in (d.get('stories') or []):
        daily.append({
            'title': (s.get('title') or '').strip(),
            'url': s.get('url') or '',
            'hint': s.get('hint') or '',
            'source': 'daily',
        })
except Exception as e:
    print(f'  [警告] 知乎日报抓取失败（{e}），仅用热榜数据；报告会标注日报缺失')

payload = {
    'fetched_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'hot_url': HOT_URL,
    'daily_url': DAILY_URL,
    'hot': hot,
    'daily': daily,
}

text = json.dumps(payload, ensure_ascii=False, indent=2)
for d in (DATA, SNAP):
    with open(os.path.join(d, 'zhihu_raw.json'), 'w', encoding='utf-8') as f:
        f.write(text)

print(f'  热榜: {len(hot)} 条')
print(f'  日报: {len(daily)} 条' + ('（接口未返回）' if not daily else ''))
print('数据快照:', SNAP)
