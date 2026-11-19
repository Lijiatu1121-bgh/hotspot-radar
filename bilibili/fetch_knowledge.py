# -*- coding: utf-8 -*-
"""抓取 B站知识区热点视频（按方向关键词 + 播放量排序），去重后存盘。"""
import urllib.request, json, time, hashlib, urllib.parse, re, os, datetime
from collections import Counter

# ---------- wbi 签名 ----------
def get_mixin_key(a, b):
    raw = a + b
    enc = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,
           37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
    return ''.join(raw[enc[i]] for i in range(32))

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def get_session():
    """取 wbi 签名 key + buvid3/buvid4。匿名搜索接口带 buvid 身份可显著降低被限流概率。"""
    base_hdr = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com'}
    cookie = ''
    try:
        with urllib.request.urlopen(urllib.request.Request(
                'https://api.bilibili.com/x/frontend/finger/spi', headers=base_hdr), timeout=20) as r:
            spi = json.loads(r.read().decode('utf-8')).get('data', {})
        if spi.get('b_3') and spi.get('b_4'):
            cookie = f"buvid3={spi['b_3']}; buvid4={spi['b_4']}"
    except Exception as e:
        print('提示：buvid 获取失败，将使用匿名请求:', e)
    with urllib.request.urlopen(urllib.request.Request(
            'https://api.bilibili.com/x/web-interface/nav',
            headers=dict(base_hdr, Cookie=cookie) if cookie else base_hdr), timeout=20) as r:
        d = json.loads(r.read().decode('utf-8'))
    wbi = d['data']['wbi_img']
    return (wbi['img_url'].rsplit('/',1)[1].split('.')[0],
            wbi['sub_url'].rsplit('/',1)[1].split('.')[0], cookie)

def sign(p, mk):
    p['wts'] = int(time.time())
    p = {k: p[k] for k in sorted(p)}
    q = urllib.parse.urlencode(p)
    return q + '&w_rid=' + hashlib.md5((q+mk).encode()).hexdigest()

_img, _sub, BUV_COOKIE = get_session()
mk = get_mixin_key(_img, _sub)
hdr = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com'}
if BUV_COOKIE:
    hdr['Cookie'] = BUV_COOKIE

def fetch(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))

def parse_count(x):
    if x is None: return 0
    if isinstance(x, (int, float)): return int(x)
    s = str(x).strip()
    if not s: return 0
    m = re.match(r'^([\d.]+)\s*(万|亿)?', s)
    if m:
        v = float(m.group(1)); u = m.group(2)
        if u == '万': v *= 1e4
        elif u == '亿': v *= 1e8
        return int(v)
    return 0

def dur2sec(d):
    if d is None: return 0
    if isinstance(d, int):
        return d/1000 if d > 100000 else d  # >100000秒视为毫秒单位
    s = str(d)
    if ':' in s:
        p = [int(x) for x in s.split(':')]
        return p[0]*3600+p[1]*60+p[2] if len(p)==3 else (p[0]*60+p[1] if len(p)==2 else p[0])
    return parse_count(s)

# ---------- 知识区方向关键词 ----------
# 注意：传统理论科目方向已排除「高中」内容（见下方抓取过滤），以后不再抓取高中知识区。
kw_dirs = {
    '人工智能':'AI/人工智能','大模型':'AI/人工智能','机器学习':'AI/人工智能','ChatGPT':'AI/人工智能',
    '物理':'传统理论科目','数学':'传统理论科目','历史':'传统理论科目','化学':'传统理论科目',
    '生物':'传统理论科目','哲学':'传统理论科目',
    '手机评测':'电子设备','笔记本':'电子设备','数码':'电子设备','耳机':'电子设备','相机':'电子设备',
    '硬件':'电子设备','显卡':'电子设备','CPU':'电子设备',
    '科普':'科学科普','宇宙':'科学科普','量子':'科学科普','科学':'科学科普','天文':'科学科普',
    '考古':'人文历史','文化':'人文历史','文物':'人文历史','古代史':'人文历史',
}

