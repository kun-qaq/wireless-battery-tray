"""直接调用主程序里的 K98Reader，连续 10 轮验证稳定性。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wireless_battery_tray import K98Reader  # noqa: E402

rd = K98Reader()
vals = []
for i in range(10):
    t0 = time.time()
    v, s = rd.read()
    dt = time.time() - t0
    vals.append(v)
    print(f"#{i}: {v}%  {s}  ({dt:.2f}s)")
    time.sleep(0.8)

ok = [v for v in vals if isinstance(v, int)]
print(f"\n成功 {len(ok)}/10，读数 {vals}，去重后 {sorted(set(ok))}")
print("结论：", "稳定" if len(ok) >= 9 and len(set(ok)) == 1 else "需继续观察")
