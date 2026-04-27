import json
import math
import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app import templates

router = APIRouter()


@router.get("/")
async def root_redirect():
    return RedirectResponse(url="/traffic-map")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _parse_age_tags(profile: dict) -> list[str]:
    """Parse investor profile age range into filter tags."""
    age_str = profile.get("age", "") if profile else ""
    if not age_str or "全年龄" in age_str:
        return ["young", "middle", "senior"]

    nums = [int(x) for x in re.findall(r'\d+', age_str)]
    if not nums:
        return ["young", "middle", "senior"]

    min_age = min(nums)
    max_age = max(nums)

    tags = []
    if min_age < 35:
        tags.append("young")
    if max_age > 35:
        tags.append("middle")
    if max_age > 55:
        tags.append("senior")

    return tags or ["young", "middle", "senior"]


def _parse_trading_tags(profile: dict) -> list[str]:
    """Parse investor profile trading into filter tags."""
    trading = profile.get("trading", "") if profile else ""
    if not trading:
        return []
    if "全品类" in trading:
        return ["hk_stock", "us_stock", "crypto", "fund_etf", "forex_deriv"]

    tags = []
    if "港股" in trading or "港美" in trading:
        tags.append("hk_stock")
    if "美股" in trading or "港美" in trading:
        tags.append("us_stock")
    if "加密" in trading or "crypto" in trading.lower():
        tags.append("crypto")
    if any(k in trading for k in ["基金", "ETF", "定投"]):
        tags.append("fund_etf")
    if any(k in trading for k in ["外汇", "期权", "期货", "窝轮", "牛熊", "量化"]):
        tags.append("forex_deriv")

    return tags


