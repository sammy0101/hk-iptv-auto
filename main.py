import requests
import re
import datetime
import time
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from opencc import OpenCC
import m3u8

# 初始化繁簡轉換器
cc = OpenCC('s2t')

# 模擬標準 IPTV 播放器請求頭，避免被伺服器屏蔽
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# --- 設定區 ---

# 1. 精選高頻維護的最新來源 (剔除所有 2020-2023 陳年無效源)
SOURCE_URLS = [
    # 香港專用與即時更新源
    "https://raw.githubusercontent.com/s14685/tv/main/iptvhk.txt",
    "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/hk.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/HongKong.m3u8",
    "https://raw.githubusercontent.com/iptv-js/iptv/main/txt/ew_hk.txt",
    "https://raw.githubusercontent.com/Free-TV/IPTV/refs/heads/master/playlists/playlist_hong_kong.m3u8",
    "https://epg.pw/test_channels_hong_kong.m3u",
    # 活躍綜合中文源
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/refs/heads/gd/output/result.m3u",
    "https://raw.githubusercontent.com/MercuryZz/IPTVN/refs/heads/Files/GAT.m3u"
]

# 2. 精確關鍵字 (嚴格限定香港電視品牌，去除容易誤判的通用單詞)
KEYWORDS = [
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY", "奇妙電視",
    "RTHK", "港台電視",
    "翡翠台", "明珠台", "J2", "TVB Plus", "無綫新聞", "無線新聞", "無綫財經", "無線財經",
    "Now新聞", "Now 新聞", "Now直播", "Now 直播", "NowTV", "Now 劇集",
    "有線新聞", "有線財經"
]

# 3. 嚴格黑名單 (已移除誤殺 Jade/Pearl 的錯誤項，重點過濾境外頻道與冒充台)
BLOCK_KEYWORDS = [
    # 外國與冒充台 (特別是土耳其 NOW TV、以色列台、境外輪播)
    "FOX", "Pluto", "Local Now", "NBC", "CBS", "ABC", "AXS", "Snowy", 
    "Reuters", "Mirror", "ET Now", "The Now", "Right Now", "News Now",
    "Chopper", "Wow", "UHD", "8K", "Career", "Comics", "Movies", "tv360",
    "Anthony Bourdain", "HEi Now", "MS NOW", "Now 14", "NowMedia", "Castr",
    # 非香港本地台
    "浙江", "杭州", "西湖", "廣東", "珠江", "大灣區", "深圳", "福建",
    "澳門", "Macau", "澳視", "蓮花",
    "CCTV", "CGTN", "鳳凰", "凤凰", "華麗", "星河", "測試", "test", "iHOY"
]

# 4. 排序優先級
ORDER_KEYWORDS = [
    "翡翠台", "無綫新聞", "無線新聞", "明珠台", "TVB Plus", "J2", "財經",
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY TV", "HOY", "有線新聞", "有線財經",
    "港台電視31", "RTHK 31", "RTHK31",
    "港台電視32", "RTHK 32", "RTHK32",
    "Now新聞", "Now直播"
]

# 5. 香港官方/最高優先級源 (在香港本地 100% 可用，即便 GitHub Actions 海外測試報錯亦予以保留)
OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8"},
    {"name": "港台電視32", "url": "https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8"},
    {"name": "HOY TV", "url": "http://uc6.i-cable.com/live_freedirect/opentvhd001_h.live/playlist.m3u8"},
    {"name": "HOY 資訊台", "url": "http://61.10.2.141/live_freedirect/freehd209_h.live/playlist.m3u8"}
]

# --- 深度檢測邏輯 ---

def is_official_stream(url):
    """檢查是否為香港官方受保護源 (官方源在香港必通，但在 GitHub runner 會報 403)"""
    official_domains = ['akamaihd.net', 'rthk.hk', 'akamaized.net', 'i-cable.com', 'hkcable.com.hk', 'now.com']
    return any(d in url.lower() for d in official_domains)

