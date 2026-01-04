import requests
import re
import datetime
from opencc import OpenCC

# 初始化繁簡轉換器 (s2t = Simplified to Traditional)
cc = OpenCC('s2t')

# --- 設定區 ---

# 1. 來源列表
SOURCE_URLS = [
    # 范明明 (IPv6 為主，但包含不少優質源)
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    
    # YueChan (綜合源，更新頻率高)
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    
    # APTV (高品質聚合)
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    
    # Yuanzl77 (老牌源)
    "https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
    
    # iptv-org (香港分區，雖然很多有Geo-block，但值得一試)
    "https://iptv-org.github.io/iptv/countries/hk.m3u",
    
    # Joevess (泛中文源)
    "https://raw.githubusercontent.com/joevess/IPTV/main/home.m3u8",
    
    # YanG-1989 (彙整源)
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u"
]

# 2. 關鍵字過濾 (包含簡體與繁體，確保能抓到所有潛在頻道)
KEYWORDS = [
    "ViuTV", "HOY", "RTHK", "Jade", "Pearl", "J2", "J5", "Now", 
    "无线", "無線", "有线", "有線", "翡翠", "明珠", "港台", 
    "电视", "電視", "高清", "News"
]

# 3. 必備的官方/穩定源 (強制加入)
STATIC_CHANNELS = [
    {"name": "RTHK 31", "url": "https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8"},
    {"name": "RTHK 32", "url": "https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8"}
]

# --- 邏輯區 ---

def check_url(url):
    """檢測鏈接是否有效 (超時 2 秒)"""
    try:
        response = requests.get(url, timeout=2, stream=True)
        return response.status_code == 200
    except:
        return False

def fetch_and_parse():
    found_channels = []
    
    print("正在抓取網路源...")
    for source in SOURCE_URLS:
        try:
            print(f"Processing: {source}")
            r = requests.get(source)
            if r.status_code != 200: continue
            
            lines = r.text.split('\n')
            current_name = ""
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if line.startswith("#EXTINF"):
                    # 提取頻道名稱
                    match = re.search(r',(.+)$', line)
                    if match:
                        raw_name = match.group(1).strip()
                        # 在這裡直接將名稱轉為繁體，方便後續比對和輸出
                        current_name = cc.convert(raw_name)
                elif line.startswith("http") and current_name:
                    # 檢查名稱是否包含關鍵字 (因為名稱已轉繁體，所以關鍵字比對也會生效)
                    # 為了保險，我們把 name 和 keyword 都轉成小寫來比對
                    if any(cc.convert(k).lower() in current_name.lower() for k in KEYWORDS):
                        # 去重：檢查 URL 是否已存在
                        if not any(c['url'] == line for c in found_channels):
                            found_channels.append({"name": current_name, "url": line})
                    current_name = "" # 重置
        except Exception as e:
            print(f"Error fetching {source}: {e}")

    return found_channels

def generate_m3u(channels):
    print(f"共找到 {len(channels)} 個潛在頻道，開始檢測有效性...")
    
    final_list = []
    
    # 1. 先加入靜態必備源
    for static in STATIC_CHANNELS:
        final_list.append(static)
        
    # 2. 檢測抓取到的源
    for ch in channels:
        print(f"Checking: {ch['name']}...", end=" ")
        if check_url(ch['url']):
            final_list.append(ch)
            print("OK")
        else:
            print("FAIL")

    # 3. 寫入文件
    content = '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n'
    content += f'# Update: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
    
    for item in final_list:
        # 再次確保寫入的是繁體 (雖然上面已經轉過了，這裡雙重保險)
        final_name = cc.convert(item["name"])
        content += f'#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/{final_name}.png",{final_name}\n'
        content += f'{item["url"]}\n'

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"完成！共收錄 {len(final_list)} 個有效頻道 (全繁體)。")

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)
