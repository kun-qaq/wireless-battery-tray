"""spawn 启动驱动并 hook 全部 HID 读写（含 ReadFile 响应），抓取电量查询报文。"""
import sys
import time

import frida

EXE = sys.argv[1]
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0

JS = r"""
var hooked = [];

function findExport(mod, name) {
    try { if (typeof Module.getGlobalExportByName === "function") return Module.getGlobalExportByName(name); } catch (e) {}
    try { if (typeof Module.getExportByName === "function") return Module.getExportByName(mod, name); } catch (e) {}
    try { return Process.getModuleByName(mod).getExportByName(name); } catch (e) {}
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

function hookWrite(mod, name, tag, getLen, getBuf) {
    var addr = findExport(mod, name);
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (a) {
            this.len = getLen(a);
            if (this.len > 0 && this.len <= 128)
                send({tag: tag, api: name, len: this.len, data: hx(getBuf(a), this.len)});
        }
    });
    hooked.push(name);
}

// 发送方向
hookWrite("kernel32.dll", "WriteFile", "TX",
          function (a) { return a[2].toInt32(); }, function (a) { return a[1]; });
hookWrite("hid.dll", "HidD_SetFeature", "TX-FEAT",
          function (a) { return a[4].toInt32(); }, function (a) { return a[1]; });

// 接收方向：ReadFile 完成后读取实际字节数
var rf = findExport("kernel32.dll", "ReadFile");
if (rf) {
    Interceptor.attach(rf, {
        onEnter: function (a) { this.buf = a[1]; this.cnt = a[3]; this.req = a[2].toInt32(); },
        onLeave: function (ret) {
            try {
                var n = this.cnt.readUInt32();
                if (n > 0 && n <= 128) send({tag: "RX", api: "ReadFile", len: n, data: hx(this.buf, n)});
            } catch (e) {}
        }
    });
    hooked.push("ReadFile");
}

// 接收方向：HidD_GetFeature 完成后
var gf = findExport("hid.dll", "HidD_GetFeature");
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


def on_message(msg, data):
    if msg["type"] == "send":
        p = msg["payload"]
        if p.get("tag") == "INFO":
            print("[frida]", p["msg"])
        else:
            print(f"[{p['tag']:<8}] {p['api']:<16} len={p['len']:<3} {p['data']}")
    elif msg["type"] == "error":
        print("[frida error]", msg.get("description"))


device = frida.get_local_device()
print("spawning", EXE)
pid = device.spawn([EXE])
session = device.attach(pid)
script = session.create_script(JS)
script.on("message", on_message)
script.load()
device.resume(pid)
print(f"resumed pid={pid}, 监听 {DURATION}s ...")
time.sleep(DURATION)
try:
    session.detach()
except Exception:
    pass
