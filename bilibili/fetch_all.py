# -*- coding: utf-8 -*-
"""抓取 B站全站排行榜 + 全站热门，刷新 data/ 当前副本，并在 reports/<批次>/data/ 留存历史快照。

关于 -352：B站对匿名高频请求会返回 code=-352（风控拦截）。实测连续请求几次就会触发，
表现为「榜单全部抓空、但程序不报错」，报告就会静默使用旧数据。
处理方式：
  1) 先取 buvid3/buvid4 放进 Cookie（匿名身份，显著降低被拦概率）
  2) 带 code 校验的重试（退避 3/6/9 秒）
  3) 抓空时明确打印警告，并写 fetch_meta.json 记录本次各分区状态，
     让下游知道哪些数据是新的、哪些是沿用的旧快照
"""
import urllib.request, json, time, os, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))   # bilibili/
DATA = os.path.join(ROOT, 'data')
TODAY = datetime.date.today().strftime('%Y-%m-%d')
BATCH = os.environ.get('BZ_BATCH') or TODAY
SNAP = os.path.join(ROOT, 'reports', BATCH, 'data')
os.makedirs(DATA, exist_ok=True)
os.makedirs(SNAP, exist_ok=True)

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')


def get_cookie():
    """取 buvid3/buvid4 作为匿名身份。失败返回空串，退回纯匿名请求。"""
    hdr = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com'}
    try:
        with urllib.request.urlopen(urllib.request.Request(
                'https://api.bilibili.com/x/frontend/finger/spi', headers=hdr), timeout=20) as r:
            spi = json.loads(r.read().decode('utf-8')).get('data', {}) or {}
        if spi.get('b_3') and spi.get('b_4'):
            return f"buvid3={spi['b_3']}; buvid4={spi['b_4']}"
    except Exception as e:
        print(f'  提示：buvid 获取失败（{e}），退回匿名请求')
    return ''


HDR = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com'}
_cookie = get_cookie()
if _cookie:
    HDR['Cookie'] = _cookie


def fetch(url, tries=3):
    """带 code 校验与退避重试。B站风控时返回 code=-352，必须当成失败而不是空数据。"""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode('utf-8'))
            code = d.get('code')
            if code not in (0, None):
                raise RuntimeError(f'接口返回 code={code} {d.get("message","")}')
            return d
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(3 * (i + 1))
    raise RuntimeError(last)


def save(name, obj):
    payload = json.dumps(obj, ensure_ascii=False, indent=2)
    for d in (DATA, SNAP):
        with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
            f.write(payload)


meta = {'fetched_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cookie': bool(_cookie), 'rank': {}, 'pop_ok': 0}

# 分区排行榜（知识/生活/鬼畜在 ranking/v2 返回 -400，故不抓）
cats = {'all': 0, 'game': 4, 'tech': 188, 'anime': 1, 'movie': 181}
rank_ok = 0
for name, rid in cats.items():
    try:
        d = fetch(f'https://api.bilibili.com/x/web-interface/ranking/v2?rid={rid}&type=all')
        items = (d.get('data') or {}).get('list') or []
        if items:
            save(f'rank_{name}.json', items)
            meta['rank'][name] = {'count': len(items), 'fresh': True}
            rank_ok += 1
            print(f'  rank_{name}: {len(items)} 条')
        else:
            meta['rank'][name] = {'count': 0, 'fresh': False}
            print(f'  rank_{name}: 返回空（沿用上次快照）')
    except Exception as e:
        meta['rank'][name] = {'count': 0, 'fresh': False, 'error': str(e)[:120]}
        print(f'  rank_{name}: 失败 {str(e)[:80]}（沿用上次快照）')
    time.sleep(1.2)

# 全站热门 6 页，按 aid 去重
all_items, seen = [], set()
for pn in range(1, 7):
    try:
        d = fetch(f'https://api.bilibili.com/x/web-interface/popular?ps=50&pn={pn}')
        got = (d.get('data') or {}).get('list') or []
        for v in got:
            aid = v.get('aid')
            if aid and aid not in seen:
                seen.add(aid)
                all_items.append(v)
        if got:
            meta['pop_ok'] += 1
    except Exception as e:
        print(f'  popular pn={pn}: 失败 {str(e)[:80]}')
    time.sleep(1.2)

if not all_items:
    raise SystemExit('错误：全站热门抓取为空，中止（避免用旧数据生成标注新日期的报告）')
save('popular.json', all_items)
print(f'  popular: {len(all_items)} 条（去重，{meta["pop_ok"]}/6 页成功）')

# 榜单全部抓空时明确告警：报告将以热门榜为主，排行榜部分沿用旧快照
if rank_ok == 0:
    print('  [警告] 榜单接口全部被风控（-352），本次排行榜数据沿用上次快照；'
          '报告中的「分区榜」统计可能不是最新。')
elif rank_ok < len(cats):
    print(f'  [提示] {len(cats)-rank_ok}/{len(cats)} 个分区榜未取到，对应部分沿用旧快照。')

for d in (DATA, SNAP):
    with open(os.path.join(d, 'fetch_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

print('数据快照:', SNAP)
