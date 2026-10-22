"""
无线设备电量托盘 (Wireless Battery Tray)
=========================================
监控三款 2.4G 设备的电量，鼠标悬停托盘图标即可查看：
  - Akko S9 Ultra 耳机  (GTAI dongle, VID 0x36EB PID 0x1087)
  - 灵豹 K98 键盘       (Compx/BY 方案, VID 0x3554 PID 0xFA09)
  - 罗技 G304 鼠标      (LIGHTSPEED 接收器, VID 0x046D PID 0xC53F)

协议说明：
  Akko : 发 output report [0x02,0x12,0x01,0x00...] + 校验尾 71 12，
         响应 [02 12 01 00 <电量%>] （响应尾为设备计算，无需校验）
  K98  : 读 feature report 0x06 (usage page 0xFF04)，data[3]=电量%，纯只读
  G304 : HID++ 2.0 标准电池特性 0x1000（BATTERY_LEVEL_STATUS），
         鼠标深度休眠/关机时接收器报 UNKNOWN_DEVICE，显示为离线
"""
import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import hid
from PIL import Image, ImageDraw, ImageFont
import pystray

import autostart
import sakura

# ----------------------------- 配置 -----------------------------
POLL_INTERVAL = 30          # 正常轮询间隔（秒）
FAST_INTERVAL = 8           # 有设备读不到时的快速重试间隔（秒）
AKKO_VID, AKKO_PID = 0x36EB, 0x1087
KB_VID, KB_PID = 0x3554, 0xFA09
LOGI_VID, LOGI_PID = 0x046D, 0xC53F

APP_NAME = "WirelessBatteryTray"

# ----------------------------- 运行日志 -----------------------------
# 写到 %TEMP%\WirelessBatteryTray.log，排查「读不到/显示离线」时先看这里
LOG_PATH = os.path.join(os.environ.get("TEMP") or ".", "WirelessBatteryTray.log")


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


# ----------------------------- 通用 HID 工具 -----------------------------

def find_path(vid, pid, usage_page, usage):
    for d in hid.enumerate(vid, pid):
        if d["usage_page"] == usage_page and d["usage"] == usage:
            return d["path"]
    return None


def open_fresh(vid, pid, usage_page, usage):
    """每次都重新枚举并打开一个新句柄。

    刻意不长期持有句柄：设备休眠/重连/系统睡眠恢复后，旧句柄会失效，
    继续读写容易在 hidapi 的 C 层直接崩掉（Python 层捕获不到）。
    打开开销是毫秒级，30 秒一轮完全无感。
    """
    path = find_path(vid, pid, usage_page, usage)
    if not path:
        return None
    try:
        d = hid.device()
        d.open_path(path)
        d.set_nonblocking(1)
        return d
    except Exception:
        return None


def close_safe(dev):
    try:
        dev.close()
    except Exception:
        pass


def drain(dev, secs=0.05):
    out = []
    end = time.time() + secs
    while time.time() < end:
        try:
            r = dev.read(128)
        except OSError:
            break
        if r:
            out.append(bytes(r))
        else:
            time.sleep(0.002)
    return out

# ----------------------------- Akko S9 -----------------------------
AKKO_QUERY = bytes([0x02, 0x12, 0x01]) + bytes(59) + bytes.fromhex("7112")  # 64 字节


class AkkoReader:
    name = "Akko S9 耳机"

    def __init__(self):
        self.dev = None
        self.fails = 0      # 连续失败次数，超过阈值强制重连

    def read(self):
        dev = open_fresh(AKKO_VID, AKKO_PID, 0x008C, 0x0001)
        if not dev:
            self.fails += 1
            log("AKKO: 找不到接口 (fails=%d)" % self.fails)
            return None, "未连接"
        try:
            for _ in range(20):
                try:
                    dev.write(AKKO_QUERY)
                except Exception as e:
                    log("AKKO: 写入失败 %s" % e)
                    break
                for r in drain(dev, 0.08):
                    if len(r) >= 5 and r[1] == 0x12 and r[2] == 0x01:
                        self.fails = 0
                        log("AKKO: 电量 %d%%" % r[4])
                        return r[4], "电量"
            self.fails += 1
            log("AKKO: 无响应 (fails=%d)" % self.fails)
            return None, "无响应"
        finally:
            close_safe(dev)