videos = {}
SEARCH = 'https://api.bilibili.com/x/web-interface/wbi/search/all/v2?'
fail_kw = []
for kw, direction in kw_dirs.items():
    for page in (1, 2):
        for attempt in range(4):   # 接口限流/空结果时重试，每次重新签名（wts 时效）
            p = {'keyword':kw,'search_type':'video','order':'click','page':page}
            try:
                d = fetch(SEARCH + sign(p, mk))
                if d.get('code') != 0:
                    raise RuntimeError(f"code={d.get('code')} {d.get('message')}")
                vids = [v for g in d.get('data', {}).get('result', [])
                        if g.get('result_type') == 'video' for v in g.get('data', [])]
                if not vids:
                    raise RuntimeError('返回空结果（疑似限流）')
                for v in vids:
                    aid = v.get('aid')
                    if not aid:
                        continue
                    play = parse_count(v.get('play'))
                    if play <= 0:
                        continue
                    clean_title = re.sub(r'<[^>]+>', '', v.get('title',''))
                    # 排除「高中」知识内容：传统理论科目方向下，标题/标签含「高中」则跳过（以后不再抓取）
                    if direction == '传统理论科目' and '高中' in (clean_title + ' ' + (v.get('tag') or '')):
                        continue
                    rec = videos.get(aid)
                    if rec is None:
                        rec = {
                            'aid': aid, 'bvid': v.get('bvid'),
                            'title': clean_title,
                            'author': v.get('author') or v.get('uname',''),
                            'play': play,
                            'danmaku': parse_count(v.get('danmaku')),
                            'review': parse_count(v.get('review')),
                            'favorites': parse_count(v.get('favorites')),
                            'like': parse_count(v.get('like')),
                            'duration': dur2sec(v.get('duration')),
                            'pubdate': v.get('pubdate') or v.get('senddate') or 0,
                            'typename': v.get('typename',''),
                            'tag': v.get('tag',''),
                            'description': re.sub(r'<[^>]+>', '', (v.get('description') or ''))[:300],
                            'dirs': set(),
                        }
                        videos[aid] = rec
                    rec['dirs'].add(direction)
                break
            except Exception as e:
                if attempt < 3:
                    time.sleep(2.0 * (attempt + 1))
                else:
                    fail_kw.append(f'{kw}/p{page}: {e}')
        time.sleep(0.9)   # 拉长间隔，降低被限流概率
if fail_kw:
    print(f'警告：{len(fail_kw)} 个关键词/分页连续 4 次失败，已跳过')

for r in videos.values():
    r['dirs'] = sorted(r['dirs'])

data = list(videos.values())

# 完整性校验（必须在写文件之前）：疑似限流导致缺方向/总量过低时中止，保留上一次数据
dc = Counter()
for r in data:
    for d in r['dirs']:
        dc[d] += 1
need = set(kw_dirs.values())
missing = sorted(need - set(dc))
MIN_TOTAL = 300
if missing or len(data) < MIN_TOTAL:
    raise SystemExit(
        f'错误：抓取不完整（总数 {len(data)} 条，最低要求 {MIN_TOTAL}；缺失方向 {missing}），'
        f'疑似 B站接口限流。中止并保留上一次数据，不生成残缺报告。'
    )

base = os.path.dirname(os.path.abspath(__file__))   # 知识热点/
TODAY = datetime.date.today().strftime('%Y-%m-%d')
BATCH = os.environ.get('BZ_BATCH') or TODAY   # scripts/run_all.py 统一分配的「每次独立文件夹」
os.makedirs(os.path.join(base, 'data'), exist_ok=True)
payload = json.dumps(data, ensure_ascii=False, indent=2)
# 当前工作副本（供报告脚本读取）
with open(os.path.join(base, 'data', 'knowledge_raw.json'), 'w', encoding='utf-8') as f:
    f.write(payload)
# 本次批次的历史快照（放进本次独立文件夹，绝不覆盖旧数据）
snap = os.path.join(base, 'reports', BATCH, 'data')
os.makedirs(snap, exist_ok=True)
with open(os.path.join(snap, 'knowledge_raw.json'), 'w', encoding='utf-8') as f:
    f.write(payload)
print('数据快照:', snap)

print('总去重视频:', len(data))
for k, c in dc.most_common():
    print(f'  {k}: {c}')
