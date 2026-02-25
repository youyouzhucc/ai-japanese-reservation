"""餐厅搜索服务：支持 OpenStreetMap(免费)、Google Places API、Mock 数据"""
from __future__ import annotations

import re
from typing import Any

# Mock 数据：无 API 时的兜底
MOCK_RESTAURANTS = [
    {"name": "銀座 すし 太郎", "phone": "+81-3-1234-5678", "address": "東京都中央区銀座1-2-3"},
    {"name": "築地 寿司 大", "phone": "+81-3-3547-6797", "address": "東京都中央区築地4-5-6"},
    {"name": "磯丸水産 新宿店", "phone": "+81-3-3352-1234", "address": "東京都新宿区西新宿7-8-9"},
    {"name": "一蘭 渋谷店", "phone": "+81-3-3463-3667", "address": "東京都渋谷区神南1-22-7"},
    {"name": "とんかつ まい泉", "phone": "+81-3-3478-0551", "address": "東京都渋谷区神宮前4-8-5"},
    {"name": "天丼 てんや", "phone": "+81-3-1234-5670", "address": "東京都港区六本木1-2-3"},
    {"name": "牛かつ もと村", "phone": "+81-3-3344-5566", "address": "東京都新宿区新宿3-22-7"},
    {"name": "うどん 丸亀製麺", "phone": "+81-3-1234-5671", "address": "東京都千代田区丸の内2-4-1"},
    {"name": "ラーメン 一風堂", "phone": "+81-3-5772-1010", "address": "東京都港区赤坂5-3-1"},
    {"name": "焼肉 叙々苑", "phone": "+81-3-3583-1234", "address": "東京都港区六本木6-10-1"},
]


async def search_restaurants(query: str, api_key: str | None = None) -> list[dict[str, Any]]:
    """
    搜索餐厅，返回 [{name, phone, address}, ...]
    - 有 api_key 时使用 Google Places API
    - 否则使用 OpenStreetMap Overpass API（免费，无需 Key）
    - OSM 无结果时回退到 mock
    """
    query = (query or "").strip()
    if not query:
        return []

    if api_key:
        return await _search_google_places(query, api_key)
    results = await _search_osm(query)
    return results if results else _search_mock(query)


async def _search_osm(query: str) -> list[dict[str, Any]]:
    """OpenStreetMap Overpass API - 完全免费，无需 API Key。电话覆盖率取决于 OSM 数据"""
    import httpx

    # 转义正则特殊字符，支持按名称搜索
    safe = re.escape(query[:50])  # 限制长度
    overpass_url = "https://overpass-api.de/api/interpreter"
    # 日本范围 bbox (south, west, north, east)，扩展以覆盖主要城市
    bbox = "(24.0,122.0,46.0,154.0)"
    body = f"""
[out:json][timeout:15];
(
  node["amenity"~"restaurant|cafe|fast_food"]{bbox}["name"~"{safe}",i];
  way["amenity"~"restaurant|cafe|fast_food"]{bbox}["name"~"{safe}",i];
);
out body;
"""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(overpass_url, content=body)
            data = resp.json()
    except Exception:
        return []

    elements = data.get("elements", [])
    results = []
    seen = set()
    for el in elements[:12]:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:phone_1") or ""
        addr_parts = [
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
            tags.get("addr:city") or tags.get("addr:town"),
            tags.get("addr:country"),
        ]
        address = " ".join(p for p in addr_parts if p) or tags.get("addr:full", "")
        results.append({"name": name, "phone": phone, "address": address})
    return results[:8]


def _search_mock(query: str) -> list[dict[str, Any]]:
    """Mock 搜索：按名称关键词过滤"""
    q = query.lower()
    results = []
    for r in MOCK_RESTAURANTS:
        if q in r["name"].lower() or q in (r.get("address") or "").lower():
            results.append({
                "name": r["name"],
                "phone": r.get("phone") or "",
                "address": r.get("address") or "",
            })
    return results[:8]  # 最多返回 8 条


async def _search_google_places(query: str, api_key: str) -> list[dict[str, Any]]:
    """Google Places API 搜索（需启用 Places API）"""
    import httpx

    # Text Search 获取 place_id 列表
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{query} 日本 餐厅", "key": api_key, "language": "zh-CN"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if data.get("status") != "OK":
        return []

    places = data.get("results", [])[:5]
    results = []
    for p in places:
        place_id = p.get("place_id")
        name = p.get("name", "")
        address = p.get("formatted_address", "")
        phone = ""

        if place_id:
            # Place Details 获取电话
            detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
            detail_params = {
                "place_id": place_id,
                "fields": "formatted_phone_number,international_phone_number",
                "key": api_key,
            }
            async with httpx.AsyncClient(timeout=10) as client:
                dr = await client.get(detail_url, params=detail_params)
                dd = dr.json()
            if dd.get("status") == "OK":
                detail = dd.get("result", {})
                phone = detail.get("international_phone_number") or detail.get("formatted_phone_number", "")

        results.append({"name": name, "phone": phone, "address": address})
    return results
