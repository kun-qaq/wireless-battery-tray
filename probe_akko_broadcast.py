"""完整打印耳机 0x10 状态广播（64 字节），对比字段变化。"""
import hid
import time

VID, PID = 0x36EB, 0x1087
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0x008C and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)

print("监听 12s，完整打印所有报文（请勿关闭 Akko 驱动窗口）...", flush=True)
end = time.time() + 12
seen = {}
while time.time() < end:
    r = dev.read(128)
    if r:
        b = bytes(r)
        key = b[:6].hex()
        seen.setdefault(key, []).append(b)
        print(f"[{key}] {b.hex(' ')}", flush=True)
    else:
        time.sleep(0.005)

print("\n=== 汇总（按前缀去重） ===")
for k, frames in seen.items():
    print(f"{k}: {len(frames)} 帧")
    for i, f in enumerate(frames[:3]):
        print("   ", f.hex(" "))
