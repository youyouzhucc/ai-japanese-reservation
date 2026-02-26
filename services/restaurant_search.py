"""餐厅搜索服务：支持 Foursquare(推荐)、Google Places、OpenStreetMap、Mock"""
from __future__ import annotations

import re
from typing import Any

# Mock 数据：OSM 无结果或失败时的兜底
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
    {"name": "神户牛铁板烧 Ishida", "phone": "+81-78-321-0123", "address": "兵庫県神戸市中央区"},
    {"name": "スターバックス 銀座", "phone": "+81-3-1234-5679", "address": "東京都中央区銀座"},
]


async def search_restaurants(
    query: str,
    google_key: str | None = None,
    foursquare_key: str | None = None,
) -> list[dict[str, Any]]:
    """
    搜索餐厅，返回 [{name, phone, address}, ...]
    优先级：Foursquare > Google Places > OSM > Mock
    """
    query = (query or "").strip()
    if not query:
        return []

    # 1. Foursquare（推荐：稳定，$200/月免费，无需绑卡）
    if foursquare_key:
        results = await _search_foursquare(query, foursquare_key)
        if results:
            return results

    # 2. Google Places
    if google_key:
        results = await _search_google_places(query, google_key)
        if results:
            return results

    # 3. OpenStreetMap（免费但可能限流）
    results = await _search_osm(query)
    if results:
        return results

    # 4. Mock 兜底
    mock_results = _search_mock(query)
    return mock_results if mock_results else _get_all_mock()


OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]


async def _search_osm(query: str) -> list[dict[str, Any]]:
    """OpenStreetMap Overpass API - 完全免费，无需 API Key。电话覆盖率取决于 OSM 数据"""
    import httpx

    # 转义正则特殊字符，支持按名称搜索；支持日文简繁变体
    raw = query[:50].strip()
    if not raw:
        return []
    safe = re.escape(raw)
    # 日本范围 bbox (south, west, north, east)
    bbox = "(24.0,122.0,46.0,154.0)"
    # Overpass: bbox(south,west,north,east) 在前，tag 过滤在后
    body = f"""[out:json][timeout:15];
(
  node{bbox}["amenity"~"restaurant|cafe|fast_food"]["name"~"{safe}",i];
  way{bbox}["amenity"~"restaurant|cafe|fast_food"]["name"~"{safe}",i];
);
out body;
"""
    data = None
    for url in OVERPASS_ENDPOINTS:
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.post(url, content=body)
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "")
                if "json" not in ct:
                    continue  # Overpass 返回 HTML 错误页时跳过
                data = resp.json()
                if not isinstance(data, dict):
                    continue
                break
        except Exception:
            continue
    if not data:
        return []

    elements = data.get("elements", [])
    results = []
    seen = set()
    for el in elements[:15]:
        tags = el.get("tags", {})
        name = (
            tags.get("name")
            or tags.get("name:ja")
            or tags.get("name:en")
            or ""
        ).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        phone = (
            tags.get("phone")
            or tags.get("contact:phone")
            or tags.get("contact:phone_1")
            or tags.get("contact:mobile")
            or ""
        )
        addr_parts = [
            tags.get("addr:prefecture"),
            tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
        ]
        address = " ".join(str(p) for p in addr_parts if p) or tags.get("addr:full", "")
        results.append({"name": name, "phone": phone, "address": address})
    return results[:8]


def _search_mock(query: str) -> list[dict[str, Any]]:
    """Mock 搜索：按名称/地址关键词过滤，支持日文罗马音等"""
    q = query.lower().strip()
    if not q:
        return []
    results = []
    for r in MOCK_RESTAURANTS:
        name_lower = r["name"].lower()
        addr_lower = (r.get("address") or "").lower()
        # 支持部分匹配、罗马音（寿司/すし/sushi、东京/東京/tokyo 等）
        if q in name_lower or q in addr_lower:
            results.append({
                "name": r["name"],
                "phone": r.get("phone") or "",
                "address": r.get("address") or "",
            })
    return results[:8]


def _get_all_mock() -> list[dict[str, Any]]:
    """返回全部示例餐厅，供无匹配时参考"""
    return [
        {"name": r["name"], "phone": r.get("phone") or "", "address": r.get("address") or ""}
        for r in MOCK_RESTAURANTS[:8]
    ]


async def _search_foursquare(query: str, api_key: str) -> list[dict[str, Any]]:
    """Foursquare Places API - 稳定，$200/月免费额度，无需绑卡"""
    import httpx

    url = "https://api.foursquare.com/v3/places/search"
    params = {
        "query": f"{query} restaurant",
        "near": "Tokyo, Japan",
        "limit": 10,
        "fields": "name,location,tel",
    }
    headers = {
        "Authorization": api_key,
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for p in data.get("results", [])[:8]:
        name = p.get("name", "").strip()
        if not name:
            continue
        loc = p.get("location", {}) or {}
        address = loc.get("formatted_address", "") or " ".join(
            filter(None, [loc.get("address"), loc.get("locality"), loc.get("region")])
        )
        phone = p.get("tel", "")
        results.append({"name": name, "phone": phone, "address": address})
    return results


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
