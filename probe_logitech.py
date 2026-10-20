"""测试罗技 G304 通过 LIGHTSPEED 接收器读取电量 (HID++ 2.0 特性 0x1000)。"""
import hid
import time

VID, PID = 0x046D, 0xC53F

# 找到 HID++ 短报文接口 (usage_page 0xFF00, usage 0x0001)
paths = []
for d in hid.enumerate(VID, PID):
    print(f"if={d['interface_number']} UP=0x{d['usage_page']:04X} U=0x{d['usage']:04X} {d['path']}")
    if d["usage_page"] == 0xFF00 and d["usage"] in (0x0001, 0x0002):
        paths.append(d)

print("candidates:", len(paths))


def open_dev(path):
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(1)
    return dev


def request(dev, payload7, long_payload=False):
    """发一条 HID++ 报文并读回复。"""
    dev.write(payload7)
    deadline = time.time() + 0.4
    while time.time() < deadline:
        r = dev.read(64)
        if r:
            return r
        time.sleep(0.01)
    return None


if not paths:
    raise SystemExit("未找到 HID++ 接口")

dev = open_dev(paths[0]["path"])
print("opened", paths[0]["path"])

for dev_index in [0xFF] + list(range(1, 7)):
    # 1) 询问 root(0x0000) 特性 0x1000 (BATTERY_LEVEL_STATUS) 的 feature index
    req = [0x10, dev_index, 0x00, 0x00, 0x00, 0x10, 0x00]
    r = request(dev, req)
    print(f"\ndevIdx={dev_index:#04x} getFeature(0x1000) -> {bytes(r).hex(' ') if r else None}")
    if not r:
        continue
    if len(r) >= 5 and r[3] != 0:
        feat_idx = r[4]
        print(f"  feature 0x1000 index = {feat_idx:#04x}")
        # 2) 读电量: function 0 = getBatteryLevelStatus
        r2 = request(dev, [0x10, dev_index, feat_idx, 0x00, 0x00, 0x00, 0x00])
        print(f"  battery -> {bytes(r2).hex(' ') if r2 else None}")
        if r2 and len(r2) >= 7:
            print(f"  ==> level={r2[4]}% status={r2[5]:#04x}")
        # 3) 备选特性 0x1001 (BATTERY_VOLTAGE)
        r3 = request(dev, [0x10, dev_index, 0x00, 0x00, 0x01, 0x10, 0x00])
        if r3 and len(r3) >= 5 and r3[3] != 0:
            fi = r3[4]
            fi3 = request(dev, [0x10, dev_index, fi, 0x00, 0x00, 0x00, 0x00])
            print(f"  feature 0x1001 idx={fi:#04x} -> {bytes(fi3).hex(' ') if fi3 else None}")

dev.close()
