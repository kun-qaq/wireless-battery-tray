"""用 frida hook 驱动进程的 HID 读写，抓取真实报文，用于逆向电量查询命令。"""
import sys
import time

import frida

TARGET = sys.argv[1] if len(sys.argv) > 1 else "AKKO-Audio.exe"
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0

JS = r"""
function mydump(arr, len) {
    var out = [];
    for (var i = 0; i < len && i < 64; i++) {
        var b = arr[i] & 0xff;
        out.push((b < 16 ? "0" : "") + b.toString(16));
    }
    return out.join(" ");
}

var hooked = [];

function findExport(mod, name) {
    // 兼容 frida 16/17 的 API 差异
    try { if (typeof Module.getGlobalExportByName === "function") return Module.getGlobalExportByName(name); } catch (e) {}
    try { if (typeof Module.getExportByName === "function") return Module.getExportByName(mod, name); } catch (e) {}
    try {
        var m = Process.getModuleByName(mod);
        return m.getExportByName(name);
    } catch (e) {}
    return null;
}

function hook(mod, name, argbuf, arglen, tag) {
    var addr = findExport(mod, name);
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (args) {
            var len = arglen(args);
            if (len === 0 || len > 128) return;
            try { send({tag: tag, api: name, len: len, data: mydump(argbuf(args), len)}); } catch (e) {}
        }
    });
    hooked.push(name);
}

// hidapi 静态链接时走 kernel32 WriteFile / ReadFile，以及 hid.dll 的 Feature report API
hook("kernel32.dll", "WriteFile",
     function (a) { return a[2].toInt32(); },       // nNumberOfBytesToWrite
     function (a) { return a[1]; }, "W");
hook("hid.dll", "HidD_SetFeature",
     function (a) { return a[4].toInt32(); },
     function (a) { return a[1]; }, "SETFEAT");
hook("hid.dll", "HidD_GetFeature",
     function (a) { return a[4].toInt32(); },
     function (a) { return a[1]; }, "GETFEAT");

send({tag: "INFO", msg: "hooked: " + hooked.join(",")});
"""

found = []


def on_message(msg, data):
    if msg["type"] == "send":
        p = msg["payload"]
        if p.get("tag") == "INFO":
            print("[frida]", p["msg"])
        else:
            print(f"[{p['tag']}] {p['api']} len={p['len']}  {p['data']}")
    elif msg["type"] == "error":
        print("[frida error]", msg.get("description"))


def main():
    # 直接按名字 attach 到已运行的进程
    device = frida.get_local_device()
    procs = [p for p in device.enumerate_processes() if TARGET.lower() in p.name.lower()]
    if not procs:
        print(f"未找到进程 {TARGET}，请先运行驱动。")
        return
    for p in procs:
        print(f"attach {p.name} pid={p.pid}")
        session = frida.attach(p.pid)
        script = session.create_script(JS)
        script.on("message", on_message)
        script.load()
        found.append(session)
    print(f"监听 {DURATION}s ... 期间请在驱动界面上点击/刷新电量")
    time.sleep(DURATION)
    for s in found:
        s.detach()


if __name__ == "__main__":
    main()
