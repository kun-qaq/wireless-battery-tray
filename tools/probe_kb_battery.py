"""确认灵豹 K98 电量命令：0x6f -> 5a a5（值 + 反码）。"""
import hid, time

VID, PID = 0x3554, 0xFA09
path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        path = d["path"]
        break

w = hid.device(); w.open_path(path); w.set_nonblocking(1)
r = hid.device(); r.open_path(path); r.set_nonblocking(1)


def ask(cmd, wait=0.25):
    try:
        w.write(bytes([0x13, cmd]) + bytes(17))
    except Exception as e:
        return None
    end = time.time() + wait
    while time.time() < end:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            return bytes(b)
    return None


print("=== 电量命令 0x6f 连读 10 次 ===")
for i in range(10):
    resp = ask(0x6f)
    if resp:
        val, inv = resp[5], resp[6]
        ok = (val ^ 0xFF) == inv
        print(f"  #{i}: {resp.hex(' ')}   电量={val}%  反码校验={'通过' if ok else '失败'}")
    else:
        print(f"  #{i}: 无响应")
    time.sleep(0.6)

print("\n=== 相邻命令对照（看是否为其它字段）===")
for cmd in (0x69, 0x6d, 0x6e, 0x6f, 0x70):
    resp = ask(cmd)
    print(f"  cmd {cmd:#04x}: {resp.hex(' ') if resp else '无响应'}")
    time.sleep(0.3)

w.close(); r.close()
