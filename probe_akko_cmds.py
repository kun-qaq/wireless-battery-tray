"""用抓到的 Akko 真实命令逐个探测，找到电量对应的命令。"""
import hid
import time

VID, PID = 0x36EB, 0x1087
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0x008C and d["usage"] == 0x0001)

dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)


def drain(secs=0.1):
    end = time.time() + secs
    out = []
    while time.time() < end:
        r = dev.read(128)
        if r:
            out.append(bytes(r))
        else:
            time.sleep(0.003)
    return out


def send_cmd(cmd, sub=0x01, retries=12, wait_each=0.06):
    pkt = bytes([0x02, cmd, sub] + [0] * 61)
    resp = []
    for _ in range(retries):
        dev.write(pkt)
        r = drain(wait_each)
        if r:
            resp.extend(r)
            # 连续读一点
            resp.extend(drain(0.15))
            break
    return resp


# 驱动发出的命令（真实流量）：0x12 0x15 0x16 0x18 0x35，另带心跳 0x10
for cmd in (0x12, 0x15, 0x16, 0x18, 0x35, 0x10):
    t0 = time.time()
    resp = send_cmd(cmd)
    dt = time.time() - t0
    uniq = []
    for r in resp:
        if r not in uniq:
            uniq.append(r)
    print(f"cmd 0x{cmd:02x} ({dt*1000:.0f}ms, {len(resp)} pkt):")
    for r in uniq[:4]:
        nz = " ".join(f"{b:02x}" for b in r if b)
        print(f"    {r.hex(' ')[:120]}{'...' if len(r) > 60 else ''}  nonzero:[{nz}]")
