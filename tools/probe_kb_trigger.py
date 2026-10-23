"""1) 被动监听 12 秒，看 0x0a 帧是否自己冒出来
2) 发 0x05 触发，重复 8 次，统计 0x0a 跟随率
3) 单独发 0x0a（带校验）重复 8 次
"""
import hid, time

VID, PID = 0x3554, 0xFA09
path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        path = d["path"]
        break

w = hid.device(); w.open_path(path); w.set_nonblocking(1)
r = hid.device(); r.open_path(path); r.set_nonblocking(1)


def cksum(b):
    return sum(b) & 0xFF


def flush():
    for _ in range(80):
        try:
            if not r.read(64):
                break
        except OSError:
            break


def collect(secs):
    end = time.time() + secs
    out = []
    while time.time() < end:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            out.append((time.time(), bytes(b)))
        time.sleep(0.003)
    return out


def send(cmd, wait=0.9):
    flush()
    body = bytes([0x13, cmd]) + bytes(16)
    w.write(body + bytes([cksum(body)]))
    return collect(wait)


def batt(frames):
    for t, f in frames:
        if len(f) > 6 and f[0] == 0x13 and f[1] == 0x0A:
            return f[6]
    return None


print("=== 1) 被动监听 12 秒 ===")
flush()
t0 = time.time()
frames = collect(12)
if frames:
    for t, f in frames:
        print(f"  +{t - t0:5.2f}s  {f.hex(' ')}")
else:
    print("  12 秒内无任何自发帧")

print("\n=== 2) 发 cmd 0x05 触发，8 次 ===")
hits = 0
vals = []
for i in range(8):
    fs = send(0x05, 0.9)
    v = batt(fs)
    if v is not None:
        hits += 1
        vals.append(v)
    print(f"  #{i}: 帧数={len(fs):2d} 电量={v}  " + " | ".join(f.hex(' ') for _, f in fs))
    time.sleep(0.5)
print(f"  跟随率 {hits}/8，电量值 {vals}")

print("\n=== 3) 单独发 cmd 0x0a，8 次 ===")
hits = 0
vals = []
for i in range(8):
    fs = send(0x0a, 0.9)
    v = batt(fs)
    if v is not None:
        hits += 1
        vals.append(v)
    print(f"  #{i}: 帧数={len(fs):2d} 电量={v}  " + " | ".join(f.hex(' ') for _, f in fs))
    time.sleep(0.5)
print(f"  成功率 {hits}/8，电量值 {vals}")

w.close(); r.close()
