# Complete Project Codebase
Generated on: Thu Sep 24 15:20:39 UTC 2026

## File: main.py
````py
import requests
import re
import json
import base64
import time
import datetime
from urllib.parse import urlparse, urlunparse, quote, urljoin
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

# --- 1. Guovin 風格頻道別名對照表 (Alias Normalization) ---
# 將網路抓到的各種混亂名稱自動校正為標準名稱
CHANNEL_ALIASES = {
    "翡翠台": ["翡翠台", "tvb翡翠台", "翡翠", "jade", "翡翠台 1080p", "翡翠台 4k", "tvb 翡翠台", "tvb-翡翠台"],
    "無綫新聞台": ["無綫新聞台", "無線新聞台", "無綫新聞", "無線新聞", "tvb新聞", "tvb無綫新聞", "inews", "無綫新聞台 1080p"],
    "明珠台": ["明珠台", "tvb明珠台", "明珠", "pearl", "tvb 明珠台", "tvb-明珠台"],
    "TVB Plus": ["tvb plus", "j2", "j5", "tvbplus"],
    "無綫財經體育資訊台": ["無綫財經體育資訊台", "無線財經體育資訊台", "無綫財經", "無線財經", "財經體育資訊台", "無綫財經台"],
    "ViuTV": ["viutv", "viu tv", "viutv 99", "viu99", "99台"],
    "ViuTVsix": ["viutvsix", "viutv 6", "viutv6", "viu6", "96台", "viutv 96"],
    "HOY TV": ["hoy tv", "hoytv", "奇妙電視", "香港開電視", "77台", "hoy tv 77"],
    "HOY 資訊台": ["hoy 資訊台", "hoy 资讯台", "hoy資訊台", "hoy78", "78台"],
    "港台電視31": ["港台電視31", "港台电视31", "rthk 31", "rthk31", "港台31", "香港電台31"],
    "港台電視32": ["港台電視32", "港台电视32", "rthk 32", "rthk32", "港台32", "香港電台32"],
    "Now新聞台": ["now新聞台", "now新闻台", "now新聞", "now新闻", "now 332", "now tv 新聞"],
    "Now直播台": ["now直播台", "now直播", "now 331", "now tv 直播"],
    "有線新聞台": ["有線新聞台", "有线新闻台", "有線新聞", "有线新闻", "香港有線新聞"]
}

# 最終輸出的頻道順序 (按照香港人習慣排列)
ORDER_KEYWORDS = [
    "翡翠台", "無綫新聞台", "明珠台", "TVB Plus", "無綫財經體育資訊台",
    "ViuTV", "ViuTVsix",
    "HOY TV", "HOY 資訊台",
    "港台電視31", "港台電視32",
    "Now新聞台", "Now直播台", "有線新聞台"
]

# 每個頻道最多保留測速最快的前 N 條優質線路 (避免 MoonTV 載入過多無效備份)
MAX_URLS_PER_CHANNEL = 4

# 香港官方高保真源 (在香港本地必通，給予優先權重)
OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8"},
    {"name": "港台電視32", "url": "https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8"}
]

# 上游導航大庫清單
TARGET_README_URLS = [
    "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md",
    "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md",
    "https://raw.githubusercontent.com/laoma2053/awesome-zhuiju-free/main/README.md",
    "https://raw.githubusercontent.com/dongyubin/IPTV/main/README.md",
    "https://raw.githubusercontent.com/Zhou-Li-Bin/Tvbox-QingNing/main/README.md",
    "https://raw.githubusercontent.com/Newtxin/TVBoxSource/main/README.md"
]

