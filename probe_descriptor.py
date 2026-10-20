"""读取设备 HID 报告描述符并解析，确定 report id 与各 report 的长度。"""
import hid

TARGETS = {
    "K98键盘": (0x3554, 0xFA09),
    "Akko S9耳机": (0x36EB, 0x1087),
}

USAGE_PAGES = {
    0x01: "GenericDesktop", 0x06: "GenericDeviceControls", 0x07: "Keyboard",
    0x08: "LED", 0x09: "Button", 0x0B: "Telephony", 0x0C: "Consumer",
    0x0D: "Digitizer", 0x8C: "BarcodeScanner", 0xFF00: "Vendor", 0xFF02: "Vendor",
    0xFF04: "Vendor", 0xFFBC: "Vendor", 0xFF7A: "Vendor", 0xFF30: "Vendor",
}


def parse(desc):
    """极简 HID 报告描述符解析：抽取 Report ID / Input / Output / Feature 的位宽。"""
    i = 0
    report_id = 0
    size = 0
    out = []
    bitpos = {"input": [0, 0], "output": [0, 0], "feature": [0, 0]}  # [id, bits]
    counts = {}
    while i < len(desc):
        b = desc[i]
        if b == 0xFE:  # long item
            dsize = desc[i + 1]
            i += 3 + dsize
            continue
        bsize = [0, 1, 2, 4][b & 0x03]
        btag = (b >> 4) & 0x0F
        btype = (b >> 2) & 0x03
        data = desc[i + 1:i + 1 + bsize]
        val = int.from_bytes(data, "little") if data else 0
        if btype == 1:  # global
            if btag == 0x7:
                report_id = val
            elif btag == 0x8:
                rid = val & 0xFF
                cnt = val >> 16
                counts[rid] = cnt
        elif btype == 0:  # main
            if btag == 0x8:  # input
                rid = report_id
                bits = counts.get(rid, 0) if False else None
                out.append(("input", rid))
            elif btag == 0x9:
                out.append(("output", report_id))
            elif btag == 0xB:
                out.append(("feature", report_id))
        i += 1 + bsize
    return out


for name, (vid, pid) in TARGETS.items():
    print(f"\n########## {name} ##########")
    seen = set()
    for d in hid.enumerate(vid, pid):
        key = (d["interface_number"], d["usage_page"], d["usage"])
        if key in seen:
            continue
        seen.add(key)
        dev = hid.device()
        try:
            dev.open_path(d["path"])
        except OSError as e:
            print(f"  if={d['interface_number']} UP=0x{d['usage_page']:04X} open fail {e}")
            continue
        try:
            desc = bytes(dev.get_report_descriptor())
        except Exception as e:
            desc = b""
            print(f"  desc fail {e}")
        dev.close()
        if desc:
            # 逐字节打印，人工可读
            print(f"  --- if={d['interface_number']} UP=0x{d['usage_page']:04X} U=0x{d['usage']:04X} desc({len(desc)}B) ---")
            print("      " + desc.hex(" "))