# ----------------------------- 灵豹 K98 -----------------------------

class K98Reader:
    name = "灵豹 K98 键盘"

    def __init__(self):
        self.dev = None
        self.fails = 0

    def read(self):
        dev = open_fresh(KB_VID, KB_PID, 0xFF04, 0x0002)
        if not dev:
            self.fails += 1
            log("K98: 找不到接口 (fails=%d)" % self.fails)
            return None, "未连接"
        try:
            data = bytes(dev.get_feature_report(0x06, 65))
        except Exception as e:
            self.fails += 1
            log("K98: 读取失败 %s" % e)
            return None, "通信失败"
        finally:
            close_safe(dev)
        # 06 <ch> <state> <kb%> <ch2%> <ch3%> <crc...>
        if len(data) >= 6 and data[0] == 0x06:
            self.fails = 0
            log("K98: 电量 %d%%" % data[3])
            return data[3], "电量"
        self.fails += 1
        log("K98: 无响应 (fails=%d)" % self.fails)
        return None, "无响应"

# ----------------------------- 罗技 G304 (HID++ 2.0) -----------------------------

class G304Reader:
    name = "罗技 G304 鼠标"
    SW_ID = 0x0E          # 与 G HUB 一致，避免 software_id 冲突

    def __init__(self):
        self.dev = None
        self.feat_idx = None
        self.fails = 0

    def _open(self):
        # 关键：HID++ 长报文 (report 0x11, 20 字节) 只能写到 usage 0x0002 的接口
        self.dev = open_fresh(LOGI_VID, LOGI_PID, 0xFF00, 0x0002)
        return self.dev

    def _req(self, di, feature_index, function, params=b"", wait=0.3):
        """发送 20 字节长报文并等匹配的回复。"""
        body = bytes([0x11, di, feature_index, (function << 4) | self.SW_ID]) + bytes(params)
        pkt = (body + bytes(20))[:20]
        try:
            # 清掉残留
            for _ in range(20):
                if not self.dev.read(128):
                    break
            self.dev.write(pkt)
        except Exception:
            return None
        end = time.time() + wait
        while time.time() < end:
            try:
                r = self.dev.read(128)
            except OSError:
                return None
            if r:
                b = bytes(r)
                if len(b) >= 5 and b[0] == 0x11 and b[1] == di:
                    return b
            time.sleep(0.004)
        return None

    def read(self):
        try:
            if not self._open():
                self.fails += 1
                return None, "未连接"
            # 设备可能不在 1 号槽位，逐个探测电池特性 0x1000
            for di in list(range(1, 7)) + [0xFF]:
                if self.feat_idx is None:
                    r = self._req(di, 0x00, 0x00, (0x10, 0x00))  # root getFeature(0x1000)
                    if not r or r[3] == 0x8F or not r[4]:
                        continue
                    self.feat_idx = r[4]
                r = self._req(di, self.feat_idx, 0x00)
                if not r or r[3] == 0x8F:
                    continue
                level = r[4]
                status = r[5] if len(r) > 5 else 0
                if 0 <= level <= 100:
                    self.fails = 0
                    note = "充电中" if status in (1, 2) else "电量"
                    log("G304: 电量 %d%% %s" % (level, note))
                    return level, note
            self.feat_idx = None
            self.fails += 1
            log("G304: 设备不在线 (fails=%d)" % self.fails)
            return None, "鼠标离线"
        except Exception as e:
            return None, f"错误 {e}"
        finally:
            if self.dev is not None:
                close_safe(self.dev)
                self.dev = None

# ----------------------------- 电量状态聚合 -----------------------------

READERS = [AkkoReader(), K98Reader(), G304Reader()]


def read_all():
    results = []
    for rd in READERS:
        try:
            v, s = rd.read()
        except Exception as e:
            v, s = None, f"错误 {e}"
        results.append((rd.name, v, s))
    return results

# ----------------------------- 托盘图标（樱花） -----------------------------

def make_icon(percents):
    """樱花图标；花瓣颜色随最低电量变化（粉/枯黄/红/灰）。"""
    return sakura.make_icon(percents, size=64)

