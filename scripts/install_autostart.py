# -*- coding: utf-8 -*-
"""安装「开机自检自动更新」。

装的是什么：在 Windows 启动文件夹里放一个 .vbs，开机时静默调用 scripts/autocheck.py。
  · 只有当距上次更新超过 7 天时才会真正抓取，按周正常运行的情况下它不会被触发
  · 用 VBS 是为了不弹黑窗口；用 UTF-16 保存是为了让中文路径正确

用法：
  python scripts/install_autostart.py --install     # 安装
  python scripts/install_autostart.py --status      # 查看是否已安装
  python scripts/install_autostart.py --remove      # 卸载

注意：开机自检和「每周五计划任务」是互补的两层，同时开不冲突——
      autocheck 会先判断天数，计划任务刚跑过的话它不会再跑一次。
"""
import os, sys, shutil, subprocess, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VBS_NAME = 'hotspot-radar-autocheck.vbs'
STARTUP = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows',
                       'Start Menu', 'Programs', 'Startup')
VBS_PATH = os.path.join(STARTUP, VBS_NAME)
TASK_NAME = 'HotspotRadarWeekly'


def find_python():
    """优先用系统安装的 Python，而不是工具链自带的私有解释器。

    sys.executable 在 WorkBuddy / 虚拟环境里指向内部路径，卸载工具后会失效，
    而开机自检是要长期跑的东西，必须绑到一个稳定的解释器上。
    """
    la = os.environ.get('LOCALAPPDATA', '')
    for v in ('314', '313', '312', '311'):
        cand = os.path.join(la, 'Programs', 'Python', f'Python{v}', 'python.exe')
        if os.path.exists(cand):
            return cand
    return sys.executable


def vbs_content():
    py = find_python()
    chk = os.path.join(ROOT, 'scripts', 'autocheck.py')
    # VBScript 里双引号要写成两个双引号
    cmd = f'""{py}"" ""{chk}""'
    return (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.CurrentDirectory = "{ROOT}"\r\n'
        f'sh.Run {cmd}, 0, False\r\n'
    )


def do_install():
    if not os.path.isdir(STARTUP):
        print(f'找不到启动文件夹：{STARTUP}')
        return 1
    logs = os.path.join(ROOT, 'logs')
    os.makedirs(logs, exist_ok=True)
    # utf-16 带 BOM，保证中文路径在 WSH 里正确解析
    tmp = os.path.join(logs, '_autocheck.vbs')
    with open(tmp, 'w', encoding='utf-16', newline='') as f:
        f.write(vbs_content())
    try:
        shutil.copy2(tmp, VBS_PATH)
    except PermissionError:
        print('写入启动文件夹被拒绝。请手动把下面这个文件复制到：')
        print(f'  {STARTUP}')
        print(f'  {tmp}')
        return 1
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    print('已安装开机自检')
    print(f'  启动项：{VBS_PATH}')
    print(f'  行为：开机时检查，距上次更新 ≥7 天才自动跑一次')
    print(f'  日志：{os.path.join(ROOT, "logs", "auto_update.log")}')
    return 0


def do_status():
    ok = True
    if os.path.exists(VBS_PATH):
        print(f'开机自检：已安装（{VBS_NAME}）')
    else:
        print('开机自检：未安装')
        ok = False
    r = subprocess.run(['schtasks', '/Query', '/TN', TASK_NAME],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode == 0:
        print(f'定时任务：已注册（{TASK_NAME}）')
    else:
        print(f'定时任务：未注册（可选，用 python scripts/setup_schedule.py 注册）')
    return 0 if ok else 1


def do_remove():
    if os.path.exists(VBS_PATH):
        os.remove(VBS_PATH)
        print('已移除开机自检')
    else:
        print('开机自检本来就没装')
    return 0


def main():
    ap = argparse.ArgumentParser(description='安装/卸载开机自检自动更新')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--install', action='store_true')
    g.add_argument('--status', action='store_true')
    g.add_argument('--remove', action='store_true')
    args = ap.parse_args()

    if args.status:
        return do_status()
    if args.remove:
        return do_remove()
    return do_install()


if __name__ == '__main__':
    sys.exit(main())
