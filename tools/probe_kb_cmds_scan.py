"""遍历灵豹 K98 的 0x13 命令通道，找返回有效数据的命令。

报文格式：13 <cmd> + 17*00 = 19 字节
响应：  13 <cmd> ... 最后字节 = (0x13 + cmd) & 0xFF 视为命令被接受
"""
import hid, time

VID, PID = 0x3554, 0xFA09

path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        path = d["path"]
        break
if not path:
    raise SystemExit("找不到 0xFF02 接口")

w = hid.device(); w.open_path(path)
r = hid.device(); r.open_path(path)
w.set_nonblocking(1); r.set_nonblocking(1)

hits = []
for cmd in range(0x00, 0x80):
    pkt = bytes([0x13, cmd]) + bytes(17)
    try:
        w.write(pkt)
    except Exception as e:
        print(f"cmd {cmd:#04x} 写入失败 {e}")
        break
    resp = None
    end = time.time() + 0.12
    while time.time() < end:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            resp = bytes(b)
            break
    if resp and len(resp) >= 3:
        body = resp[2:-1]
        nonzero = any(body)
        hits.append((cmd, resp.hex(" "), nonzero))
        flag = "  <== 有数据" if nonzero else ""
        print(f"cmd {cmd:#04x}: {resp.hex(' ')}{flag}")
    time.sleep(0.03)

print(f"\n共 {len(hits)} 条命令有响应，其中 {sum(1 for h in hits if h[2])} 条返回非零数据")
w.close(); r.close()
