"""启动目标程序后立刻 attach 并 hook HID 读写，抓取启动时/界面刷新时的查询报文。"""
import os
import subprocess
import sys
import time

import frida

EXE = sys.argv[1]
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
LAUNCH = (sys.argv[3] if len(sys.argv) > 3 else "1") == "1"

JS = r"""
var hooked = [];
function findExport(name) {
    try { if (typeof Module.getGlobalExportByName === "function") return Module.getGlobalExportByName(name); } catch (e) {}
    try { if (typeof Module.getExportByName === "function") return Module.getExportByName(null, name); } catch (e) {}
    return null;
}
function hx(ptr, len) {
    var out = [];
    for (var i = 0; i < len && i < 64; i++) {
        var b = ptr.add(i).readU8();
        out.push((b < 16 ? "0" : "") + b.toString(16));
    }
    return out.join(" ");
}
function hookW(name, tag, getLen, getBuf) {
    var a = findExport(name);
    if (!a) return;
    Interceptor.attach(a, {
        onEnter: function (args) {
            var l = getLen(args);
            if (l > 0 && l <= 128) send({tag: tag, api: name, len: l, data: hx(getBuf(args), l)});
        }
    });
    hooked.push(name);
}
hookW("WriteFile", "TX", function (a) { return a[2].toInt32(); }, function (a) { return a[1]; });
hookW("HidD_SetFeature", "TX-FEAT", function (a) { return a[4].toInt32(); }, function (a) { return a[1]; });

var rf = findExport("ReadFile");
if (rf) {
    Interceptor.attach(rf, {
        onEnter: function (a) { this.buf = a[1]; this.cnt = a[3]; },
        onLeave: function (ret) {
            try {
                var n = this.cnt.readUInt32();
                if (n > 0 && n <= 128) send({tag: "RX", api: "ReadFile", len: n, data: hx(this.buf, n)});
            } catch (e) {}
        }
    });
    hooked.push("ReadFile");
}
var gf = findExport("HidD_GetFeature");
if (gf) {
    Interceptor.attach(gf, {
        onEnter: function (a) { this.buf = a[1]; this.len = a[4].toInt32(); },
        onLeave: function (ret) {
            try { if (ret.toInt32() !== 0) send({tag: "RX-FEAT", api: "HidD_GetFeature", len: this.len, data: hx(this.buf, this.len)}); } catch (e) {}
        }
    });
    hooked.push("HidD_GetFeature");
}
send({tag: "INFO", msg: "hooked: " + hooked.join(",")});
"""

NAME = os.path.basename(EXE)


def on_message(msg, data):
    if msg["type"] == "send":
        p = msg["payload"]
        if p.get("tag") == "INFO":
            print("[frida]", p["msg"])
        else:
            print(f"[{p['tag']:<8}] {p['api']:<16} len={p['len']:<3} {p['data']}")
    else:
        print("[err]", msg.get("description"))


device = frida.get_local_device()

if LAUNCH:
    print("launching", EXE)
    subprocess.Popen([EXE], cwd=os.path.dirname(EXE))

# 等进程出现
pid = None
for _ in range(60):
    for p in device.enumerate_processes():
        if p.name.lower() == NAME.lower():
            pid = p.pid
            break
    if pid:
        break
    time.sleep(0.1)

if not pid:
    raise SystemExit("进程未出现")

print(f"attach pid={pid} after launch")
session = device.attach(pid)
script = session.create_script(JS)
script.on("message", on_message)
script.load()
print(f"监听 {DURATION}s ...（如需刷新请在界面上点击设备）")
time.sleep(DURATION)
session.detach()
