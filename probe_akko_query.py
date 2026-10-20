"""验证：自己发送带校验尾部的 0x12 电量查询命令，设备应答电量。"""
import hid
import time

VID, PID = 0x36EB, 0x1087
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0x008C and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)


def drain(secs):
    end = time.time() + secs
    out = []
    while time.time() < end:
        r = dev.read(128)
        if r:
            out.append(bytes(r))
        else:
            time.sleep(0.003)
    return out


def query(cmd, tail, retries=15, wait=0.05):
    pkt = bytes([0x02, cmd, 0x01] + [0] * 59 + list(tail))
    pkt = pkt[:62] + bytes(tail)  # 62 字节 + 2 字节尾 = 64
    for i in range(retries):
        dev.write(pkt)
        r = drain(wait)
        got = [x for x in r if len(x) > 4 and x[1] == cmd]
        if got:
            return got[0]
    return None


# 抓包中的真实 (命令, 校验尾) 对
tests = [
    (0x12, bytes.fromhex("7112")),
    (0x10, bytes.fromhex("4b43")),
    (0x15, bytes.fromhex("a2cc")),
    (0x16, bytes.fromhex("05b0")),
    (0x18, bytes.fromhex("a207")),
    (0x35, bytes.fromhex("07c1")),
]

for cmd, tail in tests:
    resp = query(cmd, tail)
    print(f"cmd 0x{cmd:02x} tail={tail.hex()} -> {resp.hex(' ') if resp else '无响应'}")
