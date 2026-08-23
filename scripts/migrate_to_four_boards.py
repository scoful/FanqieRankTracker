# -*- coding: utf-8 -*-
"""将旧版女频新书扁平数据迁移到 data/{channel}/{board}/ 四榜结构。

一次性脚本：迁移快照、趋势、latest、market、dates、api。
默认删除旧路径文件（可用 --keep-old 保留）。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.board_config import (  # noqa: E402
    api_board_dir,
    dates_path,
    latest_path,
    market_path,
    repo_root,
    snapshot_path,
    trend_path,
    trends_dir,
)


def write_json(path: str, payload: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_snapshots(root: str) -> int:
    data_dir = os.path.join(root, "data")
    pattern = os.path.join(data_dir, "fanqie_female_new_ranks_*.json")
    count = 0
    for path in sorted(glob.glob(pattern)):
        m = re.search(r"(\d{8})\.json$", path)
        if not m:
            continue
        compact = m.group(1)
        data = load_json(path)
        data["channel"] = "female"
        data["board"] = "new"
        data["label"] = "女频新书榜"
        if "date" not in data or not data["date"]:
            data["date"] = f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
        out = snapshot_path("female", "new", compact, root)
        write_json(out, data)
        count += 1
        print(f"  快照: {os.path.basename(path)} -> female/new/{compact}.json")
    return count


def migrate_trends(root: str) -> int:
    old_dir = os.path.join(root, "data", "trends")
    if not os.path.isdir(old_dir):
        return 0
    count = 0
    for path in sorted(glob.glob(os.path.join(old_dir, "*.json"))):
        name = os.path.basename(path)
        if not re.match(r"\d{4}-\d{2}-\d{2}\.json$", name):
            continue
        # 跳过已是子目录结构时误扫到的（旧结构 trends 下直接是日期文件）
        data = load_json(path)
        data["channel"] = "female"
        data["board"] = "new"
        out = trend_path("female", "new", name.replace(".json", ""), root)
        write_json(out, data)
        count += 1
        print(f"  趋势: {name} -> trends/female/new/{name}")
    return count


def migrate_singletons(root: str) -> None:
    data_dir = os.path.join(root, "data")

    latest_old = os.path.join(data_dir, "latest_ranks.json")
    if os.path.exists(latest_old):
        data = load_json(latest_old)
        data["channel"] = "female"
        data["board"] = "new"
        data["label"] = "女频新书榜"
        write_json(latest_path("female", "new", root), data)
        print("  latest_ranks.json -> data/latest/female/new.json")

    market_old = os.path.join(data_dir, "market_summary.json")
    if os.path.exists(market_old):
        data = load_json(market_old)
        data["channel"] = "female"
        data["board"] = "new"
        write_json(market_path("female", "new", root), data)
        print("  market_summary.json -> data/market/female/new.json")

    dates_old = os.path.join(data_dir, "dates.json")
    if os.path.exists(dates_old):
        data = load_json(dates_old)
        write_json(dates_path("female", "new", root), data)
        print("  dates.json -> data/dates/female/new.json")


def migrate_api(root: str) -> None:
    old_api = os.path.join(root, "api", "lastest")
    old_index = os.path.join(root, "api", "lastest.json")
    new_dir = api_board_dir("female", "new", root)
    os.makedirs(new_dir, exist_ok=True)

    if os.path.isdir(old_api):
        for path in glob.glob(os.path.join(old_api, "*.json")):
            name = os.path.basename(path)
            data = load_json(path)
            if isinstance(data, dict):
                data["channel"] = "female"
                data["board"] = "new"
            write_json(os.path.join(new_dir, name), data)
            print(f"  api/lastest/{name} -> api/female/new/{name}")

    if os.path.exists(old_index):
        data = load_json(old_index)
        data["channel"] = "female"
        data["board"] = "new"
        # 重写 url 前缀
        for item in data.get("types", []):
            url = item.get("url", "")
            if url.startswith("api/lastest/"):
                item["url"] = url.replace("api/lastest/", "api/female/new/", 1)
            elif url.startswith("api/lastest"):
                item["url"] = url.replace("api/lastest", "api/female/new", 1)
        write_json(os.path.join(new_dir, "index.json"), data)
        print("  api/lastest.json -> api/female/new/index.json")

    # 总索引
    index = {
        "boards": [
            {
                "channel": "female",
                "board": "new",
                "label": "女频新书榜",
                "url": "api/female/new/index.json",
                "all_url": "api/female/new/all.json",
            },
            {
                "channel": "female",
                "board": "read",
                "label": "女频阅读榜",
                "url": "api/female/read/index.json",
                "all_url": "api/female/read/all.json",
            },
            {
                "channel": "male",
                "board": "new",
                "label": "男频新书榜",
                "url": "api/male/new/index.json",
                "all_url": "api/male/new/all.json",
            },
            {
                "channel": "male",
                "board": "read",
                "label": "男频阅读榜",
                "url": "api/male/read/index.json",
                "all_url": "api/male/read/all.json",
            },
        ]
    }
    write_json(os.path.join(root, "api", "index.json"), index)
    print("  写入 api/index.json")


def remove_old(root: str) -> None:
    data_dir = os.path.join(root, "data")
    removed = 0

    for path in glob.glob(os.path.join(data_dir, "fanqie_female_new_ranks_*")):
        os.remove(path)
        removed += 1
    for path in glob.glob(os.path.join(data_dir, "task_state_*.json")):
        os.remove(path)
        removed += 1

    for name in ("latest_ranks.json", "market_summary.json", "dates.json"):
        path = os.path.join(data_dir, name)
        if os.path.exists(path):
            os.remove(path)
            removed += 1

    # 旧扁平 trends 日期文件（保留 trends/female 等子目录）
    trends = os.path.join(data_dir, "trends")
    if os.path.isdir(trends):
        for path in glob.glob(os.path.join(trends, "*.json")):
            if re.match(r"\d{4}-\d{2}-\d{2}\.json$", os.path.basename(path)):
                os.remove(path)
                removed += 1

    old_api_dir = os.path.join(root, "api", "lastest")
    if os.path.isdir(old_api_dir):
        shutil.rmtree(old_api_dir)
        removed += 1
    old_api_index = os.path.join(root, "api", "lastest.json")
    if os.path.exists(old_api_index):
        os.remove(old_api_index)
        removed += 1

    print(f"  已删除旧文件/目录项约 {removed} 个")


def main():
    parser = argparse.ArgumentParser(description="迁移到四榜目录结构")
    parser.add_argument("--keep-old", action="store_true", help="保留旧路径文件")
    args = parser.parse_args()
    root = repo_root()
    print(f"仓库根目录: {root}")

    print("\n[1/4] 迁移快照...")
    n1 = migrate_snapshots(root)
    print(f"  共 {n1} 个快照")

    print("\n[2/4] 迁移趋势...")
    n2 = migrate_trends(root)
    print(f"  共 {n2} 个趋势文件")

    print("\n[3/4] 迁移 latest/market/dates...")
    migrate_singletons(root)

    print("\n[4/4] 迁移 API...")
    migrate_api(root)

    if not args.keep_old:
        print("\n清理旧路径...")
        remove_old(root)
    else:
        print("\n已保留旧路径（--keep-old）")

    print("\n✅ 迁移完成")


if __name__ == "__main__":
    main()
