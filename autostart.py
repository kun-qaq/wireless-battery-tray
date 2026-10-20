"""
开机自启管理 (autostart)
========================
三种实现，开启时按优先级依次尝试，谁成功用谁：

  1. 计划任务（最优）
     - 触发：用户登录后延迟 DELAY_SEC 秒
     - 失败自动重试 3 次 / 间隔 1 分钟，错过触发时间补跑，电池供电照跑
     - 若当前环境拒绝注册任务（部分受限会话会「拒绝访问」），自动降级

  2. 开始菜单「启动」文件夹快捷方式
     - 零权限、所有 Windows 通用
     - 快捷方式带参数 --startup，程序自己延迟 DELAY_SEC 秒再读设备
       （补偿它没有计划任务那种延迟能力）

  3. 注册表 HKCU\\...\\Run（兜底，无延迟）

为什么开机要「延迟」：刚进桌面时 USB 接收器常常还没枚举完，
此时读电量会全部显示「离线」，延迟十几秒就能一次命中。

对外接口：
    startup_mode()   -> 'task' | 'lnk' | 'run' | None
    enable_startup() -> 同上（开启后返回实际生效方式）
    disable_startup()
"""
import os
import subprocess
import sys

APP_NAME = "WirelessBatteryTray"
TASK_NAME = "WirelessBatteryTray"
DELAY_SEC = 15          # 开机/登录后延迟多久再读设备
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_FLAG = "--startup"

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------------------------------------------------------------- 路径


def exe_path():
    """应当被自启拉起的程序路径（打包后是 exe 自身）。"""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def is_startup_launch():
    """本次是否由开机自启触发（需要延迟读设备）。"""
    return STARTUP_FLAG in sys.argv[1:]

# ---------------------------------------------------------------- 1. 计划任务


def _ps(script, timeout=30):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, timeout=timeout, creationflags=_NO_WINDOW,
        )
        out = (r.stdout or b"").decode("utf-8", "ignore").strip()
        err = (r.stderr or b"").decode("utf-8", "ignore").strip()
        return r.returncode == 0, (out + ("\n" + err if err else "")).strip()
    except Exception as e:
        return False, str(e)


def task_exists():
    ok, out = _ps(
        f"$t = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue;"
        f"if ($t) {{ 'EXISTS' }} else {{ 'NONE' }}"
    )
    return ok and "EXISTS" in out


def create_task():
    exe = exe_path()
    script = (
        "$ErrorActionPreference='Stop';"
        f"$a = New-ScheduledTaskAction -Execute '{exe}';"
        "$t = New-ScheduledTaskTrigger -AtLogOn;"
        f"$t.Delay = 'PT{DELAY_SEC}S';"
        "$s = New-ScheduledTaskSettingsSet"
        " -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)"
        " -ExecutionTimeLimit (New-TimeSpan -Hours 0)"
        " -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries"
        " -StartWhenAvailable;"
        f"Register-ScheduledTask -TaskName '{TASK_NAME}'"
        " -Action $a -Trigger $t -Settings $s -Force | Out-Null;"
        "'OK'"
    )
    ok, out = _ps(script)
    return ((ok and "OK" in out) or task_exists()), out


def delete_task():
    _ps(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false "
        f"-ErrorAction SilentlyContinue | Out-Null; 'DONE'")

# ---------------------------------------------------------------- 2. 启动文件夹快捷方式


def startup_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, r"Microsoft\Windows\Start Menu\Programs\Startup")


def lnk_path():
    return os.path.join(startup_dir(), APP_NAME + ".lnk")


def lnk_exists():
    p = lnk_path()
    return os.path.isfile(p)


def lnk_target_ok():
    """快捷方式是否还指向当前程序（exe 被移动后会失效，需要重建）。"""
    if not lnk_exists():
        return False
    try:
        with open(lnk_path(), "rb") as f:
            b = f.read()
        return (exe_path().encode("utf-16-le") in b) or (exe_path().encode() in b)
    except Exception:
        return False


def create_lnk():
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortcut(lnk_path())
        sc.TargetPath = exe_path()
        sc.Arguments = STARTUP_FLAG
        sc.WorkingDirectory = os.path.dirname(exe_path())
        sc.Description = "无线设备电量托盘"
        sc.Save()
        return lnk_exists()
    except Exception:
        return False


def delete_lnk():
    try:
        os.remove(lnk_path())
    except OSError:
        pass

# ---------------------------------------------------------------- 3. 注册表 Run


def run_key_command():
    exe = exe_path()
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    return f'"{sys.executable}" "{exe}"'


def run_key_exists():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_run_key(enable):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if enable:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, run_key_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass

# ---------------------------------------------------------------- 对外接口


def startup_mode():
    """当前生效的自启方式（按可靠性排序检查）。"""
    if task_exists():
        return "task"
    if lnk_exists():
        return "lnk"
    if run_key_exists():
        return "run"
    return None


def enable_startup():
    """开启自启，返回实际生效方式；None 表示三种都失败。"""
    ok, _ = create_task()
    if ok:
        _clear_others("task")
        return "task"
    if create_lnk():
        _clear_others("lnk")
        return "lnk"
    try:
        set_run_key(True)
        if run_key_exists():
            _clear_others("run")
            return "run"
    except Exception:
        pass
    return None


def disable_startup():
    delete_task()
    delete_lnk()
    try:
        set_run_key(False)
    except Exception:
        pass


def _clear_others(keep):
    """只保留一种方式，避免重复启动多个实例。"""
    try:
        if keep != "task":
            delete_task()
        if keep != "lnk":
            delete_lnk()
        if keep != "run":
            set_run_key(False)
    except Exception:
        pass


def ensure_path_current():
    """程序被移动/重装后，修好失效的自启入口（只处理快捷方式这一种）。"""
    if startup_mode() == "lnk" and not lnk_target_ok():
        return create_lnk()
    return False


def describe(mode):
    return {"task": f"已开启（登录后 {DELAY_SEC} 秒启动）",
            "lnk": "已开启（启动文件夹）",
            "run": "已开启（注册表 Run）",
            None: "已关闭"}[mode]


if __name__ == "__main__":
    print("当前:", describe(startup_mode()))
    print("exe :", exe_path())
    print("启动文件夹:", startup_dir())