# ----------------------------- 主应用 -----------------------------

class App:
    def __init__(self):
        self.state = []          # [(name, val, status)]
        self.cache = {}          # name -> (val, timestamp) 最近一次成功读数
        self.lock = threading.Lock()
        self.icon = None
        self.win = None
        self.last_update = None
        self.startup_mode = autostart.startup_mode()

        self.tray = pystray.Icon(
            APP_NAME,
            icon=make_icon([]),
            title="无线设备电量 · 正在读取…",
            menu=pystray.Menu(
                pystray.MenuItem("显示电量详情", self.show_window, default=True),
                pystray.MenuItem("立即刷新", lambda: (self.poll_once(), None)),
                pystray.MenuItem(
                    lambda _: f"开机自动启动 · {autostart.describe(self.startup_mode)}",
                    self.toggle_startup,
                    checked=lambda _: self.startup_mode is not None,
                ),
                pystray.MenuItem("退出", self.quit),
            ),
        )

    # ---- 轮询 ----
    def poll_once(self):
        res = read_all()
        now = time.time()
        with self.lock:
            out = []
            for name, v, s in res:
                if isinstance(v, int):
                    self.cache[name] = (v, now)
                    out.append((name, v, s))
                    continue
                # 这一轮没读到：6 小时内回落到最后一次真实读数，标记「休眠」
                hit = self.cache.get(name)
                if hit and now - hit[1] < 6 * 3600:
                    val, ts = hit
                    stamp = time.strftime("%H:%M", time.localtime(ts))
                    out.append((name, val, "休眠 · %s" % stamp))
                else:
                    out.append((name, None, "离线"))
            self.state = out
            self.last_update = time.strftime("%H:%M:%S")
        self.update_tray()

    def poll_loop(self):
        # 开机自启时先等一会儿：刚进桌面 USB 接收器可能还没枚举完，
        # 立刻读会全部显示「离线」。托盘图标已经出来了，只是稍晚出数字。
        if autostart.is_startup_launch():
            time.sleep(autostart.DELAY_SEC)
        self.poll_once()
        while True:
            # 只要有设备没读到，就用更短的间隔重试，尽快自愈
            with self.lock:
                missing = any(not isinstance(v, int) for _, v, _ in self.state)
            time.sleep(FAST_INTERVAL if missing else POLL_INTERVAL)
            if not quit_flag:
                self.poll_once()

    def update_tray(self):
        with self.lock:
            res = list(self.state)
        # Windows 托盘 tooltip 是单行，用短名拼接
        short = {"Akko S9 耳机": "耳机", "灵豹 K98 键盘": "键盘", "罗技 G304 鼠标": "鼠标"}
        parts = []
        for name, v, s in res:
            key = short.get(name, name)
            parts.append(f"{key} {v}%" if isinstance(v, int) else f"{key} {s}")
        title = "  |  ".join(parts)
        try:
            self.tray.title = title
            self.tray.icon = make_icon(res)
        except Exception:
            pass
        if self.win is not None:
            try:
                self.win.after(0, self.refresh_window_labels)
            except Exception:
                pass

    # ---- 详情窗口 ----
    def show_window(self, *_):
        if self.win is not None:
            try:
                self.win.deiconify()
                self.win.lift()
                return
            except Exception:
                self.win = None
        win = tk.Tk()
        win.title("无线设备电量")
        win.geometry("380x300")
        win.configure(bg="#1e1e2e")
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), setattr(self, "win", None)))
        try:
            from PIL import ImageTk
            self._win_icon = ImageTk.PhotoImage(sakura.draw_sakura(64))
            win.iconphoto(True, self._win_icon)
        except Exception:
            pass
        f_big = tkfont.Font(size=13, weight="bold")
        f_mid = tkfont.Font(size=11)
        f_small = tkfont.Font(size=9)
        self.lbls = []
        for i in range(3):
            fr = tk.Frame(win, bg="#2a2a3c", padx=12, pady=10)
            fr.pack(fill="x", padx=14, pady=6)
            name_l = tk.Label(fr, text="", bg="#2a2a3c", fg="#eaeaf0", font=f_big, anchor="w")
            name_l.pack(fill="x")
            val_l = tk.Label(fr, text="", bg="#2a2a3c", fg="#9ecbff", font=f_mid, anchor="w")
            val_l.pack(fill="x")
            bar = tk.Canvas(fr, height=10, bg="#3a3a4e", highlightthickness=0, bd=0)
            bar.pack(fill="x", pady=(4, 0))
            # 窗口尺寸/布局变化时重画，保证条长、条高与实际画布一致
            bar.bind("<Configure>", lambda _e: self.refresh_window_labels())
            self.lbls.append((name_l, val_l, bar))
        foot = tk.Label(win, text="", bg="#1e1e2e", fg="#888", font=f_small)
        foot.pack(pady=4)
        self.foot = foot
        self.win = win
        self.refresh_window_labels()
        win.mainloop()

    def refresh_window_labels(self):
        if self.win is None:
            return
        with self.lock:
            res = list(self.state)
        for i, (name, v, s) in enumerate(res):
            name_l, val_l, bar = self.lbls[i]
            name_l.config(text=name)
            w, h = bar.winfo_width(), bar.winfo_height()
            bar.delete("all")
            if not isinstance(v, int):
                val_l.config(text=s, fg="#888")
                continue
            color = "#4caf50" if v > 30 else ("#ffc107" if v > 15 else "#f44336")
            val_l.config(text=f"{v}%   {s}", fg=color)
            # 画布尚未布局完成时先不画条（Configure 事件会触发重画）
            if w < 20 or h < 4:
                continue
            # 背景槽铺满整个画布，再按电量比例画填充，宽高都用实际渲染尺寸
            bar.create_rectangle(0, 0, w, h, fill="#3a3a4e", width=0)
            fill_w = max(4, round(w * min(100, max(0, v)) / 100))
            bar.create_rectangle(0, 0, fill_w, h, fill=color, width=0)
        if self.foot and self.last_update:
            self.foot.config(text=f"上次刷新 {self.last_update}")

    # ---- 开机自启 ----
    def toggle_startup(self, *_):
        if self.startup_mode is None:
            mode = autostart.enable_startup()
            msg = ("已开启开机自启：" + autostart.describe(mode)) if mode else "开启失败，请手动添加"
        else:
            autostart.disable_startup()
            mode = autostart.startup_mode()
            msg = "已关闭开机自启"
        self.startup_mode = mode
        try:
            self.tray.notify(msg, title="无线设备电量")
        except Exception:
            pass
        self.update_menu()

    def update_menu(self):
        try:
            self.tray.update_menu()
        except Exception:
            pass

    def quit(self, *_):
        global quit_flag
        quit_flag = True
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.tray.stop()
        sys.exit(0)

    def run(self):
        t = threading.Thread(target=self.poll_loop, daemon=True)
        t.start()
        self.tray.run(setup=None)

