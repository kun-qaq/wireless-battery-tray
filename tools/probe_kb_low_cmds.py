"""验证：cmd 0x00~0x1a 逐个单发、每条等足 1.2 秒，看谁回数据。"""
import hid, time

VID, PID = 0x3554, 0xFA09
path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        path = d["path"]
        break

w = hid.device(); w.open_path(path); w.set_nonblocking(1)
r = hid.device(); r.open_path(path); r.set_nonblocking(1)


def flush():
    for _ in range(80):
        try:
            if not r.read(64):
                break
        except OSError:
            break


def ask(cmd, wait=1.2):
    flush()
    w.write(bytes([0x13, cmd]) + bytes(17))
    end = time.time() + wait
    out = []
    while time.time() < end:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            out.append(bytes(b))
        time.sleep(0.004)
    return out


for cmd in range(0x00, 0x1B):
    frames = ask(cmd)
    if not frames:
        print(f"  cmd {cmd:#04x}: 无响应")
        continue
    for f in frames:
        extra = ""
        if len(f) > 6 and f[1] == 0x44 and f[2] == 0xFF:
            val, inv = f[5], f[6]
            extra = f"   <== 值={val} 反码={inv} ({'一致' if (val ^ 0xFF) == inv else '不一致'})"
        print(f"  cmd {cmd:#04x}: {f.hex(' ')}{extra}")
    time.sleep(0.4)

w.close(); r.close()
