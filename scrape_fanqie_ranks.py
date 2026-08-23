# -*- coding: utf-8 -*-
"""番茄小说四榜爬虫：女/男 × 新书/阅读。"""
import argparse
import json
import os
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from scripts.board_config import (
    BOARDS,
    find_board,
    init_url,
    parse_board_args,
    rank_prefix,
    snapshot_path,
    task_state_path,
)

START_CODE = 58344  # 0xE3E8
CHAR_SEQUENCE = [
    "D", "在", "主", "特", "家", "军", "然", "表", "场", "4", "要", "只", "v", "和", "?", "6", "别", "还", "g", "现", "儿", "岁", "?", "?", "此", "象", "月", "3", "出", "战", "工", "相", "o", "男", "直", "失", "世", "F", "都", "平", "文", "什", "V", "O", "将", "真", "T", "那", "当", "?", "会", "立", "些", "u", "是", "十", "张", "学", "气", "大", "爱", "两", "命", "全", "后", "东", "性", "通", "被", "1", "它", "乐", "接", "而", "感", "车", "山", "公", "了", "常", "以", "何", "可", "话", "先", "p", "i", "叫", "轻", "M", "士", "w", "着", "变", "尔", "快", "l", "个", "说", "少", "色", "里", "安", "花", "远", "7", "难", "师", "放", "t", "报", "认", "面", "道", "S", "?", "克", "地", "度", "I", "好", "机", "U", "民", "写", "把", "万", "同", "水", "新", "没", "书", "电", "吃", "像", "斯", "5", "为", "y", "白", "几", "日", "教", "看", "但", "第", "加", "候", "作", "上", "拉", "住", "有", "法", "r", "事", "应", "位", "利", "你", "声", "身", "国", "问", "马", "女", "他", "Y", "比", "父", "x", "A", "H", "N", "s", "X", "边", "美", "对", "所", "金", "活", "回", "意", "到", "z", "从", "j", "知", "又", "内", "因", "点", "Q", "三", "定", "8", "R", "b", "正", "或", "夫", "向", "德", "听", "更", "?", "得", "告", "并", "本", "q", "过", "记", "L", "让", "打", "f", "人", "就", "者", "去", "原", "满", "体", "做", "经", "K", "走", "如", "孩", "c", "G", "给", "使", "物", "?", "最", "笑", "部", "?", "员", "等", "受", "k", "行", "一", "条", "果", "动", "光", "门", "头", "见", "往", "自", "解", "成", "处", "天", "能", "于", "名", "其", "发", "总", "母", "的", "死", "手", "入", "路", "进", "心", "来", "h", "时", "力", "多", "开", "已", "许", "d", "至", "由", "很", "界", "n", "小", "与", "Z", "想", "代", "么", "分", "生", "口", "再", "妈", "望", "次", "西", "风", "种", "带", "J", "?", "实", "情", "才", "这", "?", "E", "我", "神", "格", "长", "觉", "间", "年", "眼", "无", "不", "亲", "关", "结", "0", "友", "信", "下", "却", "重", "己", "老", "2", "音", "字", "m", "呢", "明", "之", "前", "高", "P", "B", "目", "太", "e", "9", "起", "稜", "她", "也", "W", "用", "方", "子", "英", "每", "理", "便", "四", "数", "期", "中", "C", "外", "样", "a", "海", "们", "任"
]


def decode_text(text: str) -> str:
    if not text:
        return ""
    result = []
    for char in text:
        code = ord(char)
        idx = code - START_CODE
        if 0 <= idx < len(CHAR_SEQUENCE):
            result.append(CHAR_SEQUENCE[idx])
        else:
            result.append(char)
    return "".join(result)


EXTRACT_JS = """
() => {
    const bookMap = new Map();
    const links = document.querySelectorAll('a[href^="/page/"]');
    links.forEach(link => {
        let container = link.parentElement;
        let depth = 0;
        while (container && depth < 6) {
            if (container.querySelector('img') && container.innerText.includes('在读')) {
                const href = link.getAttribute('href');
                if (!bookMap.has(href)) {
                    bookMap.set(href, container);
                }
                break;
            }
            container = container.parentElement;
            depth++;
        }
    });

    const cards = Array.from(bookMap.values());
    const results = [];
    for (const item of cards) {
        let imgNode = item.querySelector('img');
        let cover = imgNode ? imgNode.getAttribute('src') : "";

        let title = "";
        if (imgNode && imgNode.getAttribute('alt')) {
            title = imgNode.getAttribute('alt').trim();
        }
        if (!title) {
            let textTitleNode = item.querySelector('h4, .title, h1') || item.querySelector('a[href^="/page/"]');
            if (textTitleNode) {
                let text = textTitleNode.innerText.trim();
                if (text && !/^\\d+$/.test(text)) {
                    title = text;
                }
            }
        }
        if (!title) title = "未知";
        if (title.includes("榜单说明")) continue;

        let authorNode = item.querySelector('.author, .author-name') || item.querySelector('a[href^="/author-page/"]');
        let author = authorNode ? authorNode.innerText.trim() : "未知";

        let reads = "未知";
        const lines = item.innerText.split('\\n');
        for (let line of lines) {
            if (line.includes('在读')) {
                reads = line;
                break;
            }
        }

        let introNode = item.querySelector('.intro, .abstract, .desc');
        let intro = introNode ? introNode.innerText.trim() : "暂无简介";

        results.push({
            title: title,
            author: author,
            reads: reads,
            intro: intro,
            cover: cover,
            url: item.querySelector('a[href^="/page/"]').getAttribute('href')
        });
    }
    return results;
}
"""


