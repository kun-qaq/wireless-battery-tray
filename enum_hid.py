"""枚举系统中所有 HID 设备，输出接口详情，用于定位三家 2.4G 设备的通信接口。"""
import hid

devs = hid.enumerate()
rows = []
for d in devs:
    rows.append({
        "vid": d["vendor_id"],
        "pid": d["product_id"],
        "usage_page": d["usage_page"],
        "usage": d["usage"],
        "iface": d["interface_number"],
        "product": d.get("product_string"),
        "mfr": d.get("manufacturer_string"),
        "serial": d.get("serial_number"),
        "path": d["path"].decode("utf-8", "replace") if isinstance(d["path"], bytes) else d["path"],
    })

rows.sort(key=lambda r: (r["vid"], r["pid"], r["iface"], r["usage_page"], r["usage"]))
print(f"total {len(rows)} HID interfaces\n")
for r in rows:
    print(f"VID_{r['vid']:04X} PID_{r['pid']:04X} if={r['iface']:<3} "
          f"UP=0x{r['usage_page']:04X} U=0x{r['usage']:04X}  "
          f"{r['product']!r} | mfr={r['mfr']!r} | sn={r['serial']!r}")
    print(f"    {r['path']}")
