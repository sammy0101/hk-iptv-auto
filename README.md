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
