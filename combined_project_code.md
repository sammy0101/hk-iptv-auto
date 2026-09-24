# Complete Project Codebase
Generated on: Thu Sep 24 11:23:52 UTC 2026

## File: requirements.txt
````txt
requests
opencc-python-reimplemented
m3u8

````

## File: main.py
````py
import requests
import re
import json
import base64
import datetime
import subprocess
from urllib.parse import urlparse, urlunparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from opencc import OpenCC
import m3u8

cc = OpenCC('s2t')

# 模擬標準 Android TV 播放器標頭 (穿透多數防盜鏈)
IPTV_UA = 'okhttp/3.15.0 (Linux; Android 11; TVBox)'
HEADERS = {
    'User-Agent': IPTV_UA,
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# --- 1. 唯一上游目標 (只讀取這兩個 README.md，包含所有在線源、單倉、多倉) ---
TARGET_README_URLS = [
    "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md",
    "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md"
]

# --- 2. 嚴格過濾與排序規則 ---
KEYWORDS = [
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY", "奇妙電視",
    "RTHK", "港台電視",
    "翡翠台", "明珠台", "J2", "TVB Plus", "無綫新聞", "無線新聞", "無綫財經", "無線財經",
    "Now新聞", "Now 新聞", "Now直播", "Now 直播", "NowTV", "Now 劇集",
    "有線新聞", "有線財經"
]

BLOCK_KEYWORDS = [
    "FOX", "Pluto", "Local Now", "NBC", "CBS", "ABC", "AXS", "Snowy", 
    "Reuters", "Mirror", "ET Now", "The Now", "Right Now", "News Now",
    "Chopper", "Wow", "UHD", "8K", "Career", "Comics", "Movies", "tv360",
    "Anthony Bourdain", "HEi Now", "MS NOW", "Now 14", "NowMedia", "Castr",
    "虎牙", "斗鱼", "B站", "哔哩", "bilibili", "YY", "轮播", "电影", "电视剧",
    "浙江", "杭州", "西湖", "廣東", "珠江", "大灣區", "深圳", "福建",
    "澳門", "Macau", "澳視", "蓮花",
    "CCTV", "CGTN", "鳳凰", "凤凰", "華麗", "星河", "測試", "test", "iHOY"
]

ORDER_KEYWORDS = [
    "翡翠台", "無綫新聞", "無線新聞", "明珠台", "TVB Plus", "J2", "財經",
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY TV", "HOY", "有線新聞", "有線財經",
    "港台電視31", "RTHK 31", "RTHK31",
    "港台電視32", "RTHK 32", "RTHK32",
    "Now新聞", "Now直播"
]

# 香港官方直連保底
OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8"},
    {"name": "港台電視32", "url": "https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8"}
]

# --- 3. URL 規範化與編碼模組 ---

def clean_and_encode_url(url: str) -> str:
    """自動清理結尾雜訊、轉換 GitHub Blob 直鏈，並處理中文域名 Punycode"""
    # 剔除 Markdown 括號、註釋符、引號與空格
    url = url.strip().rstrip(')>],;\'"')
    if "github.com/" in url and "/blob/" in url:
        url = url.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")
    try:
        parts = urlparse(url)
        netloc = parts.netloc.encode('idna').decode('ascii')
        path = quote(parts.path, safe='/:@%')
        query = quote(parts.query, safe='=&%:@')
        return urlunparse((parts.scheme, netloc, path, parts.params, query, parts.fragment))
    except Exception:
        return url

def fetch_raw_content(url: str, timeout: int = 10) -> str:
    safe_url = clean_and_encode_url(url)
    try:
        r = requests.get(safe_url, headers=HEADERS, timeout=timeout)
        r.encoding = 'utf-8'
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return ""

def parse_tvbox_payload(text: str) -> dict:
    """支援純 JSON 與 Base64 / PNG 偽裝密文"""
    text = text.strip()
    if not text:
        return {}
    try:
        if text.startswith('{') or text.startswith('['):
            return json.loads(text)
    except Exception:
        pass

    try:
        clean_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', text)
        decoded = base64.b64decode(clean_b64).decode('utf-8', errors='ignore')
        if '{' in decoded:
            json_str = decoded[decoded.find('{'):decoded.rfind('}')+1]
            return json.loads(json_str)
    except Exception:
        pass

    return {}

