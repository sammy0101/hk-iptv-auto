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
