# -*- coding: utf-8 -*-
"""
构建四榜衍生数据：
1. 加载某切片最近两天 JSON 快照
2. 按分类对比趋势（新上榜/掉榜/排名变化/阅读量变化）
3. 可选 OpenAI 兼容 API 生成 AI 总结
4. 输出 data/latest|trends|market|dates + api/{channel}/{board}/
"""
import os
import re
import json
import glob
import sys
import argparse
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.board_config import (
    BOARDS,
    api_board_dir,
    board_label,
    compact_to_dash,
    dash_to_compact,
    dates_path,
    find_board,
    genre_groups_for,
    latest_path,
    market_keywords_for,
    market_path,
    parse_board_args,
    repo_root,
    snapshot_dir,
    snapshot_path,
    trend_path,
    trends_dir,
)


def parse_reads(reads_str: str) -> float:
    """将 '15.2万' 这样的字符串转为数值，用于比较。"""
    if not reads_str or reads_str == "未知":
        return 0
    s = reads_str.strip().replace(",", "")
    try:
        if "万" in s:
            return float(s.replace("万", "")) * 10000
        return float(s)
    except ValueError:
        return 0


def format_reads_change(diff: float) -> str:
    """格式化阅读量变化。"""
    if abs(diff) >= 10000:
        return f"{'+' if diff > 0 else ''}{diff / 10000:.1f}万"
    return f"{'+' if diff > 0 else ''}{int(diff)}"


def load_snapshot(path: str) -> dict:
    """加载一个 JSON 快照文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_categories(today_cats: list, prev_cats: list) -> dict:
    """
    对比两天的分类数据，返回每个分类的趋势信息。
    key = 分类名, value = trend dict
    """
    # 构建 prev 的索引: cat_name -> {url: (rank, reads_str, title)}
    prev_index = {}
    for cat in prev_cats:
        url_map = {}
        for i, book in enumerate(cat.get("books", [])):
            url_map[book["url"]] = {
                "rank": i + 1,
                "reads": book.get("reads", "未知"),
                "title": book.get("title", "未知"),
                "intro": book.get("intro", "暂无简介"),
            }
        prev_index[cat["name"]] = url_map

    trends = {}
    for cat in today_cats:
        cat_name = cat["name"]
        prev_urls = prev_index.get(cat_name, {})
        today_books = cat.get("books", [])

        new_books = []
        dropped_books = []
        risers = []
        fallers = []
        reads_growth = []

        today_urls = set()
        for i, book in enumerate(today_books):
            url = book["url"]
            today_urls.add(url)
            today_rank = i + 1
            title = book.get("title", "未知")

            if url in prev_urls:
                prev_info = prev_urls[url]
                prev_rank = prev_info["rank"]
                rank_change = prev_rank - today_rank  # 正数=上升

                if rank_change > 0:
                    risers.append({"title": title, "change": f"+{rank_change}"})
                elif rank_change < 0:
                    fallers.append({"title": title, "change": str(rank_change)})

                # 阅读量变化
                today_reads = parse_reads(book.get("reads", ""))
                prev_reads = parse_reads(prev_info["reads"])
                if today_reads > 0 and prev_reads > 0:
                    diff = today_reads - prev_reads
                    if diff != 0:
                        reads_growth.append(
                            {"title": title, "growth": format_reads_change(diff)}
                        )
            else:
                new_books.append(title)

        # 掉出榜单的书（含简介以便 AI 分析题材）
        for url, info in prev_urls.items():
            if url not in today_urls:
                dropped_books.append({
                    "title": info["title"],
                    "intro": info.get("intro", "暂无简介")[:100],
                })

        # 排序：涨幅最大的在前
        risers.sort(key=lambda x: int(x["change"].replace("+", "")), reverse=True)
        fallers.sort(key=lambda x: int(x["change"]))
        reads_growth.sort(
            key=lambda x: parse_reads(x["growth"].replace("+", "")), reverse=True
        )

        trends[cat_name] = {
            "new_count": len(new_books),
            "dropped_count": len(dropped_books),
            "new_books": new_books[:5],
            "dropped_books": dropped_books[:5],
            "top_risers": risers[:3],
            "top_fallers": fallers[:3],
            "reads_growth": reads_growth[:3],
            "summary": "",  # AI 总结，由 generate_ai_summaries 填充
        }

    return trends


def generate_trend_summary_text(cat_name: str, trend: dict) -> str:
    """生成基于规则的简短趋势文本（作为 AI 总结不可用时的 fallback）。"""
    parts = []
    if trend["new_count"] > 0:
        parts.append(f"新增{trend['new_count']}本上榜")
    if trend["dropped_count"] > 0:
        dropped_titles = [d["title"] if isinstance(d, dict) else d
                          for d in trend.get("dropped_books", [])]
        if dropped_titles:
            parts.append(f"{trend['dropped_count']}本掉出（{'、'.join('《' + t + '》' for t in dropped_titles)}）")
        else:
            parts.append(f"{trend['dropped_count']}本掉出")
    if trend["top_risers"]:
        r = trend["top_risers"][0]
        parts.append(f"《{r['title']}》排名上升{r['change']}位")
    if trend["reads_growth"]:
        g = trend["reads_growth"][0]
        parts.append(f"《{g['title']}》阅读量{g['growth']}")
    if not parts:
        parts.append("榜单无明显变动")
    return "；".join(parts) + "。"


BOARD_FOCUS_HINTS = {
    "female": "该榜为女频：分析时侧重CP设定、情感张力、女性向爽点（团宠、逆袭、宅斗、追妻等）。",
    "male": "该榜为男频：分析时侧重爽点节奏、升级线、打脸反转、争霸布局等维度。",
}


def board_focus_hint(channel: str, board: str) -> str:
    base = BOARD_FOCUS_HINTS.get(channel, "")
    if board == "read":
        return base + "这是阅读榜（存量阅读热度）：侧重长青题材、持续吸引力与读者留存，而非新书爆发力。"
    return base + "这是新书榜（新书上架表现）：侧重题材新鲜度、上架爆发力与差异化卖点。"


def build_ai_prompt(cat_name: str, cat: dict, trend: dict,
                    board_label_text: str = "", focus_hint: str = "") -> str:
    """构建 AI 总结的 prompt（统一模板）。"""
    # 当前榜单书籍
    intros = []
    for i, book in enumerate(cat.get("books", [])[:20]):
        intros.append(
            f"{i+1}. 《{book['title']}》- {book.get('author', '未知')}\n"
            f"   在读：{book.get('reads', '未知')}\n"
            f"   简介：{book.get('intro', '无')[:200]}"
        )
    intros_text = "\n".join(intros)

    # 新上榜书籍
    new_books = trend.get("new_books", [])
    new_text = "、".join(f"《{t}》" for t in new_books) if new_books else "无"

    # 掉出榜单书籍（含简介）
    dropped = trend.get("dropped_books", [])
    if dropped:
        dropped_lines = []
        for d in dropped:
            if isinstance(d, dict):
                dropped_lines.append(f"《{d['title']}》（{d.get('intro', '暂无简介')[:50]}）")
            else:
                dropped_lines.append(f"《{d}》")
        dropped_text = "、".join(dropped_lines)
    else:
        dropped_text = "无"

    # 排名变动
    risers = trend.get("top_risers", [])
    risers_text = "、".join(f"《{r['title']}》{r['change']}" for r in risers) if risers else "无"
    fallers = trend.get("top_fallers", [])
    fallers_text = "、".join(f"《{f['title']}》{f['change']}" for f in fallers) if fallers else "无"

    board_line = f"（{board_label_text}）" if board_label_text else ""
    focus_line = f"\n\n{focus_hint}" if focus_hint else ""
    return f"""你是一位网文行业分析师。请根据以下数据，为番茄小说「{cat_name}」分类榜单{board_line}生成结构化分析。{focus_line}

