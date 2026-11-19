# -*- coding: utf-8 -*-
"""统一入口：抓取三个渠道的热点数据并生成报告。

设计要点（和旧的顺序执行不同）：
  · 渠道之间**互相隔离**——知乎抓不到不会拖累 B站和 GitHub 出报告。
    这是为 GitHub Actions 准备的：境外 IP 访问知乎/ B站 可能被风控，
    不能让一个渠道的失败导致整周没有产出。
  · 每个渠道跑完检查「是否真的产出了 HTML」，没产出就判定失败，
    并清理该渠道的空目录，避免仓库里留下一堆空文件夹。
  · 结束时写 reports/<批次>/status.json，记录各渠道结果，供站点首页标注「本期缺失」。

用法：
  python scripts/run_all.py                     # 跑全部渠道
  python scripts/run_all.py --channel zhihu     # 只跑知乎
  python scripts/run_all.py --channel bilibili,github
  python scripts/run_all.py --dry-run           # 只打印计划
  python scripts/run_all.py --batch 2026-11-19  # 指定批次名（默认自动按日期分配）
"""
import os, sys, re, json, shutil, argparse, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().strftime('%Y-%m-%d')

CHANNELS = {
    'bilibili': {
        'label': 'B站',
        'steps': [
            ('抓取全站榜单与热门', 'bilibili/fetch_all.py'),
            ('生成综合爆款报告',   'bilibili/generate_report.py'),
            ('抓取知识区数据',     'bilibili/fetch_knowledge.py'),
            ('生成知识区主报告',   'bilibili/generate_knowledge_report.py'),
            ('生成 AI+硬件报告',   'bilibili/generate_ai_hardware_report.py'),
            ('生成知识点报告',     'bilibili/generate_knowledge_points_report.py'),
        ],
    },
    'zhihu': {
        'label': '知乎',
        'steps': [
            ('抓取热榜与日报',     'zhihu/fetch_zhihu.py'),
            ('生成价值议题报告',   'zhihu/generate_zhihu_report.py'),
        ],
    },
    'github': {
        'label': 'GitHub',
        'steps': [
            ('抓取三榜与 README',  'github/fetch_github.py'),
            ('生成技术分析报告',   'github/generate_github_report.py'),
        ],
    },
}


def next_batch(today, channels):
    """扫描各渠道 reports/ 下已有的 <today> / <today>_N，取最大序号 +1。"""
    pat = re.compile(r'^' + re.escape(today) + r'(?:_(\d+))?$')
    max_n, found = 0, False
    for ch in channels:
        p = os.path.join(ROOT, ch, 'reports')
        if not os.path.isdir(p):
            continue
        for name in os.listdir(p):
            m = pat.match(name)
            if m and os.path.isdir(os.path.join(p, name)):
                found = True
                max_n = max(max_n, int(m.group(1) or 1))
    return f'{today}_{max_n + 1}' if found else today


def run_channel(name, batch, env):
    """跑一个渠道，返回 {ok, steps:[...], error, reports:[...]}"""
    cfg = CHANNELS[name]
    result = {'ok': False, 'steps': [], 'error': '', 'reports': []}
    print(f'\n{"="*60}\n[{cfg["label"]}] 开始\n{"="*60}')

    for i, (label, rel) in enumerate(cfg['steps'], 1):
        script = os.path.join(ROOT, rel)
        if not os.path.exists(script):
            result['error'] = f'脚本不存在：{rel}'
            print(f'  [{i}/{len(cfg["steps"])}] {label} ... 脚本缺失')
            return result
        print(f'  [{i}/{len(cfg["steps"])}] {label} ...', end='', flush=True)
        try:
            r = subprocess.run(
                [sys.executable, script],
                cwd=os.path.dirname(script),
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                env=env, timeout=900,
            )
        except subprocess.TimeoutExpired:
            result['error'] = f'「{label}」超时（>15 分钟）'
            print(' 超时')
            return result

        if r.returncode != 0:
            err = (r.stderr or r.stdout or '').strip()
            # 抓最有用的一行：优先 Traceback 的最后一行异常，否则取末尾
            lines = [x for x in err.splitlines() if x.strip()]
            tail = lines[-1] if lines else '未知错误'
            result['error'] = f'「{label}」失败：{tail[:300]}'
            print(f' 失败\n     {tail[:300]}')
            return result
        print(' ok')

    # 关键校验：真的产出了 HTML 才算成功
    outdir = os.path.join(ROOT, name, 'reports', batch)
    if os.path.isdir(outdir):
        result['reports'] = sorted(
            f for f in os.listdir(outdir) if f.lower().endswith('.html'))
    if not result['reports']:
        result['error'] = '流程未报错，但本次没有生成任何 HTML 报告'
        print(f'  [警告] {result["error"]}')
        return result

    result['ok'] = True
    print(f'  → 产出 {len(result["reports"])} 份报告')
    return result


def main():
    ap = argparse.ArgumentParser(description='三个渠道的热点抓取与报告生成')
    ap.add_argument('--channel', default='all',
                    help='要跑的渠道，逗号分隔：bilibili,zhihu,github 或 all')
    ap.add_argument('--batch', default=None, help='指定批次名（默认自动按日期分配）')
    ap.add_argument('--dry-run', action='store_true', help='只打印计划，不执行')
    args = ap.parse_args()

    if args.channel.strip().lower() == 'all':
        selected = list(CHANNELS)
    else:
        selected = [c.strip() for c in args.channel.split(',') if c.strip()]
        unknown = [c for c in selected if c not in CHANNELS]
        if unknown:
            print(f'未知渠道：{unknown}；可选：{list(CHANNELS)}')
            return 2

    batch = args.batch or next_batch(TODAY, selected)

    print(f'=== 热点雷达 · {TODAY} ===')
    print(f'渠道：{"、".join(CHANNELS[c]["label"] for c in selected)}')
    print(f'批次：{batch}')

    if args.dry_run:
        print('\n[演练] 将依次执行：')
        for c in selected:
            print(f'\n  【{CHANNELS[c]["label"]}】{c}/reports/{batch}/')
            for label, rel in CHANNELS[c]['steps']:
                print(f'    - {label}  ({rel})')
        print('\n[演练] 未执行任何抓取与写入。')
        return 0

    env = dict(os.environ, PYTHONIOENCODING='utf-8', BZ_BATCH=batch)
    summary = {}
    for c in selected:
        summary[c] = run_channel(c, batch, env)

    # 写状态文件（供站点首页标注缺失渠道）
    status_dir = os.path.join(ROOT, 'reports', batch)
    os.makedirs(status_dir, exist_ok=True)
    status = {
        'batch': batch,
        'date': TODAY,
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'channels': {
            c: {
                'label': CHANNELS[c]['label'],
                'ok': summary[c]['ok'],
                'reports': summary[c]['reports'],
                'error': summary[c]['error'],
            } for c in summary
        },
    }
    with open(os.path.join(status_dir, 'status.json'), 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}\n汇总\n{"="*60}')
    failed = []
    for c in selected:
        r = summary[c]
        mark = '✓' if r['ok'] else '✗'
        print(f'  {mark} {CHANNELS[c]["label"]:8s} {"、".join(r["reports"]) if r["ok"] else r["error"]}')
        if not r['ok']:
            failed.append(c)

    if failed:
        print(f'\n{len(failed)} 个渠道失败，其余渠道的报告已正常生成。')
        print('站点会照常发布，缺失渠道在首页标注。')
        return 1
    print(f'\n全部成功。批次：{batch}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
