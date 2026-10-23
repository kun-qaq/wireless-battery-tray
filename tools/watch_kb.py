"""监听灵豹 K98 的厂商 input 上报（0xFF02 / report 0x13），持续 90 秒。"""
import hid, time

VID, PID = 0x3554, 0xFA09
paths = []
for d in hid.enumerate(VID, PID):
    if d["usage_page"] in (0xFF02, 0xFF04) or d["usage"] == 0x0080:
        paths.append((d["usage_page"], d["usage"], d["path"]))

devs = []
for up, u, p in paths:
    dev = hid.device()
    try:
        dev.open_path(p); dev.set_nonblocking(1); devs.append((up, u, dev))
        print(f"监听 UP=0x{up:04X} U=0x{u:04X}")
    except Exception as e:
        print(f"打不开 UP=0x{up:04X}: {e}")

end = time.time() + 90
frames = {}
t0 = time.time()
while time.time() < end:
    for up, u, dev in devs:
        try:
            r = dev.read(64)
        except OSError:
            continue
        if r:
            b = bytes(r)
            key = (up, b[:6].hex())
            if key not in frames:
                frames[key] = [0, time.time()-t0]
                print(f"[{time.time()-t0:6.1f}s] UP=0x{up:04X} {b.hex(' ')}")
            frames[key][0] += 1
    time.sleep(0.003)

print("\n=== 汇总（去重后）===")
for (up, head), (cnt, t) in sorted(frames.items(), key=lambda x: -x[1][0]):
    print(f"  x{cnt:<4} UP=0x{up:04X} {head}")
for up, u, dev in devs:
    try: dev.close()
    except Exception: pass