# ----------------------------- 单实例保护 -----------------------------
_mutex = None


def already_running():
    """用内核互斥体保证只跑一个实例，避免开机自启 + 手动双击开两个托盘。"""
    global _mutex
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    _mutex = k32.CreateMutexW(None, 0, r"Local\WirelessBatteryTray_SingleInstance")
    return ctypes.get_last_error() == 183      # ERROR_ALREADY_EXISTS


# -----------------------------

quit_flag = False


def install_excepthook():
    """把任何未捕获异常写进日志，避免 --noconsole 下崩溃无声无息。"""
    import traceback

    def hook(exc_type, exc, tb):
        log("未捕获异常: " + "".join(
            traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = hook
    threading.excepthook = lambda a: log("线程异常: " + "".join(
        traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))


def main():
    if already_running():
        # 已经有一个在跑了：提示一下就退出，不重复占托盘
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "无线设备电量托盘已经在运行了（看任务栏右下角托盘区）。",
                "无线设备电量", 0x40 | 0x1000)
        except Exception:
            pass
        return
    # exe 换过位置的话，顺手把开机自启的快捷方式修好
    try:
        autostart.ensure_path_current()
    except Exception:
        pass
    install_excepthook()
    log("启动 (startup=%s)" % autostart.is_startup_launch())
    app = App()
    app.run()


if __name__ == "__main__":
    main()
