"""探测非罗技 2.4G 接收器的 vendor HID 接口：监听主动上报 + 枚举 feature report。"""
import hid
import sys
import time

TARGETS = {
    "K98键盘": (0x3554, 0xFA09),
    "Akko S9耳机": (0x36EB, 0x1087),
}


def listen(path, seconds=4):
    dev = hid.device()
    try:
        dev.open_path(path)
    except OSError as e:
        print(f"    [open fail] {e}")
        return []
    dev.set_nonblocking(1)
    got = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            r = dev.read(64)
        except OSError:
            print("    [read unsupported on this collection]")
            break
        if r:
            got.append(bytes(r))
            print(f"    [input] {bytes(r).hex(' ')}")
        else:
            time.sleep(0.005)
    dev.close()
    return got


def feature_reports(path, ids=range(0, 12)):
    dev = hid.device()
    try:
        dev.open_path(path)
    except OSError as e:
        print(f"    [open fail] {e}")
        return
    for rid in ids:
        buf = [0] * 65
        buf[0] = rid
        try:
            n = dev.get_feature_report(bytes(buf))
            if n:
                content = bytes(buf[:n])
                if any(content[1:]):
                    print(f"    [feature {rid:#04x}] len={n} {content.hex(' ')}")
        except Exception:
            pass
    dev.close()


for name, (vid, pid) in TARGETS.items():
    print(f"\n########## {name}  VID_{vid:04X} PID_{pid:04X} ##########")
    for d in hid.enumerate(vid, pid):
        up, u = d["usage_page"], d["usage"]
        # 只关心厂商自定义 / POS 接口
        if up in (0x0001, 0x000C, 0x000D) and u in (0x0002, 0x0006, 0x0001, 0x0080):
            continue
        print(f"  if={d['interface_number']} UP=0x{up:04X} U=0x{u:04X}")
        listen(d["path"], 3)
        feature_reports(d["path"])