## 当前榜单 Top 20
{intros_text}

## 榜单变动
- 新上榜：{new_text}
- 掉出榜单：{dropped_text}
- 排名上升：{risers_text}
- 排名下降：{fallers_text}

## 输出要求（请严格按以下格式输出，使用 Markdown）

**🔥 题材趋势**
用1-2句话总结当前分类的主流题材和高频元素，点明哪些设定扎堆出现。

**📖 读者偏好**
用1句话概括读者口味方向，以及金手指类型偏好。

**🆕 新上榜作品**
列出新上榜书名，每本用一句话点评其题材亮点或差异化卖点。

**📉 掉出榜单**
列出掉出书名及其题材方向，简要分析可能掉出的原因（如题材饱和、同质化等）。

**💡 值得关注**
挑1-2本有差异化潜力的作品，说明理由。

要求：每个板块2-3句话，总字数250字以内。语言简洁专业，像行业快报。"""


BATCH_SIZE = 3  # 每批合并的分类数

MARKET_PERIODS = [("7", 7), ("14", 14), ("30", 30), ("all", None)]


def build_batch_ai_prompt(batch: list, board_label_text: str = "",
                          focus_hint: str = "") -> str:
    """构建批量 AI 总结的 prompt。

    batch: list of (cat_name, cat_data, trend_data) tuples
    """
    sections = []
    for cat_name, cat, trend in batch:
        intros = []
        for i, book in enumerate(cat.get("books", [])[:20]):
            intros.append(
                f"{i+1}. 《{book['title']}》- {book.get('author', '未知')}\n"
                f"   在读：{book.get('reads', '未知')}\n"
                f"   简介：{book.get('intro', '无')[:200]}"
            )
        intros_text = "\n".join(intros)

        new_books = trend.get("new_books", [])
        new_text = "、".join(f"《{t}》" for t in new_books) if new_books else "无"

        dropped = trend.get("dropped_books", [])
        if dropped:
            dropped_lines = []
            for d in dropped:
                if isinstance(d, dict):
                    dropped_lines.append(
                        f"《{d['title']}》（{d.get('intro', '暂无简介')[:50]}）"
                    )
                else:
                    dropped_lines.append(f"《{d}》")
            dropped_text = "、".join(dropped_lines)
        else:
            dropped_text = "无"

        risers = trend.get("top_risers", [])
        risers_text = (
            "、".join(f"《{r['title']}》{r['change']}" for r in risers)
            if risers else "无"
        )
        fallers = trend.get("top_fallers", [])
        fallers_text = (
            "、".join(f"《{f['title']}》{f['change']}" for f in fallers)
            if fallers else "无"
        )

        sections.append(
            f"### 分类：{cat_name}\n\n"
            f"**当前榜单 Top 20：**\n{intros_text}\n\n"
            f"**榜单变动：**\n"
            f"- 新上榜：{new_text}\n"
            f"- 掉出榜单：{dropped_text}\n"
            f"- 排名上升：{risers_text}\n"
            f"- 排名下降：{fallers_text}"
        )

    all_sections = "\n\n---\n\n".join(sections)
    cat_names = [b[0] for b in batch]

    output_examples = "\n\n".join(
        f"===BEGIN: {name}===\n"
        f"**🔥 题材趋势** ...\n"
        f"**📖 读者偏好** ...\n"
        f"**🆕 新上榜作品** ...\n"
        f"**📉 掉出榜单** ...\n"
        f"**💡 值得关注** ...\n"
        f"===END: {name}==="
        for name in cat_names
    )

    board_line = f"「{board_label_text}」" if board_label_text else ""
    focus_line = f"\n{focus_hint}" if focus_hint else ""
    return (
        f"你是一位网文行业分析师。请根据以下数据，"
        f"为番茄小说{board_line}的多个分类分别生成结构化分析。\n{focus_line}\n\n"
        f"{all_sections}\n\n"
        f"## 输出要求\n\n"
        f"请严格按照以下格式，为每个分类分别输出分析。"
        f"每个分类的分析必须包裹在对应的标记中：\n\n"
        f"{output_examples}\n\n"
        f"每个板块2-3句话，每个分类总字数250字以内。"
        f"语言简洁专业，像行业快报。\n"
        f"注意：必须为每个分类都输出完整分析，不可省略任何分类。"
    )


def parse_batch_response(response_text: str, cat_names: list) -> dict:
    """解析批量 AI 响应，返回 {cat_name: summary} 字典。"""
    results = {}
    for name in cat_names:
        pattern = rf"===BEGIN:\s*{re.escape(name)}\s*===(.*?)===END:\s*{re.escape(name)}\s*==="
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            summary = match.group(1).strip()
            if summary:
                results[name] = summary
    return results


def _save_trends_incremental(trend_path: str, date: str,
                             prev_date: str, trends: dict):
    """增量保存趋势数据到文件（每批成功后立即写入）。"""
    if not trend_path:
        return
    trend_output = {
        "date": date,
        "prev_date": prev_date,
        "trends": trends,
    }
    parent = os.path.dirname(trend_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(trend_path, "w", encoding="utf-8") as f:
        json.dump(trend_output, f, ensure_ascii=False, indent=2)


def api_type_filename(type_name: str) -> str:
    """将类型名转成适合作为静态 JSON 文件名的名称。"""
    name = (type_name or "").strip()
    name = re.sub(r"[\\/]+", "_", name)
    name = re.sub(r"[^\w\u4e00-\u9fff\s-]", "_", name)
    name = re.sub(r"\s+", "_", name).strip("._")
    return name or "unknown"


def write_json(path: str, payload: dict):
    """统一写 JSON，确保中文可读。"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_board_api(output: dict, channel: str, board: str, base_dir: str):
    """生成静态切片 API：api/{channel}/{board}/..."""
    api_dir = api_board_dir(channel, board, base_dir)
    os.makedirs(api_dir, exist_ok=True)
    for old_path in glob.glob(os.path.join(api_dir, "*.json")):
        os.remove(old_path)

    date = output.get("date", "")
    prev_date = output.get("prev_date", "")
    categories = output.get("categories", [])
    label = board_label(channel, board)
    url_prefix = f"api/{channel}/{board}"

    all_payload = {
        "channel": channel,
        "board": board,
        "label": label,
        "type": "all",
        "date": date,
        "prev_date": prev_date,
        "categories": categories,
    }
    write_json(os.path.join(api_dir, "all.json"), all_payload)

    types = [{
        "type": "all",
        "url": f"{url_prefix}/all.json",
        "category_count": len(categories),
        "book_count": sum(len(cat.get("books", [])) for cat in categories),
    }]

    used_filenames = {"all", "index"}
    for cat in categories:
        type_name = cat.get("name", "")
        filename = api_type_filename(type_name)
        base_filename = filename
        suffix = 2
        while filename in used_filenames:
            filename = f"{base_filename}_{suffix}"
            suffix += 1
        used_filenames.add(filename)

        payload = {
            "channel": channel,
            "board": board,
            "label": label,
            "type": type_name,
            "date": date,
            "prev_date": prev_date,
            "category": cat,
            "categories": [cat],
        }
        write_json(os.path.join(api_dir, f"{filename}.json"), payload)

        url = f"{url_prefix}/{quote(filename)}.json"
        types.append({
            "type": type_name,
            "url": url,
            "book_count": len(cat.get("books", [])),
        })

    index_payload = {
        "channel": channel,
        "board": board,
        "label": label,
        "date": date,
        "prev_date": prev_date,
        "types": types,
    }
    write_json(os.path.join(api_dir, "index.json"), index_payload)
    return api_dir


