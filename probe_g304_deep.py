"""深入排查 G304：打印接收器 HID 描述符 + 监听输入 + 多种报文格式试探。"""
import hid
import time

VID, PID = 0x046D, 0xC53F
infos = list(hid.enumerate(VID, PID))

print("=== 报告描述符 ===")
for d in infos:
    dev = hid.device()
    try:
        dev.open_path(d["path"])
        desc = bytes(dev.get_report_descriptor())
        print(f"if={d['interface_number']} UP=0x{d['usage_page']:04X} U=0x{d['usage']:04X} desc({len(desc)}B):")
        print("   ", desc.hex(" "))
    except Exception as e:
        print(f"if={d['interface_number']} UP=0x{d['usage_page']:04X} err {e}")
    finally:
        try:
            dev.close()
        except Exception:
            pass

# 打开短报文接口
path = next(d["path"] for d in infos if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)


def flush():
    for _ in range(40):
        if not dev.read(64):
            break


def tx(pkt, wait=0.3):
    flush()
    try:
        dev.write(pkt)
    except Exception as e:
        return f"write-err {e}"
    out = []
    end = time.time() + wait
    while time.time() < end:
        r = dev.read(64)
        if r:
            out.append(bytes(r).hex(" "))
        else:
            time.sleep(0.004)
    return out


print("\n=== 监听 3s（请动一下鼠标）===")
end = time.time() + 3
n = 0
while time.time() < end:
    r = dev.read(64)
    if r:
        n += 1
        if n <= 6:
            print("  input:", bytes(r).hex(" "))
    else:
        time.sleep(0.005)
print(f"  共 {n} 帧")

print("\n=== 长报文 0x11 (20B) 试探 ===")
for di in (0x01, 0xFF):
    for feat in (0x1000, 0x1001, 0x0000):
        pkt = bytes([0x11, di, 0x00, 0x01, feat >> 8, feat & 0xFF] + [0] * 14)
        print(f"  dev={di:#04x} feat={feat:#06x}: {tx(pkt)}")

print("\n=== HID++1.0 其他 subId ===")
for di in (0x01,):
    for sub in (0x02, 0x03, 0x04, 0x05, 0x07, 0x0D, 0x80, 0x81, 0x82, 0x83):
        print(f"  dev={di:#04x} sub={sub:#04x}: {tx(bytes([0x10, di, sub, 0x00, 0x00, 0x00, 0x00]))}")

print("\n=== long 版 1.0 寄存器读 (0x83, addr 0x0D) ===")
print("  ", tx(bytes([0x10, 0x01, 0x83, 0x0D, 0x00, 0x00, 0x00])))
