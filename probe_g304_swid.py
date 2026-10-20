"""照抄 G HUB 的 software_id (0xE) 重新测试 HID++ 2.0 电池读取。"""
import hid
import time

VID, PID = 0x046D, 0xC53F
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)


def flush():
    for _ in range(40):
        if not dev.read(64):
            break


def tx(pkt, wait=0.3):
    flush()
    try:
        dev.write(pkt)
    except Exception as e:
        return f"write-err {e}"
    out = []
    end = time.time() + wait
    while time.time() < end:
        r = dev.read(64)
        if r:
            out.append(bytes(r).hex(" "))
        else:
            time.sleep(0.004)
    return out


print("=== 1) root func1 getProtocolVersion, sw=0xE（G HUB 原样）===")
print("  ", tx(bytes([0x10, 0x01, 0x00, 0x1E, 0x00, 0x00, 0x00])))
print("=== 1b) 同一条 sw=0x1 ===")
print("  ", tx(bytes([0x10, 0x01, 0x00, 0x11, 0x00, 0x00, 0x00])))

print("\n=== 2) root func0 getFeature(0x1000) 各 sw_id ===")
for sw in (0x0E, 0x01, 0x02, 0x0F):
    pkt = bytes([0x10, 0x01, 0x00, (0x00 << 4) | sw, 0x10, 0x00, 0x00])
    print(f"  sw={sw:#04x} [lo,hi]:", tx(pkt))

print("\n=== 3) 接收器侧 1.0 寄存器（G HUB 同款序列）===")
for pkt in ([0x10, 0xFF, 0x81, 0x00, 0x00, 0x00, 0x00],
            [0x10, 0xFF, 0x81, 0x02, 0x00, 0x00, 0x00],
            [0x10, 0xFF, 0x80, 0x02, 0x02, 0x00, 0x00],
            [0x10, 0xFF, 0x00, 0x1E, 0x00, 0x00, 0x00],
            [0x10, 0xFF, 0x81, 0xF1, 0x01, 0x00, 0x00],
            [0x10, 0xFF, 0x81, 0xF1, 0x02, 0x00, 0x00],
            [0x10, 0xFF, 0x81, 0xF1, 0x11, 0x00, 0x00]):
    print(f"  {bytes(pkt).hex(' ')} ->", tx(bytes(pkt)))

print("\n=== 4) 再次给鼠标 root 请求（接收器状态刷新后）===")
for sw in (0x0E,):
    print("  ", tx(bytes([0x10, 0x01, 0x00, (0x00 << 4) | sw, 0x10, 0x00, 0x00]), 0.5))
