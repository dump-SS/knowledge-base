# -*- coding: utf-8 -*-
"""
全库扫描：l2_points.id 的 册(G#B#)/模块段 是否与文件名一致（只读，不改任何文件）。
id 段位因学科而异（如 DL_RJ_G1_B1_DM_001 6 段、HX_G1_B1_NHL_001 5 段），
这里用正则定位 G# 与 B# 段，不依赖固定下标。

输出: review/id不一致扫描.txt
"""

import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR.parent / "docs" / "knowledge-points"
REPORT = SCRIPT_DIR / "id不一致扫描.txt"

G_RE = re.compile(r"G\d+")
B_RE = re.compile(r"B\d+")


def main() -> None:
    lines: list[str] = []
    total = 0
    files = sorted(SOURCE_DIR.glob("*.json"))
    for f in files:
        stem = f.name[:-5]
        fm = re.search(r"(G\d+B\d+)", stem)
        if not fm:
            continue
        file_book = fm.group(1)
        file_mod = stem.split("_")[-1]
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in d.get("l2_points", []):
            pid = p.get("id", "")
            seg = pid.split("_")
            gi = next((i for i, s in enumerate(seg) if G_RE.fullmatch(s)), None)
            bi = next((i for i, s in enumerate(seg) if B_RE.fullmatch(s)), None)
            if gi is None or bi is None:
                lines.append(f"[id格式异常] {f.name}: {pid}")
                total += 1
                continue
            id_book = seg[gi] + seg[bi]
            id_mod = seg[bi + 1] if bi + 1 < len(seg) else ""
            if id_book != file_book or id_mod != file_mod:
                lines.append(f"{f.name}: {pid}  (id册号={id_book} 文件名册号={file_book}  id模块={id_mod} 文件名模块={file_mod})")
                total += 1

    REPORT.write_text("\n".join(lines) + f"\n\n不一致总数: {total}\n", encoding="utf-8")
    print(f"不一致总数: {total} -> 明细已写入 {REPORT.name}")


if __name__ == "__main__":
    main()
