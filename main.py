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