def write_api_root_index(base_dir: str):
    """写入四榜总索引 api/index.json。"""
    boards = []
    for cfg in BOARDS:
        ch, bd = cfg["channel"], cfg["board"]
        boards.append({
            "channel": ch,
            "board": bd,
            "label": cfg["label"],
            "url": f"api/{ch}/{bd}/index.json",
            "all_url": f"api/{ch}/{bd}/all.json",
        })
    write_json(os.path.join(base_dir, "api", "index.json"), {"boards": boards})


def parse_change(change: str) -> int:
    """解析 '+3' / '-2' 这类排名变化。"""
    try:
        return int(str(change or "0").replace("+", ""))
    except ValueError:
        return 0


def load_trend_rows(trends_dir: str) -> list:
    """加载全部趋势归档，按日期升序排列。"""
    rows = []
    for path in sorted(glob.glob(os.path.join(trends_dir, "*.json"))):
        try:
            data = load_snapshot(path)
            rows.append({
                "date": data.get("date", ""),
                "prev_date": data.get("prev_date", ""),
                "trends": data.get("trends", {}),
            })
        except Exception as e:
            print(f"  ⚠️  跳过趋势文件 {path}: {e}")
    return sorted([r for r in rows if r["date"]], key=lambda x: x["date"])


def summarize_market_rows(rows: list) -> dict:
    """汇总某个分类在一组趋势行中的动能指标。"""
    totals = {
        "new_count": 0,
        "dropped_count": 0,
        "riser_count": 0,
        "faller_count": 0,
        "read_count": 0,
        "read_growth_total": 0,
        "active_days": 0,
    }
    for row in rows:
        trend = row.get("trend") or {}
        riser_count = len(trend.get("top_risers", []))
        faller_count = len(trend.get("top_fallers", []))
        read_count = len(trend.get("reads_growth", []))
        read_growth_total = sum(
            parse_reads(item.get("growth", ""))
            for item in trend.get("reads_growth", [])
        )
        totals["new_count"] += int(trend.get("new_count", 0) or 0)
        totals["dropped_count"] += int(trend.get("dropped_count", 0) or 0)
        totals["riser_count"] += riser_count
        totals["faller_count"] += faller_count
        totals["read_count"] += read_count
        totals["read_growth_total"] += read_growth_total
        if (
            trend.get("new_count", 0) or trend.get("dropped_count", 0)
            or riser_count or faller_count or read_count
        ):
            totals["active_days"] += 1
    return totals


