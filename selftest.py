"""命令行自检：不开托盘，直接读三台设备电量，验证读取器是否正常。"""
import sys
import time

sys.path.insert(0, r"D:\codeeeee\python_files\wireless_battery_tray")
from wireless_battery_tray import read_all

t0 = time.time()
res = read_all()
print(f"耗时 {time.time()-t0:.2f}s")
for name, v, s in res:
    print(f"  {name:<14} -> {v if v is not None else '-':>4}  [{s}]")
