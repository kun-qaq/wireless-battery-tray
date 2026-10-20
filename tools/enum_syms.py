"""枚举目标进程模块的导出/调试符号，寻找与电量相关的函数。"""
import sys
import frida

TARGET = sys.argv[1]
KW = [k.lower() for k in (sys.argv[2:] or ["battery", "headset", "power"])]

JS = r"""
var mods = Process.enumerateModules();
var names = [];
mods.forEach(function (m) { names.push(m.name + " @ " + m.base); });
send({tag: "MODS", list: names});

var target = null;
mods.forEach(function (m) {
    if (m.name.toLowerCase().indexOf("%NAME%") >= 0) target = m;
});
if (!target) { send({tag: "ERR", msg: "module not found"}); }
else {
    var syms = [];
    try { syms = target.enumerateSymbols(); } catch (e) { send({tag: "ERR", msg: "" + e}); }
    send({tag: "COUNT", n: syms.length});
    syms.forEach(function (s) {
        syms_out.push(s.name + " | " + s.address);
    });
    send({tag: "SYMS", list: syms_out});
}
var syms_out = [];
"""

# 上面的脚本逻辑需要顺序修正，改用简单版本
JS = r"""
var mods = Process.enumerateModules();
var target = null;
mods.forEach(function (m) {
    if (m.name.toLowerCase().indexOf("%NAME%") >= 0) target = m;
});
if (!target) { send({tag: "ERR", msg: "module not found"}); }
else {
    var out = [];
    try {
        var syms = target.enumerateSymbols();
        syms.forEach(function (s) { out.push(s.name + " | " + s.address); });
    } catch (e) { send({tag: "ERR", msg: "" + e}); }
    send({tag: "SYMS", list: out});
}
""".replace("%NAME%", TARGET.lower().replace(".exe", ""))


def on_message(msg, data):
    if msg["type"] != "send":
        print("[err]", msg.get("description"))
        return
    p = msg["payload"]
    if p["tag"] == "ERR":
        print("[frida]", p["msg"])
        return
    if p["tag"] == "SYMS":
        hits = [s for s in p["list"] if any(k in s.lower() for k in KW)]
        print(f"符号总数 {len(p['list'])}，命中 {len(hits)}")
        for h in hits[:60]:
            print("  ", h)


device = frida.get_local_device()
procs = [p for p in device.enumerate_processes() if TARGET.lower() in p.name.lower()]
if not procs:
    raise SystemExit(f"进程 {TARGET} 未运行")
for p in procs:
    print("attach", p.name, p.pid)
    s = device.attach(p.pid)
    sc = s.create_script(JS)
    sc.on("message", on_message)
    sc.load()
    s.detach()
