#!/usr/bin/env python3
import struct, os, sys

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

def verify_header(h, file_size):
    errors = []
    if h["magic"] != b"FONT":
        errors.append(f"魔数错误: {h['magic']!r}, 期望 b'FONT'")
    if h["version"] != 1:
        errors.append(f"版本未知: {h['version']}, 期望 1")
    if h["char_count"] == 0:
        errors.append("字符数量为 0")
    if h["font_size"] not in (8, 12, 16, 24, 32, 48):
        errors.append(f"字号异常: {h['font_size']}")
    return errors

def verify_index(idx, h):
    errors = []
    codes = [e["code"] for e in idx]

    if len(idx) == 0:
        errors.append("索引表为空")
        return errors

    invalid = [e for e in idx if e["code"] is None or e["code"] == 0]
    if invalid:
        errors.append(f"存在 {len(invalid)} 个无效 Unicode 码点 (0/None)")

    dup_count = len(codes) - len(set(codes))
    if dup_count > 0:
        errors.append(f"存在 {dup_count} 个重复码点")

    unsorted = 0
    first_bad = None
    for i in range(1, len(codes)):
        if codes[i] < codes[i - 1]:
            unsorted += 1
            if first_bad is None:
                first_bad = (i, codes[i - 1], codes[i])
    if unsorted > 0:
        i, prev, cur = first_bad
        errors.append(
            f"索引未按码点升序排列: {unsorted} 处逆序, "
            f"首个: idx[{i-1}] U+{prev:04X} > idx[{i}] U+{cur:04X}"
        )

    data_start = 16 + sum(1 + (4 if e["code"] > 0xFFFF else 3 if e["code"] > 0x7FF else 2 if e["code"] > 0x7F else 1) + 8 for e in idx)
    bad_offset = [e for e in idx if e["offset"] < data_start]
    if bad_offset:
        errors.append(f"{len(bad_offset)} 个条目 offset 指向索引区 (< {data_start})")

    return errors

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

def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["font16.bin", "font24.bin", "font32.bin"]
    all_pass = True

    print("=" * 60)
    print("           字库文件验证工具")
    print("=" * 60)

    for bp in targets:
        print(f"\n{'=' * 60}")
        print(f"文件: {bp}")
        print("=" * 60)
        if not os.path.exists(bp):
            print("  [SKIP] 文件不存在")
            continue

        fs = os.path.getsize(bp)
        print(f"  文件大小: {fs} 字节 ({fs/1024:.1f} KB)")

        h, idx = read_bin(bp)

        print(f"  魔数: {h['magic']!r}")
        print(f"  版本: {h['version']}")
        print(f"  字符数量: {h['char_count']}")
        print(f"  字号: {h['font_size']}px")

        errors = verify_header(h, fs)
        errors += verify_index(idx, h)

        if errors:
            all_pass = False
            print(f"\n  [FAIL] 发现 {len(errors)} 个问题:")
            for e in errors:
                print(f"    ✗ {e}")
        else:
            print("\n  [PASS] 头部正确, 索引有效, 码点升序")

        print("\n  可视化抽样:")
        for cd in [0x9EDE, 0x4E2D, 0x56FD, 0x0041]:
            e = next((x for x in idx if x["code"] == cd), None)
            if e:
                print(f"    U+{cd:04X}({chr(cd)}) [{e['w']}x{e['h']}]:")
                art = vis(bp, e)
                for line in art.split("\n"):
                    print("      " + line)

    print(f"\n{'=' * 60}")
    print("验证完成: " + ("ALL PASS" if all_pass else "HAS ERRORS"))
    print("=" * 60)
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
