import time, hid
Q = bytes([0x02,0x12,0x01]) + bytes(59) + bytes.fromhex("7112")
path = None
for d in hid.enumerate(0x36EB, 0x1087):
    if d["usage_page"]==0x008C and d["usage"]==0x0001:
        path = d["path"]; break
print("接口路径:", path)
dev = hid.device(); dev.open_path(path); dev.set_nonblocking(1)
print("保持句柄，每 3 秒查一次（共 20 次）：")
ok = 0
for i in range(20):
    try:
        dev.write(Q)
    except Exception as e:
        print(f"  #{i:02d} 写入失败: {e}"); break
    end = time.time()+0.6; got = None
    while time.time()<end:
        try: r = dev.read(128)
        except OSError as e:
            print(f"  #{i:02d} 读取异常(句柄失效): {e}"); got="ERR"; break
        if r:
            b=bytes(r)
            if len(b)>=5 and b[1]==0x12 and b[2]==0x01:
                got=b[4]; break
        time.sleep(0.01)
    print(f"  #{i:02d} -> {got}")
    if isinstance(got,int): ok+=1
    time.sleep(3)
print(f"成功 {ok}/20")
dev.close()