def market_score(totals: dict) -> int:
    """计算全站热点分：综合赛道和具体分类只看新增在读量。"""
    return round(totals["read_growth_total"])


def format_market_reads(value: float) -> str:
    """格式化市场层面的新增在读量。"""
    if abs(value) >= 10000:
        return f"{value / 10000:.1f}万"
    return str(round(value))


def collect_market_hot_types(categories: list, rows_window: list) -> list:
    """统计具体分类热度。"""
    result = []
    for name in categories:
        rows = [
            {"trend": row.get("trends", {}).get(name)}
            for row in rows_window
            if row.get("trends", {}).get(name)
        ]
        totals = summarize_market_rows(rows)
        score = market_score(totals)
        if score <= 0:
            continue
        result.append({
            "name": name,
            "score": score,
            "new_count": totals["new_count"],
            "dropped_count": totals["dropped_count"],
            "read_count": totals["read_count"],
            "read_growth_total": totals["read_growth_total"],
            "active_days": totals["active_days"],
        })
    return sorted(
        result,
        key=lambda x: (x["read_growth_total"], x["read_count"]),
        reverse=True
    )


def collect_market_hot_genres(categories: list, hot_types: list,
                              genre_groups: list = None) -> list:
    """按综合赛道聚合具体分类热度。"""
    genre_groups = genre_groups or []
    type_map = {item["name"]: item for item in hot_types}
    genres = []
    for group in genre_groups:
        matched = []
        for name in group["categories"]:
            if name not in categories:
                continue
            matched.append(type_map.get(name, {
                "name": name,
                "score": 0,
                "new_count": 0,
                "dropped_count": 0,
                "read_count": 0,
                "read_growth_total": 0,
                "active_days": 0,
            }))
        if not matched:
            continue
        read_growth_total = sum(item["read_growth_total"] for item in matched)
        if read_growth_total <= 0:
            continue
        lead = sorted(
            matched,
            key=lambda x: (x["read_growth_total"], x["read_count"]),
            reverse=True
        )[0]
        genres.append({
            "name": group["name"],
            "score": round(read_growth_total),
            "new_count": sum(item["new_count"] for item in matched),
            "dropped_count": sum(item["dropped_count"] for item in matched),
            "read_count": sum(item["read_count"] for item in matched),
            "read_growth_total": read_growth_total,
            "active_days": sum(item["active_days"] for item in matched),
            "lead_category": lead["name"],
            "categories": [item["name"] for item in matched],
        })
    return sorted(
        genres,
        key=lambda x: (x["read_growth_total"], x["read_count"]),
        reverse=True
    )


