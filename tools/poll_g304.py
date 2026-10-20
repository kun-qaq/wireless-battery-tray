"""90 秒内持续向 G304 (dev 1) 发送 HID++2.0 电量请求，捕捉它唤醒后的响应。"""
import hid
import time

VID, PID = 0x046D, 0xC53F
path = next(d["path"] for d in hid.enumerate(VID, PID)
            if d["usage_page"] == 0xFF00 and d["usage"] == 0x0001)
dev = hid.device()
dev.open_path(path)
dev.set_nonblocking(1)

print("轮询 G304 电量 90s（请在这期间动一动鼠标）...", flush=True)
end = time.time() + 90
n = 0
while time.time() < end:
    n += 1
    dev.write([0x10, 0x01, 0x00, 0x00, 0x00, 0x10, 0x00])
    got = False
    t0 = time.time()
    while time.time() - t0 < 0.25:
        r = dev.read(64)
        if r:
            print(f"#{n} reply: {bytes(r).hex(' ')}", flush=True)
            got = True
        time.sleep(0.01)
    time.sleep(0.25)
print("结束", flush=True)