# 高頻直連香港庫
SPECIFIC_HK_DIRECT_SOURCES = [
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hk.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_hong_kong.m3u8",
    "https://raw.githubusercontent.com/s14685/tv/main/iptvhk.txt",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/HongKong.m3u8",
    "https://epg.pw/test_channels_hong_kong.m3u",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
    "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u",
    "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv6.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/kimwang1978/collect-tv-txt/main/merged_output.txt",
    "https://raw.githubusercontent.com/ssili126/tv/main/itvlist.txt",
    "https://raw.githubusercontent.com/Fairy8o/IPTV/main/PDX-V4.txt",
    "https://raw.githubusercontent.com/Fairy8o/IPTV/main/PDX-V6.txt",
    "https://raw.githubusercontent.com/Ftindy/IPTV-URL/main/IPV6.m3u",
    "https://raw.githubusercontent.com/qingwen07/awesome-iptv/main/tvbox_live_all.txt"
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

# --- 2. 工具函數 ---

def clean_and_encode_url(url: str) -> str:
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

def process_candidate_url(target_url: str, visited: set = None, depth: int = 0) -> list:
    if visited is None:
        visited = set()
    if depth > 3:
        return []

    safe_url = clean_and_encode_url(target_url)
    if safe_url in visited:
        return []
    visited.add(safe_url)

    lower_path = urlparse(safe_url).path.lower()
    if any(lower_path.endswith(ext) for ext in ['.m3u', '.m3u8', '.txt']) and 'dc.txt' not in lower_path:
        return [safe_url]

    text = fetch_raw_content(safe_url, timeout=8)
    if not text:
        return []

    first_few_lines = text.split('\n')[:15]
    if '#EXTM3U' in text or any('#genre#' in l for l in first_few_lines) or any(',' in l and 'http' in l for l in first_few_lines):
        return [safe_url]

    data = parse_tvbox_payload(text)
    if not isinstance(data, dict):
        return []

    extracted_lives = []
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

    if 'urls' in data and isinstance(data['urls'], list):
        for sub_item in data['urls']:
            if isinstance(sub_item, dict) and 'url' in sub_item:
                sub_url = sub_item['url']
                if isinstance(sub_url, str) and sub_url.startswith('http'):
                    extracted_lives.extend(process_candidate_url(sub_url, visited, depth + 1))

    return list(set(extracted_lives))

def extract_all_sources() -> list:
    print("🌐 開始動態提取所有上游資源...", flush=True)
    all_extracted_playlists = set([clean_and_encode_url(u) for u in SPECIFIC_HK_DIRECT_SOURCES])
    candidate_urls = set()

    for readme_url in TARGET_README_URLS:
        content = fetch_raw_content(readme_url, timeout=12)
        if not content:
            continue
        raw_urls = re.findall(r'https?://[^\s#<>"\']+', content)
        for u in raw_urls:
            clean_u = u.strip().rstrip(')>],;\'"')
            if any(ext in clean_u.lower() for ext in ['.apk', '.exe', '.zip', 'shields.io', 'badge.svg', '.jpg', '.jpeg', '.gif']):
                continue
            candidate_urls.add(clean_u)

    print(f"🔍 全網共獲取到 {len(candidate_urls)} 個候選網址，開始深入解碼...", flush=True)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_candidate_url, u) for u in candidate_urls]
        for f in as_completed(futures):
            try:
                res = f.result()
                all_extracted_playlists.update(res)
            except Exception:
                pass

    final_sources = list(all_extracted_playlists)
    print(f"✅ 全部分析完畢！共聚合出 {len(final_sources)} 個直播源清單。", flush=True)
    return final_sources

# --- 3. Guovin/iptv-api 核心測速與切片驗效技術 (Speed & Delay Test) ---

