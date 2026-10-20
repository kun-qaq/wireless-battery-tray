"""从二进制文件中提取可打印字符串，并按关键字过滤，用于逆向驱动与设备的通信协议。"""
import re
import sys

def strings(path, minlen=4):
    with open(path, "rb") as f:
        data = f.read()
    # 同时提取 ascii 与 utf-16le 字符串
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
        yield m.group().decode("ascii", "replace")

def strings_utf16(path, minlen=4):
    with open(path, "rb") as f:
        data = f.read()
    pat = rb"(?:[\x20-\x7e]\x00){%d,}" % minlen
    for m in re.finditer(pat, data):
        yield m.group().decode("utf-16le", "replace")

if __name__ == "__main__":
    path = sys.argv[1]
    kws = [k.lower() for k in sys.argv[2:]]
    seen = set()
    for s in list(strings(path)) + list(strings_utf16(path)):
        low = s.lower()
        if kws and not any(k in low for k in kws):
            continue
        if s in seen:
            continue
        seen.add(s)
        print(s)
