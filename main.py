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

# 最終輸出的頻道順序 (按照香港收視習慣)
ORDER_KEYWORDS = [
    "翡翠台", "無綫新聞台", "明珠台", "TVB Plus", "無綫財經體育資訊台",
    "ViuTV", "ViuTVsix",
    "HOY TV", "HOY 資訊台",
    "港台電視31", "港台電視32",
    "Now新聞台", "Now直播台", "有線新聞台"
]

# 每個頻道保留測速最快的前 N 條線路
MAX_URLS_PER_CHANNEL = 4

# 香港官方高保真源保底
OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8"},
    {"name": "港台電視32", "url": "https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8"}
]

# 上游導航大庫清單 (動態解碼單倉/多倉)
TARGET_README_URLS = [
    "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md",
    "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md",
    "https://raw.githubusercontent.com/laoma2053/awesome-zhuiju-free/main/README.md",
    "https://raw.githubusercontent.com/dongyubin/IPTV/main/README.md",
    "https://raw.githubusercontent.com/Zhou-Li-Bin/Tvbox-QingNing/main/README.md",
    "https://raw.githubusercontent.com/Newtxin/TVBoxSource/main/README.md"
]

# 高頻直連清單 (已加入 iptv-org 全球總匯庫)
SPECIFIC_HK_DIRECT_SOURCES = [
    # iptv-org 全球總匯庫 (新增) 與香港分區庫
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hk.m3u",
    
    # 國際與專屬分區
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_hong_kong.m3u8",
    "https://raw.githubusercontent.com/s14685/tv/main/iptvhk.txt",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/HongKong.m3u8",
    "https://epg.pw/test_channels_hong_kong.m3u",
    
    # 社群大佬高頻維護源
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

def fetch_raw_content(url: str, timeout: int = 15) -> str:
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

# --- 3. Guovin/iptv-api 測速與分片驗證引擎 ---

def test_stream_speed(url: str, timeout: int = 5) -> tuple:
    safe_url = clean_and_encode_url(url)
    
    if any(d in safe_url.lower() for d in ['rthk.hk', 'akamaized.net']):
        return True, 5.0, 50.0

    t_start = time.time()
    try:
        r = requests.get(safe_url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return False, 0, float('inf')
        
        text = r.text
        if '#EXTM3U' not in text:
            delay = (time.time() - t_start) * 1000
            speed = len(r.content) / (1024 * 1024) / max((time.time() - t_start), 0.001)
            return len(r.content) > 1024, speed, delay

        parsed = m3u8.loads(text)
        target_seg_url = None

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
            lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
            if lines:
                target_seg_url = urljoin(safe_url, lines[0])

        if not target_seg_url:
            return False, 0, float('inf')

        t_seg_start = time.time()
        seg_res = requests.get(target_seg_url, headers=HEADERS, timeout=timeout, stream=True)
        if seg_res.status_code != 200:
            return False, 0, float('inf')

        delay = (time.time() - t_seg_start) * 1000
        bytes_read = 0
        t_download_start = time.time()

        for chunk in seg_res.iter_content(chunk_size=32768):
            bytes_read += len(chunk)
            if bytes_read >= 256 * 1024 or (time.time() - t_download_start) >= 2.5:
                break
        seg_res.close()

        elapsed = time.time() - t_download_start
        speed = (bytes_read / (1024 * 1024)) / max(elapsed, 0.001)

        is_alive = bytes_read >= 40 * 1024
        return is_alive, speed, delay

    except Exception:
        return False, 0, float('inf')

def match_standard_channel_name(raw_name: str) -> str:
    clean_n = raw_name.lower().replace(" ", "").replace("-", "")
    for std_name, aliases in CHANNEL_ALIASES.items():
        for a in aliases:
            if a.lower().replace(" ", "").replace("-", "") in clean_n:
                return std_name
    return ""

def parse_single_playlist(source_url: str) -> list:
    channels = []
    content = fetch_raw_content(source_url, timeout=12)
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

    final_list = []
    
    # 官方保底源優先置頂
    for off in OFFICIAL_CHANNELS:
        final_list.append(off)

    for c_name in ORDER_KEYWORDS:
        candidates = channel_test_results.get(c_name, [])
        if not candidates:
            continue
        
        # Guovin 排序策略：速率快優先，延遲低優先
        candidates.sort(key=lambda x: (-x['speed'], x['delay']))
        
        # 每個頻道精選前 MAX_URLS_PER_CHANNEL 條最快線路
        selected = candidates[:MAX_URLS_PER_CHANNEL]
        for item in selected:
            if not any(f['url'] == item['url'] for f in final_list):
                final_list.append(item)

    # 輸出嚴格雙行 MoonTV / TiviMate 標準格式
    lines = ['#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml" url-tvg="https://epg.112114.xyz/pp.xml"']

    for item in final_list:
        name = item["name"]
        logo_url = f"https://epg.112114.xyz/logo/{name}.png"
        lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo_url}" group-title="Hong Kong",{name}')
        lines.append(f'{item["url"]}')

    content = "\n".join(lines) + "\n"

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 測速與篩選完成！已精選導出 {len(final_list)} 條最高速、可秒播的香港電視頻道。", flush=True)

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)
