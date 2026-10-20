"""验证耳机 63 字节报文的末尾两字节是否为 CRC16 校验。"""
FRAMES = [
    "10 01 " + "00 " * 59 + "4b 43",
    "12 01 01 " + "00 " * 57 + "3f 2a",
    "66 " + "00 " * 61 + "00 00",
]


def crc16(data, poly, init, refin=False, xorout=0):
    crc = init
    if refin:
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
    else:
        for b in data:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc ^ xorout


VARIANTS = {
    "CRC16-CCITT-FALSE(0x1021,initFFFF)": (0x1021, 0xFFFF, False, 0),
    "CRC16-XMODEM(0x1021,init0)": (0x1021, 0x0000, False, 0),
    "CRC16-MODBUS(0xA001,initFFFF,ref)": (0xA001, 0xFFFF, True, 0),
    "CRC16-IBM-ARC(0xA001,init0,ref)": (0xA001, 0x0000, True, 0),
    "CRC16-CCITT-REF(0x8408,initFFFF,ref)": (0x8408, 0xFFFF, True, 0),
    "CRC16-X25(0x8408,initFFFF,ref,xorFFFF)": (0x8408, 0xFFFF, True, 0xFFFF),
    "CRC16-DNP": (0xA6BC, 0x0000, True, 0xFFFF),
    "CRC16-USB(0xA001,initFFFF,ref,xorFFFF)": (0xA001, 0xFFFF, True, 0xFFFF),
}

for frame in FRAMES:
    raw = bytes.fromhex(frame.replace(" ", ""))
    payload, tail = raw[:-2], raw[-2:]
    want_le = int.from_bytes(tail, "little")
    want_be = int.from_bytes(tail, "big")
    print(f"\nframe {raw[:4].hex(' ')}... tail={tail.hex(' ')} (le={want_le:#06x} be={want_be:#06x})")
    for name, (poly, init, refin, xorout) in VARIANTS.items():
        c = crc16(payload, poly, init, refin, xorout)
        mark = ""
        if c == want_le:
            mark = "  <== MATCH little-endian"
        elif c == want_be:
            mark = "  <== MATCH big-endian"
        print(f"   {name:42s} {c:#06x}{mark}")

# 同时检查简单累加和 / 异或
for frame in FRAMES:
    raw = bytes.fromhex(frame.replace(" ", ""))
    payload, tail = raw[:-2], raw[-2:]
    print(f"\nframe {raw[:2].hex()}: sum8={sum(payload)&0xFF:#04x} xor={__import__('functools').reduce(lambda a,b:a^b,payload,0):#04x} "
          f"tail={tail.hex(' ')} sum16={sum(payload)&0xFFFF:#06x}")