def test_stream_speed(url: str, timeout: int = 5) -> tuple:
    """
    實裝 Guovin/iptv-api 測速引擎：
    1. 下載完整 M3U8 (拒絕斷章截斷)
    2. 穿透多碼率 Playlist，提取真實視頻切片 (.ts / .m4s)
    3. 實時測量 首包延遲 (Delay, ms) 與 下載吞吐速率 (Speed, MB/s)
    4. 自動識別並過濾廣告 / 無信號循環源
    """
    safe_url = clean_and_encode_url(url)
    
    # 港台官方 Akamai CDN 保護放行
    if any(d in safe_url.lower() for d in ['rthk.hk', 'akamaized.net']):
        return True, 5.0, 50.0

    t_start = time.time()
    try:
        r = requests.get(safe_url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return False, 0, float('inf')
        
        text = r.text
        # 如果不是 M3U8，直接測試首字節下載
        if '#EXTM3U' not in text:
            # 針對直接返回 TS/FLV 流的接口
            delay = (time.time() - t_start) * 1000
            speed = len(r.content) / (1024 * 1024) / max((time.time() - t_start), 0.001)
            return len(r.content) > 1024, speed, delay

        # 解析 M3U8 尋找真實視頻切片
        parsed = m3u8.loads(text)
        target_seg_url = None

        # 多碼率 Master Playlist 穿透
        if parsed.is_variant and parsed.playlists:
            sub_url = urljoin(safe_url, parsed.playlists[0].uri)
            sub_r = requests.get(sub_url, headers=HEADERS, timeout=timeout)
            if sub_r.status_code == 200:
                sub_parsed = m3u8.loads(sub_r.text)
                if sub_parsed.segments:
                    target_seg_url = urljoin(sub_url, sub_parsed.segments[0].uri)
        elif parsed.segments:
            target_seg_url = urljoin(safe_url, parsed.segments[0].uri)
        else:
            # 正則備用語法 (兼容非標準 M3U8)
            lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
            if lines:
                target_seg_url = urljoin(safe_url, lines[0])

        if not target_seg_url:
            return False, 0, float('inf')

        # 實測視頻分片傳輸速度
        t_seg_start = time.time()
        seg_res = requests.get(target_seg_url, headers=HEADERS, timeout=timeout, stream=True)
        if seg_res.status_code != 200:
            return False, 0, float('inf')

        delay = (time.time() - t_seg_start) * 1000
        bytes_read = 0
        t_download_start = time.time()

        for chunk in seg_res.iter_content(chunk_size=32768):
            bytes_read += len(chunk)
            # 讀取約 256KB 數據即完成測速 (兼顧速度與準確度)
            if bytes_read >= 256 * 1024 or (time.time() - t_download_start) >= 2.5:
                break
        seg_res.close()

        elapsed = time.time() - t_download_start
        speed = (bytes_read / (1024 * 1024)) / max(elapsed, 0.001)

        # 必須能成功拉取至少 40KB 二進位視頻才視為活源
        is_alive = bytes_read >= 40 * 1024
        return is_alive, speed, delay

    except Exception:
        return False, 0, float('inf')

def match_standard_channel_name(raw_name: str) -> str:
    """根據 Guovin 頻識別名表，精確匹配並歸一化為標準名稱"""
    clean_n = raw_name.lower().replace(" ", "").replace("-", "")
    for std_name, aliases in CHANNEL_ALIASES.items():
        for a in aliases:
            if a.lower().replace(" ", "").replace("-", "") in clean_n:
                return std_name
    return ""

def parse_single_playlist(source_url: str) -> list:
    channels = []
    content = fetch_raw_content(source_url, timeout=8)
    if not content:
        return channels

    lines = [l.strip() for l in content.split('\n') if l.strip()]
    current_raw_name = ""
    is_m3u = any(line.startswith('#EXTM3U') or line.startswith('#EXTINF') for line in lines[:10])

    for line in lines:
        if is_m3u:
            if line.startswith("#EXTINF"):
                match = re.search(r',(.+)$', line)
                if match:
                    current_raw_name = match.group(1).strip()
            elif line.startswith("http"):
                stream_url = line.split('$')[0].strip()
                if current_raw_name:
                    if not any(b.lower() in current_raw_name.lower() for b in BLOCK_KEYWORDS):
                        std_name = match_standard_channel_name(current_raw_name)
                        if std_name:
                            channels.append({"name": std_name, "raw_name": current_raw_name, "url": stream_url})
                current_raw_name = ""
        else:
            if ',' in line and not line.startswith('http'):
                parts = line.split(',', 1)
                if len(parts) == 2:
                    raw_n = parts[0].strip()
                    url_p = parts[1].split('$')[0].strip()
                    if url_p.startswith('http'):
                        if not any(b.lower() in raw_n.lower() for b in BLOCK_KEYWORDS):
                            std_name = match_standard_channel_name(raw_n)
                            if std_name:
                                channels.append({"name": std_name, "raw_name": raw_n, "url": url_p})

    return channels

# --- 4. 主執行流程 ---

def fetch_and_parse() -> list:
    found_channels = []
    seen_urls = set()

    playlist_sources = extract_all_sources()
    print(f"🚀 開始使用 20 線程並行抓取 {len(playlist_sources)} 個清單中的香港電視頻道...", flush=True)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(parse_single_playlist, s): s for s in playlist_sources}
        for f in as_completed(futures):
            try:
                ch_list = f.result()
                for ch in ch_list:
                    if ch['url'] not in seen_urls:
                        seen_urls.add(ch['url'])
                        found_channels.append(ch)
            except Exception:
                pass

    print(f"\n📊 全部解析完畢，共提取到 {len(found_channels)} 個香港電視候選串流。", flush=True)
    return found_channels

