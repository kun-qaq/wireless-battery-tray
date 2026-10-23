"""连读 cmd 0x0a，看第 6 字节是否为真实电量（会变化）。"""
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


def ask(cmd, wait=0.8):
    flush()
    w.write(bytes([0x13, cmd]) + bytes(17))
    end = time.time() + wait
    frames = []
    while time.time() < end:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            frames.append(bytes(b))
        time.sleep(0.004)
    return frames


for i in range(8):
    fs = ask(0x0a)
    line = " | ".join(f.hex(" ") for f in fs) if fs else "无响应"
    val = ""
    for f in fs:
        if len(f) >= 8 and f[1] == 0x0A:
            val = f"  -> byte6={f[6]} (0x{f[6]:02x})  byte7={f[7]}"
    print(f"#{i}: {line}{val}")
    time.sleep(1.0)

print("\n--- 顺带看 cmd 0x05 是否也带电量 ---")
for i in range(3):
    for f in ask(0x05):
        print("  ", f.hex(" "))
    time.sleep(0.8)

w.close(); r.close()
