# -*- coding: utf-8 -*-
"""
按文件名前缀把 docs/knowledge-points 下的 JSON 知识点文件分成 理科/文科 两组清单。

分类规则（前缀 = 文件名第一个下划线之前的段）：
  理科：SX（数学，含 SX_B）、HX（化学）、WL（物理）、SW（生物）
  文科：YW（语文）、YY（英语，含 YY_RJ/YY_WY）、LS（历史）、DL（地理，含 DL_RJ/DL_ZT）、ZZ（政治）

只读源目录；产物（理科清单.txt / 文科清单.txt）写入本脚本所在目录（review/）。
"""

from pathlib import Path

SCIENCE_PREFIXES = {"SX", "HX", "WL", "SW"}
LIBERAL_PREFIXES = {"YW", "YY", "LS", "DL", "ZZ"}

SCRIPT_DIR = Path(__file__).resolve().parent   # review/
REPO_ROOT = SCRIPT_DIR.parent
SOURCE_DIR = REPO_ROOT / "docs" / "knowledge-points"


def main() -> None:
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"源目录不存在: {SOURCE_DIR}")

    files = sorted(p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix == ".json")
    science: list[Path] = []
    liberal: list[Path] = []
    unknown: list[Path] = []
    by_prefix: dict[str, list[Path]] = {}

    for f in files:
        prefix = f.stem.split("_")[0]
        by_prefix.setdefault(prefix, []).append(f)
        if prefix in SCIENCE_PREFIXES:
            science.append(f)
        elif prefix in LIBERAL_PREFIXES:
            liberal.append(f)
        else:
            unknown.append(f)

    for name, group in (("理科清单.txt", science), ("文科清单.txt", liberal)):
        out = SCRIPT_DIR / name
        out.write_text(
            "\n".join(p.resolve().as_posix() for p in group) + ("\n" if group else ""),
            encoding="utf-8",
        )
        print(f"{name}: {len(group)} 个文件 -> {out}")

    if unknown:
        print(f"\n警告: {len(unknown)} 个文件无法归类（不在任何学科前缀内）:")
        for f in unknown:
            print("  ", f.name)

    print("\n各前缀文件数: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(by_prefix.items())))
    print(f"合计: 理科 {len(science)} 个, 文科 {len(liberal)} 个")


if __name__ == "__main__":
    main()
