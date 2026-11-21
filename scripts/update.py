# -*- coding: utf-8 -*-
"""一键更新：抓取三个渠道 → 生成站点 → 提交并推送到 GitHub。

这就是每周只需要跑的那一条命令。

用法：
  python scripts/update.py                # 完整流程（抓取 + 建站 + 提交 + 推送）
  python scripts/update.py --no-push      # 只到提交，不推送（先本地看看效果）
  python scripts/update.py --site-only    # 不抓数据，只重建站点（改了模板后用）
  python scripts/update.py --channel zhihu  # 只更新某一个渠道

注意：
  · 推送需要先配置好 GitHub 凭据（一次配置，之后免密/令牌自动生效）。
  · 首次使用请先按 README 的「第一次配置」建好远程仓库。
"""
import os, sys, subprocess, datetime, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().strftime('%Y-%m-%d')


def run(cmd, cwd=None, capture=True):
    return subprocess.run(cmd, cwd=cwd or ROOT, capture_output=capture,
                          text=True, encoding='utf-8', errors='replace')


def git(*args, check=False):
    r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or '').strip())
    return r


def latest_batch():
    """找出本地最新的报告批次名。

    commit message 若用「运行日期」，补推昨天报告时会写成今天，误导自己。
    改成按各渠道 reports/ 下实际存在的批次取最大值。
    """
    import re
    best = None
    for ch in ('bilibili', 'zhihu', 'github'):
        d = os.path.join(ROOT, ch, 'reports')
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if re.match(r'^\d{4}-\d{2}-\d{2}', name) and os.path.isdir(os.path.join(d, name)):
                if best is None or name > best:
                    best = name
    return best


def main():
    ap = argparse.ArgumentParser(description='一键更新热点报告并发布')
    ap.add_argument('--no-push', action='store_true', help='只提交，不推送')
    ap.add_argument('--site-only', action='store_true', help='跳过抓取，只重建站点')
    ap.add_argument('--channel', default='all', help='bilibili,zhihu,github 或 all')
    args = ap.parse_args()

    print('=' * 62)
    print(f'  热点雷达 · 一键更新  |  {TODAY}')
    print('=' * 62)

    # ---------- 1. 抓取 + 生成报告 ----------
    if args.site_only:
        print('\n[1/4] 跳过抓取（--site-only）')
    else:
        print('\n[1/4] 抓取并生成报告')
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'run_all.py'),
             '--channel', args.channel],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        out = (r.stdout or '').strip()
        if out:
            print('\n'.join('    ' + x for x in out.splitlines()[-30:]))
        if r.returncode != 0:
            print('\n[注意] 有渠道失败，但已成功的渠道会照常发布。')

    # ---------- 2. 重建站点 ----------
    print('\n[2/4] 生成站点 docs/')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'build_site.py')],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    print('\n'.join('    ' + x for x in (r.stdout or '').strip().splitlines()))
    if r.returncode != 0:
        print('    [失败] 站点生成失败：' + (r.stderr or '')[-300:])
        return 1

    # ---------- 3. 提交 ----------
    print('\n[3/4] 提交到 git')
    if git('rev-parse', '--is-inside-work-tree').returncode != 0:
        print('    当前目录还没初始化 git 仓库，跳过提交。')
        print('    先执行： git init && git branch -M main')
        return 0

    git('add', '-A')
    status = git('status', '--porcelain').stdout.strip()
    if not status:
        print('    没有变更，跳过提交。')
    else:
        changed = len(status.splitlines())
        batch = latest_batch() or TODAY
        msg = f'chore: 更新 {batch} 批次报告（{changed} 个文件变更）'
        c = git('commit', '-m', msg)
        if c.returncode != 0:
            print('    提交失败：' + (c.stderr or c.stdout).strip()[:300])
            return 1
        print(f'    已提交 {changed} 个文件变更')

    # ---------- 4. 推送 ----------
    if args.no_push:
        print('\n[4/4] 跳过推送（--no-push）')
        print('\n完成。本地打开 docs/index.html 预览，确认无误后执行 git push。')
        return 0

    print('\n[4/4] 推送到 GitHub')
    remote = git('remote').stdout.strip()
    if not remote:
        print('    还没配置远程仓库，跳过推送。')
        print('    执行： git remote add origin https://github.com/<你的用户名>/<仓库名>.git')
        print('    然后： git push -u origin main')
        return 0

    p = git('push')
    if p.returncode != 0:
        err = (p.stderr or p.stdout).strip()
        print('    推送失败：' + err[:400])
        print('    常见原因：未登录 / 无推送权限 / 远程有新提交需要先 pull')
        return 1
    print('    推送成功')

    url = git('remote', 'get-url', 'origin').stdout.strip()
    m = url.replace('.git', '').rstrip('/')
    if 'github.com' in m:
        parts = m.split('github.com')[-1].strip(':/')
        seg = [x for x in parts.split('/') if x]
        if len(seg) >= 2:
            user, repo = seg[0], seg[1]
            print(f'\n网页（Pages 生效后）：https://{user}.github.io/{repo}/')

    print('\n完成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
