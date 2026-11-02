"""
FluentShell v3 —— 真正的 Windows 11 风格图形界面骨架（可复用）
====================================================================
底座: tkinter.ttk + Sun Valley 主题(sv_ttk) + pywinstyles

为什么不是 CustomTkinter?
    CustomTkinter 是「它自己设计的一套圆角方块」, 控件全部自绘, 跟 Win11
    原生观感没关系 —— 所以看起来总是差一口气。
    GitHub 上公认让 tkinter 变成 Win11 原生观感的方案是:
      * sv_ttk        https://github.com/rdbende/Sun-Valley-ttk-theme
                      真正的 Fluent 皮肤, 直接用 ttk 控件就能拿到
                      Accent.TButton(强调按钮) / Switch.TCheckbutton(开关)
                      / Card.TFrame(圆角卡片) / Toggle.TButton / Fluent 滑块
                      / 进度条 / 输入框 / 下拉框
      * pywinstyles   https://github.com/Akascape/py-window-styles
                      Win11 原生深色标题栏 + 标题栏/标题文字/边框配色

依赖: pip install sv-ttk pywinstyles
    (tkinter 自带; 只有系统 Python 有 tkinter, managed Python 3.13 没有)

用法:
    from fluent_shell import FluentShell

    app = FluentShell(title="我的工具", app_name="MyTool", subtitle="一行简介",
                      pages=[("home", "概览", "功能入口"), ("set", "设置", "参数")])
    p = app.page("home")
    c = app.card(p, "操作")
    app.btn(c, "开始", doit, primary=True).pack(anchor="w", pady=8)
    app.mainloop()

约定: 深色 #1c1c1c / 卡片 #2b2b2b / 强调色跟随 Sun Valley 主题 (#57c8ff)
      字体: 思源黑体 (Source Han Sans) / 其开源发行版 Noto Sans SC
            (两者字形完全一致; 机器上装了哪个用哪个, 都没装再回退微软雅黑)
      mode="system" 时跟随 Windows 系统深浅色, 并监听系统切换自动变更
"""
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import sv_ttk

try:
    import pywinstyles
except Exception:                                     # 非 Windows / 没装也照样能跑
    pywinstyles = None

try:
    import darkdetect                                 # 跟随系统深浅色(Windows/Mac)
except Exception:                                     # 没装也能跑(默认深色)
    darkdetect = None

from PIL import Image, ImageTk

# ------------------------------------------------------------------ 调色板
# 刻意跟随 Sun Valley 主题自身的配色, 这样强调按钮(主题内置, 不能改色)
# 和骨架自己画的东西颜色才一致。
DARK = {"bg": "#1c1c1c", "card": "#2b2b2b", "card2": "#333333", "hover": "#2f2f2f",
        "sel": "#343434", "text": "#fafafa", "sub": "#a5a5a5",
        "accent": "#57c8ff", "accent_h": "#7ed4ff", "accent_t": "#102c38",
        "entry": "#1f1f1f", "border": "#3b3b3b", "canvas": "#141414"}
LIGHT = {"bg": "#fafafa", "card": "#ffffff", "card2": "#f0f0f0", "hover": "#ededed",
         "sel": "#e6e6e6", "text": "#1c1c1c", "sub": "#5f5f5f",
         "accent": "#005fb8", "accent_h": "#1a6fc4", "accent_t": "#ffffff",
         "entry": "#ffffff", "border": "#e0e0e0", "canvas": "#f0f0f0"}

# Sun Valley 主题自带的 8 个字体, 统一按 Win11 规范重设(px 尺寸 = 负数)
_SV_FONTS = {"SunValleyCaptionFont": (12, False, "ui"),
             "SunValleyBodyFont": (14, False, "ui"),
             "SunValleyBodyStrongFont": (14, True, "ui"),
             "SunValleyBodyLargeFont": (18, False, "ui"),
             "SunValleySubtitleFont": (20, True, "disp"),
             "SunValleyTitleFont": (28, True, "disp"),
             "SunValleyTitleLargeFont": (40, True, "disp"),
             "SunValleyDisplayFont": (68, True, "disp")}


# ------------------------------------------------------------------ 小工具
def _round_rect(c, x1, y1, x2, y2, r=4, **kw):
    """在 canvas 上画圆角矩形(返回所有 item id, 方便换色/隐藏)。"""
    kw.setdefault("outline", "")
    ids = [c.create_rectangle(x1 + r, y1, x2 - r + 1, y2 + 1, **kw),
           c.create_rectangle(x1, y1 + r, x2 + 1, y2 - r + 1, **kw)]
    for ax, ay, a0 in ((x1, y1, 90), (x2 - 2 * r, y1, 0),
                       (x2 - 2 * r, y2 - 2 * r, 270), (x1, y2 - 2 * r, 180)):
        ids.append(c.create_arc(ax, ay, ax + 2 * r, ay + 2 * r,
                                start=a0, extent=90, **kw))
    return ids


