"""先移动鼠标唤醒 G304，再立刻发 2.0 请求，验证是否为休眠导致无响应。"""
import ctypes
import hid
import time

VID, PID = 0x046D, 0xC53F
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)

user32 = ctypes.windll.user32


def wiggle():
    p = ctypes.wintypes.POINT() if hasattr(ctypes, "wintypes") else None
    import ctypes.wintypes as wt
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    for dx in (1, -1, 1):
        user32.SetCursorPos(pt.x + dx, pt.y + dx)
        time.sleep(0.02)
    user32.SetCursorPos(pt.x, pt.y)


def flush():
    for _ in range(30):
        if not dev.read(64):
            break


def tx(payload, wait=0.5):
    flush()
    dev.write(payload)
    out = []
    deadline = time.time() + wait
    while time.time() < deadline:
        r = dev.read(64)
        if r:
            out.append(bytes(r).hex(" "))
        else:
            time.sleep(0.005)
    return out

wiggle()
time.sleep(0.2)

print("after wiggle, 2.0 getFeature(0x1000) on dev 1..6 / ff")
for di in (0x01, 0x02, 0xFF):
    print(f"  dev={di:#04x}:", tx([0x10, di, 0x00, 0x00, 0x00, 0x10, 0x00]))

print("\nretry dev=1 x5 with 250ms gap")
for i in range(5):
    wiggle()
    print(f"  try{i}:", tx([0x10, 0x01, 0x00, 0x00, 0x00, 0x10, 0x00], 0.4))
    time.sleep(0.25)
