"""扫描罗技接收器 HID++ 报文的各种组合，找出能返回电量的请求格式。"""
import hid
import time

VID, PID = 0x046D, 0xC53F

path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001:
        path = d["path"]
        break
print("path:", path)

dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)


def flush():
    for _ in range(20):
        if not dev.read(64):
            break


def tx(payload, wait=0.35, reads=4):
    flush()
    try:
        dev.write(payload)
    except Exception as e:
        return [f"write-error {e}"]
    out = []
    deadline = time.time() + wait
    while time.time() < deadline and len(out) < reads:
        try:
            r = dev.read(64)
        except OSError:
            break
        if r:
            out.append(bytes(r).hex(" "))
        else:
            time.sleep(0.01)
    return out


tests = []
# HID++2.0 root getFeature, 两种 featureId 字节序, devIdx 0xff 与 1
for di in (0xFF, 0x01):
    for feat_id in (0x1000, 0x1001, 0x0000, 0x0005, 0x0003):
        tests.append((f"20.getFeature({feat_id:#06x}) dev={di:#04x} [lo,hi]",
                      [0x10, di, 0x00, 0x00, feat_id & 0xFF, feat_id >> 8, 0x00]))
        tests.append((f"20.getFeature({feat_id:#06x}) dev={di:#04x} [hi,lo]",
                      [0x10, di, 0x00, 0x00, feat_id >> 8, feat_id & 0xFF, 0x00]))
# HID++1.0 ping
tests.append(("10.ping dev=1", [0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]))
tests.append(("10.ping dev=ff", [0x10, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00]))
# HID++1.0 GET_REGISTER(0x83) 读电池寄存器 0x0D / 0x07
for addr in (0x0D, 0x07, 0x0B):
    for di in (0xFF, 0x01):
        tests.append((f"10.getReg(addr={addr:#04x}) dev={di:#04x}",
                      [0x10, di, 0x83, addr, 0x00, 0x00, 0x00]))
# HID++1.0 电池相关 subId 0x07
for sub in (0x07, 0x0D):
    tests.append((f"10.subId={sub:#04x} dev=1", [0x10, 0x01, sub, 0x00, 0x00, 0x00, 0x00]))

for name, payload in tests:
    res = tx(payload)
    print(f"{name:52s} -> {res}")
