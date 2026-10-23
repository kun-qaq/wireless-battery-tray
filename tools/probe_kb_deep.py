"""灵豹 K98 深度探测：枚举全部厂商接口，扫 feature report，监听 input 上报。"""
import hid, time

VID, PID = 0x3554, 0xFA09

infos = hid.enumerate(VID, PID)
print(f"共 {len(infos)} 个接口:")
for d in infos:
    print(f"  if={d['interface_number']} UP=0x{d['usage_page']:04X} U=0x{d['usage']:04X} {d['product_string']}")

for d in infos:
    up, u = d["usage_page"], d["usage"]
    if up < 0xFF00:
        continue
    print(f"\n===== if={d['interface_number']} UP=0x{up:04X} U=0x{u:04X} =====")
    dev = hid.device()
    try:
        dev.open_path(d["path"])
    except Exception as e:
        print("  open fail:", e)
        continue
    # 扫 feature report 0x01~0x20
    for rid in range(0x01, 0x21):
        try:
            data = bytes(dev.get_feature_report(rid, 65))
        except Exception:
            continue
        body = data[1:]
        if any(body):
            print(f"  feature {rid:#04x} len={len(data)}: {data.hex(' ')}")
    # 监听 input 12 秒
    dev.set_nonblocking(1)
    print("  listening 12s ...")
    end = time.time() + 12
    seen = {}
    while time.time() < end:
        try:
            r = dev.read(64)
        except OSError:
            print("  read unsupported")
            break
        if r:
            b = bytes(r)
            key = b[:4].hex()
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= 2:
                print("  input:", b.hex(" "))
        time.sleep(0.004)
    print("  帧统计:", {k: v for k, v in sorted(seen.items(), key=lambda x: -x[1])[:8]})
    dev.close()
