"""灵豹键盘：读 feature report 0x06 + 监听 0xFF02/0xFF04 的 input 上报。"""
import hid
import time

VID, PID = 0x3554, 0xFA09

for d in hid.enumerate(VID, PID):
    up, u = d["usage_page"], d["usage"]
    if up not in (0xFF02, 0xFF04):
        continue
    print(f"== if={d['interface_number']} UP=0x{up:04X} U=0x{u:04X} ==")
    dev = hid.device()
    try:
        dev.open_path(d["path"])
    except OSError as e:
        print("   open fail:", e)
        continue
    # 1) feature report 0x06 (7 字节)
    for rid in (0x06, 0x13, 0x01, 0x02, 0x03, 0x04, 0x05, 0x07, 0x08):
        try:
            data = dev.get_feature_report(rid, 65)
            if data and any(bytes(data)[1:]):
                print(f"   feature {rid:#04x} len={len(data)}: {bytes(data).hex(' ')}")
            elif data:
                print(f"   feature {rid:#04x} len={len(data)}: 全零")
        except Exception as e:
            print(f"   feature {rid:#04x} err: {e}")
            break
    # 2) 监听 input 5 秒（期间可以敲几下键盘）
    dev.set_nonblocking(1)
    print("   listening 6s（可以敲几下键盘触发上报）...")
    end = time.time() + 6
    cnt = 0
    while time.time() < end:
        try:
            r = dev.read(64)
        except OSError:
            print("   read unsupported")
            break
        if r:
            cnt += 1
            if cnt <= 10:
                print("   input:", bytes(r).hex(" "))
        time.sleep(0.004)
    print(f"   共 {cnt} 帧")
    dev.close()
