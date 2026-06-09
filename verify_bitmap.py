#!/usr/bin/env python3
import struct, os

def utf8_to_unicode(utf8_bytes):
    if len(utf8_bytes) == 1: return utf8_bytes[0]
    elif len(utf8_bytes) == 2: return ((utf8_bytes[0] & 0x1F) << 6) | (utf8_bytes[1] & 0x3F)
    elif len(utf8_bytes) == 3: return ((utf8_bytes[0] & 0x0F) << 12) | ((utf8_bytes[1] & 0x3F) << 6) | (utf8_bytes[2] & 0x3F)
    elif len(utf8_bytes) == 4: return ((utf8_bytes[0] & 0x07) << 18) | ((utf8_bytes[1] & 0x3F) << 12) | ((utf8_bytes[2] & 0x3F) << 6) | (utf8_bytes[3] & 0x3F)

def read_bin(p):
    with open(p, "rb") as f:
        m = f.read(4)
        v = struct.unpack("<I", f.read(4))[0]
        c = struct.unpack("<I", f.read(4))[0]
        s = struct.unpack("<I", f.read(4))[0]
        h = {"magic": m, "version": v, "char_count": c, "font_size": s}
        idx = []
        for i in range(c):
            ul = struct.unpack("B", f.read(1))[0]
            ub = f.read(ul)
            o = struct.unpack("<I", f.read(4))[0]
            w = struct.unpack("H", f.read(2))[0]
            ht = struct.unpack("H", f.read(2))[0]
            idx.append({"code": utf8_to_unicode(ub), "offset": o, "w": w, "h": ht})
        return h, idx

def vis(p, e):
    with open(p, "rb") as f:
        f.seek(e["offset"])
        bs = ((e["w"] + 7) // 8) * e["h"]
        d = f.read(bs)
    w = e["w"]
    h = e["h"]
    rb = (w + 7) // 8
    lines = []
    for y in range(h):
        ln = ""
        for x in range(w):
            bi = y * rb + (x // 8)
            ti = 7 - (x % 8)
            ln += "\u2588" if (d[bi] >> ti) & 1 else " "
        lines.append(ln)
    return "\n".join(lines)

print("=" * 60)
print("           字库文件验证工具")
print("=" * 60)

for bp in ["font_16.bin", "font_32.bin"]:
    print("\n" + "=" * 60)
    print("文件: " + bp)
    print("=" * 60)
    if not os.path.exists(bp):
        print("  文件不存在!")
        continue
    fs = os.path.getsize(bp)
    print("  文件大小: {} 字节 ({:.1f} KB)".format(fs, fs / 1024))
    h, idx = read_bin(bp)
    print("  魔数: {} {}".format(h["magic"], "OK" if h["magic"] == b"FONT" else "ERR"))
    print("  版本: {}".format(h["version"]))
    print("  字符数量: {}".format(h["char_count"]))
    print("  字号: {}px".format(h["font_size"]))
    codes = set(e["code"] for e in idx)
    print("  唯一字符数: {}".format(len(codes)))
    print("  编码唯一: {}".format("OK" if len(codes) == len(idx) else "ERR"))
    print("\n  可视化抽样:")
    for cd in [0x4E2D, 0x56FD, 0x0041]:
        e = next((x for x in idx if x["code"] == cd), None)
        if e:
            print("    U+{:04X}({}) [{}x{}]:".format(cd, chr(cd), e["w"], e["h"]))
            art = vis(bp, e)
            for line in art.split("\n"):
                print("      " + line)

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
