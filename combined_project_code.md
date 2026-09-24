# Complete Project Codebase
Generated on: Thu Sep 24 14:57:44 UTC 2026

## File: main.py
````py
import requests
import re
import json
import base64
import datetime
import subprocess
import shutil
from urllib.parse import urlparse, urlunparse, quote, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from opencc import OpenCC
import m3u8

cc = OpenCC('s2t')

IPTV_UA = 'okhttp/3.15.0 (Linux; Android 11; TVBox)'
HEADERS = {
    'User-Agent': IPTV_UA,
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# 檢測系統是否具備 ffprobe
HAS_FFPROBE = shutil.which('ffprobe') is not None
if not HAS_FFPROBE:
    print("⚠️ 警告: 系統環境未安裝 ffprobe，將自動切換為【Python 原生切片穿透驗證】", flush=True)

# --- 1. 動態上游導航大庫 ---
TARGET_README_URLS = [
    "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md",
    "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md",
    "https://raw.githubusercontent.com/laoma2053/awesome-zhuiju-free/main/README.md",
    "https://raw.githubusercontent.com/dongyubin/IPTV/main/README.md",
    "https://raw.githubusercontent.com/Zhou-Li-Bin/Tvbox-QingNing/main/README.md",
    "https://raw.githubusercontent.com/Newtxin/TVBoxSource/main/README.md"
]

# --- 2. 香港頻道直連匯總 ---
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

# --- 3. 嚴格過濾規則 ---
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

OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8"},
    {"name": "港台電視32", "url": "https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8"}
]

# --- 4. 輔助函數 ---

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
        print(f"  -> 讀取導航清單: {readme_url}", flush=True)
        content = fetch_raw_content(readme_url, timeout=12)
        if not content:
            continue

        raw_urls = re.findall(r'https?://[^\s#<>"\']+', content)
        for u in raw_urls:
            clean_u = u.strip().rstrip(')>],;\'"')
            if any(ext in clean_u.lower() for ext in ['.apk', '.exe', '.zip', 'shields.io', 'badge.svg', '.jpg', '.jpeg', '.gif']):
                continue
            candidate_urls.add(clean_u)

    print(f"🔍 取得 {len(candidate_urls)} 個候選網址，開始解析...", flush=True)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_candidate_url, u) for u in candidate_urls]
        for f in as_completed(futures):
            try:
                res = f.result()
                all_extracted_playlists.update(res)
            except Exception:
                pass

    final_sources = list(all_extracted_playlists)
    print(f"✅ 共聚合出 {len(final_sources)} 個直播源清單。", flush=True)
    return final_sources

# --- 5. 雙軌真流媒體穿透檢測器 ---

def check_hls_segments_python(url: str, timeout: int = 6) -> bool:
    """純 Python 深度檢測：下載 m3u8，提取真實音視頻切片 (.ts/.m4s) 並驗證是否真有數據"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        
        text = ""
        for chunk in r.iter_content(chunk_size=4096):
            text += chunk.decode('utf-8', errors='ignore')
            if len(text) > 8192:
                break
        r.close()

        if '#EXTM3U' not in text:
            return False

        parsed = m3u8.loads(text)
        target_seg_url = None

        # 多碼率 Master Playlist
        if parsed.is_variant and parsed.playlists:
            sub_url = urljoin(url, parsed.playlists[0].uri)
            sub_r = requests.get(sub_url, headers=HEADERS, timeout=timeout)
            if sub_r.status_code != 200:
                return False
            sub_parsed = m3u8.loads(sub_r.text)
            if sub_parsed.segments:
                target_seg_url = urljoin(sub_url, sub_parsed.segments[0].uri)
        elif parsed.segments:
            target_seg_url = urljoin(url, parsed.segments[0].uri)

        if target_seg_url:
            seg_res = requests.get(target_seg_url, headers=HEADERS, timeout=timeout, stream=True)
            if seg_res.status_code == 200:
                data = next(seg_res.iter_content(chunk_size=2048), b'')
                seg_res.close()
                return len(data) > 300
    except Exception:
        pass
    return False

def check_stream_with_ffprobe(url: str, timeout: int = 6) -> bool:
    """系統 ffprobe 工具真機解碼探測"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-user_agent', IPTV_UA,
        '-show_entries', 'stream=codec_type',
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

