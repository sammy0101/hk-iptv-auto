import requests
import re
import datetime
from opencc import OpenCC

# 初始化繁簡轉換器
cc = OpenCC('s2t')

# --- 設定區 (已更新你提供的來源與過濾設定) ---

# 1. 來源列表
SOURCE_URLS = [
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/1300%E4%B8%AA%E7%9B%B4%E6%92%AD%E6%BA%90%E5%85%A8%E9%83%A8%E6%9C%89%E6%95%88%E3%80%90%E5%85%A8%E9%83%A84k%E8%80%81%E7%94%B5%E8%84%91%E5%88%AB%E7%94%A8%E3%80%91.m3u8",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/5000%E4%B8%AA%E7%9B%B4%E6%92%AD%E6%BA%90%E5%85%A8%E9%83%A8%E6%9C%89%E6%95%88.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E6%88%91%E7%9A%84%E6%92%AD%E6%94%BE%E6%BA%90.m3u8",
    "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
    "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "https://raw.githubusercontent.com/joevess/IPTV/main/home.m3u8",
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u"
]

# 2. 關鍵字過濾 (已移除鳳凰)
KEYWORDS = [
    "ViuTV", "HOY", "RTHK", "Jade", "Pearl", "J2", "J5", "Now", 
    "无线", "無線", "有线", "有線", "翡翠", "明珠", "港台", 
]

# 3. 必備的官方/穩定源
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
    
    # flush=True 確保在 GitHub Action 中能即時看到輸出
    print("🚀 任務開始！正在抓取網路源...", flush=True)
    
    for index, source in enumerate(SOURCE_URLS):
        print(f"  [{index+1}/{len(SOURCE_URLS)}] 正在讀取: {source}", flush=True)
        try:
            # 設定 15 秒超時，避免大文件卡住
            r = requests.get(source, timeout=15)
            r.encoding = 'utf-8' # 強制編碼，防止亂碼
            
            if r.status_code != 200:
                print(f"    ⚠️ 無法讀取 (Status: {r.status_code})", flush=True)
                continue
            
            lines = r.text.split('\n')
            current_name = ""
            count_added = 0
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if line.startswith("#EXTINF"):
                    # 提取頻道名稱
                    match = re.search(r',(.+)$', line)
                    if match:
                        raw_name = match.group(1).strip()
                        
                        # 1. 轉繁體
                        converted_name = cc.convert(raw_name)
                        
                        # 2. 修正「臺」為「台」
                        current_name = converted_name.replace('臺', '台')
                        
                elif line.startswith("http") and current_name:
                    # 檢查關鍵字 (統一轉小寫比對)
                    if any(cc.convert(k).replace('臺', '台').lower() in current_name.lower() for k in KEYWORDS):
                        # 去重
                        if not any(c['url'] == line for c in found_channels):
                            found_channels.append({"name": current_name, "url": line})
                            count_added += 1
                    current_name = "" # 重置
            
            print(f"    ✅ 抓取成功，新增 {count_added} 個頻道", flush=True)
            
        except Exception as e:
            print(f"    ❌ 抓取錯誤: {e}", flush=True)

    return found_channels

def generate_m3u(channels):
    total = len(channels)
    print(f"\n🔍 共找到 {total} 個潛在頻道，開始檢測有效性...", flush=True)
    
    final_list = []
    
    # 1. 加入靜態源
    for static in STATIC_CHANNELS:
        final_list.append(static)
        
    # 2. 檢測網路源
    for i, ch in enumerate(channels):
        # 顯示進度 [1/100]
        print(f"[{i+1}/{total}] 檢測: {ch['name']} ...", end=" ", flush=True)
        
        if check_url(ch['url']):
            final_list.append(ch)
            print("🟢 有效", flush=True)
        else:
            print("🔴 失效", flush=True)

    # 3. 寫入文件
    content = '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n'
    content += f'# Update: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
    
    for item in final_list:
        final_name = item["name"].replace('臺', '台')
        content += f'#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/{final_name}.png",{final_name}\n'
        content += f'{item["url"]}\n'

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 全部完成！共收錄 {len(final_list)} 個有效頻道。", flush=True)

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)
