# -*- coding: utf-8 -*-
"""开机自检：距上次更新超过 N 天时，自动补跑一次完整更新。

为什么需要它：
  Windows 计划任务（每周五 09:00）只在电脑开机时触发。如果那个时间点电脑是关的，
  这一周就漏了，而且不会有任何提示。这个脚本放在「启动」文件夹里，每次开机检查一次：
  只有在确实超过 N 天没更新时才动手，按周正常跑的情况下它永远不会触发，不重复抓取。

设计取舍：
  · 开机后网络往往还没就绪，所以先做连通性探测，失败则退避重试（最多 5 次 / 每次 30 秒）
  · 用锁文件避免计划任务和开机自检同时跑
  · 全程写日志到 logs/auto_update.log，静默运行不打扰用户；失败不弹窗，只记日志
"""
import os, sys, time, json, socket, datetime, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(ROOT, 'logs')
LOG = os.path.join(LOGDIR, 'auto_update.log')
LOCK = os.path.join(LOGDIR, '.running')
MIN_DAYS = 7          # 超过这么多天没更新才补跑
NET_RETRIES = 5       # 开机后等网络的最大重试次数
NET_WAIT = 30         # 每次重试间隔（秒）


def log(msg):
    os.makedirs(LOGDIR, exist_ok=True)
    line = f'[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line)


def latest_batch():
    """返回 (批次名, 日期对象)；没有任何报告时返回 (None, None)。"""
    best = None
    for ch in ('bilibili', 'zhihu', 'github'):
        d = os.path.join(ROOT, ch, 'reports')
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            m = name[:10]
            if len(m) == 10 and m[4] == '-' and m[7] == '-':
                if best is None or name > best:
                    best = name
    if not best:
        return None, None
    try:
        return best, datetime.date.fromisoformat(best[:10])
    except ValueError:
        return best, None


def net_ready():
    """轻量连通性探测：能连上 B站 的 443 端口就认为网络可用。"""
    for host in ('api.bilibili.com', 'www.baidu.com'):
        try:
            socket.create_connection((host, 443), timeout=8).close()
            return True
        except OSError:
            continue
    return False


def main():
    os.makedirs(LOGDIR, exist_ok=True)

    if os.path.exists(LOCK):
        try:
            age = time.time() - os.path.getmtime(LOCK)
            if age < 3600:
                log('已有实例在运行（锁文件 <1 小时），本次跳过')
                return 0
        except OSError:
            pass

    batch, bdate = latest_batch()
    if bdate is None:
        log(f'没有找到历史报告，直接执行首次更新（batch={batch}）')
        need = True
        days = None
    else:
        days = (datetime.date.today() - bdate).days
        need = days >= MIN_DAYS
        log(f'最新批次 {batch}，距今 {days} 天，阈值 {MIN_DAYS} 天 → {"需要更新" if need else "跳过"}')

    if not need:
        return 0

    # 等网络就绪再跑，避免开机瞬间抓取全失败
    for i in range(NET_RETRIES):
        if net_ready():
            break
        log(f'网络未就绪，{(i+1)*NET_WAIT}s 后重试（{i+1}/{NET_RETRIES}）')
        time.sleep(NET_WAIT)
    else:
        log('网络始终未就绪，放弃本次自动更新（下次开机会再试）')
        return 1

    open(LOCK, 'w').close()
    try:
        log('开始自动更新…')
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'update.py')],
            cwd=ROOT, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=1800)
        tail = (r.stdout or '').strip().splitlines()[-15:]
        for line in tail:
            log('  ' + line)
        if r.returncode == 0:
            log('自动更新完成')
            return 0
        log(f'自动更新失败，退出码 {r.returncode}：{(r.stderr or "")[:300]}')
        return 1
    except subprocess.TimeoutExpired:
        log('自动更新超时（>30 分钟），已放弃')
        return 1
    except Exception as e:
        log(f'自动更新异常：{e}')
        return 1
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == '__main__':
    sys.exit(main())