def _generate_insights(all_channels: list) -> list:
    """Generate actionable insights from channel coverage data.

    IMPORTANT: all_channels mixes two different metrics:
    - Social platforms: hk_total_users (unique users, from DataReportal ads audience)
    - Other channels: hk_monthly_visits (page sessions, from SimilarWeb/Semrush)
    These CANNOT be summed — one person visits many platforms and generates
    multiple sessions. HK has ~7.4M people, ~2.5M investors total.
    """
    HK_INVESTORS = 2_500_000  # SFC/HKMA 2024 estimate

    insights = []

    # Separate channels with traffic data vs without
    with_traffic = [ch for ch in all_channels if ch["users"] > 0]
    n_total = len(all_channels)
    n_with = len(with_traffic)

    # Coverage distribution
    low_cov = [ch for ch in with_traffic if ch["futu_coverage_pct"] <= 5]
    mid_cov = [ch for ch in with_traffic if 5 < ch["futu_coverage_pct"] <= 15]
    high_cov = [ch for ch in with_traffic if ch["futu_coverage_pct"] > 15]

    # Median coverage
    sorted_pcts = sorted(ch["futu_coverage_pct"] for ch in with_traffic)
    median_pct = sorted_pcts[len(sorted_pcts) // 2] if sorted_pcts else 0

    insights.append({
        "type": "summary",
        "title": f"内容占比中位数: {median_pct}%  |  {n_total} 个渠道",
        "body": (
            f"香港约 250 万投资者分布在 {n_total} 个线上渠道中。"
            f"富途在 {len(low_cov)} 个渠道营销内容占比 ≤5%（薄弱），"
            f"{len(mid_cov)} 个在 5-15%（中等），"
            f"{len(high_cov)} 个 >15%（已有优势）。"
            f"各渠道投资者人数为去重估算（平台用户 × 投资者渗透率），同一投资者平均使用 3-5 个渠道，不可跨渠道求和。"
        ),
        "color": "indigo",
    })

    # Top coverage gaps: high traffic + low coverage
    gaps = [ch for ch in with_traffic if ch["futu_coverage_pct"] <= 5 and ch["users"] >= 1000000]
    gaps.sort(key=lambda x: x["users"], reverse=True)
    if gaps:
        def _fmt_traffic(ch):
            u = ch["users"]
            label = f"{u // 10000}万" if u >= 10000 else f"{u:,}"
            return f"{ch['display_name']}（{label}/月, 内容占比{ch['futu_coverage_pct']}%）"
        insights.append({
            "type": "gap",
            "title": f"高流量低覆盖 — {len(gaps)} 个蓝海渠道",
            "body": "以下渠道月流量均超百万但富途内容占比 ≤5%，是最大的增量空间：",
            "details": [_fmt_traffic(ch) for ch in gaps[:6]],
            "color": "red",
        })

    # Quick wins: high relevance but low coverage
    quick_wins = []
    for ch in with_traffic:
        rel = ch.get("futu_relevance", "")
        if "极高" in rel and ch["futu_coverage_pct"] <= 10:
            quick_wins.append(ch)
    if quick_wins:
        insights.append({
            "type": "quickwin",
            "title": f"高相关度低覆盖 — {len(quick_wins)} 个快速突破点",
            "body": "与富途业务高度相关但覆盖不足，投入产出比最高的渠道：",
            "details": [
                f"{ch['display_name']}（内容占比{ch['futu_coverage_pct']}%）"
                for ch in quick_wins[:5]
            ],
            "color": "amber",
        })

    # Category coverage analysis (use count-based average, not traffic-weighted)
    cat_stats = {}
    for ch in with_traffic:
        cat = ch["type_zh"]
        if cat not in cat_stats:
            cat_stats[cat] = {"pcts": [], "count": 0}
        cat_stats[cat]["pcts"].append(ch["futu_coverage_pct"])
        cat_stats[cat]["count"] += 1
    weakest = []
    for cat, s in cat_stats.items():
        avg = round(sum(s["pcts"]) / len(s["pcts"]), 1)
        weakest.append({"name": cat, "pct": avg, "count": s["count"]})
    weakest.sort(key=lambda x: x["pct"])
    low_cats = [c for c in weakest if c["pct"] < 8][:4]
    if low_cats:
        insights.append({
            "type": "category",
            "title": "覆盖最薄弱的渠道类型",
            "body": "以下类型渠道富途内容占比最低，建议优先制定策略：",
            "details": [
                f"{c['name']}：平均 {c['pct']}%（{c['count']} 个渠道）"
                for c in low_cats
            ],
            "color": "orange",
        })

    # Strengths — top covered channels
    top_covered = sorted(with_traffic, key=lambda x: x["futu_coverage_pct"], reverse=True)[:5]
    if top_covered:
        insights.append({
            "type": "strength",
            "title": "富途已有优势的阵地",
            "body": "这些渠道富途内容占比领先，建议巩固优势、提升转化效率：",
            "details": [
                f"{ch['display_name']}（内容占比{ch['futu_coverage_pct']}%）"
                for ch in top_covered
            ],
            "color": "emerald",
        })

    return insights


def _load_market_data() -> dict:
    p = DATA_DIR / "platform_market_data.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"platforms": [], "other_channels": []}


@router.get("/traffic-map")
async def traffic_map(request: Request):
    data = _load_market_data()
    platforms = data.get("platforms", [])
    other_channels = data.get("other_channels", [])
    methodology = data.get("methodology", {})
    updated_at = data.get("updated_at", "")
    investor_behavior = data.get("investor_behavior", {})
    analysis_frameworks = data.get("analysis_frameworks", {})
    futu_hk_stats = data.get("futu_hk_stats", {})
    arpu_analysis = data.get("arpu_analysis", {})
    conversion_analysis = data.get("conversion_analysis", {})
    new_investor_analysis = data.get("new_investor_analysis", {})
    ai_acquisition = data.get("ai_acquisition", {})
    acquisition_plan = data.get("acquisition_plan", {})
    investor_motivations = data.get("investor_motivations", {})
    wealth_panorama = data.get("wealth_panorama", {})
    competitor_landscape = data.get("competitor_landscape", {})
    user_overlap = data.get("user_overlap", {})
    broker_overlap_st = data.get("broker_overlap_st", {})
    social_finance_overlap = data.get("social_finance_overlap", {})
    tab_insights = data.get("tab_insights", {})
    incremental_channel_matrix = data.get("incremental_channel_matrix", {})
    channel_strategy = data.get("channel_strategy", {})
    executive_summary = data.get("executive_summary", [])
    offline_district_analysis = data.get("offline_district_analysis", {})
    data_date_range = data.get("data_date_range", "")
    data_date_detail = data.get("data_date_detail", "")

    # Build waterfall data: merge platform/channel total users with scatter conversion data
    waterfall_data = []
    scatter_map = {ch["name"]: ch for ch in conversion_analysis.get("full_scatter", [])}
    # Map display_name -> platform total users
    plat_users = {p["display_name"]: p.get("hk_total_users", 0) for p in platforms}
    chan_users = {}
    for ch in other_channels:
        raw = ch.get("hk_monthly_visits") or ch.get("hk_monthly_users") or 0
        chan_users[ch["display_name"]] = raw
    # Name mapping from scatter names to display names
    name_map = {
        "WhatsApp 群组": "WhatsApp", "Google 搜索(HK)": "Google 搜索(HK)",
        "YouTube": "YouTube", "Facebook": "Facebook", "Instagram": "Instagram",
        "TikTok": "TikTok", "Threads": "Threads", "Bilibili": "Bilibili",
        "LinkedIn": "LinkedIn", "X / Twitter": "X / Twitter",
        "小红书": "小红书", "微博": "微博",
    }
    for sc in conversion_analysis.get("full_scatter", []):
        display = name_map.get(sc["name"], sc["name"])
        total = plat_users.get(display, 0) or chan_users.get(display, 0)
        if total == 0:
            total = sc.get("investors", 0)  # fallback
        investors = sc.get("investors", 0)
        futu_clients = sc.get("futu_clients", 0)
        remaining = sc.get("remaining_convertible", 0)
        convertible = sc.get("est_actual_converts", 0)
        rate_label = sc.get("est_conversion_label", "")
        if investors > 0:
            waterfall_data.append({
                "name": sc["name"],
                "total_users": total,
                "investors": investors,
                "futu_clients": futu_clients,
                "remaining": remaining,
                "convertible": convertible,
                "rate_label": rate_label,
                "conversion_note": sc.get("conversion_note", ""),
            })
    waterfall_data.sort(key=lambda x: x["convertible"], reverse=True)

    # Add jitter to scatter points that share the same (execution, conversion) position
    full_scatter = conversion_analysis.get("full_scatter", [])
    if full_scatter:
        # Group by (execution, conversion)
        pos_groups: dict[tuple, list] = {}
        for ch in full_scatter:
            key = (ch.get("execution", 5), ch.get("conversion", 5))
            pos_groups.setdefault(key, []).append(ch)
        # Apply circular jitter to clusters of 2+
        for (ex, cv), group in pos_groups.items():
            if len(group) == 1:
                group[0]["x_jitter"] = 0
                group[0]["y_jitter"] = 0
            else:
                n = len(group)
                # Sort by est_actual_converts desc so biggest is in center-ish
                group.sort(key=lambda c: c.get("est_actual_converts", 0), reverse=True)
                radius = min(0.6 + n * 0.08, 1.2)  # scale with cluster size
                for i, ch in enumerate(group):
                    angle = 2 * math.pi * i / n
                    ch["x_jitter"] = round(radius * math.cos(angle), 2)
                    ch["y_jitter"] = round(radius * math.sin(angle), 2)

    # Add filter tags
    for p in platforms:
        profile = p.get("hk_investor_profile", {})
        p["age_tags"] = _parse_age_tags(profile)
        p["trading_tags"] = _parse_trading_tags(profile)
    for ch in other_channels:
        profile = ch.get("hk_investor_profile", {})
        ch["age_tags"] = _parse_age_tags(profile)
        ch["trading_tags"] = _parse_trading_tags(profile)

    # Group other_channels by category
    channel_groups = {}
    for ch in other_channels:
        cat = ch.get("category_zh", "其他")
        if cat not in channel_groups:
            channel_groups[cat] = []
        channel_groups[cat].append(ch)

    # Build unified list — use hk_unique_investors as primary ranking metric
    all_channels = []
    for p in platforms:
        all_channels.append({
            "name": p["name"],
            "display_name": p["display_name"],
            "type": "social",
            "type_zh": "社媒平台",
            "users": p.get("hk_unique_investors", 0),
            "users_note": p.get("hk_unique_investors_note", ""),
            "raw_traffic": p.get("hk_total_users", 0),
            "raw_traffic_label": "MAU",
            "finance_users": p.get("hk_finance_users", 0),
            "profile": p.get("hk_investor_profile", {}),
            "futu_coverage_pct": p.get("futu_in_finance_pct", 0),
            "futu_in_broker_pct": p.get("futu_in_broker_pct", 0),
            "growth_trend": p.get("growth_trend", "stable"),
            "coverage_note": p.get("futu_in_finance_note", ""),
            "age_tags": p["age_tags"],
            "trading_tags": p["trading_tags"],
            "journey_stages": p.get("journey_stages", []),
            "futu_investment": p.get("futu_investment", "none"),
        })
    for ch in other_channels:
        raw = ch.get("hk_monthly_visits") or ch.get("hk_monthly_users") or 0
        all_channels.append({
            "name": ch["name"],
            "display_name": ch["display_name"],
            "type": ch.get("category", "other"),
            "type_zh": ch.get("category_zh", "其他"),
            "users": ch.get("hk_unique_investors", 0),
            "users_note": ch.get("hk_unique_investors_note", ""),
            "raw_traffic": raw,
            "raw_traffic_label": "visits" if ch.get("hk_monthly_visits") else "MAU",
            "finance_users": raw,
            "profile": ch.get("hk_investor_profile", {}),
            "futu_coverage_pct": ch.get("futu_coverage_pct", 0),
            "futu_relevance": ch.get("futu_relevance", ""),
            "acquisition_method": ch.get("acquisition_method", ""),
            "coverage_note": ch.get("futu_coverage_note", ""),
            "age_tags": ch["age_tags"],
            "trading_tags": ch["trading_tags"],
            "journey_stages": ch.get("journey_stages", []),
            "futu_investment": ch.get("futu_investment", "none"),
        })

    # Sort by users descending
    all_channels.sort(key=lambda x: x["users"], reverse=True)
    max_users = all_channels[0]["users"] if all_channels else 1

    # Compute priority scores — 6-factor model:
    # traffic × gap × relevance × threat × incremental × journey × investment
    rel_weights = {"极高": 1.0, "高": 0.7, "中高": 0.5, "中": 0.3, "中(竞品)": 0.1, "低": 0.1}
    inv_discount = {"high": 0.2, "medium": 0.5, "low": 0.8, "none": 1.0}
    inv_labels = {"high": "已重点投入", "medium": "有一定投入", "low": "少量投入", "none": "未投入"}

    # Collect all display names for fuzzy matching in lookups
    all_display_names = [ch["display_name"] for ch in all_channels]

    # Build competitive threat lookup: channel display_name → threat multiplier
    # Uses IBKR + Webull MoM from social_finance_overlap (positive MoM = growing threat)
    overlap_platforms = social_finance_overlap.get("platforms", [])
    threat_raw = {}  # overlap platform name → threat value
    for op in overlap_platforms:
        ibkr_mom = op.get("ibkr_mom") or 0
        webull_mom = op.get("webull_mom") or 0
        raw_threat = max(ibkr_mom, 0) + max(webull_mom, 0)
        threat_raw[op["platform"]] = round(1.0 + min(raw_threat / 3.0, 1.0), 2)
    # Match overlap names to channel display_names (prefix/contains matching)
    threat_lookup = {}
    for olap_name, val in threat_raw.items():
        for dn in all_display_names:
            if olap_name == dn or dn.startswith(olap_name) or olap_name in dn:
                threat_lookup[dn] = val
    # Handle WeChat → 微信 special case
    if "WeChat" in threat_raw:
        for dn in all_display_names:
            if "微信" in dn:
                threat_lookup[dn] = threat_raw["WeChat"]
    if "X/Twitter" in threat_raw:
        for dn in all_display_names:
            if "X /" in dn or "Twitter" in dn:
                threat_lookup[dn] = threat_raw["X/Twitter"]

    # Build incremental density lookup: channel → weighted avg density (0-5)
    # Weight each source by its pct contribution (来港人才52%, 年轻首投14%, etc.)
    inc_sources = incremental_channel_matrix.get("sources", [])
    inc_raw = {}  # short channel name → weighted density
    total_pct = sum(s.get("pct", 0) for s in inc_sources) or 100
    for source in inc_sources:
        src_weight = source.get("pct", 0) / total_pct
        for ch_data in source.get("channels", []):
            ch_name = ch_data["channel"]
            density = ch_data.get("density", 0) * src_weight
            inc_raw[ch_name] = inc_raw.get(ch_name, 0) + density
    # Match short names to display_names and normalize to multiplier
    inc_density_lookup = {}
    for inc_name, raw in inc_raw.items():
        multiplier = round(0.5 + raw * 0.3, 2)  # 0→0.5, 5→2.0
        for dn in all_display_names:
            if inc_name == dn or dn.startswith(inc_name) or inc_name in dn:
                inc_density_lookup[dn] = multiplier
    # Special mappings
    if "微信" in inc_raw:
        for dn in all_display_names:
            if "微信" in dn:
                inc_density_lookup[dn] = round(0.5 + inc_raw["微信"] * 0.3, 2)
    if "Google搜索" in inc_raw:
        for dn in all_display_names:
            if "Google" in dn:
                inc_density_lookup[dn] = round(0.5 + inc_raw["Google搜索"] * 0.3, 2)
    if "X/Twitter" in inc_raw:
        for dn in all_display_names:
            if "X /" in dn or "Twitter" in dn:
                inc_density_lookup[dn] = round(0.5 + inc_raw["X/Twitter"] * 0.3, 2)

    # Build journey stage verdict lookup
    journey_stages = analysis_frameworks.get("user_journey", {}).get("stages", [])
    verdict_weights = {"danger": 1.5, "warning": 1.2, "strong": 1.0}
    stage_verdict = {}
    for stage in journey_stages:
        stage_verdict[stage["id"]] = verdict_weights.get(stage.get("verdict", ""), 1.0)

    for ch in all_channels:
        rel = ch.get("futu_relevance", "")
        rel_w = 0.3
        for key, w in rel_weights.items():
            if key in rel:
                rel_w = w
                break
        gap = 100 - ch["futu_coverage_pct"]
        inv = ch.get("futu_investment", "none")
        inv_w = inv_discount.get(inv, 1.0)

        # Factor 1: Competitive threat (1.0-2.0×)
        threat_w = threat_lookup.get(ch["display_name"], 1.0)

        # Factor 2: Incremental investor density (0.5-2.0×)
        inc_w = inc_density_lookup.get(ch["display_name"], 0.8)

        # Factor 3: Journey stage weakness (avg verdict weight of channel's stages)
        ch_stages = ch.get("journey_stages", [])
        if ch_stages:
            journey_w = round(sum(stage_verdict.get(s, 1.0) for s in ch_stages) / len(ch_stages), 2)
        else:
            journey_w = 1.0

        ch["priority_score"] = round(ch["users"] / 10000 * gap * rel_w * threat_w * inc_w * journey_w * inv_w)
        ch["investment_label"] = inv_labels.get(inv, "")
        # Store factor breakdown for display
        ch["priority_factors"] = {
            "threat": threat_w,
            "incremental": inc_w,
            "journey": journey_w,
            "relevance": rel_w,
            "gap": gap,
            "investment": inv_w,
        }

    # Build journey stage grouping
    stage_ids = ["awareness", "interest", "consideration", "conversion", "retention", "referral"]
    journey_map = {s: [] for s in stage_ids}
    for ch in all_channels:
        for s in ch.get("journey_stages", []):
            if s in journey_map:
                journey_map[s].append({
                    "name": ch["display_name"],
                    "users": ch["users"],
                    "coverage": ch["futu_coverage_pct"],
                })

    # Build coverage method × platform heatmap
    METHOD_CATEGORIES = [
        ("KOL/达人", ["KOL合作", "KOL种草", "KOL短视频", "KOL频道合作", "KOL公众号", "KOL投放", "KOL问答", "大V合作", "主播口播", "嘉宾访谈", "嘉宾演讲"]),
        ("付费广告", ["信息流广告", "展示广告", "Reels广告", "贴片广告", "LinkedIn Ads", "Google Ads", "SEM竞价", "SEM截流", "搜索广告", "朋友圈广告", "财经频道广告", "限时动态"]),
        ("内容/SEO", ["SEO优化", "SEO截流", "SEO合作", "SEO内容", "笔记SEO", "知识图谱", "软文植入", "原生广告", "内容赞助", "赞助内容", "赞助专栏", "品牌内容", "内容植入", "PR新闻稿", "PR报道", "财经版赞助", "赞助专区", "Markets频道赞助", "经济日历赞助"]),
        ("官方运营", ["官方频道", "官方主页", "官方账号", "官方号运营", "公众号运营", "机构号运营", "群组运营", "客户服务群"]),
        ("社区/口碑", ["口碑营销", "口碑传播", "口碑/自然讨论", "MGM裂变", "用户讨论引导", "社区赞助", "社区话题", "话题营销", "热搜话题"]),
        ("活动/联名", ["直播活动", "直播", "联名活动", "活动联名", "联名优惠", "赞助冠名", "展位参展", "现场开户", "挑战赛/话题", "品牌贴纸", "弹幕互动"]),
        ("数据/产品", ["数据合作", "Broker集成", "Bot集成", "图表工具联动", "CPA合作", "小程序引流", "企微私域", "Marketplace", "频道赞助"]),
        ("比较/开户", ["Broker评测", "产品比较页", "开户优惠专区", "开户Banner", "开户优惠", "好物推荐", "跨品类推荐", "跨品类内容", "组合赞助", "资产配置推广", "品牌差异化", "竞品监控"]),
    ]

    def _categorize_methods(methods):
        cats = {}
        for cat_name, keywords in METHOD_CATEGORIES:
            matched = [m for m in methods if m in keywords]
            if matched:
                cats[cat_name] = matched
        return cats

    # Top 20 channels by users for heatmap
    top_channels = sorted(all_channels, key=lambda x: x["users"], reverse=True)[:20]
    heatmap_categories = [cat for cat, _ in METHOD_CATEGORIES]
    heatmap_data = []
    for ch in top_channels:
        methods = []
        # Find original methods from platforms or other_channels
        for p in platforms:
            if p["name"] == ch["name"]:
                methods = p.get("coverage_methods", [])
                break
        else:
            for oc in other_channels:
                if oc["name"] == ch["name"]:
                    methods = oc.get("coverage_methods", [])
                    break
        cats = _categorize_methods(methods)
        # Value score: users / 10000 for each available category
        row = {
            "name": ch["display_name"],
            "users": ch["users"],
            "cells": {},
        }
        for cat_name in heatmap_categories:
            if cat_name in cats:
                # Score = investors(万) × method_count, capped
                score = ch["users"] / 10000 * len(cats[cat_name])
                row["cells"][cat_name] = {
                    "available": True,
                    "score": round(score),
                    "methods": cats[cat_name],
                    "count": len(cats[cat_name]),
                }
            else:
                row["cells"][cat_name] = {"available": False, "score": 0, "methods": [], "count": 0}
        heatmap_data.append(row)

    # Compute max score for color scaling
    heatmap_max = max(
        (cell["score"] for row in heatmap_data for cell in row["cells"].values() if cell["available"]),
        default=1
    )

    # Generate insights
    insights = _generate_insights(all_channels)

    return templates.TemplateResponse("traffic_map.html", {
        "request": request,
        "platforms": platforms,
        "other_channels": other_channels,
        "channel_groups": channel_groups,
        "all_channels": all_channels,
        "max_users": max_users,
        "methodology": methodology,
        "updated_at": updated_at,
        "insights": insights,
        "investor_behavior": investor_behavior,
        "analysis_frameworks": analysis_frameworks,
        "journey_map": journey_map,
        "futu_hk_stats": futu_hk_stats,
        "arpu_analysis": arpu_analysis,
        "heatmap_data": heatmap_data,
        "heatmap_categories": heatmap_categories,
        "heatmap_max": heatmap_max,
        "conversion_analysis": conversion_analysis,
        "new_investor_analysis": new_investor_analysis,
        "ai_acquisition": ai_acquisition,
        "acquisition_plan": acquisition_plan,
        "waterfall_data": waterfall_data,
        "investor_motivations": investor_motivations,
        "wealth_panorama": wealth_panorama,
        "competitor_landscape": competitor_landscape,
        "user_overlap": user_overlap,
        "broker_overlap_st": broker_overlap_st,
        "social_finance_overlap": social_finance_overlap,
        "tab_insights": tab_insights,
        "channel_strategy": channel_strategy,
        "incremental_channel_matrix": incremental_channel_matrix,
        "executive_summary": executive_summary,
        "data_date_range": data_date_range,
        "data_date_detail": data_date_detail,
        "offline_district_analysis": offline_district_analysis,
    })