# --- 4. 萬能候選鏈接萃取器 (內容探針) ---

def process_candidate_url(target_url: str, visited: set = None, depth: int = 0) -> list:
    """
    通用探針：全自動識別目標網址是：
    1. 直連 M3U / TXT 直播源（包括無後綴如 /zb、/dsy 等）
    2. TVBox 單倉（提取 lives）
    3. TVBox 多倉（遞迴展開 urls）
    """
    if visited is None:
        visited = set()
    if depth > 3:
        return []

    safe_url = clean_and_encode_url(target_url)
    if safe_url in visited:
        return []
    visited.add(safe_url)

    # 1. 如果副檔名已經明確是 M3U/TXT 且不是多倉清單，直接作為直播清單返回
    lower_path = urlparse(safe_url).path.lower()
    if any(lower_path.endswith(ext) for ext in ['.m3u', '.m3u8', '.txt']) and 'dc.txt' not in lower_path:
        return [safe_url]

    # 2. 發起探針請求確認內部真實格式
    text = fetch_raw_content(safe_url, timeout=8)
    if not text:
        return []

    # 2.1 內容本身就是 M3U 或 TXT 直播列表（例如游魂 /tv/zb、天神 /dsy）
    first_few_lines = text.split('\n')[:15]
    if '#EXTM3U' in text or any('#genre#' in l for l in first_few_lines) or any(',' in l and 'http' in l for l in first_few_lines):
        return [safe_url]

    # 2.2 嘗試按 TVBox 單倉/多倉 JSON 處理
    data = parse_tvbox_payload(text)
    if not isinstance(data, dict):
        return []

    extracted_lives = []

    # 提取單倉 lives 直播節點
    if 'lives' in data and isinstance(data['lives'], list):
        for item in data['lives']:
            if isinstance(item, dict):
                l_url = item.get('url')
                if l_url and isinstance(l_url, str) and l_url.startswith('http'):
                    extracted_lives.append(clean_and_encode_url(l_url))
                elif 'channels' in item and isinstance(item['channels'], list):
                    for sub in item['channels']:
                        for u in sub.get('urls', []):
                            if isinstance(u, str) and u.startswith('http'):
                                extracted_lives.append(clean_and_encode_url(u))

    # 提取多倉 urls 節點並遞迴
    if 'urls' in data and isinstance(data['urls'], list):
        for sub_item in data['urls']:
            if isinstance(sub_item, dict) and 'url' in sub_item:
                sub_url = sub_item['url']
                if isinstance(sub_url, str) and sub_url.startswith('http'):
                    extracted_lives.extend(process_candidate_url(sub_url, visited, depth + 1))

    return list(set(extracted_lives))

def extract_all_sources_from_readmes() -> list:
    """全量讀取兩個目標 README.md，抓出包含推薦在線源、IPv4、IPv6、海外、單多倉在內的所有直播清單"""
    print("🌐 開始解析目標 README.md 全文...", flush=True)
    all_extracted_playlists = set()
    candidate_urls = set()

    for readme_url in TARGET_README_URLS:
        print(f"  -> 抓取上游清單: {readme_url}", flush=True)
        content = fetch_raw_content(readme_url, timeout=12)
        if not content:
            continue

        # 匹配所有有效的 http/https 鏈接 (精確去除 Markdown 雜訊)
        raw_urls = re.findall(r'https?://[^\s#<>"\']+', content)
        for u in raw_urls:
            clean_u = u.strip().rstrip(')>],;\'"')
            # 排除非流媒體非配置鏈接
            if any(ext in clean_u.lower() for ext in ['.apk', '.exe', '.zip', 'shields.io', 'badge.svg', '.jpg', '.jpeg', '.gif', 'github.com/youhunwl/tvapp', 'github.com/ngo5/iptv']):
                continue
            candidate_urls.add(clean_u)

    print(f"🔍 全文共掃描出 {len(candidate_urls)} 個候選網址，開始深入解碼與分類...", flush=True)

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(process_candidate_url, u) for u in candidate_urls]
        for f in as_completed(futures):
            try:
                res = f.result()
                all_extracted_playlists.update(res)
            except Exception:
                pass

    final_sources = list(all_extracted_playlists)
    print(f"✅ 全部分析完畢！共獲取到 {len(final_sources)} 個可下載的直播源清單（含全部在線源與影視倉 lives）。", flush=True)
    return final_sources

