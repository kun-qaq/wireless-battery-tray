"""精测：加长等待时间，消除响应错位，确认哪条命令真的回数据。"""
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
    for _ in range(50):
        try:
            if not r.read(64):
                break
        except OSError:
            break


def ask(cmd, wait=0.5):
    flush()
    try:
        w.write(bytes([0x13, cmd]) + bytes(17))
    except Exception as e:
        return ("WRITE_FAIL", str(e))
    end = time.time() + wait
    while time.time() < end:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            return bytes(b)
        time.sleep(0.005)
    return None


print("=== 基准：cmd 0x01（已知会回显）===")
print("  ", ask(0x01))

print("\n=== 精确扫描 0x60~0x80，每条等 0.5s ===")
for cmd in range(0x60, 0x81):
    resp = ask(cmd)
    if resp is None:
        label = "无响应"
    elif isinstance(resp, tuple):
        label = str(resp)
    else:
        label = resp.hex(" ")
    print(f"  cmd {cmd:#04x}: {label}")
    time.sleep(0.25)

w.close(); r.close()
