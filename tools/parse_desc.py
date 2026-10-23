"""把 HID 报告描述符解析成可读结构：report id -> 字段(usage/size/count)。"""
import sys, hid

PAGES = {0x01:"Desktop",0x06:"DeviceCtl",0x07:"Keyboard",0x08:"LED",0x09:"Button",
         0x0C:"Consumer",0x0D:"Digitizer",0xFF00:"Vendor",0xFF02:"Vendor",
         0xFF04:"Vendor",0x8C:"Barcode"}
KNOWN = {(0x06,0x20):"BatteryStrength",(0x01,0x30):"X",(0x01,0x31):"Y"}


def parse(desc):
    i = 0; g = {"usage_page":0,"rcount":0,"rsize":0,"rid":0,"lmin":0,"lmax":0}
    gstack = []; usages = []; reports = {}
    while i < len(desc):
        b = desc[i]
        if b == 0xFE:
            i += 3 + desc[i+1]; continue
        size = [0,1,2,4][b & 3]; tag = (b>>4)&0x0F; typ = (b>>2)&3
        data = desc[i+1:i+1+size]
        val = int.from_bytes(data, "little") if data else 0
        if typ == 1:
            if tag == 0x0: g["usage_page"] = val
            elif tag == 0x1: g["lmin"] = val
            elif tag == 0x2: g["lmax"] = val
            elif tag == 0x7: g["rsize"] = val
            elif tag == 0x8: g["rid"] = val
            elif tag == 0x9: g["rcount"] = val
            elif tag == 0xA: gstack.append(dict(g))
            elif tag == 0xB and gstack: g = gstack.pop()
        elif typ == 2:
            if tag == 0x0: usages.append(val)
            elif tag == 0x1: usages.append(("min", val))
            elif tag == 0x2: usages.append(("max", val))
        elif typ == 0:
            if tag in (0x8, 0x9, 0xB):
                kind = {0x8:"in",0x9:"out",0xB:"feat"}[tag]
                rid = g["rid"]; bits = g["rsize"]*g["rcount"]
                key = (kind, rid)
                reports.setdefault(key, [])
                u = usages[-1] if usages else 0
                reports[key].append({
                    "up": g["usage_page"],
                    "usage": u if not isinstance(u, tuple) else u,
                    "size": g["rsize"], "count": g["rcount"],
                    "lmin": g["lmin"], "lmax": g["lmax"], "bits": bits,
                })
                usages = []
            elif tag == 0xA:  # collection 里的 local 清空
                usages = []
        i += 1 + size
    return reports


vid, pid = int(sys.argv[1], 0), int(sys.argv[2], 0)
seen = set()
for d in hid.enumerate(vid, pid):
    key = (d["interface_number"], d["usage_page"], d["usage"])
    if key in seen: continue
    seen.add(key)
    dev = hid.device()
    try: dev.open_path(d["path"])
    except Exception as e:
        print(f"if={d['interface_number']} UP=0x{d['usage_page']:04X} open fail {e}"); continue
    try: desc = bytes(dev.get_report_descriptor())
    except Exception: desc = b""
    dev.close()
    if not desc: continue
    print(f"\n===== if={d['interface_number']} UP=0x{d['usage_page']:04X} U=0x{d['usage']:04X}  desc {len(desc)}B =====")
    for (kind, rid), fields in sorted(parse(desc).items()):
        total = sum(f["bits"] for f in fields) // 8
        print(f"  {kind} report 0x{rid:02X}  {total}B")
        byteoff = 0
        for f in fields:
            name = PAGES.get(f["up"], hex(f["up"]))
            u = f["usage"]
            uname = KNOWN.get((f["up"], u), f"0x{u:02X}" if isinstance(u,int) else str(u))
            nb = f["size"]//8 if f["size"]>=8 else f"{f['size']}bit"
            print(f"     +{byteoff:<2} {name}.{uname}  {f['count']}x{nb}  range[{f['lmin']},{f['lmax']}]")
            byteoff += f["bits"]//8
