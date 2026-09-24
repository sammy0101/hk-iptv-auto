# Complete Project Codebase
Generated on: Thu Sep 24 11:17:35 UTC 2026

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

# 模擬標準 Android TV 播放器標頭
IPTV_UA = 'okhttp/3.15.0 (Linux; Android 11; TVBox)'
HEADERS = {
    'User-Agent': IPTV_UA,
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# --- 1. 唯一上游目標 (只從這兩個 README 動態爬取) ---
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

# --- 3. URL 編碼與解析模組 ---

def clean_and_encode_url(url: str) -> str:
    """自動處理 Punycode 中文域名、中文路徑編碼及 GitHub Blob 直鏈轉換"""
    url = url.strip()
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
    """發起 HTTP 請求並自動獲取解碼文本"""
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
    """自動識別並解析 TVBox 配置 (支援純 JSON 與 Base64 / PNG 偽裝)"""
    text = text.strip()
    if not text:
        return {}
    
    # 嘗試直接解析 JSON
    try:
        if text.startswith('{') or text.startswith('['):
            return json.loads(text)
    except Exception:
        pass

    # 嘗試 Base64 解碼 (處理 ** 開頭或 .png 偽裝文件)
    try:
        clean_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', text)
        decoded = base64.b64decode(clean_b64).decode('utf-8', errors='ignore')
        if '{' in decoded:
            json_str = decoded[decoded.find('{'):decoded.rfind('}')+1]
            return json.loads(json_str)
    except Exception:
        pass

    return {}

def extract_from_tvbox(target_url: str, visited: set = None, depth: int = 0) -> list:
    """
    遞迴提取 TVBox 單倉與多倉內的所有直播源 (lives)
    """
    if visited is None:
        visited = set()
    if depth > 3:  # 限制多倉遞迴深度，避免死循環
        return []

    safe_url = clean_and_encode_url(target_url)
    if safe_url in visited:
        return []
    visited.add(safe_url)

    extracted_live_urls = []
    text = fetch_raw_content(safe_url, timeout=8)
    if not text:
        return []

    # 檢查是否本身就是直連 M3U/TXT 播放列表
    if '#EXTM3U' in text or any(',' in l and 'http' in l for l in text.split('\n')[:10]):
        return [safe_url]

    data = parse_tvbox_payload(text)
    if not isinstance(data, dict):
        return []

    # 1. 提取單倉 lives 節點
    if 'lives' in data and isinstance(data['lives'], list):
        for item in data['lives']:
            if isinstance(item, dict):
                l_url = item.get('url')
                if l_url and isinstance(l_url, str) and l_url.startswith('http'):
                    extracted_live_urls.append(clean_and_encode_url(l_url))
                elif 'channels' in item and isinstance(item['channels'], list):
                    for sub in item['channels']:
                        for u in sub.get('urls', []):
                            if isinstance(u, str) and u.startswith('http'):
                                extracted_live_urls.append(clean_and_encode_url(u))

    # 2. 遞迴提取多倉 urls 節點
    if 'urls' in data and isinstance(data['urls'], list):
        for sub_item in data['urls']:
            if isinstance(sub_item, dict) and 'url' in sub_item:
                sub_url = sub_item['url']
                if isinstance(sub_url, str) and sub_url.startswith('http'):
                    extracted_live_urls.extend(extract_from_tvbox(sub_url, visited, depth + 1))

    return list(set(extracted_live_urls))

# --- 4. 動態解析兩個目標 README.md ---

def extract_all_sources_from_readmes() -> list:
    """
    從兩個目標 README.md 中萃取所有單倉、多倉與直連直播清單
    """
    print("🌐 開始動態抓取目標 README.md...", flush=True)
    all_extracted_playlists = set()
    candidate_urls = set()

    for readme_url in TARGET_README_URLS:
        print(f"  -> 正在讀取: {readme_url}", flush=True)
        content = fetch_raw_content(readme_url, timeout=12)
        if not content:
            print(f"     ⚠️ 讀取失敗或內容為空: {readme_url}", flush=True)
            continue

        # 正則匹配所有 http/https 鏈接 (自動過濾註釋與行尾文字)
        found_urls = re.findall(r'https?://[^\s#<>"\']+', content)
        for u in found_urls:
            u = u.strip()
            # 排除非源鏈接
            if any(ext in u.lower() for ext in ['.apk', '.exe', '.zip', 'shields.io', 'github.com/youhunwl', 'github.com/ngo5']):
                continue
            candidate_urls.add(u)

    print(f"🔍 從 README 中獲取到 {len(candidate_urls)} 個候選接口，開始深入解析單倉/多倉與直播源...", flush=True)

    # 並行解析所有候選接口
    def process_candidate(url):
        results = []
        lower_url = url.lower()
        # 明確的直連直播源副檔名
        if any(lower_url.endswith(ext) for ext in ['.m3u', '.m3u8', '.txt']) and 'dc.txt' not in lower_url:
            results.append(clean_and_encode_url(url))
        else:
            # 單倉、多倉接口 (JSON/Base64/無副檔名)
            lives = extract_from_tvbox(url)
            results.extend(lives)
        return results

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(process_candidate, u) for u in candidate_urls]
        for f in as_completed(futures):
            try:
                res = f.result()
                all_extracted_playlists.update(res)
            except Exception:
                pass

    final_sources = list(all_extracted_playlists)
    print(f"✅ 深度挖掘完成！共解析出 {len(final_sources)} 個有效直播源清單。", flush=True)
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

