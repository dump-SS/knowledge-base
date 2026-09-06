import json, glob, csv

SUBJECT_CN = {"SX":"数学","HX":"化学","WL":"物理","SW":"生物",
              "YW":"语文","YY":"英语","LS":"历史","DL":"地理","ZZ":"政治"}

# 1. 合并两份 total_review.json
reviews = []
for f in glob.glob("review/reviews/*/total_review.json"):
    reviews.extend(json.load(open(f, encoding="utf-8")))

# 2. 建原始数据索引：id -> 知识点（回查快照用）
index = {}
for f in glob.glob("docs/knowledge-points/*.json"):
    for kp in json.load(open(f, encoding="utf-8")).get("l2_points", []):
        index[kp["id"]] = kp

# 3. 去重 + 补快照 + 转可读列
seen, rows = set(), []
for r in reviews:
    if r["id"] in seen: continue
    seen.add(r["id"])
    kp = index.get(r["id"], {})
    issues = "；".join(r.get("issues", []))
    if r.get("reason"): issues += f"（{r['reason']}）"
    rows.append({
        "id": r["id"],
        "学科": SUBJECT_CN.get(r["id"].split("_")[0], "?"),
        "知识点": r.get("name") or kp.get("name", ""),
        "置信度": r["confidence"],
        "问题描述": issues,
        "定义原文": kp.get("definition", ""),
        "详解原文": kp.get("explanation", ""),
        "修正后定义": "",
        "验收结果": "",
    })

# 4. 按置信度升序（40 分以下高危优先置顶）
rows.sort(key=lambda x: x["置信度"])

# 5. 写 CSV（utf-8-sig = 带 BOM，飞书导入中文不乱码）
with open("review/low_confidence.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id","学科","知识点","置信度","问题描述","定义原文","详解原文","修正后定义","验收结果"])
    w.writeheader(); w.writerows(rows)

print(f"共 {len(rows)} 条，已写 review/low_confidence.csv")
