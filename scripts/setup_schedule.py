# -*- coding: utf-8 -*-
"""注册「每周自动更新」的 Windows 计划任务。

为什么用 schtasks 而不是 .bat：
  本机路径含中文（D:\\日常\\自媒体\\B站热点），.bat/.ps1 文件在 GBK 编码下会把中文路径写坏。
  计划任务的命令行由任务计划程序以 Unicode 存储，不经过脚本文件，所以不受影响。

用法：
  python scripts/setup_schedule.py                    # 每周五 09:00 自动更新
  python scripts/setup_schedule.py --time 21:30       # 改时间
  python scripts/setup_schedule.py --day SAT --time 10:00
  python scripts/setup_schedule.py --status           # 查看是否已注册
  python scripts/setup_schedule.py --remove           # 删除
  python scripts/setup_schedule.py --run-now          # 立即跑一次测试

注意：
  · 任务在「用户登录后」运行；电脑关机/休眠时不会执行，下次开机会错过（需手动跑一次）。
  · 自动推送依赖已保存的 GitHub 凭据。若从未推送过，请先在终端手动执行一次
    git push，让 Git Credential Manager 记住令牌，之后即可免密推送。
"""
import os, sys, subprocess, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_NAME = 'HotspotRadarWeekly'
DAYS = {'MON': 'MON', 'TUE': 'TUE', 'WED': 'WED', 'THU': 'THU',
        'FRI': 'FRI', 'SAT': 'SAT', 'SUN': 'SUN'}


def schtasks(*args):
    r = subprocess.run(['schtasks', *args], capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def show_status():
    code, out = schtasks('/Query', '/TN', TASK_NAME, '/FO', 'LIST')
    if code != 0:
        print(f'未注册（任务名 {TASK_NAME} 不存在）')
        return 1
    keep = ('TaskName', '任务名', 'Next Run Time', '下次运行时间',
            'Status', '状态', 'Schedule Type', '计划类型', 'Start Time', '开始时间')
    for line in out.splitlines():
        if any(k in line for k in keep):
            print('  ' + line.strip())
    return 0


def create(day, at):
    python = sys.executable
    target = os.path.join(ROOT, 'scripts', 'update.py')
    if not os.path.exists(target):
        print(f'找不到 {target}')
        return 1

    # schtasks 的 /TR 只接受一整条命令；路径含空格时必须成对加引号
    tr = f'"{python}" "{target}"'
    code, out = schtasks('/Create', '/TN', TASK_NAME, '/TR', tr,
                         '/SC', 'WEEKLY', '/D', day, '/ST', at, '/RL', 'LIMITED', '/F')
    if code != 0:
        print('创建失败：')
        print(out.strip()[:600])
        print('\n可以改用图形界面手动配置（见 README「每周自动运行」一节）。')
        return 1
    print(f'已创建计划任务：{TASK_NAME}')
    print(f'  运行时间：每周{day} {at}')
    print(f'  执行命令：{tr}')
    return 0


def remove():
    code, out = schtasks('/Delete', '/TN', TASK_NAME, '/F')
    print('已删除计划任务' if code == 0 else f'删除失败：{out.strip()[:300]}')


def run_now():
    code, out = schtasks('/Run', '/TN', TASK_NAME)
    print('已触发运行（窗口不会弹出，可在任务管理器看到 python 进程）'
          if code == 0 else f'触发失败：{out.strip()[:300]}')


def main():
    ap = argparse.ArgumentParser(description='注册每周自动更新任务')
    ap.add_argument('--day', default='FRI', choices=list(DAYS), help='星期几，默认 FRI')
    ap.add_argument('--time', default='09:00', help='时间 HH:MM，默认 09:00')
    ap.add_argument('--status', action='store_true', help='查看当前任务状态')
    ap.add_argument('--remove', action='store_true', help='删除任务')
    ap.add_argument('--run-now', action='store_true', help='立即触发一次')
    args = ap.parse_args()

    if args.status:
        return show_status()
    if args.remove:
        remove()
        return 0
    if args.run_now:
        run_now()
        return 0
    return create(args.day, args.time)


if __name__ == '__main__':
    sys.exit(main())