def add_theme_hits(score_map: dict, keywords: list, text: str,
                   category_name: str, weight: int):
    """给命中的题材关键词加权。"""
    source = str(text or "")
    if not source:
        return
    for keyword in keywords:
        if keyword not in source:
            continue
        item = score_map[keyword]
        item["count"] += weight
        item["categories"].add(category_name)


def collect_market_hot_themes(output: dict, rows_window: list,
                              categories: list, keywords: list = None) -> list:
    """只统计近期新上榜作品中的高频题材词。"""
    keywords = keywords or []
    score_map = {
        name: {"name": name, "count": 0, "categories": set()}
        for name in keywords
    }
    latest_book_map = {}
    for cat in output.get("categories", []):
        for book in cat.get("books", []):
            title = book.get("title", "")
            if title:
                latest_book_map[title] = book

    for row in rows_window:
        for cat_name in categories:
            trend = row.get("trends", {}).get(cat_name)
            if not trend:
                continue
            for title in trend.get("new_books", []):
                book = latest_book_map.get(title, {})
                add_theme_hits(
                    score_map,
                    keywords,
                    f"{title} {book.get('intro', '')}",
                    cat_name,
                    1
                )

    themes = []
    for item in score_map.values():
        if item["count"] <= 0:
            continue
        themes.append({
            "name": item["name"],
            "count": item["count"],
            "category_count": len(item["categories"]),
        })
    return sorted(
        themes,
        key=lambda x: (x["count"], x["category_count"]),
        reverse=True
    )


def build_rule_market_summary(period_label: str, hot_genres: list,
                              hot_types: list, hot_themes: list) -> str:
    """基于统计结果生成全站热点兜底文案。"""
    top_genres = "、".join(item["name"] for item in hot_genres[:2])
    top_types = "、".join(item["name"] for item in hot_types[:3])
    top_themes = "、".join(item["name"] for item in hot_themes[:6])
    if not top_genres and not top_types:
        return f"{period_label}暂无足够数据判断全站热点。"
    return (
        f"{period_label}里，{top_genres or top_types} 的阅读增长更强，"
        f"具体分类以 {top_types} 的新增在读更集中；新书题材上 {top_themes} "
        f"更高频，说明读者仍偏好强设定、强情绪钩子和明确爽点。"
    )


def build_market_summary_payload(output: dict, trends_directory: str,
                                 channel: str = "female",
                                 board: str = "new") -> dict:
    """生成本榜热点统计和规则兜底总结。"""
    categories = [cat.get("name", "") for cat in output.get("categories", [])]
    trend_rows = load_trend_rows(trends_directory)
    groups = genre_groups_for(channel)
    keywords = market_keywords_for(channel)
    periods = {}

    for key, days in MARKET_PERIODS:
        rows_window = trend_rows if days is None else trend_rows[-days:]
        period_label = "全部样本" if days is None else f"近 {days} 日"
        hot_types = collect_market_hot_types(categories, rows_window)
        hot_genres = collect_market_hot_genres(categories, hot_types, groups)
        hot_themes = collect_market_hot_themes(
            output, rows_window, categories, keywords
        )
        fallback_summary = build_rule_market_summary(
            period_label, hot_genres, hot_types, hot_themes
        )
        periods[key] = {
            "period": period_label,
            "source": "rule",
            "summary": fallback_summary,
            "fallback_summary": fallback_summary,
            "hot_genres": hot_genres[:5],
            "hot_types": hot_types[:6],
            "hot_themes": hot_themes[:14],
        }

    return {
        "channel": channel,
        "board": board,
        "label": board_label(channel, board),
        "date": output.get("date", ""),
        "prev_date": output.get("prev_date", ""),
        "periods": periods,
    }