def generate_m3u(channels: list):
    print(f"\n⚡ 正在啟動【Guovin 測速引擎】：實測下載速率 (Speed) 與 延遲 (Delay)...", flush=True)
    
    # 1. 並行測速
    channel_test_results = {}
    
    def test_worker(ch):
        is_alive, speed, delay = test_stream_speed(ch['url'])
        return ch, is_alive, speed, delay

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(test_worker, ch) for ch in channels]
        for f in as_completed(futures):
            ch, is_alive, speed, delay = f.result()
            c_name = ch['name']
            if c_name not in channel_test_results:
                channel_test_results[c_name] = []
            
            if is_alive:
                channel_test_results[c_name].append({
                    "name": c_name,
                    "url": ch['url'],
                    "speed": speed,
                    "delay": delay
                })
                print(f"  🟢 [可播] {c_name} | 速率: {speed:.2f} MB/s | 延遲: {delay:.0f} ms", flush=True)
            else:
                print(f"  🔴 [不可播/逾時] {c_name}", flush=True)

    # 2. Guovin 核心排序與 Top-K 篩選策略
    final_list = []
    
    # 加入官方保底源
    for off in OFFICIAL_CHANNELS:
        final_list.append(off)

    for c_name in ORDER_KEYWORDS:
        candidates = channel_test_results.get(c_name, [])
        if not candidates:
            continue
        
        # 按照 Guovin 策略：下載速率高優先 (speed desc)，延遲低優先 (delay asc)
        candidates.sort(key=lambda x: (-x['speed'], x['delay']))
        
        # 每個頻道精選前 MAX_URLS_PER_CHANNEL 條最快線路
        selected = candidates[:MAX_URLS_PER_CHANNEL]
        for item in selected:
            # 避免重複加入官方源
            if not any(f['url'] == item['url'] for f in final_list):
                final_list.append(item)

    # 3. 輸出嚴格雙行 MoonTV / TiviMate 標準格式
    lines = ['#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml" url-tvg="https://epg.112114.xyz/pp.xml"']

    for item in final_list:
        name = item["name"]
        logo_url = f"https://epg.112114.xyz/logo/{name}.png"
        # 第 1 行：標準信息
        lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo_url}" group-title="Hong Kong",{name}')
        # 第 2 行：串流 URL (完全緊貼)
        lines.append(f'{item["url"]}')

    content = "\n".join(lines) + "\n"

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 測速與篩選完成！已精選導出 {len(final_list)} 條最高速、可秒播的香港電視頻道。", flush=True)

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
  workflow_dispatch: # 支援手動觸發

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install System FFmpeg
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg

    - name: Install Python dependencies
      run: pip install -r requirements.txt

    - name: Run script
      run: python -u main.py

    - name: Commit and push
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add hk_live.m3u
        git commit -m "Auto-update channel list [skip ci]" || echo "No changes to commit"
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
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml" url-tvg="https://epg.112114.xyz/pp.xml"
#EXTINF:-1 tvg-name="翡翠台" tvg-logo="https://epg.112114.xyz/logo/翡翠台.png" group-title="Hong Kong",翡翠台
http://r.jdshipin.com/GeWKr
#EXTINF:-1 tvg-name="翡翠台" tvg-logo="https://epg.112114.xyz/logo/翡翠台.png" group-title="Hong Kong",翡翠台
http://r.jdshipin.com/qClQf
#EXTINF:-1 tvg-name="翡翠台" tvg-logo="https://epg.112114.xyz/logo/翡翠台.png" group-title="Hong Kong",翡翠台
http://r.jdshipin.com/n90gt
#EXTINF:-1 tvg-name="翡翠台" tvg-logo="https://epg.112114.xyz/logo/翡翠台.png" group-title="Hong Kong",翡翠台
http://r.jdshipin.com/qrfbg
#EXTINF:-1 tvg-name="翡翠台" tvg-logo="https://epg.112114.xyz/logo/翡翠台.png" group-title="Hong Kong",翡翠台
http://r.jdshipin.com/62WM7
#EXTINF:-1 tvg-name="TVB翡翠台 4K" tvg-logo="https://epg.112114.xyz/logo/TVB翡翠台 4K.png" group-title="Hong Kong",TVB翡翠台 4K
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct4
#EXTINF:-1 tvg-name="TVB翡翠台（備用）" tvg-logo="https://epg.112114.xyz/logo/TVB翡翠台（備用）.png" group-title="Hong Kong",TVB翡翠台（備用）
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct
#EXTINF:-1 tvg-name="TVB翡翠台 1080P" tvg-logo="https://epg.112114.xyz/logo/TVB翡翠台 1080P.png" group-title="Hong Kong",TVB翡翠台 1080P
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct3
#EXTINF:-1 tvg-name="翡翠台北美版" tvg-logo="https://epg.112114.xyz/logo/翡翠台北美版.png" group-title="Hong Kong",翡翠台北美版
http://php.jdshipin.com:8880/TVOD/iptv.php?id=j1
#EXTINF:-1 tvg-name="無線新聞" tvg-logo="https://epg.112114.xyz/logo/無線新聞.png" group-title="Hong Kong",無線新聞
http://php.jdshipin.com/TVOD/iptv.php?id=wxxw
#EXTINF:-1 tvg-name="無線新聞" tvg-logo="https://epg.112114.xyz/logo/無線新聞.png" group-title="Hong Kong",無線新聞
https://h5cdn3.kylintv.tv/live/tvbnews_iphone.m3u8
#EXTINF:-1 tvg-name="無線新聞" tvg-logo="https://epg.112114.xyz/logo/無線新聞.png" group-title="Hong Kong",無線新聞
http://r.jdshipin.com/CkuBd
#EXTINF:-1 tvg-name="TVB明珠台" tvg-logo="https://epg.112114.xyz/logo/TVB明珠台.png" group-title="Hong Kong",TVB明珠台
http://php.jdshipin.com/TVOD/iptv.php?id=mzt
#EXTINF:-1 tvg-name="明珠台" tvg-logo="https://epg.112114.xyz/logo/明珠台.png" group-title="Hong Kong",明珠台
http://r.jdshipin.com/ZQ4kN
#EXTINF:-1 tvg-name="明珠台" tvg-logo="https://epg.112114.xyz/logo/明珠台.png" group-title="Hong Kong",明珠台
http://r.jdshipin.com/jUx8K
#EXTINF:-1 tvg-name="明珠台" tvg-logo="https://epg.112114.xyz/logo/明珠台.png" group-title="Hong Kong",明珠台
http://php.jdshipin.com/TVOD/iptv.php?id=mzt2
#EXTINF:-1 tvg-name="TVB Plus" tvg-logo="https://epg.112114.xyz/logo/TVB Plus.png" group-title="Hong Kong",TVB Plus
http://r.jdshipin.com/ndGgS
#EXTINF:-1 tvg-name="TVB Plus" tvg-logo="https://epg.112114.xyz/logo/TVB Plus.png" group-title="Hong Kong",TVB Plus
http://r.jdshipin.com/Nr5jq
#EXTINF:-1 tvg-name="Viutv" tvg-logo="https://epg.112114.xyz/logo/Viutv.png" group-title="Hong Kong",Viutv
http://php.jdshipin.com/TVOD/iptv.php?id=viutv
#EXTINF:-1 tvg-name="Viutv" tvg-logo="https://epg.112114.xyz/logo/Viutv.png" group-title="Hong Kong",Viutv
http://r.jdshipin.com/TcKr2
#EXTINF:-1 tvg-name="Viutv" tvg-logo="https://epg.112114.xyz/logo/Viutv.png" group-title="Hong Kong",Viutv
http://r.jdshipin.com/vSJvl
#EXTINF:-1 tvg-name="Viutv" tvg-logo="https://epg.112114.xyz/logo/Viutv.png" group-title="Hong Kong",Viutv
http://php.jdshipin.com/TVOD/iptv.php?id=viutv2
#EXTINF:-1 tvg-name="HOY TV" tvg-logo="https://epg.112114.xyz/logo/HOY TV.png" group-title="Hong Kong",HOY TV
http://r.jdshipin.com/sFw4S
#EXTINF:-1 tvg-name="HOY TV" tvg-logo="https://epg.112114.xyz/logo/HOY TV.png" group-title="Hong Kong",HOY TV
http://php.jdshipin.com/TVOD/iptv.php?id=hoytv
#EXTINF:-1 tvg-name="HOY TV" tvg-logo="https://epg.112114.xyz/logo/HOY TV.png" group-title="Hong Kong",HOY TV
http://uc6.i-cable.com/live_freedirect/opentvhd001_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="HOY TV" tvg-logo="https://epg.112114.xyz/logo/HOY TV.png" group-title="Hong Kong",HOY TV
https://uc6.i-cable.com/live_freedirect/opentvhd001_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="HOY TV" tvg-logo="https://epg.112114.xyz/logo/HOY TV.png" group-title="Hong Kong",HOY TV
https://uc6.i-cable.com/live_freedirect/opentvhd001.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.134:80/live_freedirect/freehd209_h.live/chunklist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.141/live_freedirect/hd110_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://cm61-10-2-140.hkcable.com.hk/live_freedirect/freehd209_h.live/chunklist_w135209556.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.141:80/live_freedirect/freehd209_h.live/chunklist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.151:80/live_freedirect/freehd209_h.live/chunklist_w1201085709.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.141/live_freedirect/freehd209_h.live/playlist.m3u
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.140/live_freedirect/opentvhd002_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://cm61-10-2-143.hkcable.com.hk/live_freedirect/freehd209_h.live/chunklist_w1949275579.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.146/live_freedirect/freehd209_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞台" tvg-logo="https://epg.112114.xyz/logo/有線新聞台.png" group-title="Hong Kong",有線新聞台
http://61.10.2.140:80/live_freedirect/freehd209_h.live/chunklist_w135209556.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.140/live_freedirect/freehd209_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://cm61-10-2-143.hkcable.com.hk/live_freedirect/hd110_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞台" tvg-logo="https://epg.112114.xyz/logo/有線新聞台.png" group-title="Hong Kong",有線新聞台
http://61.10.2.141/live_freedirect/freehd209_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞台" tvg-logo="https://epg.112114.xyz/logo/有線新聞台.png" group-title="Hong Kong",有線新聞台
http://cm61-10-2-143.hkcable.com.hk/live_freedirect/freehd209_h.live/playlist.m3u8
#EXTINF:-1 tvg-name="有線新聞" tvg-logo="https://epg.112114.xyz/logo/有線新聞.png" group-title="Hong Kong",有線新聞
http://61.10.2.140/live_freedirect/freehd209_h.live/chunklist_w135209556.m3u8
#EXTINF:-1 tvg-name="港台電視31" tvg-logo="https://epg.112114.xyz/logo/港台電視31.png" group-title="Hong Kong",港台電視31
https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8
#EXTINF:-1 tvg-name="RTHK TV 31 (港台電視31) (360p) [Geo-blocked]" tvg-logo="https://epg.112114.xyz/logo/RTHK TV 31 (港台電視31) (360p) [Geo-blocked].png" group-title="Hong Kong",RTHK TV 31 (港台電視31) (360p) [Geo-blocked]
https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/master.m3u8
#EXTINF:-1 tvg-name="港台電視31" tvg-logo="https://epg.112114.xyz/logo/港台電視31.png" group-title="Hong Kong",港台電視31
http://php.jdshipin.com:8880/TVOD/iptv.php?id=rthk31
#EXTINF:-1 tvg-name="RTHK31" tvg-logo="https://epg.112114.xyz/logo/RTHK31.png" group-title="Hong Kong",RTHK31
http://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_810_av-b.m3u8
#EXTINF:-1 tvg-name="RTHK31" tvg-logo="https://epg.112114.xyz/logo/RTHK31.png" group-title="Hong Kong",RTHK31
http://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8
#EXTINF:-1 tvg-name="港台電視32" tvg-logo="https://epg.112114.xyz/logo/港台電視32.png" group-title="Hong Kong",港台電視32
https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 tvg-name="RTHK TV 32 (港台電視32) (360p) [Geo-blocked]" tvg-logo="https://epg.112114.xyz/logo/RTHK TV 32 (港台電視32) (360p) [Geo-blocked].png" group-title="Hong Kong",RTHK TV 32 (港台電視32) (360p) [Geo-blocked]
https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/master.m3u8
#EXTINF:-1 tvg-name="港台電視32" tvg-logo="https://epg.112114.xyz/logo/港台電視32.png" group-title="Hong Kong",港台電視32
http://php.jdshipin.com:8880/TVOD/iptv.php?id=rthk32
#EXTINF:-1 tvg-name="RTHK32" tvg-logo="https://epg.112114.xyz/logo/RTHK32.png" group-title="Hong Kong",RTHK32
http://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 tvg-name="RTHK32" tvg-logo="https://epg.112114.xyz/logo/RTHK32.png" group-title="Hong Kong",RTHK32
http://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8
#EXTINF:-1 tvg-name="RTHK TV 33 (港台電視33) (1080p) [Geo-blocked]" tvg-logo="https://epg.112114.xyz/logo/RTHK TV 33 (港台電視33) (1080p) [Geo-blocked].png" group-title="Hong Kong",RTHK TV 33 (港台電視33) (1080p) [Geo-blocked]
https://rthktv33-live.akamaized.net/hls/live/2101641/RTHKTV33/master.m3u8
#EXTINF:-1 tvg-name="RTHK TV 34 (港台電視34) (1080p) [Geo-blocked]" tvg-logo="https://epg.112114.xyz/logo/RTHK TV 34 (港台電視34) (1080p) [Geo-blocked].png" group-title="Hong Kong",RTHK TV 34 (港台電視34) (1080p) [Geo-blocked]
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/master.m3u8
#EXTINF:-1 tvg-name="RTHK TV 35 (港台電視35) (1080p) [Geo-blocked]" tvg-logo="https://epg.112114.xyz/logo/RTHK TV 35 (港台電視35) (1080p) [Geo-blocked].png" group-title="Hong Kong",RTHK TV 35 (港台電視35) (1080p) [Geo-blocked]
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/master.m3u8
#EXTINF:-1 tvg-name="RTHK TV 36 (港台電視36) (1080p) [Geo-blocked]" tvg-logo="https://epg.112114.xyz/logo/RTHK TV 36 (港台電視36) (1080p) [Geo-blocked].png" group-title="Hong Kong",RTHK TV 36 (港台電視36) (1080p) [Geo-blocked]
https://rthktv36-live.akamaized.net/hls/live/2112176/RTHKTV36/master.m3u8
#EXTINF:-1 tvg-name="港台電視33" tvg-logo="https://epg.112114.xyz/logo/港台電視33.png" group-title="Hong Kong",港台電視33
https://rthktv33-live.akamaized.net/hls/live/2101641/RTHKTV33/stream05/streamPlaylist.m3u8?
#EXTINF:-1 tvg-name="港台電視34" tvg-logo="https://epg.112114.xyz/logo/港台電視34.png" group-title="Hong Kong",港台電視34
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/stream04/streamPlaylist.m3u8?
#EXTINF:-1 tvg-name="港台電視34" tvg-logo="https://epg.112114.xyz/logo/港台電視34.png" group-title="Hong Kong",港台電視34
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/stream05/streamPlaylist.m3u8?
#EXTINF:-1 tvg-name="港台電視35" tvg-logo="https://epg.112114.xyz/logo/港台電視35.png" group-title="Hong Kong",港台電視35
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/stream04/streamPlaylist.m3u8?
#EXTINF:-1 tvg-name="港台電視35" tvg-logo="https://epg.112114.xyz/logo/港台電視35.png" group-title="Hong Kong",港台電視35
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/stream05/streamPlaylist.m3u8?
#EXTINF:-1 tvg-name="RTHK3" tvg-logo="https://epg.112114.xyz/logo/RTHK3.png" group-title="Hong Kong",RTHK3
https://rthkradio3-live.akamaized.net/hls/live/2040079/radio3/master.m3u8
#EXTINF:-1 tvg-name="RTHK普通話" tvg-logo="https://epg.112114.xyz/logo/RTHK普通話.png" group-title="Hong Kong",RTHK普通話
https://rthkradiopth-live.akamaized.net/hls/live/2040082/radiopth/master.m3u8

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