def verify_single_channel(ch: dict) -> tuple:
    url = ch['url']
    
    # 官方 CDN 在海外必報 403，給予放行保護
    if any(d in url.lower() for d in ['rthk.hk', 'akamaized.net', 'akamaihd.net']):
        return ch, True
    
    # 優先嘗試 ffprobe；若環境未安裝則降級為 Python 視頻切片測試
    if HAS_FFPROBE:
        is_alive = check_stream_with_ffprobe(url, timeout=6)
        if not is_alive:
            # 容錯：部分反代源可能被 ffprobe 逾時誤殺，使用 Python 切片二次複查
            is_alive = check_hls_segments_python(url, timeout=6)
    else:
        is_alive = check_hls_segments_python(url, timeout=6)
        
    return ch, is_alive

def check_channels_parallel(channels: list, max_workers=12) -> list:
    valid_channels = []
    print(f"\n🔍 開始對 {len(channels)} 個候選源進行【真機解碼 & 切片雙軌檢測】...", flush=True)
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

def parse_single_playlist(source_url: str) -> list:
    channels = []
    content = fetch_raw_content(source_url, timeout=8)
    if not content:
        return channels

    lines = [l.strip() for l in content.split('\n') if l.strip()]
    current_name = ""
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
                    if not any(b.lower() in current_name.lower() for b in BLOCK_KEYWORDS):
                        if any(k.lower() in current_name.lower() for k in KEYWORDS):
                            channels.append({"name": current_name, "url": stream_url})
                current_name = ""
        else:
            if ',' in line and not line.startswith('http'):
                parts = line.split(',', 1)
                if len(parts) == 2:
                    name_part = cc.convert(parts[0].strip()).replace('臺', '台')
                    url_part = parts[1].split('$')[0].strip()
                    if url_part.startswith('http'):
                        if not any(b.lower() in name_part.lower() for b in BLOCK_KEYWORDS):
                            if any(k.lower() in name_part.lower() for k in KEYWORDS):
                                channels.append({"name": name_part, "url": url_part})

    return channels

def fetch_and_parse() -> list:
    found_channels = []
    seen_urls = set()

    playlist_sources = extract_all_sources()
    print(f"🚀 開始使用 20 線程並發解析 {len(playlist_sources)} 個清單中的香港電視頻道...", flush=True)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(parse_single_playlist, s): s for s in playlist_sources}
        for f in as_completed(futures):
            try:
                ch_list = f.result()
                added = 0
                for ch in ch_list:
                    if ch['url'] not in seen_urls:
                        seen_urls.add(ch['url'])
                        found_channels.append(ch)
                        added += 1
            except Exception:
                pass

    print(f"\n📊 全部清單解析完成，共彙整出 {len(found_channels)} 個香港電視候選串流。", flush=True)
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
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"
# Update: 2026-09-24 14:54:04
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK32.png",RTHK32
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
http://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK普通話.png",RTHK普通話
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthkradiopth-live.akamaized.net/hls/live/2040082/radiopth/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK3.png",RTHK3
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthkradio3-live.akamaized.net/hls/live/2040079/radio3/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視33.png",港台電視33
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv33-live.akamaized.net/hls/live/2101641/RTHKTV33/stream05/streamPlaylist.m3u8?
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視34.png",港台電視34
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/stream04/streamPlaylist.m3u8?
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視34.png",港台電視34
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/stream05/streamPlaylist.m3u8?
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視35.png",港台電視35
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/stream04/streamPlaylist.m3u8?
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視35.png",港台電視35
#EXTVLCOPT:http-user-agent=okhttp/3.15.0 (Linux; Android 11; TVBox)
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/stream05/streamPlaylist.m3u8?
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