def build_market_ai_prompt(payload: dict) -> str:
    """构建全站热点 AI 总结 prompt。"""
    sections = []
    for key, data in payload.get("periods", {}).items():
        genres = "、".join(
            f"{item['name']}(新增在读{format_market_reads(item.get('read_growth_total', 0))}, "
            f"增长作品{item.get('read_count', 0)})"
            for item in data.get("hot_genres", [])[:5]
        )
        types = "、".join(
            f"{item['name']}(新增在读{format_market_reads(item.get('read_growth_total', 0))}, "
            f"增长作品{item.get('read_count', 0)})"
            for item in data.get("hot_types", [])[:6]
        )
        themes = "、".join(
            f"{item['name']}(新书{item['count']}本)"
            for item in data.get("hot_themes", [])[:10]
        )
        sections.append(
            f"周期 {key} / {data['period']}:\n"
            f"- 综合赛道（按阅读增长量排序）: {genres or '无'}\n"
            f"- 具体分类（按阅读增长量排序）: {types or '无'}\n"
            f"- 高频题材（只统计新上榜作品，按新书数量排序）: {themes or '无'}\n"
            f"- 规则兜底: {data['fallback_summary']}"
        )

    label = payload.get("label") or "番茄榜单"
    return f"""你是一位网文市场编辑，请根据番茄小说「{label}」的统计结果，为每个周期生成一段本榜热点判断。

{chr(10).join(sections)}

要求：
1. 只基于给定统计，不要编造未出现的类型或题材。
2. 每个周期输出 1 段中文，80-140 字。
3. 综合赛道和具体分类必须按“新增在读/阅读增长”解读，不要写“榜单动能”或“排名动能”。
4. 高频题材必须按“新上榜作品数量”解读，不要混入存量榜单或摘要题材。
5. 点明综合赛道、具体分类、题材关键词，以及一句编辑判断。
6. 输出严格 JSON，不要 Markdown，不要解释，格式如下：
{{
  "7": "总结文本",
  "14": "总结文本",
  "30": "总结文本",
  "all": "总结文本"
}}"""


def parse_json_object(text: str) -> dict:
    """尽量从模型响应中提取 JSON 对象。"""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def chat_create_kwargs(model: str) -> dict:
    """DeepSeek V4 系列思考模式默认开启，思维链走 reasoning_content，
    content 偶发为空；趋势总结是格式化任务，显式关闭思考模式。
    其他服务商不传该参数，避免未知字段报错。"""
    if "deepseek" in (model or "").lower():
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}


def enrich_market_summary_with_ai(payload: dict, api_key: str,
                                  base_url: str, model: str) -> dict:
    """使用 AI 改写全站热点总结；失败时保留规则兜底。"""
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  openai 库未安装，跳过全站热点 AI 总结。")
        return payload

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": build_market_ai_prompt(payload)}],
            max_tokens=900,
            temperature=0.5,
            **chat_create_kwargs(model),
        )
        parsed = parse_json_object(response.choices[0].message.content)
        label = payload.get("label") or "未知榜"
        total = len(payload.get("periods", {}))
        updated = 0
        for key, summary in parsed.items():
            if key in payload["periods"] and isinstance(summary, str) and summary.strip():
                payload["periods"][key]["summary"] = summary.strip()
                payload["periods"][key]["source"] = "ai"
                updated += 1
        if total and updated == total:
            print(f"✅ {label} 全站热点 AI 总结已生成（{updated}/{total} 周期）")
        elif updated:
            print(f"⚠️  {label} 全站热点 AI 总结仅覆盖 {updated}/{total} 周期，其余保留规则兜底")
        else:
            print(f"⚠️  {label} 全站热点 AI 响应未解析出有效周期，保留规则兜底")
    except Exception as e:
        label = payload.get("label") or "未知榜"
        print(f"⚠️  {label} 全站热点 AI 总结失败，使用规则兜底: {e}")

    return payload



def is_rule_summary(summary: str) -> bool:
    """判断一个总结是否为规则模板生成的（非 AI）。
    规则摘要特征：短小、分号分隔、以句号结尾、无换行。
    """
    if not summary:
        return True
    if summary == "首日数据，暂无趋势对比。":
        return True
    # 规则摘要一般 < 150 字，用分号分隔，无换行
    if len(summary) < 150 and "；" in summary and "\n" not in summary:
        return True
    return False