# --- 5. ffprobe 真機解碼級驗證 ---

def check_stream_with_ffprobe(url: str, timeout: int = 5) -> bool:
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-user_agent', IPTV_UA,
        '-show_entries', 'stream=codec_type,codec_name',
        '-of', 'json',
        '-timeout', str(timeout * 1000000),
        url
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 2)
        if result.returncode != 0:
            return False
        info = json.loads(result.stdout.decode('utf-8'))
        streams = info.get('streams', [])
        return any(s.get('codec_type') == 'video' for s in streams)
    except Exception:
        return False

def fast_pre_filter(url: str, timeout: int = 3) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        header_bytes = b''
        for chunk in r.iter_content(chunk_size=1024):
            header_bytes += chunk
            if len(header_bytes) >= 4096:
                break
        r.close()
        text = header_bytes.decode('utf-8', errors='ignore')
        if any(err in text.lower() for err in ['error', 'expired', 'denied', 'unauthorized', '404 not found', '<html>']):
            return False
        return True
    except Exception:
        return False

def verify_single_channel(ch: dict) -> tuple:
    url = ch['url']
    if any(domain in url for domain in ['rthk.hk', 'akamaized.net']):
        return ch, True
    if not fast_pre_filter(url):
        return ch, False
    is_playable = check_stream_with_ffprobe(url, timeout=5)
    return ch, is_playable

def check_channels_parallel(channels: list, max_workers=10) -> list:
    valid_channels = []
    print(f"\n🔍 開始對 {len(channels)} 個候選源進行【ffprobe 真機解碼級驗證】...", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(verify_single_channel, ch) for ch in channels]
        for f in as_completed(futures):
            ch, is_alive = f.result()
            if is_alive:
                valid_channels.append(ch)
                print(f"  🟢 [可播放]: {ch['name']}", flush=True)
            else:
                print(f"  🔴 [不可播/假源]: {ch['name']}", flush=True)
    return valid_channels

def get_sort_key(item: dict) -> int:
    name = item["name"]
    for index, keyword in enumerate(ORDER_KEYWORDS):
        if keyword.lower() in name.lower():
            return index
    return 999

# --- 6. 主流程執行 ---

def fetch_and_parse() -> list:
    found_channels = []
    seen_urls = set()

    # 1. 唯一來源：解析兩個 README.md 中所有類型的網址
    playlist_sources = extract_all_sources_from_readmes()
    print(f"🚀 開始檢索各清單中的香港電視頻道...", flush=True)

    # 2. 逐一提取香港電視台並過濾
    for index, source in enumerate(playlist_sources):
        content = fetch_raw_content(source, timeout=8)
        if not content:
            continue

        lines = [l.strip() for l in content.split('\n') if l.strip()]
        current_name = ""
        count_added = 0
        is_m3u = any(line.startswith('#EXTM3U') or line.startswith('#EXTINF') for line in lines[:10])

        for line in lines:
            if is_m3u:
                if line.startswith("#EXTINF"):
                    match = re.search(r',(.+)$', line)
                    if match:
                        raw_name = match.group(1).strip()
                        current_name = cc.convert(raw_name).replace('臺', '台')
                elif line.startswith("http"):
                    stream_url = line.split('$')[0].strip()
                    if current_name:
                        if any(b.lower() in current_name.lower() for b in BLOCK_KEYWORDS):
                            current_name = ""
                            continue
                        if any(k.lower() in current_name.lower() for k in KEYWORDS):
                            if stream_url not in seen_urls:
                                seen_urls.add(stream_url)
                                found_channels.append({"name": current_name, "url": stream_url})
                                count_added += 1
                    current_name = ""
            else:
                if ',' in line and not line.startswith('http'):
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        name_part = cc.convert(parts[0].strip()).replace('臺', '台')
                        url_part = parts[1].split('$')[0].strip()
                        if url_part.startswith('http'):
                            if any(b.lower() in name_part.lower() for b in BLOCK_KEYWORDS):
                                continue
                            if any(k.lower() in name_part.lower() for k in KEYWORDS):
                                if url_part not in seen_urls:
                                    seen_urls.add(url_part)
                                    found_channels.append({"name": name_part, "url": url_part})
                                    count_added += 1

        if count_added > 0:
            print(f"  [{index+1}/{len(playlist_sources)}] 提取到 {count_added} 個香港候選頻道 (來源: {source})", flush=True)

    return found_channels