def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(c1, c2, t):
    """两个 hex 颜色按比例混合, 用来生成 hover / 禁用态。"""
    a, b = _hex2rgb(c1), _hex2rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ 滚动页面
class _ScrollPage(ttk.Frame):
    """单个可滚动页面: Canvas + 内部 body 框架(往 body 里塞卡片)。"""

    def __init__(self, master, shell):
        super().__init__(master)
        self.shell = shell
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                bg=shell.P["bg"])
        self.sb = ttk.Scrollbar(self, orient="vertical",
                                command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, style="Page.TFrame",
                              padding=(26, 6, 34, 26))
        self._win = self.canvas.create_window((0, 0), window=self.body,
                                              anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.sb.grid(row=0, column=1, sticky="ns")
        self.body.bind("<Configure>", lambda e: self._sync_scroll())
        self.canvas.bind("<Configure>", self._on_cfg)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all(
            "<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all(
            "<MouseWheel>"))

    def _on_cfg(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        self._sync_scroll()

    def _sync_scroll(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        need = self.body.winfo_reqheight() > self.canvas.winfo_height() + 2
        if need:
            self.sb.grid()
        else:
            self.sb.grid_remove()

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def apply_bg(self, color):
        self.canvas.configure(bg=color)


# ------------------------------------------------------------------ 导航项
class _NavItem(tk.Canvas):
    """Win11 设置页那样的导航项: 左侧 3px 强调色小竖条 + 悬停/选中底色。"""

    W, H = 240, 38

    def __init__(self, master, shell, text, command):
        super().__init__(master, width=self.W, height=self.H,
                         highlightthickness=0, bd=0, bg=shell.P["bg"])
        self.shell = shell
        self.command = command
        self.active = False
        self.hover = False
        self._bg_ids = _round_rect(self, 8, 2, self.W - 12, self.H - 2, 4,
                                   fill="", outline="")
        self._pip = self.create_rectangle(18, 11, 21, 27, fill="", outline="")
        self._txt = self.create_text(34, self.H / 2 + 1, text=text, anchor="w",
                                     font=shell.f_nav, fill=shell.P["sub"])
        for ev, fn in (("<Button-1>", self._click),
                       ("<Enter>", lambda e: self._set_hover(True)),
                       ("<Leave>", lambda e: self._set_hover(False))):
            self.bind(ev, fn)

    def _click(self, _e=None):
        if self.command:
            self.command()

    def _set_hover(self, on):
        self.hover = on
        self.repaint()

    def set_active(self, on):
        self.active = on
        self.repaint()

    def repaint(self):
        P = self.shell.P
        bg = ""
        if self.active:
            bg = P["sel"]
        elif self.hover:
            bg = P["hover"]
        for i in self._bg_ids:
            self.itemconfigure(i, fill=bg, outline=bg)
        self.itemconfigure(self._pip, fill=P["accent"] if self.active else "",
                           outline="")
        self.itemconfigure(self._txt,
                           fill=P["text"] if (self.active or self.hover) else P["sub"])
        self.configure(bg=P["bg"])


# ------------------------------------------------------------------ 占位输入框
class _Entry(ttk.Entry):
    """带 placeholder 的 ttk.Entry(Win11 里输入框提示文字是灰色的)。"""

    def __init__(self, master, shell, placeholder="", **kw):
        super().__init__(master, **kw)
        self._shell = shell
        self._ph = placeholder
        self._showing = False
        if placeholder:
            self._show()
            self.bind("<FocusIn>", self._in, add="+")
            self.bind("<FocusOut>", self._out, add="+")

    def _show(self):
        if self._ph and not self.get():
            self._showing = True
            self.insert(0, self._ph)
            self.configure(foreground=self._shell.P["sub"])

    def _in(self, _e=None):
        if self._showing:
            self.delete(0, "end")
            self._showing = False
            self.configure(foreground=self._shell.P["text"])

    def _out(self, _e=None):
        self._show()

    def value(self):
        return "" if self._showing else self.get()

    def set(self, text):
        self._showing = False
        self.delete(0, "end")
        self.insert(0, text)
        self.configure(foreground=self._shell.P["text"])

    def repaint(self):
        self.configure(foreground=self._shell.P["sub"] if self._showing
                       else self._shell.P["text"])


# ------------------------------------------------------------------ 分段选择器
class _Segmented(ttk.Frame):
    """Win11 分段控件: 一排紧挨着的按钮, 选中项变强调色。"""

    def __init__(self, master, shell, values, variable=None, command=None):
        super().__init__(master)
        self.shell = shell
        self.values = list(values)
        self.command = command
        self.var = variable if variable is not None else tk.StringVar()
        if not self.var.get():
            self.var.set(self.values[0])
        self.btns = []
        for i, v in enumerate(self.values):
            b = ttk.Button(self, text=v, style="Seg.TButton",
                           command=lambda i=i: self._pick(i))
            b.pack(side="left", padx=1)
            self.btns.append(b)
        self.var.trace_add("write", lambda *_a: self._sync())
        self._sync()

    def _pick(self, i):
        v = self.values[i]
        if self.var.get() != v:
            self.var.set(v)          # 改选中项 -> trace 更新高亮
        if self.command:
            self.command(v)          # 始终触发回调(否则换选项后说明/预览要再点一次才更新)

    def _sync(self):
        cur = self.var.get()
        for i, b in enumerate(self.btns):
            b.configure(style="Accent.TButton" if self.values[i] == cur
                        else "Seg.TButton")


# ------------------------------------------------------------------ 进度条
class _Progress(ttk.Progressbar):
    """在 ttk.Progressbar 上补 CTk 风格的 .set(0~1)/.get(), 项目代码不用改。"""

    def set(self, v):
        try:
            self.configure(value=max(0.0, min(1.0, float(v))) * 100)
        except Exception:
            pass

    def get(self):
        try:
            return float(self["value"]) / 100.0
        except Exception:
            return 0.0


# ------------------------------------------------------------------ 主骨架
class FluentShell:
    def __init__(self, title="App", app_name="App", subtitle="", pages=(),
                 width=1040, height=720, mode="system", icon=None, builder=None,
                 footer=None):
        """
        pages:   [(key, 导航标题, 页面副标题), ...]
        icon:    .ico 路径 或 PIL 图像
        builder: 建内容的回调 builder(self)(内容只会建一次; 换主题不再重建窗口)
        footer:  左下角小字(比如版本号)
        """
        # mode="system" 时跟随 Windows 系统深浅色, 并监听系统切换自动变更
        self._auto_follow = (mode == "system")
        if self._auto_follow:
            mode = self._detect_system_mode()
        self.mode = mode
        self.P = DARK if mode == "dark" else LIGHT
        self.pages = list(pages) or [("home", "主页", "")]
        self.app_name = app_name
        self.subtitle = subtitle
        self.builder = builder
        self._title = title
        self._icon = icon
        self._footer = footer
        self._size = (width, height)
        self._dyn = []                       # 需要跟着主题换色的 (控件, 选项, key)
        self._q = queue.Queue()

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(max(560, width - 160), max(420, height - 120))
        self.root.configure(bg=self.P["bg"])
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.style = ttk.Style()

        sv_ttk.set_theme(mode)
        self._setup_fonts()
        self._setup_styles()
        self._apply_icon(icon)

        self._build_nav()
        self._build_content()
        if builder:
            builder(self)
        if self._auto_follow:
            self._start_theme_watchdog()

    # ---------------------------------------------------------- 字体 / 样式
    def _setup_fonts(self):
        fams = set(tkfont.families())

        def pick(*cands):
            for c in cands:
                if c in fams:
                    return c
            return cands[-1]

        # 设计字体: 思源黑体 (Source Han Sans) 及其开源发行版 Noto Sans SC,
        # 两者字形完全一致, 机器装了哪个用哪个; 都没装再回退微软雅黑等。
        # 注意: 不要用 Segoe UI Variable! 它是可变字体, Tk/GDI 渲染中文又糊又粗。
        self.f_ui = pick("Source Han Sans SC", "Source Han Sans", "思源黑体",
                         "Noto Sans SC", "微软雅黑", "Microsoft YaHei UI",
                         "DengXian", "等线", "Microsoft JhengHei UI", "Segoe UI")
        self.f_disp = self.f_ui
        self.f_mono_name = ("Cascadia Mono" if "Cascadia Mono" in fams
                            else "Consolas" if "Consolas" in fams
                            else "Courier New")
        # 把 Sun Valley 自带的 8 个字体族统一改成 Win11 规范
        # (它默认用的名字在部分机器上会回退到宋体, 中文会很丑)
        for name, (size, bold, kind) in _SV_FONTS.items():
            try:
                f = tkfont.nametofont(name)
            except Exception:
                continue
            f.configure(family=self.f_disp if kind == "disp" else self.f_ui,
                        size=-size, weight="bold" if bold else "normal")

        self.f_body = tkfont.nametofont("SunValleyBodyFont")        # 14
        self.f_h2 = tkfont.nametofont("SunValleyBodyStrongFont")    # 14 半粗
        self.f_large = tkfont.nametofont("SunValleyBodyLargeFont")  # 18
        self.f_nav = tkfont.nametofont("SunValleyBodyFont")
        self.f_small = tkfont.nametofont("SunValleyCaptionFont")    # 12
        self.f_title = tkfont.Font(family=self.f_disp, size=-24, weight="bold")
        self.f_brand = tkfont.Font(family=self.f_disp, size=-17, weight="bold")
        self.f_mono = tkfont.Font(family=self.f_mono_name, size=11)
        self.f_big = tkfont.Font(family=self.f_disp, size=-42, weight="bold")
        self.f_icon = tkfont.Font(family="Segoe Fluent Icons", size=16)

    def _setup_styles(self):
        P = self.P
        st = self.style
        st.configure("Page.TFrame", background=P["bg"])
        st.configure("Nav.TFrame", background=P["bg"])
        # Card: 用主题可控的「实心背景」, 这样和卡片内的标签/文字背景永远同色。
        # sv_ttk 自带的 Card.TFrame 是烘焙死的图片元素, 深色下还会渲染异常(变白),
        # 所以这里改用 Frame.border 实心填充 + 1px 细描边(提供层次)。
        st.layout("Card.TFrame", [("Frame.border", {"sticky": "nswe"})])
        st.configure("Card.TFrame", background=P["card"], borderwidth=1,
                     relief="solid", bordercolor=P["border"])
        st.configure("Tool.TFrame", background=P["card"])
        st.configure("Seg.TButton", padding=(16, 5), anchor="center")
        st.configure("Sub.TLabel", background=P["card"], foreground=P["sub"],
                     font=self.f_small)
        st.configure("Hint.TLabel", background=P["bg"], foreground=P["sub"],
                     font=self.f_small)
        st.configure("Body.TLabel", background=P["card"], foreground=P["text"],
                     font=self.f_body)
        st.configure("CardTitle.TLabel", background=P["card"],
                     foreground=P["text"], font=self.f_h2)
        st.configure("HC.Horizontal.TProgressbar", background=P["accent"],
                     troughcolor=_mix(P["card"], P["bg"], .5))
        st.configure("HC.Vertical.TProgressbar", background=P["accent"],
                     troughcolor=_mix(P["card"], P["bg"], .5))

    # ---------------------------------------------------------- 窗口外观
    def _apply_icon(self, icon):
        if icon is None:
            return
        try:
            if isinstance(icon, (str, os.PathLike)):
                if os.path.isfile(icon):
                    self.root.iconbitmap(str(icon))
            else:
                self._icon_tk = ImageTk.PhotoImage(icon)
                self.root.iconphoto(True, self._icon_tk)
        except Exception:
            pass

    def set_icon(self, pil_image):
        self._apply_icon(pil_image)

    def _apply_window(self):
        """Win11 原生深色标题栏(失败静默)。"""
        if pywinstyles is None:
            return
        try:
            self.root.update_idletasks()
            ver = sys.getwindowsversion()
            if ver.major == 10 and ver.build >= 22000:
                pywinstyles.change_header_color(self.root, self.P["bg"])
                pywinstyles.change_title_color(
                    self.root, "#ffffff" if self.mode == "dark" else "#000000")
                if self.mode == "dark":
                    pywinstyles.change_border_color(self.root, "#3b3b3b")
            elif ver.major == 10:
                pywinstyles.apply_style(
                    self.root, "dark" if self.mode == "dark" else "normal")
        except Exception:
            pass

    # ---------------------------------------------------------- 左侧导航
    def _build_nav(self):
        P = self.P
        nav = ttk.Frame(self.root, style="Nav.TFrame", width=248)
        nav.grid(row=0, column=0, sticky="nsw")
        nav.grid_propagate(False)
        nav.columnconfigure(0, weight=1)
        self.nav = nav

        head = ttk.Frame(nav, style="Nav.TFrame", padding=(24, 22, 12, 6))
        head.pack(fill="x")
        if self._icon is not None:
            try:
                img = (Image.open(self._icon) if isinstance(self._icon, str)
                       else self._icon)
                self._brand_img = ImageTk.PhotoImage(
                    img.resize((30, 30), Image.LANCZOS))
                ttk.Label(head, image=self._brand_img,
                          background=P["bg"]).pack(anchor="w", pady=(0, 8))
            except Exception:
                pass
        ttk.Label(head, text=self.app_name, font=self.f_brand,
                  background=P["bg"], foreground=P["text"]).pack(anchor="w")
        if self.subtitle:
            ttk.Label(head, text=self.subtitle, font=self.f_small,
                      background=P["bg"], foreground=P["sub"]).pack(
                anchor="w", pady=(1, 14))
        else:
            ttk.Frame(head, height=12, style="Nav.TFrame").pack(fill="x")

        self.nav_items = {}
        for key, label, _sub in self.pages:
            it = _NavItem(nav, self, label, command=lambda k=key: self.switch(k))
            it.pack(fill="x")
            self.nav_items[key] = it

        spacer = ttk.Frame(nav, style="Nav.TFrame")
        spacer.pack(fill="both", expand=True)
        self._sw = ttk.Checkbutton(nav, text="浅色模式", style="Switch.TCheckbutton",
                                   variable=None, command=self.switch_mode)
        self._sw.configure(variable=self._dummy_var())
        self._sw.pack(anchor="w", padx=24, pady=(0, 8))
        if self._footer:
            ttk.Label(nav, text=self._footer, font=self.f_small,
                      background=P["bg"], foreground=P["sub"]).pack(
                anchor="w", padx=24, pady=(0, 16))

    def _dummy_var(self):
        v = tk.BooleanVar(value=(self.mode == "light"))
        self._theme_var = v
        return v

    # ---------------------------------------------------------- 右侧内容区
    def _build_content(self):
        P = self.P
        content = ttk.Frame(self.root, style="Page.TFrame")
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(2, weight=1)
        content.columnconfigure(0, weight=1)
        self.content = content

        self.lbl_title = ttk.Label(content, text=self.pages[0][1],
                                   font=self.f_title, background=P["bg"],
                                   foreground=P["text"], anchor="w")
        self.lbl_title.grid(row=0, column=0, sticky="ew", padx=36, pady=(24, 0))
        self.lbl_sub = ttk.Label(content, text=self.pages[0][2],
                                 font=self.f_body, background=P["bg"],
                                 foreground=P["sub"], anchor="w")
        self.lbl_sub.grid(row=1, column=0, sticky="ew", padx=36, pady=(2, 12))

        self.page_host = ttk.Frame(content, style="Page.TFrame")
        self.page_host.grid(row=2, column=0, sticky="nsew")
        self.page_frames = {}
        for key, _l, _s in self.pages:
            pg = _ScrollPage(self.page_host, self)
            self.page_frames[key] = pg
        self.current = None
        self.switch(self.pages[0][0], anim=False)

    def switch(self, key, anim=True):
        if key not in self.page_frames or key == self.current:
            return
        new, old = self.page_frames[key], (
            self.page_frames[self.current] if self.current else None)
        self.current = key
        for k, label, sub in self.pages:
            if k == key:
                self.lbl_title.configure(text=label)
                self.lbl_sub.configure(text=sub)
            self.nav_items[k].set_active(k == key)
        if old:
            old.place_forget()
        if not anim or old is None:
            for f in self.page_frames.values():
                f.place_forget()
            new.place(x=0, y=0, relwidth=1, relheight=1)
            return
        n = 9

        def step(i):
            if i == 0:
                old.place(x=0, y=0, relwidth=1, relheight=1)
                new.place(x=34, y=0, relwidth=1, relheight=1)
                new.lift()
            t = i / n
            ease = 1 - (1 - t) ** 3
            new.place(x=int((1 - ease) * 34), y=0, relwidth=1, relheight=1)
            old.place(x=-int(ease * 34), y=0, relwidth=1, relheight=1)
            if i < n:
                self.page_host.after(14, lambda: step(i + 1))
            else:
                old.place_forget()
                new.place(x=0, y=0, relwidth=1, relheight=1)
        step(0)

    def page(self, key):
        """取页面容器(往里塞卡片)。"""
        return self.page_frames[key].body

    # ---------------------------------------------------------- 控件
    def card(self, parent, title=None, padding=16):
        f = ttk.Frame(parent, style="Card.TFrame", padding=padding)
        if title:
            ttk.Label(f, text=title, style="CardTitle.TLabel").pack(
                fill="x", pady=(0, 6))
        return f

    def label(self, parent, text="", role="text", font=None, anchor="w",
              bg=None, **kw):
        """role: text / sub / accent —— 换主题时颜色自动跟着变。"""
        P = self.P
        bg = bg or ("card" if str(parent).endswith("frame") else "card")
        bgc = P[bg] if bg in P else (bg or P["card"])
        fg = {"text": P["text"], "sub": P["sub"], "accent": P["accent"]}.get(
            role, P["text"])
        l = ttk.Label(parent, text=text, font=font or self.f_body,
                      background=bgc, foreground=fg, anchor=anchor, **kw)
        self._dyn.append((l, "foreground", role, "background", bg))
        return l

    def sublabel(self, parent, text):
        l = ttk.Label(parent, text=text, style="Sub.TLabel", anchor="w",
                      wraplength=760, justify="left")
        l.pack(fill="x", pady=(2, 6))
        return l

    def hint(self, parent, text):
        """页面级(背景色)说明文字。"""
        l = ttk.Label(parent, text=text, style="Hint.TLabel", anchor="w",
                      wraplength=760, justify="left")
        l.pack(fill="x", pady=(2, 6))
        return l

    def hbox(self, parent, style="Tool.TFrame", **kw):
        """横向排按钮的容器。卡片里用默认; 直接放页面上传 style='Page.TFrame'。"""
        return ttk.Frame(parent, style=style, **kw)

    def progress_color(self, pg, color):
        """给进度条单独换色(如电量绿/黄/红), 自动生成一个临时样式。"""
        name = "pc" + color.lstrip("#").lower()
        st = name + ".Horizontal.TProgressbar"
        self.style.configure(st, background=color)
        pg.configure(style=st)

    def btn(self, parent, text, cmd, primary=False, width=None):
        b = ttk.Button(parent, text=text, command=cmd,
                       style="Accent.TButton" if primary else "TButton")
        if width:
            b.configure(width=max(6, int(width // 9)))
        return b

    def switch_row(self, parent, text, desc=None, var=None):
        r = ttk.Frame(parent, style="Tool.TFrame")
        r.pack(fill="x", pady=6)
        box = ttk.Frame(r, style="Tool.TFrame")
        box.pack(side="left", fill="x", expand=True)
        ttk.Label(box, text=text, style="Body.TLabel").pack(fill="x")
        if desc:
            ttk.Label(box, text=desc, style="Sub.TLabel", anchor="w",
                      wraplength=620, justify="left").pack(fill="x")
        self.toggle(r, "", var).pack(side="right")
        return r

    def row(self, parent, text="", desc=None):
        """一行设置项: 左侧标题(可选说明), 右侧留给你 pack 控件。"""
        r = ttk.Frame(parent, style="Tool.TFrame")
        r.pack(fill="x", pady=6)
        if text:
            box = ttk.Frame(r, style="Tool.TFrame")
            box.pack(side="left", fill="x", expand=True)
            ttk.Label(box, text=text, style="Body.TLabel").pack(fill="x")
            if desc:
                ttk.Label(box, text=desc, style="Sub.TLabel", anchor="w",
                          wraplength=620, justify="left").pack(fill="x")
        return r

    def entry(self, parent, placeholder="", width=220, justify="left"):
        return _Entry(parent, self, placeholder=placeholder,
                      width=max(6, int(width // 8)), justify=justify,
                      font=self.f_body)

    def segmented(self, parent, values, variable=None, command=None):
        return _Segmented(parent, self, values, variable, command)

    def toggle(self, parent, text, var=None, command=None):
        """一个 Fluent 开关(Switch)。整行带说明用 switch_row。"""
        return ttk.Checkbutton(parent, text=text, style="Switch.TCheckbutton",
                               variable=var, command=command)

    def listbox(self, parent, height=6, on_select=None):
        """视频/文件列表(深色, 已登记换主题)。"""
        lb = tk.Listbox(parent, height=height, font=self.f_body,
                        bg=self.P["entry"], fg=self.P["text"],
                        selectbackground=self.P["sel"],
                        selectforeground=self.P["text"],
                        activestyle="none", highlightthickness=1,
                        highlightbackground=self.P["border"],
                        relief="flat", bd=6, exportselection=False)
        if on_select:
            lb.bind("<<ListboxSelect>>", lambda e: on_select(lb))
        self.track(lb, fg="text", bg="entry")
        return lb

    def slider(self, parent, from_, to, variable=None, command=None, steps=None):
        s = ttk.Scale(parent, from_=from_, to=to, orient="horizontal",
                      variable=variable, command=command)
        return s

    def progress(self, parent, mode="determinate", length=260):
        p = _Progress(parent, mode=mode, length=length,
                      style="HC.Horizontal.TProgressbar",
                      maximum=100, value=0)
        return p

    def optionmenu(self, parent, values, variable=None, command=None, width=120):
        v = variable if variable is not None else tk.StringVar()
        if not v.get():
            v.set(values[0])
        c = ttk.Combobox(parent, values=list(values), textvariable=v,
                         state="readonly", width=max(6, int(width // 8)),
                         font=self.f_body)
        if command:
            c.bind("<<ComboboxSelected>>", lambda e: command(v.get()))
        return c

    def image(self, parent, pil_img=None, size=(268, 268)):
        lbl = ttk.Label(parent, background=self.P["entry"], anchor="center")
        self._dyn.append((lbl, "foreground", "text", "background", "entry"))
        if pil_img is not None:
            self.set_image(lbl, pil_img, size)
        return lbl

    def set_image(self, label, pil_img, size=(268, 268)):
        img = ImageTk.PhotoImage(pil_img.resize(size, Image.LANCZOS))
        label.configure(image=img)
        label._img = img          # 必须留引用, 否则图片不显示

    def logbox(self, parent, height=200):
        t = tk.Text(parent, height=max(3, int(height // 20)), wrap="word",
                    font=self.f_mono, bg=self.P["entry"], fg=self.P["text"],
                    insertbackground=self.P["text"], relief="flat", bd=8,
                    highlightthickness=1, highlightbackground=self.P["border"])
        t.pack(fill="both", expand=True, pady=(4, 6))
        t.configure(state="disabled")
        self._dyn.append((t, "fg", "text", "bg", "entry"))
        return t

    # ---------------------------------------------------------- 线程安全
    def ui(self, fn):
        """后台线程更新界面一律走这里, 避免 RuntimeError。"""
        self._q.put(fn)

    def log(self, msg, textbox=None):
        if textbox is None:
            return
        self._q.put((textbox, str(msg)))

    def _drain(self):
        try:
            while True:
                item = self._q.get_nowait()
                try:
                    if callable(item):
                        item()
                    else:
                        tb, msg = item
                        tb.configure(state="normal")
                        tb.insert("end", msg + "\n")
                        tb.see("end")
                        tb.configure(state="disabled")
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.root.after(80, self._drain)

    # ---------------------------------------------------------- Toast
    def toast(self, text, ok=True):
        P = self.P
        wrap = tk.Frame(self.root, bg=P["accent"] if ok else "#e74856",
                        highlightthickness=0)
        inner = tk.Frame(wrap, bg=P["card"])
        inner.pack(fill="both", expand=True, padx=(3, 1), pady=1)
        tk.Label(inner, text=("✔  " if ok else "✖  ") + text,
                 font=self.f_body, bg=P["card"], fg=P["text"],
                 anchor="w", justify="left", wraplength=300).pack(
            padx=16, pady=11, fill="x")
        wrap.place(relx=1.0, rely=1.0, x=-26, y=70, anchor="se")

        def _in_(i=0):
            if i > 10:
                self.root.after(2800, lambda: _out())
                return
            wrap.place(y=int(70 - 64 * (i / 10)))
            self.root.after(12, lambda: _in_(i + 1))

        def _out(i=0):
            if i > 10:
                wrap.destroy()
                return
            wrap.place(y=int(6 + 64 * (i / 10)))
            self.root.after(12, lambda: _out(i + 1))
        _in_()

    # ---------------------------------------------------------- 主题切换
    def _detect_system_mode(self):
        """读系统深浅色: Windows 看 Personalize.AppsUseLightTheme, 其他平台靠 darkdetect。
        调试用: 设 FLUENT_FORCE_MODE=light/dark 可强制某个主题(不设置则跟随系统)。"""
        forced = os.environ.get("FLUENT_FORCE_MODE")
        if forced in ("light", "dark"):
            return forced
        if darkdetect is None:
            return "dark"
        try:
            t = darkdetect.theme()
        except Exception:
            return "dark"
        return "light" if t and t.lower() == "light" else "dark"

    def _apply_mode(self, mode):
        """真正执行主题切换(供手动切换与系统监听调用)。"""
        if mode not in ("dark", "light") or mode == self.mode:
            return
        self.mode = mode
        self.P = DARK if mode == "dark" else LIGHT
        sv_ttk.set_theme(mode)
        self._setup_fonts()
        self._setup_styles()
        self.root.configure(bg=self.P["bg"])
        self._refresh()
        self._apply_window()
        try:
            self._theme_var.set(mode == "light")
        except Exception:
            pass

    def _start_theme_watchdog(self):
        """后台轮询系统主题(每 2s), 变化时自动切换(仅自动跟随模式下)。"""
        if darkdetect is None:
            return
        last = self._detect_system_mode()

        def loop():
            nonlocal last
            while self._auto_follow:
                time.sleep(2)
                try:
                    cur = self._detect_system_mode()
                except Exception:
                    continue
                if cur != last and self._auto_follow:
                    last = cur
                    try:
                        self.root.after(0, self._apply_mode, cur)
                    except Exception:
                        pass

        threading.Thread(target=loop, daemon=True).start()

    def switch_mode(self):
        """手动切换深浅色(切一次后停止跟随系统)。"""
        self._auto_follow = False
        self.mode = "light" if self.mode == "dark" else "dark"
        self.P = DARK if self.mode == "dark" else LIGHT
        sv_ttk.set_theme(self.mode)
        self._setup_fonts()
        self._setup_styles()
        self.root.configure(bg=self.P["bg"])
        self._refresh()
        self._apply_window()
        try:
            self._theme_var.set(self.mode == "light")
        except Exception:
            pass

    def _refresh(self):
        P = self.P
        for it in self.nav_items.values():
            it.repaint()
        for pg in self.page_frames.values():
            pg.apply_bg(P["bg"])
            pg.body.configure(style="Page.TFrame")
        for w, fgopt, fkey, bgopt, bkey in self._dyn:
            try:
                kw = {}
                if fkey:
                    kw[fgopt] = P.get(fkey, P["text"])
                if bkey:
                    kw[bgopt] = P.get(bkey, P["card"])
                if kw:
                    w.configure(**kw)
            except Exception:
                pass
        self.root.update_idletasks()

    def track(self, widget, fg="text", bg="card"):
        """登记一个原生 tk 控件, 换主题时自动换色(fg/bg 传 None 则跳过那一项)。
        例: app.track(canvas, fg=None, bg='canvas')"""
        self._dyn.append((widget, "foreground", fg, "background", bg))

    def register(self, widget, fg_key="text", bg_key="card"):
        """track 的别名(保持旧接口)。"""
        self.track(widget, fg_key, bg_key)

    # ---------------------------------------------------------- 启动
    def mainloop(self):
        self.root.update_idletasks()
        self._apply_window()
        self.root.after(80, self._drain)
        # 测试钩子: 设了环境变量 FLUENT_SHOT 就在 1.8s 后截屏退出(平时不生效)
        shot = os.environ.get("FLUENT_SHOT")
        if shot:
            self.root.after(1800, lambda: self._debug_shot(shot))
        self.root.mainloop()

    def _debug_shot(self, path):
        try:
            from PIL import ImageGrab
            self.root.update_idletasks()
            self.root.update()
            # 提到最前, 避免被其它窗口遮挡导致截到背景
            self.root.lift()
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass
            self.root.update()
            time.sleep(0.3)
            # 用逻辑坐标(winfo_rootx/width)截, 避免高 DPI 下物理/逻辑错位
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
        except Exception as e:
            print("shot fail:", e)
        self.root.destroy()


# ------------------------------------------------------------------ demo
if __name__ == "__main__":
    app = FluentShell(title="FluentShell v3 示例", app_name="示例工具",
                      subtitle="真正的 Win11 观感",
                      pages=[("home", "概览", "常用功能入口"),
                             ("settings", "设置", "调整各项参数")],
                      footer="v3.0")

    p1 = app.page("home")
    c1 = app.card(p1, "操作")
    c1.pack(fill="x", pady=6)
    bar = app.hbox(c1)
    bar.pack(fill="x", pady=(4, 10))
    app.btn(bar, "点我试试", lambda: app.toast("操作完成啦"), primary=True).pack(
        side="left", padx=(0, 10))
    app.btn(bar, "次要按钮", lambda: app.toast("提示", ok=False)).pack(side="left")
    app.sublabel(c1, "切到「设置」页可以看滑动动画、开关和分段控件")

    c = app.card(p1, "进度")
    c.pack(fill="x", pady=6)
    pg = app.progress(c)
    pg.pack(fill="x", pady=6)
    pg.start(18)

    p2 = app.page("settings")
    c2 = app.card(p2, "选项")
    c2.pack(fill="x", pady=6)
    app.switch_row(c2, "启用某项", "打开后会有神奇效果", tk.BooleanVar(value=True))
    app.switch_row(c2, "另一项", "关掉也行", tk.BooleanVar(value=False))
    r = app.row(c2, "数量", "0 ~ 100")
    app.slider(r, 0, 100, variable=tk.DoubleVar(value=40)).pack(side="right")
    r2 = app.row(c2, "模式")
    app.segmented(r2, ["标准", "高", "自定义"],
                  tk.StringVar(value="标准")).pack(side="right")
    r3 = app.row(c2, "名称", "随便填点什么")
    app.entry(r3, placeholder="例如：锟哥的工具", width=240).pack(side="right")
    app.mainloop()
