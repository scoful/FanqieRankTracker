# -*- coding: utf-8 -*-
"""四榜切片配置：channel × board。"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

# (channel, board) 主键
BOARDS: List[dict] = [
    {
        "channel": "female",
        "board": "new",
        "gender": "0",
        "rank_type": "1",
        "init_category_id": "1139",
        "label": "女频新书榜",
    },
    {
        "channel": "female",
        "board": "read",
        "gender": "0",
        "rank_type": "2",
        "init_category_id": "1139",
        "label": "女频阅读榜",
    },
    {
        "channel": "male",
        "board": "new",
        "gender": "1",
        "rank_type": "1",
        "init_category_id": "1141",
        "label": "男频新书榜",
    },
    {
        "channel": "male",
        "board": "read",
        "gender": "1",
        "rank_type": "2",
        "init_category_id": "1141",
        "label": "男频阅读榜",
    },
]

FEMALE_GENRE_GROUPS = [
    {"name": "古风言情", "categories": ["古风世情", "古言脑洞", "宫斗宅斗", "种田"]},
    {"name": "现代言情", "categories": ["现言脑洞", "豪门总裁", "职场婚恋", "青春甜宠"]},
    {"name": "幻想言情", "categories": ["玄幻言情", "科幻末世", "悬疑脑洞", "女频悬疑"]},
    {"name": "快穿衍生", "categories": ["快穿", "女频衍生"]},
    {"name": "年代民国", "categories": ["年代", "民国言情"]},
    {"name": "娱乐星光", "categories": ["星光璀璨"]},
    {"name": "游戏体育", "categories": ["游戏体育"]},
]

MALE_GENRE_GROUPS = [
    {"name": "都市脑洞", "categories": ["都市日常", "都市脑洞", "都市种田", "都市修真", "都市高武"]},
    {"name": "玄幻仙侠", "categories": ["传统玄幻", "玄幻脑洞", "东方仙侠", "西方奇幻"]},
    {"name": "历史军事", "categories": ["历史古代", "历史脑洞", "抗战谍战"]},
    {"name": "战神赘婿", "categories": ["战神赘婿"]},
    {"name": "科幻末世", "categories": ["科幻末世"]},
    {"name": "悬疑灵异", "categories": ["悬疑灵异", "悬疑脑洞"]},
    {"name": "游戏衍生", "categories": ["游戏体育", "动漫衍生", "男频衍生"]},
]

FEMALE_MARKET_KEYWORDS = [
    "重生", "穿书", "快穿", "系统", "空间", "团宠", "萌宝", "幼崽", "女配", "炮灰",
    "反派", "权臣", "宅斗", "宫斗", "和离", "替嫁", "逃荒", "种田", "美食", "经商",
    "年代", "七零", "八零", "军婚", "豪门", "总裁", "真假千金", "先婚后爱", "追妻",
    "甜宠", "双洁", "强制爱", "无CP", "末世", "废土", "天灾", "囤货", "异能",
    "国运", "星际", "修仙", "玄学", "无限流", "悬疑", "直播", "综艺", "娱乐圈",
    "校园", "暗恋", "青梅竹马", "民国", "兽世", "远古", "基建",
]

MALE_MARKET_KEYWORDS = [
    "重生", "穿越", "系统", "签到", "无敌", "退婚", "赘婿", "战神", "兵王", "神医",
    "国运", "基建", "科技", "末日", "末世", "囤货", "异能", "修仙", "玄幻", "仙侠",
    "高武", "都市", "脑洞", "直播", "游戏", "电竞", "无限流", "诸天", "万界", "穿越",
    "历史", "争霸", "权谋", "谍战", "抗战", "灵异", "悬疑", "犯罪", "种田", "经营",
    "多女主", "后宫", "无女主", "爽文", "打脸", "装逼", "升级", "练功", "功法",
]


def board_key(channel: str, board: str) -> str:
    return f"{channel}/{board}"


def find_board(channel: str, board: str) -> Optional[dict]:
    for item in BOARDS:
        if item["channel"] == channel and item["board"] == board:
            return item
    return None


def rank_prefix(gender: str, rank_type: str) -> str:
    return f"/rank/{gender}_{rank_type}_"


def init_url(board_cfg: dict) -> str:
    return (
        f"https://fanqienovel.com/rank/"
        f"{board_cfg['gender']}_{board_cfg['rank_type']}_{board_cfg['init_category_id']}"
    )


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def snapshot_dir(channel: str, board: str, root: Optional[str] = None) -> str:
    base = root or repo_root()
    return os.path.join(base, "data", channel, board)


def snapshot_path(channel: str, board: str, date_compact: str, root: Optional[str] = None) -> str:
    return os.path.join(snapshot_dir(channel, board, root), f"{date_compact}.json")


def task_state_path(channel: str, board: str, date_compact: str, root: Optional[str] = None) -> str:
    return os.path.join(snapshot_dir(channel, board, root), f"task_state_{date_compact}.json")


def trends_dir(channel: str, board: str, root: Optional[str] = None) -> str:
    base = root or repo_root()
    return os.path.join(base, "data", "trends", channel, board)


def trend_path(channel: str, board: str, date_dash: str, root: Optional[str] = None) -> str:
    return os.path.join(trends_dir(channel, board, root), f"{date_dash}.json")


def latest_path(channel: str, board: str, root: Optional[str] = None) -> str:
    base = root or repo_root()
    return os.path.join(base, "data", "latest", channel, board + ".json")


def market_path(channel: str, board: str, root: Optional[str] = None) -> str:
    base = root or repo_root()
    return os.path.join(base, "data", "market", channel, board + ".json")


def dates_path(channel: str, board: str, root: Optional[str] = None) -> str:
    base = root or repo_root()
    return os.path.join(base, "data", "dates", channel, board + ".json")


def api_board_dir(channel: str, board: str, root: Optional[str] = None) -> str:
    base = root or repo_root()
    return os.path.join(base, "api", channel, board)


def genre_groups_for(channel: str) -> List[dict]:
    return FEMALE_GENRE_GROUPS if channel == "female" else MALE_GENRE_GROUPS


def market_keywords_for(channel: str) -> List[str]:
    return FEMALE_MARKET_KEYWORDS if channel == "female" else MALE_MARKET_KEYWORDS


def board_label(channel: str, board: str) -> str:
    cfg = find_board(channel, board)
    return cfg["label"] if cfg else f"{channel}/{board}"


def parse_board_args(channel: str = "", board: str = "") -> List[Tuple[str, str]]:
    """解析 CLI 的 channel/board；空则返回全部四榜。"""
    if channel and board:
        if not find_board(channel, board):
            raise ValueError(f"未知切片: {channel}/{board}")
        return [(channel, board)]
    if channel and not board:
        items = [(b["channel"], b["board"]) for b in BOARDS if b["channel"] == channel]
        if not items:
            raise ValueError(f"未知频道: {channel}")
        return items
    if board and not channel:
        items = [(b["channel"], b["board"]) for b in BOARDS if b["board"] == board]
        if not items:
            raise ValueError(f"未知榜种: {board}")
        return items
    return [(b["channel"], b["board"]) for b in BOARDS]


def compact_to_dash(date_compact: str) -> str:
    return f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"


def dash_to_compact(date_dash: str) -> str:
    return date_dash.replace("-", "")