def clean_reads(raw: str) -> str:
    r_raw = decode_text(raw)
    if "在读" in r_raw:
        parts = r_raw.split("在读")
        if len(parts) > 1:
            return parts[1].replace(":", "").replace("：", "").strip()
    return r_raw


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: str, payload: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def scrape_one_board(page, board_cfg: dict, limit: int = 30, sleep_sec: float = 5):
    channel = board_cfg["channel"]
    board = board_cfg["board"]
    label = board_cfg["label"]
    date_str = datetime.now().strftime("%Y%m%d")
    date_dash = datetime.now().strftime("%Y-%m-%d")
    output_file = snapshot_path(channel, board, date_str)
    state_file = task_state_path(channel, board, date_str)
    prefix = rank_prefix(board_cfg["gender"], board_cfg["rank_type"])

    state = load_json(state_file, {"completed": []})
    completed_cats = state.get("completed", [])
    existing = load_json(output_file, {})
    all_categories = existing.get("categories", []) if completed_cats else []
    # 避免重复追加同名分类
    done_names = {c.get("name") for c in all_categories}

    entry = init_url(board_cfg)
    print(f"\n===== {label} ({channel}/{board}) =====")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 入口: {entry}")
    page.goto(entry, wait_until="load", timeout=15000)
    page.wait_for_selector('a[href^="/page/"]', timeout=8000)

    categories_js = f"""
    () => {{
        return Array.from(document.querySelectorAll('a'))
            .filter(a => a.href.includes('{prefix}'))
            .map(a => ({{
                name: a.innerText.trim(),
                href: a.getAttribute('href')
            }}))
            .filter(item => item.name && item.href);
    }}
    """
    categories = page.evaluate(categories_js)
    # 去重，保持顺序
    seen = set()
    uniq = []
    for cat in categories:
        key = cat["name"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(cat)
    categories = uniq
    print(f"✅ 提取到 {len(categories)} 个分类")

    for cat in categories:
        cat_name = cat["name"]
        cat_href = cat["href"]

        if cat_name in completed_cats or cat_name in done_names:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️ 跳过已完成: {cat_name}")
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 切换分类 -> {cat_name}")
        try:
            page.locator(f"a[href='{cat_href}']").first.click()
            time.sleep(2)
            page.wait_for_selector('a[href^="/page/"]', timeout=8000)
        except Exception as e:
            print(f"切换分类失败 {cat_name}: {e}")

        for _ in range(3):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(1.5)

        try:
            books_data = page.evaluate(EXTRACT_JS)
        except Exception as e:
            print(f"抽取失败 {cat_name}: {e}")
            books_data = []

        category_books = []
        for b in books_data[:limit]:
            category_books.append({
                "title": decode_text(b.get("title", "")),
                "author": decode_text(b.get("author", "")),
                "reads": clean_reads(b.get("reads", "")),
                "intro": decode_text(b.get("intro", "")).replace("\\n", " "),
                "cover": b.get("cover", ""),
                "url": "https://fanqienovel.com" + (b.get("url") or ""),
            })

        all_categories.append({"name": cat_name, "books": category_books})
        done_names.add(cat_name)

        snapshot = {
            "channel": channel,
            "board": board,
            "label": label,
            "date": date_dash,
            "categories": all_categories,
        }
        write_json(output_file, snapshot)

        completed_cats.append(cat_name)
        write_json(state_file, {"completed": completed_cats, "channel": channel, "board": board})
        print(f"成功 {cat_name}: {len(category_books)} 本，已存档。等待 {sleep_sec}s")
        time.sleep(sleep_sec)

    print(f"✅ {label} 完成: {output_file}")
    return output_file


def run_scraper(targets=None, limit=30, sleep_sec=5):
    targets = targets or [(b["channel"], b["board"]) for b in BOARDS]
    with sync_playwright() as p:
        if os.environ.get("GITHUB_ACTIONS"):
            browser = p.chromium.launch(headless=True)
        else:
            browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        for channel, board in targets:
            cfg = find_board(channel, board)
            if not cfg:
                print(f"⚠️ 跳过未知切片 {channel}/{board}")
                continue
            try:
                scrape_one_board(page, cfg, limit=limit, sleep_sec=sleep_sec)
            except Exception as e:
                print(f"❌ {cfg['label']} 失败: {e}")
        browser.close()
    print("\n✅ 全部选定榜单抓取流程结束")


def main():
    parser = argparse.ArgumentParser(description="番茄小说四榜爬虫")
    parser.add_argument("--channel", default="", help="female / male，空=全部")
    parser.add_argument("--board", default="", help="new / read，空=全部")
    parser.add_argument("--limit", type=int, default=30, help="每分类 Top N")
    parser.add_argument("--sleep", type=float, default=5, help="分类间隔秒")
    args = parser.parse_args()

    targets = parse_board_args(args.channel, args.board)
    print("开始抓取切片:", ", ".join(f"{c}/{b}" for c, b in targets))
    run_scraper(targets=targets, limit=args.limit, sleep_sec=args.sleep)


if __name__ == "__main__":
    main()
