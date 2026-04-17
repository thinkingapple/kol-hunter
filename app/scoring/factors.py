import math
import re
from datetime import datetime

# Finance-related keywords for relevance scoring
FINANCE_KEYWORDS = {
    "high": [
        "港股", "美股", "股票", "投資", "投资", "stock", "trading", "ETF",
        "IPO", "開戶", "开户", "证券", "證券", "基金", "理財", "理财",
        "wealth", "broker", "dividend", "期權", "期权", "options",
        "港股分析", "美股分析", "股市", "牛市", "熊市",
    ],
    "medium": [
        "財經", "财经", "finance", "economy", "market", "crypto", "加密貨幣",
        "加密货币", "比特幣", "比特币", "blockchain", "金融", "bank", "fintech",
        "基金經理", "投行", "量化", "quant", "forex", "外匯",
    ],
    "low": [
        "money", "business", "entrepreneurship", "創業", "创业",
        "被動收入", "passive income", "side hustle", "副業",
        "financial freedom", "財務自由",
    ],
}

REGION_SCORES = {
    "HK": 100,
    "GBA": 85,
    "TW": 60,
    "SG": 55,
    "MY": 50,
    "CN_other": 40,
    "other_asia": 30,
    "unknown": 25,
    "western": 15,
}

# Indicators for region detection
HK_INDICATORS = [
    "hong kong", "香港", "hk", "港", "中環", "旺角", "銅鑼灣",
    "尖沙咀", "九龍", "新界", "港島",
]
GBA_INDICATORS = [
    "大灣區", "大湾区", "深圳", "shenzhen", "廣州", "广州", "guangzhou",
    "珠海", "zhuhai", "澳門", "澳门", "macau", "東莞", "佛山",
]
TW_INDICATORS = ["台灣", "台湾", "taiwan", "台北", "taipei"]
SG_INDICATORS = ["singapore", "新加坡"]


def calc_reach_score(total_followers: int) -> float:
    """Score based on total audience size (0-100). Log scale."""
    if total_followers <= 0:
        return 0.0
    raw = math.log10(total_followers)
    # Map: log10(1000)=3 -> ~14, log10(10K)=4 -> ~43, log10(100K)=5 -> ~71, log10(1M)=6 -> 100
    score = (raw - 2.5) * 28.57
    return max(0.0, min(100.0, score))


def calc_engagement_score(avg_engagement_rate: float) -> float:
    """Score based on engagement rate percentage (0-100).
    Finance content typically has 1-5% engagement."""
    if avg_engagement_rate <= 0:
        return 0.0
    # 0.5% -> 10, 1% -> 20, 2% -> 40, 3% -> 60, 5% -> 100
    return max(0.0, min(100.0, avg_engagement_rate * 20))


def calc_relevance_score(bio_text: str, post_titles: list = None) -> float:
    """Score based on finance keyword matches (0-100)."""
    text = (bio_text or "").lower()
    if post_titles:
        text += " " + " ".join(t.lower() for t in post_titles)

    score = 0.0
    matched = set()
    for kw in FINANCE_KEYWORDS["high"]:
        if kw.lower() in text and kw not in matched:
            score += 12
            matched.add(kw)
    for kw in FINANCE_KEYWORDS["medium"]:
        if kw.lower() in text and kw not in matched:
            score += 6
            matched.add(kw)
    for kw in FINANCE_KEYWORDS["low"]:
        if kw.lower() in text and kw not in matched:
            score += 3
            matched.add(kw)

    return max(0.0, min(100.0, score))


def detect_region(bio_text: str, language: str = "") -> str:
    """Detect likely region from bio text and language."""
    text = (bio_text or "").lower() + " " + (language or "").lower()

    for indicator in HK_INDICATORS:
        if indicator.lower() in text:
            return "HK"
    for indicator in GBA_INDICATORS:
        if indicator.lower() in text:
            return "GBA"
    for indicator in TW_INDICATORS:
        if indicator.lower() in text:
            return "TW"
    for indicator in SG_INDICATORS:
        if indicator.lower() in text:
            return "SG"

    # Check character usage (traditional = more likely HK/TW)
    traditional_chars = len(re.findall(r'[\u4e00-\u9fff]', bio_text or ""))
    if traditional_chars > 10:
        # Rough heuristic: traditional Chinese more common in HK/TW
        has_traditional = any(c in (bio_text or "") for c in "開證會區點對號機關發實")
        if has_traditional:
            return "HK"  # Default to HK for traditional Chinese finance content

    return "unknown"


def calc_region_score(region: str) -> float:
    """Score based on geographic match (0-100)."""
    return float(REGION_SCORES.get(region, 25))


def calc_recency_score(last_post_date: datetime = None) -> float:
    """Score based on how recently active (0-100)."""
    if not last_post_date:
        return 10.0  # Unknown recency gets minimal score

    days_since = (datetime.utcnow() - last_post_date).days
    if days_since <= 7:
        return 100.0
    if days_since <= 30:
        return 80.0
    if days_since <= 90:
        return 50.0
    if days_since <= 180:
        return 20.0
    return 0.0


def calc_competitor_score(competitor_history: list = None) -> float:
    """Score based on prior broker collaborations (0-100).
    Having worked with competitors is a POSITIVE signal."""
    if not competitor_history:
        return 0.0

    count = len(competitor_history)
    if count >= 3:
        return 100.0
    if count >= 2:
        return 75.0
    if count >= 1:
        return 50.0
    return 0.0
