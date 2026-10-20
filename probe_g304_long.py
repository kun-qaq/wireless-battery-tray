"""关键修正：HID++ long report (0x11) 必须写到 usage 0x0002 的接口上。"""
import hid
import time

VID, PID = 0x046D, 0xC53F
infos = list(hid.enumerate(VID, PID))
p_short = next(d["path"] for d in infos if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001)
p_long = next(d["path"] for d in infos if d["usage_page"] == 0xFF00 and d["usage"] == 0x0002)


def open_dev(path):
    d = hid.device()
    d.open_path(path)
    d.set_nonblocking(1)
    return d


longdev = open_dev(p_long)
shortdev = open_dev(p_short)


def tx(dev, pkt, wait=0.35):
    for _ in range(30):
        if not dev.read(128):
            break
    try:
        dev.write(pkt)
    except Exception as e:
        return f"write-err {e}"
    out = []
    end = time.time() + wait
    while time.time() < end:
        r = dev.read(128)
        if r:
            out.append(bytes(r).hex(" "))
        else:
            time.sleep(0.004)
    return out


print("=== 长报文发到 0x0002 接口 ===")
for di in (0x01, 0xFF):
    for func, name in ((0x01, "getProtocolVersion"), (0x00, "getFeature(0x1000)")):
        if func == 0:
            pkt = bytes([0x11, di, 0x00, 0x0E, 0x10, 0x00] + [0] * 14)
        else:
            pkt = bytes([0x11, di, 0x00, 0x1E] + [0] * 16)
        print(f"  dev={di:#04x} {name}: {tx(longdev, pkt)}")

print("\n=== 短报文发到 0x0002 接口（对照）===")
print("  ", tx(longdev, bytes([0x10, 0x01, 0x00, 0x1E, 0x00, 0x00, 0x00])))

print("\n=== 如果拿到了 feature index，读电量 ===")
# 先查 feature index
pkt = bytes([0x11, 0x01, 0x00, 0x0E, 0x10, 0x00] + [0] * 14)
res = tx(longdev, pkt)
print("  getFeature(0x1000):", res)
if res and isinstance(res, list) and res[0].startswith("11"):
    b = bytes.fromhex(res[0].replace(" ", ""))
    if len(b) > 4 and b[3] != 0x8F and b[4]:
        fi = b[4]
        print(f"  feature index = {fi:#04x}")
        batt = tx(longdev, bytes([0x11, 0x01, fi, 0x0E] + [0] * 16))
        print("  battery:", batt)
        if batt and isinstance(batt, list):
            bb = bytes.fromhex(batt[0].replace(" ", ""))
            print(f"  ==> level={bb[4]}% status={bb[5]:#04x}")
