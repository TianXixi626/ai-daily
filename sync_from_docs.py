#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_from_docs.py - 从腾讯文档智能表同步产品数据到 products.json

用法:
  python3 sync_from_docs.py

会生成 products.json，工作台 HTML 从此文件读取数据。
可以手动运行，也可以加到自动化任务里定期执行。
"""
import subprocess
import json
import os
import sys

# Config
FILE_ID = "JFKLdUTBJMEl"
SHEET_ID = "t00i2h"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.json")

# Find mcporter
MCPORTER = None
for p in [
    os.path.expanduser("~/.npm/_npx/bdbf2deecdd22bc5/node_modules/.bin/mcporter"),
    "/usr/local/bin/mcporter",
]:
    if os.path.exists(p):
        MCPORTER = p
        break

if not MCPORTER:
    # Try finding it
    import glob
    candidates = glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/.bin/mcporter"))
    if candidates:
        MCPORTER = candidates[0]
    else:
        print("ERROR: mcporter not found")
        sys.exit(1)


FIELD_TITLES = ["产品名称","中文名","系列","年份","国区现价","国区原价","折扣","史低价","国区在售","好评率","中文评论占比","Steam在线","合同状态","运营模式","备注","AppID"]


def call_mcporter(tool, args):
    """Call mcporter and return parsed JSON."""
    result = subprocess.run(
        [MCPORTER, "call", "tencent-docs", tool, "--args", json.dumps(args, ensure_ascii=False)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print(f"ERROR calling {tool}: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"ERROR parsing response from {tool}: {result.stdout[:200]}")
        return None


def fetch_all_records():
    """Fetch all records from the smartsheet, handling pagination."""
    all_records = []
    offset = 0
    limit = 20

    while True:
        resp = call_mcporter("smartsheet.list_records", {
            "file_id": FILE_ID,
            "sheet_id": SHEET_ID,
            "field_titles": FIELD_TITLES,
            "offset": offset,
            "limit": limit,
        })

        if not resp or resp.get("error"):
            print(f"ERROR: {resp}")
            break

        records = resp.get("records", [])
        all_records.extend(records)
        print(f"  Fetched {len(records)} records (total: {len(all_records)})")

        if not resp.get("has_more", False):
            break
        offset = resp.get("next", offset + limit)

    return all_records


def transform_records(records):
    """Transform smartsheet records to clean product list."""
    products = []
    for r in records:
        fv = r.get("field_values", {})
        if not fv.get("产品名称"):
            continue

        def text(key):
            """Extract text from field value (handles both text array and plain string)."""
            v = fv.get(key)
            if v is None:
                return ""
            if isinstance(v, list) and len(v) > 0:
                return str(v[0].get("text", "")).strip()
            if isinstance(v, str):
                return v.strip()
            return str(v).strip()

        def num(key):
            """Extract number from field value."""
            v = fv.get(key)
            if v is None or v == "":
                return None
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, list) and len(v) > 0:
                try:
                    return float(v[0].get("text", 0))
                except (ValueError, TypeError):
                    return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        product = {
            "n": text("产品名称"),
            "c": text("中文名") or text("产品名称"),
            "s": text("系列"),
            "y": int(num("年份")) if num("年份") else 0,
            "price": num("国区现价"),
            "orig": num("国区原价"),
            "disc": text("折扣"),
            "low": num("史低价"),
            "avail": text("国区在售") or "是",
            "rv": text("好评率"),
            "cnr": text("中文评论占比"),
            "sm": int(num("Steam在线") or 0),
            "contract": text("合同状态"),
            "model": text("运营模式"),
            "notes": text("备注"),
            "aid": int(num("AppID") or 0),
        }

        # Determine franchise
        series = product["s"]
        if "Assassin" in series:
            product["f"] = "ac"
        elif "Far Cry" in series:
            product["f"] = "fc"
        elif "Tom Clancy" in series:
            product["f"] = "tc"
        else:
            product["f"] = "ot"

        products.append(product)

    return products


def main():
    print(f"Syncing from Tencent Docs: {FILE_ID}")
    print(f"Sheet: {SHEET_ID}")

    records = fetch_all_records()
    if not records:
        print("No records fetched!")
        sys.exit(1)

    products = transform_records(records)
    print(f"\nTransformed {len(products)} products")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"Saved to {OUTPUT}")
    print(f"File size: {os.path.getsize(OUTPUT)} bytes")


if __name__ == "__main__":
    main()