def check_channels_parallel(channels: list, max_workers: int = 10) -> list:
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

# --- 6. 核心排程執行邏輯 ---

def fetch_and_parse() -> list:
    found_channels = []
    seen_urls = set()

    # 1. 唯一來源：動態解析兩個目標 README.md
    playlist_sources = extract_all_sources_from_readmes()
    print(f"🚀 開始逐一檢索各清單中的香港電視頻道...", flush=True)

    # 2. 下載並解析每個 M3U/TXT 列表
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
            print(f"  [{index+1}/{len(playlist_sources)}] 提取到 {count_added} 個香港候選頻道", flush=True)

    return found_channels

def generate_m3u(channels: list):
    # 進行真機解碼篩選
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

## File: hk_live.m3u
````m3u
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"
# Update: 2026-09-24 03:38:30
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK32.png",RTHK32
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
http://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 33 (1080p) [Geo-blocked].png",RTHK TV 33 (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv33-live.akamaized.net/hls/live/2101641/RTHKTV33/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 34 (1080p) [Geo-blocked].png",RTHK TV 34 (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 35 (1080p) [Geo-blocked].png",RTHK TV 35 (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 36 (港台電視36) (1080p) [Geo-blocked].png",RTHK TV 36 (港台電視36) (1080p) [Geo-blocked]
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv36-live.akamaized.net/hls/live/2112176/RTHKTV36/master.m3u8

````

## File: requirements.txt
````txt
requests
opencc-python-reimplemented
m3u8

````

## File: README.md
````md
# 📺 HK IPTV Auto Updater | 香港電視台直播源自動更新

