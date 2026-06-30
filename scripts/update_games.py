#!/usr/bin/env python3
import html
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

SEARCH = "https://store.steampowered.com/search/results/"
TAGS_URL = "https://store.steampowered.com/tagdata/populartags/english"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "games.json")
COUNT = 100
WORKERS = 2
ONLINE_TAGS = {
    "Multiplayer", "Massively Multiplayer", "Online Co-Op", "Co-op", "PvP",
    "MMORPG", "Asynchronous Multiplayer", "Battle Royale", "Team-Based",
    "Competitive", "eSports", "Co-op Campaign", "Looter Shooter", "Hero Shooter"
}

def request(url, retries=7):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; FreeGamesExplorer/1.0)",
        "Accept": "application/json,text/html",
        "Accept-Language": "en-US,en;q=0.9",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                retry_after = int(exc.headers.get("Retry-After", "0") or 0)
                time.sleep(max(retry_after, min(60, 5 * (2 ** attempt))))
                continue
            raise
        except Exception:
            if attempt == retries - 1: raise
            time.sleep(min(30, 2 * (attempt + 1)))

def page_url(start):
    params = {
        "query": "", "start": start, "count": COUNT, "dynamic_data": "",
        "sort_by": "_ASC", "maxprice": "free", "category1": "998",
        "infinite": "1", "ndl": "1", "l": "english", "cc": "us"
    }
    return SEARCH + "?" + urllib.parse.urlencode(params)

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()

def attr(block, name):
    match = re.search(rf'{re.escape(name)}="([^"]*)"', block)
    return html.unescape(match.group(1)) if match else ""

def parse_page(payload, tag_map):
    raw = json.loads(payload)
    source = raw.get("results_html", "")
    blocks = re.findall(r'<a\b[^>]*class="[^"]*search_result_row[^"]*"[\s\S]*?</a>', source)
    games = []
    for block in blocks:
        if not re.search(r'class="[^"]*discount_final_price[^"]*\bfree\b', block, re.I):
            continue
        appid = attr(block, "data-ds-appid").split(",")[0]
        if not appid.isdigit():
            continue
        title_m = re.search(r'<span class="title">([\s\S]*?)</span>', block)
        img_m = re.search(r'<div class="search_capsule"><img src="([^"]+)"', block)
        release_m = re.search(r'<div class="search_released[^"]*">([\s\S]*?)</div>', block)
        review_m = re.search(r'class="search_review_summary\s+([^"]*)"[^>]*data-tooltip-html="([^"]*)"', block)
        tags_raw = attr(block, "data-ds-tagids")
        try: tag_ids = json.loads(tags_raw)
        except Exception: tag_ids = []
        tags = [tag_map.get(str(tag_id)) for tag_id in tag_ids if tag_map.get(str(tag_id))]
        review_text, review_percent = "", 0
        if review_m:
            tooltip = clean(review_m.group(2))
            review_text = tooltip.split("<br>")[0] if "<br>" in tooltip else re.split(r"\d+%", tooltip)[0].strip()
            percent = re.search(r"(\d+)%", html.unescape(review_m.group(2)))
            review_percent = int(percent.group(1)) if percent else 0
        release = clean(release_m.group(1)) if release_m else ""
        try:
            release_ts = int(datetime.strptime(release, "%b %d, %Y").replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            release_ts = 0
        platforms = {
            "windows": 'platform_img win' in block,
            "mac": 'platform_img mac' in block,
            "linux": 'platform_img linux' in block,
        }
        capsule = html.unescape(img_m.group(1)) if img_m else f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
        games.append({
            "appid": int(appid), "name": clean(title_m.group(1)) if title_m else f"App {appid}",
            "url": f"https://store.steampowered.com/app/{appid}/",
            "capsule": capsule, "header": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
            "screenshots": [], "tags": tags, "online": bool(ONLINE_TAGS.intersection(tags)),
            "platforms": platforms, "release": release, "releaseTimestamp": release_ts,
            "reviewText": review_text, "reviewPercent": review_percent,
        })
    return raw.get("total_count", 0), games

def enrich_featured(game):
    try:
        raw = json.loads(request(f"https://store.steampowered.com/api/appdetails?appids={game['appid']}&l=english&cc=us"))
        data = raw.get(str(game["appid"]), {}).get("data", {})
        game["header"] = data.get("header_image", game["header"])
        game["screenshots"] = [s.get("path_thumbnail") for s in data.get("screenshots", [])[:4] if s.get("path_thumbnail")]
    except Exception:
        pass
    return game

def main():
    if os.environ.get("FEATURED_ONLY") == "1" and os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        popular_ids = [730, 1172470, 230410, 570, 578080, 1085660, 440, 291550]
        by_id = {game["appid"]: game for game in payload["games"]}
        featured = [by_id[appid].copy() for appid in popular_ids if appid in by_id]
        with ThreadPoolExecutor(max_workers=4) as pool:
            payload["featured"] = list(pool.map(enrich_featured, featured))
        with open(OUT, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        print(f"Refreshed {len(featured)} featured games")
        return

    tags = json.loads(request(TAGS_URL))
    tag_map = {str(item["tagid"]): item["name"] for item in tags}
    first_payload = request(page_url(0))
    total, first_games = parse_page(first_payload, tag_map)
    max_pages_env = int(os.environ.get("MAX_PAGES", "0"))
    pages = math.ceil(total / COUNT)
    if max_pages_env: pages = min(pages, max_pages_env)
    games = list(first_games)
    failed_pages = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(request, page_url(page * COUNT)): page for page in range(1, pages)}
        for future in as_completed(futures):
            try:
                _, batch = parse_page(future.result(), tag_map)
                games.extend(batch)
            except Exception as exc:
                failed_pages += 1
                print(f"Page {futures[future]} failed: {exc}")
    if failed_pages and os.path.exists(OUT):
        try:
            with open(OUT, "r", encoding="utf-8") as handle:
                previous_games = json.load(handle).get("games", [])
            games = previous_games + games
            print(f"Merged previous catalog because {failed_pages} pages were unavailable")
        except Exception:
            pass
    unique = {g["appid"]: g for g in games}
    games = list(unique.values())
    games.sort(key=lambda g: (-g["reviewPercent"], g["name"].lower()))

    category_counts = {}
    for game in games:
        for tag in game["tags"]:
            category_counts[tag] = category_counts.get(tag, 0) + 1
    categories = [{"name": name, "count": count} for name, count in category_counts.items()]
    categories.sort(key=lambda x: (-x["count"], x["name"]))

    first_ids = [game["appid"] for game in first_games]
    featured = [unique[appid].copy() for appid in first_ids if appid in unique][:8]
    with ThreadPoolExecutor(max_workers=4) as pool:
        featured = list(pool.map(enrich_featured, featured))

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "https://store.steampowered.com/",
        "searchSource": "https://store.steampowered.com/search/?maxprice=free&category1=998&ndl=1",
        "reportedSearchTotal": total,
        "total": len(games),
        "onlineCount": sum(1 for g in games if g["online"]),
        "categories": categories,
        "featured": featured,
        "games": games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {len(games)} free Steam games from {pages} result pages")

if __name__ == "__main__":
    main()
