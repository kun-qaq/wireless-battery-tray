"""探测 Akko S9 耳机 (HID POS, report 0x02) 与 K98 键盘 (vendor, report 0x13) 的命令响应。"""
import hid
import time
import sys

dev_serial = None


def open_first(vid, pid, usage_page, usage):
    for d in hid.enumerate(vid, pid):
        if d["usage_page"] == usage_page and d["usage"] == usage:
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(1)
            return dev, d
    return None, None


def drain(dev, secs=0.15):
    end = time.time() + secs
    out = []
    while time.time() < end:
        try:
            r = dev.read(128)
        except OSError:
            break
        if r:
            out.append(bytes(r))
        else:
            time.sleep(0.004)
    return out


def probe(dev, report_id, payload_len, tests, wait=0.3, label=""):
    print(f"\n===== {label} =====")
    for t in tests:
        body = list(t) + [0] * (payload_len - len(t))
        pkt = bytes([report_id] + body)
        drain(dev)
        try:
            dev.write(pkt)
        except Exception as e:
            print(f"  send {bytes(t).hex(' '):<24} -> write error {e}")
            continue
        resp = drain(dev, wait)
        shown = [r.hex(" ") for r in resp]
        # 只显示与请求同 cmd 的响应，过滤心跳噪声
        interesting = []
        for r in resp:
            b = bytes(r)
            if len(b) < 3:
                continue
            if b[1] == t[0] and b[2] == (t[1] if len(t) > 1 else 0):
                interesting.append(b.hex(" "))
        print(f"  send {bytes(t).hex(' '):<24} -> match={interesting if interesting else '-'} all={shown[:3]}")


which = sys.argv[1] if len(sys.argv) > 1 else "akko"

if which == "akko":
    dev, info = open_first(0x36EB, 0x1087, 0x008C, 0x0001)
    if not dev:
        raise SystemExit("耳机接口未找到")
    print("耳机接口:", info["path"].decode() if isinstance(info["path"], bytes) else info["path"])
    print("先静听 2 秒看心跳:")
    for r in drain(dev, 2.0):
        print("   ", r.hex(" "))
    tests = []
    # 复现已知的 0x10 0x01
    tests.append([0x10, 0x01])
    for sub in range(0x00, 0x09):
        tests.append([0x10, sub])
    for cmd in range(0x00, 0x14):
        tests.append([cmd, 0x00])
    probe(dev, 0x02, 63, tests, 0.25, "Akko S9 output report 0x02")
    dev.close()
else:
    dev, info = open_first(0x3554, 0xFA09, 0xFF02, 0x0002)
    if not dev:
        raise SystemExit("键盘 vendor 接口未找到")
    print("键盘接口:", info["path"].decode() if isinstance(info["path"], bytes) else info["path"])
    dev.set_nonblocking(1)
    tests = [[c, 0x00] for c in range(0x00, 0x14)]
    probe(dev, 0x13, 19, tests, 0.3, "K98 output report 0x13")
    dev.close()