def generate_m3u(channels: list):
    tested_channels = check_channels_parallel(channels)

    final_dict = {}
    for off in OFFICIAL_CHANNELS:
        final_dict[off['url']] = off

    for ch in tested_channels:
        if ch['url'] not in final_dict:
            final_dict[ch['url']] = ch

    final_list = list(final_dict.values())
    final_list.sort(key=get_sort_key)

    content = '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n'
    content += f'# Update: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'

    for item in final_list:
        name = item["name"].replace('臺', '台')
        content += f'#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/{name}.png",{name}\n'
        content += f'#EXTVLCOPT:http-user-agent={IPTV_UA}\n'
        content += f'{item["url"]}\n'

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 驗證完成！共篩選出 {len(final_list)} 個實質可解碼播放的優質香港電視頻道。", flush=True)

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)

````

## File: README.md
````md
# 📺 HK IPTV Auto Updater | 香港電視台直播源自動更新

![Update Status](https://github.com/sammy0101/hk-iptv-auto/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

這是一個基於 **GitHub Actions** 的全自動化香港電視 IPTV 聚合過濾專案。  
系統捨棄了傳統靜態易失效的死鏈清單，採用**動態上游雙引擎解析架構**，每日自動穿透各大影視倉與在線源，配合 **`ffprobe` 真機解碼級檢測**、**播放器 UA 標頭注入**、**OpenCC 港式繁體標準化** 與 **收視優先級自動排序**，生成實質可出畫面的純淨香港電視直播清單 (`.m3u`)。

---

## 🚀 訂閱地址 (Subscription URL)

請在支援 IPTV 的播放器 (TiviMate, TVBox, Kodi, PotPlayer, APTV, 影視倉 等) 中輸入以下鏈接：

| 線路 | 鏈接 (URL) | 推薦度 | 說明 |
| :--- | :--- | :--- | :--- |
| **jsDelivr CDN (推薦)** | `https://cdn.jsdelivr.net/gh/sammy0101/hk-iptv-auto@main/hk_live.m3u` | ⭐⭐⭐⭐⭐ | 全球節點 CDN 緩存加速，訪問高速穩定 |
| **GitHub Raw** | `https://raw.githubusercontent.com/sammy0101/hk-iptv-auto/refs/heads/main/hk_live.m3u` | ⭐⭐⭐ | 原始倉庫直連，適合直通海外網絡之設備 |

> 💡 **提示**：生成的 `.m3u` 已為各大播放器注入 `#EXTVLCOPT:http-user-agent`，可自動繞過反代伺服器的客戶端驗證。

---

## ❤️ 特別鳴謝 (Credits)

本專案的核心數據源完全依賴以下開源專案與社區維護者的無私奉獻，特此致謝：

*   **核心動態上游**:
    *   **youhunwl**: [TVAPP](https://github.com/youhunwl/TVAPP) *(自動同步其最新在線源、單倉與多倉清單)*
    *   **ngo5**: [IPTV](https://github.com/ngo5/IPTV) *(自動同步其全網彙整源)*
*   **基礎生態貢獻者**:
    *   **fanmingming**: [live](https://github.com/fanmingming/live)
    *   **Guovin**: [TV](https://github.com/Guovin/TV)
    *   **YueChan**: [Live](https://github.com/YueChan/Live)
    *   **Kimentanm**: [APTV](https://github.com/Kimentanm/aptv)
    *   **iptv-org**: [IPTV Collection](https://github.com/iptv-org/iptv)
    *   **Free-TV**, **epg.pw**, **jsDelivr** 以及所有 TVBox 影視倉（飯太硬、肥貓、小盒子、道長等）的無私維護者。

---

## 📺 收錄頻道 (Supported Channels)

本專案專注於香港本地頻道，並按照收視習慣完成了優先級排序：

1.  **TVB 系列**: 翡翠台 (Jade), 無綫新聞台 (News), 明珠台 (Pearl), TVB Plus (J2), 無綫財經體育資訊台
2.  **ViuTV 系列**: ViuTV (99台), ViuTVsix (96台)
3.  **HOY TV 系列**: HOY TV (77台), HOY 資訊台 (78台)
4.  **RTHK 系列**: 港台電視 31, 港台電視 32, 港台電視 33
5.  **Now TV 系列**: Now 新聞台, Now 直播台
6.  **其他資訊**: 有線新聞、有線財經等

---

## ✨ 核心技術特點 (Features)

*   **🌐 雙上游動態同步 (零靜態死鏈)**:
    *   拒絕在代碼中寫死易失效的清單，每次執行定時自動向 `youhunwl/TVAPP` 與 `ngo5/IPTV` 抓取最新內容，上游換倉換源，本地自動無感同步。
*   **🧬 萬能內容探針與影視倉穿透**:
    *   **單倉解析**: 自動解碼 Base64、`.png` 偽裝數據，深層提取 `lives` 節點。
    *   **多倉遞迴**: 自動展開多倉內所有子倉，遍歷挖掘隱藏電視清單。
    *   **無後綴源識別**: 自動識別無副檔名（如 `/zb`、`/dsy`）的純文字清單。
    *   **Punycode 自動轉碼**: 自動處理中文網址（如 `www.饭太硬.net`、`肥猫.net`、`哈基米.png`），避免請求崩潰。
*   **🔬 `ffprobe` 真機解碼級驗證 (徹底消滅假活源)**:
    *   淘汰傳統僅看「HTTP 200」的假檢測機制。
    *   直接調用系統底層 `ffprobe` 解碼多媒體封包，必須實質解析出合法 `video` 視頻軌道才判定為有效，杜絕空殼 M3U8、過期跳轉與授權報錯頁面。
*   **🛡️ 官方源保護與 UA 偽裝**:
    *   針對港台 RTHK 等官方 CDN 設置保護放行，避免海外 Runner 因 Geo-block 誤刪本地可用源。
    *   輸出檔案自帶 Android TVBox 專屬 User-Agent 標頭，解決播放器 403 阻擋。
*   **📝 繁簡轉化與文字規範**:
    *   集成 `OpenCC` 繁簡轉換引擎，並強制將「臺」全面校正為香港慣用之「台」字。
*   **🔄 自動排序**:
    *   嚴格遵循 TVB ➔ Viu ➔ HOY ➔ 港台 ➔ Now 的香港觀眾收視順序排列。

---

## 🛠️ 給 Fork 用戶的修改指南 (For Developers)

如果你 Fork 了本專案，並希望自定義抓取來源或篩選規則，請直接編輯 `main.py`：

### 1. 修改或增加上游抓取目標
找到 `TARGET_README_URLS`，你可以增減需要自動爬取的上游 Markdown 來源：
```python
TARGET_README_URLS = [
    "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md",
    "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md"
]
```

### 2. 修改過濾規則
*   **白名單 (`KEYWORDS`)**: 頻道名稱**必須包含**這些關鍵字才會進入解碼候選池。
*   **黑名單 (`BLOCK_KEYWORDS`)**: 頻道名稱若包含這些關鍵字（如輪播、外國台、非港澳內容），會被**強制剔除**。

### 3. 調整頻道排序
編輯 `ORDER_KEYWORDS` 列表，排名越靠前的關鍵字，在產生的 `.m3u` 中位置越靠前。

### 4. 修改訂閱鏈接
Fork 之後，請編輯 `README.md`，將訂閱地址中的 `sammy0101` 替換為你的 GitHub 用戶名：
*   **jsDelivr 格式範例**:
    `https://cdn.jsdelivr.net/gh/<你的用戶名>/<倉庫名稱>@main/hk_live.m3u`

### ⚠️ 重要：Fork 後啟用自動更新
Fork 本專案後，GitHub Actions 預設處於關閉狀態。請手動啟用：
1.  進入倉庫的 **Actions** 分頁。
2.  點擊綠色按鈕 **"I understand my workflows, go ahead and enable them"**。
3.  在左側選擇 **Update IPTV Source** ➔ 點擊 **Enable workflow**。
4.  點擊 **Run workflow** 即可手動進行首次抓取與解碼測試。

---

## ⚠️ 免責聲明 (Disclaimer)

1.  **僅供學習交流**: 本專案僅為網絡串流測試與自動化資訊爬取技術研究，不具任何商業目的。
2.  **不存儲視頻資源**: 所有直播源數據均來自互聯網公開開源庫與影視倉接口，本專案伺服器與倉庫**不存儲、不託管、不轉發、不重播**任何音視頻串流文件。
3.  **版權聲明**: 電視台信號版權全數歸相關版權方所有。若相關鏈接涉及侵權，請開 Issue 通知，我們將立即配合移除相關過濾關鍵字與上游來源。
4.  **地區限制**: 官方直連串流帶有嚴格的 Geo-blocking 地區版權限制，需在香港本地網絡環境下直接收看。

**Last Update:** 每日定時自動更新

````

## File: hk_live.m3u
````m3u
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"
# Update: 2026-09-24 11:20:03
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 33 (1080p) [Geo-blocked].png",RTHK TV 33 (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv33-live.akamaized.net/hls/live/2101641/RTHKTV33/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 34 (1080p) [Geo-blocked].png",RTHK TV 34 (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 35 (1080p) [Geo-blocked].png",RTHK TV 35 (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/master.m3u8

````

## File: .github/workflows/combine-code.yml
````yml
name: Generate All Codebase to MD

on:
  push:
    branches:
      - main
    paths-ignore:
      - 'combined_project_code.md' # 避免此檔案自身更新引發無限循環
  workflow_dispatch: # 支援在 GitHub 網頁上手動觸發執行

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Combine All Files into MD
        run: |
          OUT_FILE="combined_project_code.md"
          echo "# Complete Project Codebase" > "$OUT_FILE"
          echo "Generated on: $(date)" >> "$OUT_FILE"
          echo "" >> "$OUT_FILE"

          # 遍歷專案內的所有檔案，排除依賴、Git 歷史、打包產物及二進位檔案
          find . -type f \
            -not -path "*/node_modules/*" \
            -not -path "*/.git/*" \
            -not -path "*/dist/*" \
            -not -name "package-lock.json" \
            -not -name "yarn.lock" \
            -not -name "pnpm-lock.yaml" \
            -not -name "$OUT_FILE" \
            -not -name "*.png" \
            -not -name "*.jpg" \
            -not -name "*.jpeg" \
            -not -name "*.gif" \
            -not -name "*.ico" \
            -not -name "*.woff*" \
            -not -name "*.ttf" | while read -r file; do
              
              # 取得相對路徑與副檔名
              rel_path="${file#./}"
              ext="${file##*.}"
              
              # 如果無副檔名，清除變數避免格式混亂
              if [ "$ext" = "$rel_path" ]; then
                ext=""
              fi
              
              # 寫入檔案標題
              echo "## File: $rel_path" >> "$OUT_FILE"
              # 使用四個反單引號（````）包裹，防止內部程式碼的三個反單引號造成排版衝突
              echo "\`\`\`\`$ext" >> "$OUT_FILE"
              cat "$file" >> "$OUT_FILE"
              echo "" >> "$OUT_FILE"
              echo "\`\`\`\`" >> "$OUT_FILE"
              echo "" >> "$OUT_FILE"
          done

      - name: Commit and Push changes
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add combined_project_code.md
          
          if git diff --staged --quiet; then
            echo "No changes in codebase."
          else
            git commit -m "docs: auto-generate complete codebase [skip ci]"
            git push origin main
          fi

````

## File: .github/workflows/main.yml
````yml
name: Update IPTV Source

on:
  schedule:
    # 每天香港時間 08:00 和 20:00 運行 (UTC 00:00, 12:00)
    - cron: '0 0,12 * * *'
  workflow_dispatch: # 允許手動點擊按鈕

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: pip install -r requirements.txt

    - name: Run script
      run: python main.py

    - name: Commit and push
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add hk_live.m3u
        git commit -m "Auto-update channel list" || echo "No changes to commit"
        git push

````

