"""1) 连读 feature 0x06 比对是否静态  2) 试 0xFF02 的 out 0x13 命令通道"""
import hid, time

VID, PID = 0x3554, 0xFA09
f_path = c_path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF04 and d["usage"] == 0x0002:
        f_path = d["path"]
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        c_path = d["path"]

print("=== 1) feature 0x06 连续三次（间隔 2s）===")
dev = hid.device(); dev.open_path(f_path)
for i in range(3):
    d = bytes(dev.get_feature_report(0x06, 65))
    print(f"  #{i}: len={len(d)}  {d.hex(' ')}")
    time.sleep(2)
dev.close()

print("\n=== 2) out 0x13 命令通道探测 ===")
if not c_path:
    print("  没找到 0xFF02 接口")
else:
    cmd_dev = hid.device(); cmd_dev.open_path(c_path)
    cmd_dev.set_nonblocking(1)
    dev2 = hid.device(); dev2.open_path(c_path); dev2.set_nonblocking(1)
    trials = [
        [0x13] + [0]*18,
        [0x13, 0x01] + [0]*17,
        [0x13, 0x02] + [0]*17,
        [0x13, 0x03] + [0]*17,
        [0x13, 0x06] + [0]*17,
        [0x13, 0x10] + [0]*17,
        [0x13, 0x12] + [0]*17,
        [0x13, 0x18] + [0]*17,
        [0x13, 0x20] + [0]*17,
        [0x13, 0x00, 0x02] + [0]*16,
    ]
    for t in trials:
        try:
            n = cmd_dev.write(bytes(t))
        except Exception as e:
            print(f"  write {t[:3]}: 失败 {e}")
            continue
        got = []
        end = time.time() + 0.3
        while time.time() < end:
            try:
                r = dev2.read(64)
            except OSError:
                break
            if r:
                got.append(bytes(r).hex(" "))
        print(f"  write {bytes(t[:4]).hex(' ')} -> {n}B  响应: {got if got else '无'}")
        time.sleep(0.2)
    cmd_dev.close(); dev2.close()
