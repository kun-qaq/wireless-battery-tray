"""90 秒全局监听：等待 Akko / 灵豹驱动进程出现并 hook 其 HID 读写，抓取真实电量查询报文。"""
import sys
import time

import frida

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0

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
hookW("HidD_SetOutputReport", "TX-OUT", function (a) { return a[4].toInt32(); }, function (a) { return a[1]; });
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
var gof = findExport("HidD_GetOutputReport");
if (gof) {
    Interceptor.attach(gof, {
        onEnter: function (a) { this.buf = a[1]; this.len = a[4].toInt32(); },
        onLeave: function (ret) {
            try { if (ret.toInt32() !== 0) send({tag: "RX-OUT", api: "HidD_GetOutputReport", len: this.len, data: hx(this.buf, this.len)}); } catch (e) {}
        }
    });
    hooked.push("HidD_GetOutputReport");
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
send({tag: "INFO", msg: "hooked ok"});
"""

TAG = {}

seen = set()


def on_message(pid, name):
    def handler(msg, data):
        if msg["type"] == "send":
            p = msg["payload"]
            if p.get("tag") == "INFO":
                print(f"[{name}] hooked", flush=True)
            else:
                print(f"[{name} pid={pid} {p['tag']:<7}] {p['api']:<16} len={p['len']:<3} {p['data']}", flush=True)
        else:
            print(f"[{name} err] {msg.get('description')}", flush=True)
    return handler


device = frida.get_local_device()
deadline = time.time() + DURATION
print(f"监听 {DURATION:.0f}s，等待驱动进程出现...", flush=True)
while time.time() < deadline:
    for p in device.enumerate_processes():
        low = p.name.lower()
        if (low in ("akko-audio.exe", "oemdrv.exe")) and p.pid not in seen:
            seen.add(p.pid)
            try:
                s = device.attach(p.pid)
                sc = s.create_script(JS)
                sc.on("message", on_message(p.pid, p.name))
                sc.load()
                print(f"### attached {p.name} pid={p.pid}", flush=True)
            except Exception as e:
                print(f"### attach fail {p.name}: {e}", flush=True)
    time.sleep(0.4)
print("监听结束", flush=True)
