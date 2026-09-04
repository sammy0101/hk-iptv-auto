# Complete Project Codebase
Generated on: Fri Sep  4 14:52:34 UTC 2026

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

````

## File: README.md
````md
# 📺 HK IPTV Auto Updater | 香港電視台直播源自動更新

![Update Status](https://github.com/sammy0101/hk-iptv-auto/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

這是一個基於 **GitHub Actions** 的自動化 IPTV 聚合項目。
它每天定時從網路上抓取公開的直播源，自動過濾、檢測有效性、進行繁簡轉換與名稱修正，最終生成一份乾淨、可用的香港電視頻道列表 (`.m3u`)。

---

## 🚀 訂閱地址 (Subscription URL)

請在您的播放器 (TiviMate, TVBox, Kodi, PotPlayer 等) 中輸入以下鏈接：

| 線路 | 鏈接 (URL) | 推薦度 |
| :--- | :--- | :--- |
| **CDN 加速 (推薦)** | `https://raw.gh.registry.cyou/sammy0101/hk-iptv-auto/refs/heads/main/hk_live.m3u` | ⭐⭐⭐⭐⭐ |
| **GitHub Raw** | `https://raw.githubusercontent.com/sammy0101/hk-iptv-auto/refs/heads/main/hk_live.m3u` | ⭐⭐⭐ |

> ⚡ **CDN 加速服務由 [cmliussss](https://blog.cmliussss.com/) 提供，特此感謝！**
> 
> 💡 **提示**：推薦使用上方 **CDN 加速** 鏈接，在部分網路環境下更新速度會更快、更穩定。

---

## ❤️ 特別鳴謝 (Credits)

本項目的數據來源主要基於以下開源項目與維護者的大力奉獻，在此致以最誠摯的謝意：

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
*   **Free-TV**, **epg.pw** 以及所有無私維護直播源的開發者們。

---

## 📺 收錄頻道 (Supported Channels)

本項目專注於香港本地頻道，並根據習慣進行了排序：

1.  **TVB 系列**: 翡翠台 (Jade), 明珠台 (Pearl), 無線新聞台 (News), J2, 財經體育資訊台
2.  **ViuTV 系列**: ViuTV (99台), ViuTVsix (96台)
3.  **HOY TV 系列**: HOY TV (77台), HOY 資訊台 (78台), 76台
4.  **RTHK 系列**: 港台電視 31, 32, 33
5.  **Now TV 系列**: Now 新聞台, Now 直播台

---

## ✨ 項目特點 (Features)

*   **🤖 全自動維護**: 利用 GitHub Actions 每天定時抓取最新源。
*   **🔍 智能過濾**: 白名單保留香港頻道，黑名單攔截無效內容。
*   **✅ 有效性檢測**: 自動測試直播源連接，剔除失效鏈接。
*   **📝 名稱標準化**: 集成 `OpenCC` 繁簡轉換，並統一修正「台」字。
*   **🔄 智能排序**: 依照香港觀眾習慣自動排列頻道順序。

---

## 🛠️ 給 Fork 用戶的修改指南 (For Developers)

如果你 Fork 了本項目，並希望自定義抓取來源或過濾邏輯，請參考以下步驟：

### 1. 增加/刪除直播源 (Sources)
直接編輯 `main.py`，找到 `SOURCE_URLS` 列表。你可以加入任何公開的 `.m3u` 或 `.m3u8` 鏈接。

### 2. 修改過濾規則 (Filters)
*   **白名單 (`KEYWORDS`)**: 頻道名稱**必須包含**這些關鍵字才會被抓取。
*   **黑名單 (`BLOCK_KEYWORDS`)**: 頻道名稱若包含這些字，會被**強制丟棄**。

### 3. 調整頻道排序 (Sorting)
編輯 `main.py` 中的 `ORDER_KEYWORDS` 列表。越上面的關鍵字，優先級越高。

### 4. 修改訂閱鏈接 (Update Subscription URL)
Fork 之後，`README.md` 顯示的訂閱鏈接仍然指向原作者 (`sammy0101`) 的倉庫。
請務必編輯 `README.md`，將訂閱鏈接中的 `sammy0101` 替換為你的 GitHub 用戶名，否則你的用戶將無法獲取你更新的列表。

*   **CDN 格式範例**:
    `https://raw.gh.registry.cyou/<你的用戶名>/<倉庫名稱>/refs/heads/main/hk_live.m3u`

### ⚠️ 重要：Fork 後如何啟用自動更新
Fork 本項目後，GitHub Actions 默認是關閉的。你需要：
1.  進入你倉庫的 **Actions** 頁面。
2.  點擊綠色按鈕 **"I understand my workflows, go ahead and enable them"**。
3.  左側選擇 **Update IPTV Source** -> **Enable workflow**。

---

## ⚠️ 免責聲明 (Disclaimer)

1.  **僅供學習交流**: 本項目僅是一個技術研究項目。
2.  **不存儲視頻**: 所有直播源鏈接均來自網際網路上的公開渠道，本倉庫不存儲任何視頻流文件。
3.  **版權聲明**: 頻道版權歸相關電視台所有。
4.  **地區限制**: 部分源可能僅限香港 IP 播放。

**Last Update:** 每天自動更新

````

## File: hk_live.m3u
````m3u
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"
# Update: 2026-09-04 03:20:44
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台北美版.png",翡翠台北美版
http://php.jdshipin.com:8880/TVOD/iptv.php?id=j1
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/GeWKr?id=fct720
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://122.152.202.33/s/81a8a44f/index.m3u8?id=53
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/qClQf
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/qrfbg
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/62WM7
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/n90gt
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/GeWKr
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠.png",翡翠
http://php.jdshipin.com/TVOD/iptv.php?id=fct2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠.png",翡翠
http://php.jdshipin.com/TVOD/iptv.php?id=fct3
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB翡翠台 1080P.png",TVB翡翠台 1080P
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct3
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct4
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞台.png",無線新聞台
http://r.jdshipin.com/CkuBd
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB無線新聞.png",TVB無線新聞
http://122.152.202.33/s/81a8a44f/index.m3u8?id=21
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞.png",無線新聞
https://h5cdn3.kylintv.tv/live/tvbnews_iphone.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞.png",無線新聞
http://php.jdshipin.com/TVOD/iptv.php?id=wxxw
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://r.jdshipin.com/GeWKr?id=mzt720
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB明珠.png",TVB明珠
http://122.152.202.33/s/81a8a44f/index.m3u8?id=23
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://r.jdshipin.com/ZQ4kN
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://r.jdshipin.com/jUx8K
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://php.jdshipin.com/TVOD/iptv.php?id=mzt2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/有線財經信息台.png",有線財經信息台
https://epg.pw/stream/0fddc0600d3868b05ad741d46294410aebca0fdc4fada5028dc54e624b7b17ca.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/ViuTV.png",ViuTV
http://r.jdshipin.com/vSJvl
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Viutv.png",Viutv
http://r.jdshipin.com/TcKr2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Viutv.png",Viutv
http://php.jdshipin.com/TVOD/iptv.php?id=viutv
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Viutv.png",Viutv
http://php.jdshipin.com/TVOD/iptv.php?id=viutv2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY TV.png",HOY TV
http://uc6.i-cable.com/live_freedirect/opentvhd001_h.live/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY TV.png",HOY TV
http://r.jdshipin.com/sFw4S
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY TV.png",HOY TV
http://php.jdshipin.com/TVOD/iptv.php?id=hoytv
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/有線新聞.png",有線新聞
http://61.10.2.140/live_freedirect/freehd209_h.live/chunklist_w135209556.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/香港有線新聞.png",香港有線新聞
https://epg.pw/stream/4c65fc12a950810e9f068c55b2abf43cf7937762e9c5d4d44381205743c731bf.ctv
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/有線新聞.png",有線新聞
http://61.10.2.141/live_freedirect/freehd209_h.live/playlist.m3u
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/有線新聞台.png",有線新聞台
http://cm61-10-2-143.hkcable.com.hk/live_freedirect/freehd209_h.live/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31 (官方).png",港台電視31 (官方)
https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
http://php.jdshipin.com/TVOD/iptv.php?id=rthk31
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
http://bziyunshao.synology.me:8892/bysid/31#https://live.hkdvb.com/hls/live/31.m3u8?token=415002797090467
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK 31.png",RTHK 31
https://www.rthk.hk/feeds/dtt/rthktv31_https.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32 (官方).png",港台電視32 (官方)
https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
http://php.jdshipin.com/TVOD/iptv.php?id=rthk32
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
http://bziyunshao.synology.me:8892/bysid/32#https://live.hkdvb.com/hls/live/32.m3u8?token=415002797090467
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK 32.png",RTHK 32
https://www.rthk.hk/feeds/dtt/rthktv32_https.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK31.png",RTHK31
http://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_810_av-b.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK31.png",RTHK31
http://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK31.png",RTHK31
https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK31.png",RTHK31
https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/MS NOW.png",MS NOW
https://d1bl6tskrpq9ze.cloudfront.net/hls/master.m3u8?ads.xumo_channelId=99984003
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線 TVB Plus.png",無線 TVB Plus
http://php.jdshipin.com/TVOD/iptv.php?id=tvbp
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK31.png",RTHK31
http://php.jdshipin.com:8880/TVOD/iptv.php?id=rthk31
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK32.png",RTHK32
http://php.jdshipin.com:8880/TVOD/iptv.php?id=rthk32
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Anthony Bourdain: Parts Unknown.png",Anthony Bourdain: Parts Unknown
https://jmp2.uk/plu-69173ce8abd4703b27f71d44.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HEi Now (1080p).png",HEi Now (1080p)
https://copacogen.desdeparaguay.net/heitv/heitv_py_alta/playlist.m3u8?admin=nacion
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Now 14 (1080p).png",Now 14 (1080p)
https://r.il.cdn-redge.media/livehls/oil/ch14/live/ch14/live.livx/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/NOW News Arabic (720p).png",NOW News Arabic (720p)
https://live.nowtelly.com/now_arabic/live/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/NOW News Global (720p).png",NOW News Global (720p)
https://nowhls.wns.live/hls/stream.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/NOW News Spanish (1080p).png",NOW News Spanish (1080p)
https://live.nowtelly.com/now_spanish/live/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/NOW News USA (1080p).png",NOW News USA (1080p)
https://live.nowtelly.com/now_usa/live_usa/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/NOW TV (720p).png",NOW TV (720p)
https://uycyyuuzyh.turknet.ercdn.net/nphindgytw/nowtv/nowtv.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Unknown Russia HD (1080p).png",Unknown Russia HD (1080p)
http://185.23.80.23:8080/NeizvestnayaRossia/index.m3u8

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