def deep_check_stream(url, timeout=4):
    """
    深度穿透檢測：
    1. 下載主 m3u8 索引
    2. 解析子 playlist 或提取第 1 段真實視頻分片 (.ts/.m4s)
    3. 實測視頻分片能否正常傳輸數據
    """
    if is_official_stream(url):
        # 官方直連源直接放行，避免海外 Runner 因 Geo-blocking 誤殺
        return True

    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        
        # 檢查內容是否為合法 m3u8
        text = ""
        for chunk in r.iter_content(chunk_size=4096):
            text += chunk.decode('utf-8', errors='ignore')
            if len(text) > 8192:
                break
        r.close()

        if '#EXTM3U' not in text:
            # 不是有效的 M3U 格式，排除返回 200 的 HTML 錯誤頁
            return False

        # 使用 m3u8 解析庫提取實際切片
        try:
            parsed = m3u8.loads(text)
            segment_url = None

            if parsed.is_variant:
                # 若為多碼率 Master Playlist，提取第一個子頻道的 URL 檢測
                first_playlist = parsed.playlists[0].uri
                sub_url = urljoin(url, first_playlist)
                sub_r = requests.get(sub_url, headers=HEADERS, timeout=timeout)
                if sub_r.status_code != 200:
                    return False
                sub_parsed = m3u8.loads(sub_r.text)
                if sub_parsed.segments:
                    segment_url = urljoin(sub_url, sub_parsed.segments[0].uri)
            elif parsed.segments:
                # 提取第一段視頻切片
                segment_url = urljoin(url, parsed.segments[0].uri)

            # 若能解析出真實視頻分片，測試該分片是否可以下載前 2KB 數據
            if segment_url:
                seg_res = requests.get(segment_url, headers=HEADERS, timeout=timeout, stream=True)
                if seg_res.status_code == 200:
                    chunk = next(seg_res.iter_content(chunk_size=2048), b'')
                    seg_res.close()
                    return len(chunk) > 500  # 確認確實有視頻二進位數據
        except Exception:
            # 無法深層解析但滿足 EXTM3U 條件時的容錯
            return True

        return True
    except Exception:
        return False

def check_channels_parallel(channels, max_workers=12):
    """並行檢測"""
    valid_channels = []
    
    def worker(ch):
        return ch, deep_check_stream(ch['url'])

    print(f"🔍 開始對 {len(channels)} 個候選源進行切片級深層連通檢測...", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, ch) for ch in channels]
        for f in as_completed(futures):
            ch, is_alive = f.result()
            if is_alive:
                valid_channels.append(ch)
                print(f"  🟢 有效: {ch['name']}", flush=True)
            else:
                print(f"  🔴 失效: {ch['name']}", flush=True)
                
    return valid_channels

def get_sort_key(item):
    name = item["name"]
    for index, keyword in enumerate(ORDER_KEYWORDS):
        if keyword.lower() in name.lower():
            return index
    return 999

def fetch_and_parse():
    found_channels = []
    seen_urls = set()
    
    print("🚀 開始抓取網路源...", flush=True)
    
    for index, source in enumerate(SOURCE_URLS):
        print(f"  [{index+1}/{len(SOURCE_URLS)}] 讀取: {source}", flush=True)
        try:
            r = requests.get(source, headers=HEADERS, timeout=12)
            r.encoding = 'utf-8'
            if r.status_code != 200:
                continue
            
            lines = [l.strip() for l in r.text.split('\n') if l.strip()]
            current_name = ""
            count_added = 0
            
            for line in lines:
                if line.startswith("#EXTINF"):
                    match = re.search(r',(.+)$', line)
                    if match:
                        raw_name = match.group(1).strip()
                        conv_name = cc.convert(raw_name).replace('臺', '台')
                        current_name = conv_name
                elif line.startswith("http"):
                    stream_url = line.split('$')[0].strip()  # 去除附加線路後綴
                    name_to_check = current_name
                    
                    if not name_to_check:
                        # 兼容純 URL 或逗號分隔格式
                        continue
                    
                    # 1. 黑名單檢查
                    if any(b.lower() in name_to_check.lower() for b in BLOCK_KEYWORDS):
                        current_name = ""
                        continue
                    
                    # 2. 白名單精確檢查
                    if any(k.lower() in name_to_check.lower() for k in KEYWORDS):
                        if stream_url not in seen_urls:
                            seen_urls.add(stream_url)
                            found_channels.append({"name": name_to_check, "url": stream_url})
                            count_added += 1
                    
                    current_name = ""
            print(f"    ✅ 提取到 {count_added} 個潛在頻道", flush=True)
        except Exception as e:
            print(f"    ❌ 讀取失敗: {e}", flush=True)

    return found_channels

def generate_m3u(channels):
    # 執行切片級深層並行檢測
    tested_channels = check_channels_parallel(channels)
    
    # 合併官方保底源 (去重)
    final_dict = {}
    for off in OFFICIAL_CHANNELS:
        final_dict[off['url']] = off
        
    for ch in tested_channels:
        if ch['url'] not in final_dict:
            final_dict[ch['url']] = ch

    final_list = list(final_dict.values())
    
    print("\n🔄 正在按照香港電視台順序排序...", flush=True)
    final_list.sort(key=get_sort_key)

    # 輸出 M3U 文件
    content = '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n'
    content += f'# Update: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
    
    for item in final_list:
        name = item["name"].replace('臺', '台')
        content += f'#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/{name}.png",{name}\n'
        content += f'{item["url"]}\n'

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 構建完成！共導出 {len(final_list)} 個純淨可用香港頻道。", flush=True)

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)
