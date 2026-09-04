import requests
import re
import json
import base64
import datetime
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from opencc import OpenCC
import m3u8

# 初始化繁簡轉換器
cc = OpenCC('s2t')

# 模擬標準播放器請求頭
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# --- 1. 自動同步上游倉庫設定 ---
YOUHUNWL_README_URL = "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md"

# 兜底靜態直播源 (當上游暫時無法連線時使用，已涵蓋你提供的所有在線源)
FALLBACK_STANDARD_SOURCES = [
    # 推薦在線源
    "https://www.iyouhun.com/tv/zb",
    "https://live.zbds.top/tv/iptv4.txt",
    "https://live.zbds.top/tv/iptv4.m3u",
    "https://develop202.github.io/migu_video/interface.txt",
    "https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.txt",
    "https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv6/result.m3u",
    "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u",
    "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv6.m3u",
    # 純 IPv4 / IPv6
    "https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/master/TV-IPV4.m3u",
    "https://raw.githubusercontent.com/vamoschuck/TV/main/M3U",
    "https://live.zbds.top/tv/iptv6.txt",
    "https://live.zbds.top/tv/iptv6.m3u",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://live.fanmingming.cn/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://gitee.com/xxy002/zhiboyuan/raw/master/dsy",
    # 集合與部分海外
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/BigBigGrandG/IPTV-URL/release/Gather.m3u",
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://epg.pw/test_channels_hong_kong.m3u",
    "https://epg.pw/test_channels_taiwan.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://iptv-org.github.io/iptv/countries/hk.m3u"
]

# 兜底 TVBox 倉庫接口 (單倉 + 多倉)
FALLBACK_TVBOX_CONFIGS = [
    "http://www.饭太硬.net/tv",
    "http://肥猫.net",
    "http://我不是.摸鱼儿.top",
    "http://tvbox.王二小放牛娃.top",
    "https://9280.kstore.vip/newwex.json",
    "https://17264.kstore.space/哈基米.png",
    "https://www.yingm.cc/dm/dm.json",
    "http://home.jundie.top:81/top98.json",
    "http://cdn.qiaoji8.com/tvbox.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://gitee.com/free-kingdom/dc/raw/main/T4.json",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://tv.菜妮丝.top",
    "https://api.hgyx.vip/hgyx.json",
    "https://dxawi.github.io/0/0.json",
    "http://xhztv.top/xhz",
    "http://xhztv.top/4k.json",
    "https://9877.kstore.space/ONE/one.json",
    "https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json",
    "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://xn--anna-wn6lw489o.v.nxog.top/m/",
    "https://www.252035.xyz/z/FongMi.json",
    "http://www.meowtv.vip/tvbox.json",
    "http://fmys.top/fmys.json",
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://raw.githubusercontent.com/maoystv/6/main/000.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config",
    "https://android.lushunming.qzz.io/json/index.json",
    "https://gitee.com/cpu-iy/iy/raw/master/%E5%A4%A9%E7%A5%9EIY.json",
    "https://www.iyouhun.com/tv/dc",
    "https://www.iyouhun.com/tv/yh",
    "https://9877.kstore.space/AnotherDS/api.json",
    "http://xhztv.top/dc/",
    "http://xhztv.top/DC.txt",
    "http://xmbjm.fh4u.org/dc.txt"
]

# --- 2. 頻道過濾與排序設定 ---

# 嚴格鎖定香港電視台品牌
KEYWORDS = [
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY", "奇妙電視",
    "RTHK", "港台電視",
    "翡翠台", "明珠台", "J2", "TVB Plus", "無綫新聞", "無線新聞", "無綫財經", "無線財經",
    "Now新聞", "Now 新聞", "Now直播", "Now 直播", "NowTV", "Now 劇集",
    "有線新聞", "有線財經"
]

# 黑名單：過濾斗魚/虎牙/B站/大陸/日韓/海外無關台
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

