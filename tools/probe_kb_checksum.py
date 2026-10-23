"""验证 K98 命令帧的校验 = 前面所有字节求和取低 8 位，并测试带校验后 cmd 0x0a 是否直读。"""
import hid, time

VID, PID = 0x3554, 0xFA09
path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        path = d["path"]
        break
print("path:", path)

w = hid.device(); w.open_path(path); w.set_nonblocking(1)
r = hid.device(); r.open_path(path); r.set_nonblocking(1)


def cksum(body):
    return sum(body) & 0xFF


# 先验证已知帧的校验
for h in ["130a01000405621000000000000000000099",
          "130501000a030000000212010000000000003b",
          "13010000000000000000000000000000000014"]:
    b = bytes.fromhex(h)
    print(f"{h[:2]}... 实测尾={b[-1]:02x} 计算尾={cksum(b[:-1]):02x} {'✓' if b[-1] == cksum(b[:-1]) else '✗'}")

print()


def flush():
    for _ in range(80):
        try:
            if not r.read(64):
                break
        except OSError:
            break


def ask(cmd, wait=0.9, use_sum=True):
    """发 19 字节命令帧，末字节为 sum8 校验。"""
    flush()
    body = bytes([0x13, cmd]) + bytes(16)
    frame = body + bytes([cksum(body) if use_sum else 0])
    w.write(frame)
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


print("=== 带 sum8 校验，直接读 cmd 0x0a ===")
for i in range(4):
    fs = ask(0x0a)
    print(f"#{i}:", " | ".join(f.hex(" ") for f in fs) if fs else "无响应")
    time.sleep(0.6)

print("\n=== cmd 0x05 ===")
for i in range(2):
    fs = ask(0x05)
    print(f"#{i}:", " | ".join(f.hex(" ") for f in fs) if fs else "无响应")
    time.sleep(0.6)

print("\n=== 其它疑似电量命令 ===")
for cmd in (0x03, 0x04, 0x06, 0x08, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f):
    fs = ask(cmd, wait=0.6)
    print(f"cmd 0x{cmd:02x}:", " | ".join(f.hex(" ") for f in fs) if fs else "无响应")
    time.sleep(0.3)

w.close(); r.close()
