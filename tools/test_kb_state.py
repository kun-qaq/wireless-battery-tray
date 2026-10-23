"""发一条命令触发后，连续抓 4 秒所有帧，看是否跟出状态帧（13 44 ff ...）。"""
import hid, time

VID, PID = 0x3554, 0xFA09
path = None
for d in hid.enumerate(VID, PID):
    if d["usage_page"] == 0xFF02 and d["usage"] == 0x0002:
        path = d["path"]
        break

w = hid.device(); w.open_path(path); w.set_nonblocking(1)
r = hid.device(); r.open_path(path); r.set_nonblocking(1)

for trigger in (0x01, 0x02, 0x03):
    print(f"\n===== 发送 cmd {trigger:#04x}，之后连抓 4 秒 =====")
    try:
        w.write(bytes([0x13, trigger]) + bytes(17))
    except Exception as e:
        print("  write fail", e)
        continue
    t0 = time.time()
    seen = set()
    while time.time() - t0 < 4:
        try:
            b = r.read(64)
        except OSError:
            break
        if b:
            bb = bytes(b)
            h = bb.hex(" ")
            mark = ""
            if bb[1] == 0x44:
                mark = "   <== 状态帧"
            print(f"  [{time.time()-t0:4.2f}s] {h}{mark}")
            seen.add(h)
        time.sleep(0.004)
    print(f"  共 {len(seen)} 种帧")

w.close(); r.close()