def generate_ai_summaries(categories: list, trends: dict,
                          api_key: str, base_url: str,
                          model: str, force: bool = False,
                          existing_trends: dict = None,
                          trend_path: str = None,
                          trend_date: str = "",
                          prev_date: str = "",
                          board_label_text: str = "",
                          focus_hint: str = "") -> dict:
    """通过 OpenAI 兼容 API 为每个分类生成 AI 总结。

    采用批量合并策略（每 BATCH_SIZE 个分类一次调用）减少 API 调用次数，
    并在每批成功后增量保存，避免中途失败丢失已完成的结果。
    批量失败的分类会自动降级为逐个重试。
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  openai 库未安装，跳过 AI 总结。pip install openai")
        return trends

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
    existing_trends = existing_trends or {}

    # 1. 筛选需要生成总结的分类
    pending = []  # (cat_name, cat_data, trend_data)
    skipped = 0

    for cat in categories:
        cat_name = cat["name"]
        if cat_name not in trends:
            continue

        if not force:
            existing_summary = existing_trends.get(cat_name, {}).get("summary", "")
            if existing_summary and not is_rule_summary(existing_summary):
                trends[cat_name]["summary"] = existing_summary
                skipped += 1
                continue

        pending.append((cat_name, cat, trends[cat_name]))

    if skipped > 0:
        print(f"  ⏭️  跳过 {skipped} 个已有 AI 总结的分类")

    if not pending:
        print("  ✅ 所有分类已有 AI 总结，无需生成")
        return trends

    # 2. 分批处理
    batches = [
        pending[i:i + BATCH_SIZE]
        for i in range(0, len(pending), BATCH_SIZE)
    ]
    failed_cats = []  # 批量失败后需单独重试的分类

    print(f"  📦 共 {len(pending)} 个分类，分 {len(batches)} 批处理"
          f"（每批最多 {BATCH_SIZE} 个）")

    for batch_idx, batch in enumerate(batches):
        batch_names = [b[0] for b in batch]
        print(f"\n  📦 第 {batch_idx + 1}/{len(batches)} 批: "
              f"{', '.join(batch_names)}")

        prompt = build_batch_ai_prompt(batch, board_label_text, focus_hint)

        max_retries = 3
        batch_success = False
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800 * len(batch),
                    temperature=0.7,
                    **chat_create_kwargs(model),
                )
                content = response.choices[0].message.content
                if not content or not content.strip():
                    finish = response.choices[0].finish_reason
                    raise ValueError(
                        f"API 返回空内容 (finish_reason={finish})")

                # 解析批量响应
                parsed = parse_batch_response(content, batch_names)

                if parsed:
                    for name, summary in parsed.items():
                        trends[name]["summary"] = summary
                        print(f"    ✅ {name}")

                    # 未解析出的分类加入失败队列
                    for name in batch_names:
                        if name not in parsed:
                            print(f"    ⚠️  未解析到: {name}（将单独重试）")
                            failed_cats.append(
                                next(b for b in batch if b[0] == name)
                            )

                    # 增量保存
                    _save_trends_incremental(
                        trend_path, trend_date, prev_date, trends
                    )
                    batch_success = True
                    break
                else:
                    raise ValueError("批量响应解析失败，未匹配到任何分类")

            except Exception as e:
                print(f"    ⚠️  第 {attempt} 次失败: {e}")
                if attempt < max_retries:
                    import time
                    time.sleep(5 * attempt)

        if not batch_success:
            print(f"    ❌ 批量生成失败（已重试 {max_retries} 次），"
                  f"将逐个重试")
            failed_cats.extend(batch)

    # 3. 对失败的分类逐个重试（降级为单分类 prompt）
    if failed_cats:
        print(f"\n  🔄 逐个重试 {len(failed_cats)} 个失败分类...")
        for cat_name, cat, trend in failed_cats:
            prompt = build_ai_prompt(cat_name, cat, trend,
                                     board_label_text, focus_hint)
            max_retries = 3
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=700,
                        temperature=0.7,
                        **chat_create_kwargs(model),
                    )
                    content = response.choices[0].message.content
                    if not content or not content.strip():
                        finish = response.choices[0].finish_reason
                        raise ValueError(
                            f"API 返回空内容 (finish_reason={finish})")
                    trends[cat_name]["summary"] = content.strip()
                    print(f"    ✅ {cat_name}")
                    _save_trends_incremental(
                        trend_path, trend_date, prev_date, trends
                    )
                    success = True
                    break
                except Exception as e:
                    print(f"    ⚠️  {cat_name} 第 {attempt} 次失败: {e}")
                    if attempt < max_retries:
                        import time
                        time.sleep(5 * attempt)

            if not success:
                print(f"    ❌ {cat_name} 最终失败")
                old = existing_trends.get(cat_name, {}).get("summary", "")
                if old and not is_rule_summary(old):
                    trends[cat_name]["summary"] = old
                    print(f"    ↩️  保留旧 AI 总结: {cat_name}")
                else:
                    trends[cat_name]["summary"] = generate_trend_summary_text(
                        cat_name, trend
                    )

    return trends


def list_snapshots(channel: str, board: str, base_dir: str) -> list:
    sdir = snapshot_dir(channel, board, base_dir)
    return sorted(glob.glob(os.path.join(sdir, "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json")))


def build_one_board(channel: str, board: str, base_dir: str,
                    target_date: str = "", force: bool = False,
                    api_base_url: str = "", api_key: str = "",
                    api_model: str = "") -> bool:
    """构建单个切片。无快照时返回 False。"""
    label = board_label(channel, board)
    snapshots = list_snapshots(channel, board, base_dir)
    if not snapshots:
        print(f"\n⏭️  {label}: 无快照，跳过")
        return False

    if target_date:
        compact = dash_to_compact(target_date)
        target_path = snapshot_path(channel, board, compact, base_dir)
        if not os.path.exists(target_path):
            print(f"❌ {label}: 未找到 {target_date} 快照")
            return False
        target_idx = snapshots.index(target_path) if target_path in snapshots else -1
        latest_snap_path = target_path
    else:
        latest_snap_path = snapshots[-1]
        target_idx = len(snapshots) - 1

    latest_data = load_snapshot(latest_snap_path)
    print(f"\n===== {label} =====")
    print(f"目标快照: {os.path.basename(latest_snap_path)} ({latest_data.get('date')})")

    prev_data = None
    prev_date = ""
    if target_idx > 0:
        prev_path = snapshots[target_idx - 1]
        prev_data = load_snapshot(prev_path)
        prev_date = prev_data.get("date", "")
        print(f"对比快照: {os.path.basename(prev_path)} ({prev_date})")

    t_dir = trends_dir(channel, board, base_dir)
    os.makedirs(t_dir, exist_ok=True)
    t_path = trend_path(channel, board, latest_data["date"], base_dir)

    existing_trends = {}
    if os.path.exists(t_path) and not force:
        try:
            existing_trend_data = load_snapshot(t_path)
            existing_trends = existing_trend_data.get("trends", {})
            ai_count = sum(
                1 for t in existing_trends.values()
                if not is_rule_summary(t.get("summary", ""))
            )
            rule_count = len(existing_trends) - ai_count
            print(f"已有趋势: {ai_count} AI / {rule_count} 待补充")
        except Exception:
            pass

    if force:
        print("🔄 强制重新生成 AI 总结")

    if prev_data:
        trends = compare_categories(
            latest_data.get("categories", []),
            prev_data.get("categories", []),
        )
    else:
        print("仅有一天数据，无法生成趋势对比。")
        trends = {
            cat["name"]: {
                "new_count": 0,
                "dropped_count": 0,
                "new_books": [],
                "dropped_books": [],
                "top_risers": [],
                "top_fallers": [],
                "reads_growth": [],
                "summary": "首日数据，暂无趋势对比。",
            }
            for cat in latest_data.get("categories", [])
        }

    if api_base_url and api_key and api_model:
        print(f"使用 {api_model} 生成 AI 总结...")
        trends = generate_ai_summaries(
            latest_data.get("categories", []), trends,
            api_key, api_base_url, api_model,
            force=force,
            existing_trends=existing_trends,
            trend_path=t_path,
            trend_date=latest_data["date"],
            prev_date=prev_date,
            board_label_text=label,
            focus_hint=board_focus_hint(channel, board),
        )
    else:
        print("未配置 AI，使用规则摘要。")
        for cat_name, trend in trends.items():
            old = existing_trends.get(cat_name, {}).get("summary", "")
            if old and not is_rule_summary(old):
                trend["summary"] = old
            elif not trend.get("summary"):
                trend["summary"] = generate_trend_summary_text(cat_name, trend)

    output = {
        "channel": channel,
        "board": board,
        "label": label,
        "date": latest_data["date"],
        "prev_date": prev_date,
        "categories": [],
    }
    for cat in latest_data.get("categories", []):
        cat_name = cat["name"]
        output["categories"].append({
            "name": cat_name,
            "trend": trends.get(cat_name, {}),
            "books": cat.get("books", []),
        })

    out_path = latest_path(channel, board, base_dir)
    write_json(out_path, output)
    print(f"✅ latest: {out_path}")

    api_dir = build_board_api(output, channel, board, base_dir)
    print(f"✅ api: {api_dir}")

    trend_output = {
        "channel": channel,
        "board": board,
        "date": latest_data["date"],
        "prev_date": prev_date,
        "trends": trends,
    }
    write_json(t_path, trend_output)
    print(f"✅ trends: {t_path}")

    market_payload = build_market_summary_payload(
        output, t_dir, channel=channel, board=board
    )
    if api_base_url and api_key and api_model:
        market_payload = enrich_market_summary_with_ai(
            market_payload, api_key, api_base_url, api_model
        )
    m_path = market_path(channel, board, base_dir)
    write_json(m_path, market_payload)
    print(f"✅ market: {m_path}")

    date_list = []
    for s in snapshots:
        m = re.search(r"(\d{4})(\d{2})(\d{2})\.json$", os.path.basename(s))
        if m:
            date_list.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    d_path = dates_path(channel, board, base_dir)
    write_json(d_path, {"channel": channel, "board": board, "dates": sorted(date_list)})
    print(f"✅ dates: {d_path} ({len(date_list)} 天)")
    return True


def main():
    parser = argparse.ArgumentParser(description="构建四榜 latest / trends / api")
    parser.add_argument("--force", action="store_true",
                        help="强制重新生成所有 AI 总结")
    parser.add_argument("--date", type=str, default="",
                        help="目标日期 YYYY-MM-DD，默认最新快照")
    parser.add_argument("--channel", type=str, default="",
                        help="female / male，空=全部")
    parser.add_argument("--board", type=str, default="",
                        help="new / read，空=全部")
    args = parser.parse_args()

    base_dir = repo_root()
    targets = parse_board_args(args.channel, args.board)
    api_base_url = os.environ.get("API_BASE_URL", "")
    api_key = os.environ.get("API_KEY", "")
    api_model = os.environ.get("API_MODEL", "")

    built = 0
    for channel, board in targets:
        ok = build_one_board(
            channel, board, base_dir,
            target_date=args.date,
            force=args.force,
            api_base_url=api_base_url,
            api_key=api_key,
            api_model=api_model,
        )
        if ok:
            built += 1

    write_api_root_index(base_dir)
    print(f"\n✅ api/index.json 已更新；成功构建 {built}/{len(targets)} 个切片")
    if built == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
