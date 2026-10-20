"""罗技接收器第二轮：HID++ 1.0 寄存器读取 + 长报文测试。"""
import hid
import time

VID, PID = 0x046D, 0xC53F
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)


def flush():
    for _ in range(30):
        if not dev.read(64):
            break


def tx(payload, wait=0.4):
    flush()
    try:
        dev.write(payload)
    except Exception as e:
        return f"write-error {e}"
    out = []
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            r = dev.read(64)
        except OSError:
            break
        if r:
            out.append(bytes(r).hex(" "))
        else:
            time.sleep(0.005)
    return out

BATT_LEVELS = [0, 5, 20, 40, 60, 80, 90, 100]

print("=== HID++1.0 GET_REGISTER(0x81) ===")
for di in (0xFF, 0x01):
    for addr in (0x0D, 0x07, 0x0F, 0x0B, 0x00, 0x02):
        r = tx([0x10, di, 0x81, addr, 0x00, 0x00, 0x00])
        extra = ""
        for item in (r if isinstance(r, list) else []):
            b = bytes.fromhex(item)
            if len(b) >= 5 and b[2] == 0x81 and b[3] == addr:
                lvl = b[4]
                extra = f"  <= level raw={lvl} -> {BATT_LEVELS[lvl] if lvl < 8 else '?'}%  status={b[6] if len(b)>6 else '-'}"
        print(f"dev={di:#04x} addr={addr:#04x} -> {r}{extra}")

print("\n=== HID++1.0 GET_LONG_REGISTER(0x83) 16字节 ===")
for addr in (0x0D, 0x07, 0x0F):
    r = tx([0x10, 0x01, 0x83, addr, 0x01, 0x00, 0x00])
    print(f"addr={addr:#04x} -> {r}")

print("\n=== 长报文 0x11 试探 (2.0) ===")
for di in (0xFF, 0x01):
    p = [0x11, di, 0x00, 0x00, 0x00, 0x10] + [0] * 14
    print(f"dev={di:#04x} -> {tx(p)}")
