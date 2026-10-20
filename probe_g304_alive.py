"""确认 G304 是否真的连在这个接收器上：监听鼠标 HID 报告 + 接收器连接事件。"""
import hid
import time

VID, PID = 0x046D, 0xC53F
infos = list(hid.enumerate(VID, PID))

# MI_01 的鼠标接口 (usage 0x0001 / 0x0002, report id 0x02)
mouse = next((d for d in infos if d["usage_page"] == 0x0001 and d["usage"] == 0x0002), None)
# 接收器事件通道 (usage 0x0004, report 0x20/0x21)
events = next((d for d in infos if d["usage_page"] == 0xFF00 and d["usage"] == 0x0004), None)

devs = []
if mouse:
    d = hid.device()
    d.open_path(mouse["path"])
    d.set_nonblocking(1)
    devs.append(("鼠标报告", d))
    print("已打开鼠标报告接口", mouse["path"].decode() if isinstance(mouse["path"], bytes) else mouse["path"])
if events:
    d2 = hid.device()
    try:
        d2.open_path(events["path"])
        d2.set_nonblocking(1)
        devs.append(("接收器事件", d2))
        print("已打开接收器事件接口")
    except OSError as e:
        print("事件接口打开失败", e)

print("\n监听 8 秒 —— 请移动鼠标、点击滚轮。", flush=True)
end = time.time() + 8
counts = {}
while time.time() < end:
    for name, d in devs:
        try:
            r = d.read(64)
        except OSError:
            continue
        if r:
            counts[name] = counts.get(name, 0) + 1
            if counts[name] <= 8:
                print(f"  [{name}] {bytes(r).hex(' ')}", flush=True)
    time.sleep(0.002)

print("\n统计:", counts if counts else "零上报 —— 该接收器上没有活跃的鼠标数据流")