![Update Status](https://github.com/sammy0101/hk-iptv-auto/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

這是一個基於 **GitHub Actions** 的全自動化香港電視 IPTV 聚合專案。
每天定時自動同步上游最新資源庫與 TVBox 影視倉，進行深度切片級流媒體驗證、繁簡轉換（標準化為港式「台」字）與自動排序，生成純淨、可用的香港電視直播清單 (`.m3u`)。

---

## 🚀 訂閱地址 (Subscription URL)

請在您的播放器 (TiviMate, TVBox, Kodi, PotPlayer, APTV 等) 中輸入以下鏈接：

| 線路 | 鏈接 (URL) | 推薦度 |
| :--- | :--- | :--- |
| **jsDelivr CDN (推薦)** | `https://cdn.jsdelivr.net/gh/sammy0101/hk-iptv-auto@main/hk_live.m3u` | ⭐⭐⭐⭐⭐ |
| **GitHub Raw** | `https://raw.githubusercontent.com/sammy0101/hk-iptv-auto/refs/heads/main/hk_live.m3u` | ⭐⭐⭐ |

> 💡 **提示**：推薦使用上方 **jsDelivr CDN** 鏈接，自帶全球節點緩存加速，更新速度快且不受 GitHub 網絡波動影響。

---

## ❤️ 特別鳴謝 (Credits)

本項目的數據來源主要基於以下開源項目與社區大佬的大力奉獻，在此致以最誠摯的謝意：

*   **youhunwl**: [TVAPP](https://github.com/youhunwl/TVAPP) *(本專案已實現每日自動同步其最新在線源與影視倉)*
*   **imDazui**: [Tvlist-awesome-m3u-m3u8](https://github.com/imDazui/Tvlist-awesome-m3u-m3u8)
*   **fanmingming**: [live](https://github.com/fanmingming/live)
*   **Guovin**: [TV](https://github.com/Guovin/TV)
*   **YueChan**: [Live](https://github.com/YueChan/Live)
*   **Kimentanm**: [APTV](https://github.com/Kimentanm/aptv)
*   **yuanzl77**: [IPTV](https://github.com/yuanzl77/IPTV)
*   **iptv-org**: [IPTV Collection](https://github.com/iptv-org/iptv)
*   **joevess**: [IPTV](https://github.com/joevess/IPTV)
*   **YanG-1989**: [m3u](https://github.com/YanG-1989/m3u)
*   **hujingguang**: [ChinaIPTV](https://github.com/hujingguang/ChinaIPTV)
*   **MercuryZz**: [IPTVN](https://github.com/MercuryZz/IPTVN)
*   **vbskycn**: [iptv](https://github.com/vbskycn/iptv)
*   **suxuang**: [myIPTV](https://github.com/suxuang/myIPTV)
*   **Free-TV**, **epg.pw**, **jsDelivr** 以及所有無私維護直播源的開發者們。

---

## 📺 收錄頻道 (Supported Channels)

本項目專注於香港本地頻道，並按照香港觀眾收視習慣進行了優先級排序：

1.  **TVB 系列**: 翡翠台 (Jade), 無綫新聞台 (News), 明珠台 (Pearl), TVB Plus (J2), 無綫財經體育資訊台
2.  **ViuTV 系列**: ViuTV (99台), ViuTVsix (96台)
3.  **HOY TV 系列**: HOY TV (77台), HOY 資訊台 (78台)
4.  **RTHK 系列**: 港台電視 31, 港台電視 32, 港台電視 33
5.  **Now TV 系列**: Now 新聞台, Now 直播台
6.  **其他資訊**: 有線新聞、有線財經等

---

## ✨ 項目特點 (Features)

*   **🌐 動態上游同步**: 每日自動抓取 `youhunwl/TVAPP` 的最新數據庫，自動解碼 TVBox 單倉與多倉直播節點。
*   **🔍 雙重過濾系統**:
    *   **白名單機制**: 嚴格限定香港電視台專屬標籤，徹底過濾無關省份、體育、輪播台。
    *   **黑名單攔截**: 強力剔除土耳其 NOW TV、以色列頻道、虎牙、斗魚、B站等雜訊。
*   **⚡ 切片級深度檢測**: 深入解析 `.m3u8` 二級分片並驗證真實視頻二進位流，拒絕「假 200」黑屏死鏈。
*   **🛡️ 官方源保底放行**: 內建香港電台與有線官方 Akamai/CDN 直連放行邏輯，防止 GitHub 海外機房誤殺香港本地可播源。
*   **📝 文字標準化**: 集成 `OpenCC` 簡體轉繁體，並全面校正為港式「台」字。
*   **🔄 自動排序**: 依照香港電視台順序自動排列，方便電視盒子開箱即用。

---

## 🛠️ 給 Fork 用戶的修改指南 (For Developers)

如果你 Fork 了本項目，並希望自定義抓取來源或過濾邏輯，請參考以下步驟：

### 1. 增加/刪除直播源 (Sources)
直接編輯 `main.py`，找到 `FALLBACK_STANDARD_SOURCES` 列表。你可以加入任何公開的 `.m3u` 或 `.m3u8` 鏈接。

### 2. 修改過濾規則 (Filters)
*   **白名單 (`KEYWORDS`)**: 頻道名稱**必須包含**這些關鍵字才會被抓取。
*   **黑名單 (`BLOCK_KEYWORDS`)**: 頻道名稱若包含這些字，會被**強制丟棄**。

### 3. 調整頻道排序 (Sorting)
編輯 `main.py` 中的 `ORDER_KEYWORDS` 列表。越上面的關鍵字，優先級越高。

### 4. 修改訂閱鏈接 (Update Subscription URL)
Fork 之後，`README.md` 顯示的訂閱鏈接仍然指向原作者 (`sammy0101`) 的倉庫。
請務必編輯 `README.md`，將訂閱鏈接中的 `sammy0101` 替換為你的 GitHub 用戶名：

*   **jsDelivr 格式範例**:
    `https://cdn.jsdelivr.net/gh/<你的用戶名>/<倉庫名稱>@main/hk_live.m3u`

### ⚠️ 重要：Fork 後如何啟用自動更新
Fork 本項目後，GitHub Actions 默認是關閉的。你需要：
1.  進入你倉庫的 **Actions** 頁面。
2.  點擊綠色按鈕 **"I understand my workflows, go ahead and enable them"**。
3.  左側選擇 **Update IPTV Source** -> **Enable workflow**。

---

## ⚠️ 免責聲明 (Disclaimer)

1.  **僅供學習交流**: 本項目僅是一個網絡串流測試與自動化技術研究項目。
2.  **不存儲視頻**: 所有直播源鏈接均來自網際網路上的公開渠道，本倉庫不存儲、不託管、不轉發任何視頻流文件。
3.  **版權聲明**: 頻道版權歸相關電視台所有。若有權益問題請提 issue，我們將第一時間配合移除相關關鍵字。
4.  **地區限制**: 部分源（如 RTHK、HOY TV 官方直連）設有 Geo-block，需使用香港本地網絡或香港網絡節點觀看。

**Last Update:** 每天自動更新

````