# 香港本地官方直連保底
OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8"},
    {"name": "港台電視32", "url": "https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8"},
    {"name": "HOY TV", "url": "http://uc6.i-cable.com/live_freedirect/opentvhd001_h.live/playlist.m3u8"},
    {"name": "HOY 資訊台", "url": "http://61.10.2.141/live_freedirect/freehd209_h.live/playlist.m3u8"}
]

# --- 輔助模組 ---

def encode_punycode_url(url):
    """將中文域名安全轉為 Punycode 格式"""
    try:
        parts = urlparse(url)
        netloc = parts.netloc.encode('idna').decode('ascii')
        return urlunparse((parts.scheme, netloc, parts.path, parts.params, parts.query, parts.fragment))
    except Exception:
        return url

def sync_from_youhunwl_tvapp():
    """
    動態爬取 youhunwl/TVAPP 最新 README.md，
    自動提取單倉、多倉以及所有直連直播源 URL
    """
    print("🌐 正在向 youhunwl/TVAPP 同步最新資源清單...", flush=True)
    live_sources = set(FALLBACK_STANDARD_SOURCES)
    tvbox_configs = set(FALLBACK_TVBOX_CONFIGS)

    try:
        r = requests.get(YOUHUNWL_README_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            content = r.text
            # 正則提取所有 http/https 鏈接 (自動忽略行尾註釋如 # 游魂直播源)
            extracted_links = re.findall(r'https?://[^\s#<>"\']+', content)
            
            new_sources = 0
            new_configs = 0
            for link in extracted_links:
                link = link.strip()
                # 排除非源鏈接 (如 github 倉庫、apk 下載、圖片 logo)
                if any(ext in link.lower() for ext in ['.apk', '.exe', '.zip', 'github.com/youhunwl', 'shields.io', '.jpg']):
                    continue

                if any(link.lower().endswith(ext) for ext in ['.m3u', '.m3u8', '.txt']) or '/m3u/' in link:
                    if link not in live_sources:
                        live_sources.add(link)
                        new_sources += 1
                else:
                    # 推測為 TVBox 配置 (json, png 或帶路徑的倉接口)
                    if link not in tvbox_configs:
                        tvbox_configs.add(link)
                        new_configs += 1

            print(f"  ✅ 同步成功！從 youhunwl 額外獲取到 {new_sources} 個直播源，{new_configs} 個影視倉接口", flush=True)
        else:
            print(f"  ⚠️ 上游請求失敗 (HTTP {r.status_code})，無縫啟用本地備份源", flush=True)
    except Exception as e:
        print(f"  ⚠️ 連線異常: {e}，無縫啟用本地備份源", flush=True)

    return list(live_sources), list(tvbox_configs)

def extract_tvbox_lives(target_url, visited=None):
    """解碼 TVBox 單倉/多倉 (支援 Base64、PNG 偽裝、多倉遞迴)"""
    if visited is None:
        visited = set()

    real_url = encode_punycode_url(target_url)
    if real_url in visited:
        return []
    visited.add(real_url)

    live_urls = []
    try:
        r = requests.get(real_url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return []
        
        text = r.text.strip()
        if text.startswith('**') or not (text.startswith('{') or text.startswith('[')):
            clean_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', text)
            try:
                decoded = base64.b64decode(clean_b64).decode('utf-8', errors='ignore')
                if '{' in decoded:
                    text = decoded[decoded.find('{'):decoded.rfind('}')+1]
            except Exception:
                pass

        data = json.loads(text)

        if isinstance(data, dict):
            # 提取 lives
            if 'lives' in data and isinstance(data['lives'], list):
                for item in data['lives']:
                    if isinstance(item, dict):
                        l_url = item.get('url')
                        if l_url and isinstance(l_url, str) and l_url.startswith('http'):
                            live_urls.append(l_url)
                        elif 'channels' in item and isinstance(item['channels'], list):
                            for sub in item['channels']:
                                for u in sub.get('urls', []):
                                    if isinstance(u, str) and u.startswith('http'):
                                        live_urls.append(u)

            # 多倉遞迴解析
            if 'urls' in data and isinstance(data['urls'], list):
                for sub_item in data['urls']:
                    if isinstance(sub_item, dict) and 'url' in sub_item:
                        sub_url = sub_item['url']
                        if sub_url.startswith('http') and len(visited) < 35:
                            live_urls.extend(extract_tvbox_lives(sub_url, visited))
    except Exception:
        pass

    return list(set(live_urls))

# --- 流媒體深度檢測器 ---

def is_official_stream(url):
    official_domains = ['akamaihd.net', 'rthk.hk', 'akamaized.net', 'i-cable.com', 'hkcable.com.hk', 'now.com']
    return any(d in url.lower() for d in official_domains)

def deep_check_stream(url, timeout=4):
    if is_official_stream(url):
        return True

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

        try:
            parsed = m3u8.loads(text)
            segment_url = None

            if parsed.is_variant and parsed.playlists:
                first_playlist = parsed.playlists[0].uri
                sub_url = requests.compat.urljoin(url, first_playlist)
                sub_r = requests.get(sub_url, headers=HEADERS, timeout=timeout)
                if sub_r.status_code != 200:
                    return False
                sub_parsed = m3u8.loads(sub_r.text)
                if sub_parsed.segments:
                    segment_url = requests.compat.urljoin(sub_url, sub_parsed.segments[0].uri)
            elif parsed.segments:
                segment_url = requests.compat.urljoin(url, parsed.segments[0].uri)

            if segment_url:
                seg_res = requests.get(segment_url, headers=HEADERS, timeout=timeout, stream=True)
                if seg_res.status_code == 200:
                    chunk = next(seg_res.iter_content(chunk_size=2048), b'')
                    seg_res.close()
                    return len(chunk) > 500
        except Exception:
            return True

        return True
    except Exception:
        return False

def check_channels_parallel(channels, max_workers=12):
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

# --- 主提取執行流程 ---

def fetch_and_parse():
    found_channels = []
    seen_urls = set()

    # 1. 自動從 youhunwl/TVAPP 同步所有線上直連源與影視倉
    dynamic_sources, dynamic_configs = sync_from_youhunwl_tvapp()

    # 2. 解析影視倉獲取隱藏直播源列表
    print("📦 正在解析影視倉內部直播源...", flush=True)
    for conf in dynamic_configs:
        extracted = extract_tvbox_lives(conf)
        if extracted:
            dynamic_sources.extend(extracted)

    dynamic_sources = list(set(dynamic_sources))
    print(f"🚀 清單彙整完畢，共獲取 {len(dynamic_sources)} 個直播源列表，開始檢索香港電視頻道...", flush=True)

    # 3. 逐一提取頻道並進行繁簡轉換與關鍵字過濾
    for index, source in enumerate(dynamic_sources):
        try:
            r = requests.get(encode_punycode_url(source), headers=HEADERS, timeout=10)
            r.encoding = 'utf-8'
            if r.status_code != 200:
                continue

            lines = [l.strip() for l in r.text.split('\n') if l.strip()]
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
                print(f"  [{index+1}/{len(dynamic_sources)}] 提取到 {count_added} 個候選頻道 (來源: {source})", flush=True)

        except Exception:
            continue

    return found_channels

def generate_m3u(channels):
    tested_channels = check_channels_parallel(channels)

    # 官方源保底合併
    final_dict = {}
    for off in OFFICIAL_CHANNELS:
        final_dict[off['url']] = off

    for ch in tested_channels:
        if ch['url'] not in final_dict:
            final_dict[ch['url']] = ch

    final_list = list(final_dict.values())

    print("\n🔄 正在按照香港電視台順序排序...", flush=True)
    final_list.sort(key=get_sort_key)

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
