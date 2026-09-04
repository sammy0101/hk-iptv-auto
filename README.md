# 📺 HK IPTV Auto Updater | 香港電視台直播源自動更新

![Update Status](https://github.com/sammy0101/hk-iptv-auto/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

這是一個基於 **GitHub Actions** 的全自動化香港電視 IPTV 聚合專案。
每天定時自動同步上游最新資源庫與 TVBox 影視倉，進行深度切片級流媒體驗證、繁簡轉換（標準化為港式「台」字）與自動排序，生成純淨、可用的香港電視直播清單 (`.m3u`)。

---

## 🚀 訂閱地址 (Subscription URL)

請在您的播放器 (TiviMate, TVBox, Kodi, PotPlayer, APTV 等) 中輸入以下鏈接：

| 線路 | 鏈接 (URL) | 推薦度 |
| :--- | :--- | :--- |
| **jsDelivr CDN (推薦)** | `https://cdn.jsdelivr.net/gh/sammy0101/hk-iptv-auto@main/hk_live.m3u` | ⭐⭐⭐⭐⭐ |
| **GitHub Raw** | `https://raw.githubusercontent.com/sammy0101/hk-iptv-auto/refs/heads/main/hk_live.m3u` | ⭐⭐⭐ |

> 💡 **提示**：推薦使用上方 **jsDelivr CDN** 鏈接，自帶全球節點緩存加速，更新速度快且不受 GitHub 網絡波動影響。

---

## ❤️ 特別鳴謝 (Credits)

本項目的數據來源主要基於以下開源項目與社區大佬的大力奉獻，在此致以最誠摯的謝意：

*   **youhunwl**: [TVAPP](https://github.com/youhunwl/TVAPP) *(本專案已實現每日自動同步其最新在線源與影視倉)*
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
*   **Free-TV**, **epg.pw**, **jsDelivr** 以及所有無私維護直播源的開發者們。

---

## 📺 收錄頻道 (Supported Channels)

本項目專注於香港本地頻道，並按照香港觀眾收視習慣進行了優先級排序：

1.  **TVB 系列**: 翡翠台 (Jade), 無綫新聞台 (News), 明珠台 (Pearl), TVB Plus (J2), 無綫財經體育資訊台
2.  **ViuTV 系列**: ViuTV (99台), ViuTVsix (96台)
3.  **HOY TV 系列**: HOY TV (77台), HOY 資訊台 (78台)
4.  **RTHK 系列**: 港台電視 31, 港台電視 32, 港台電視 33
5.  **Now TV 系列**: Now 新聞台, Now 直播台
6.  **其他資訊**: 有線新聞、有線財經等

---

## ✨ 項目特點 (Features)

*   **🌐 動態上游同步**: 每日自動抓取 `youhunwl/TVAPP` 的最新數據庫，自動解碼 TVBox 單倉與多倉直播節點。
*   **🔍 雙重過濾系統**:
    *   **白名單機制**: 嚴格限定香港電視台專屬標籤，徹底過濾無關省份、體育、輪播台。
    *   **黑名單攔截**: 強力剔除土耳其 NOW TV、以色列頻道、虎牙、斗魚、B站等雜訊。
*   **⚡ 切片級深度檢測**: 深入解析 `.m3u8` 二級分片並驗證真實視頻二進位流，拒絕「假 200」黑屏死鏈。
*   **🛡️ 官方源保底放行**: 內建香港電台與有線官方 Akamai/CDN 直連放行邏輯，防止 GitHub 海外機房誤殺香港本地可播源。
*   **📝 文字標準化**: 集成 `OpenCC` 簡體轉繁體，並全面校正為港式「台」字。
*   **🔄 自動排序**: 依照香港電視台順序自動排列，方便電視盒子開箱即用。

---

## 🛠️ 給 Fork 用戶的修改指南 (For Developers)

如果你 Fork 了本項目，並希望自定義抓取來源或過濾邏輯，請參考以下步驟：

### 1. 增加/刪除直播源 (Sources)
直接編輯 `main.py`，找到 `FALLBACK_STANDARD_SOURCES` 列表。你可以加入任何公開的 `.m3u` 或 `.m3u8` 鏈接。

### 2. 修改過濾規則 (Filters)
*   **白名單 (`KEYWORDS`)**: 頻道名稱**必須包含**這些關鍵字才會被抓取。
*   **黑名單 (`BLOCK_KEYWORDS`)**: 頻道名稱若包含這些字，會被**強制丟棄**。

### 3. 調整頻道排序 (Sorting)
編輯 `main.py` 中的 `ORDER_KEYWORDS` 列表。越上面的關鍵字，優先級越高。

### 4. 修改訂閱鏈接 (Update Subscription URL)
Fork 之後，`README.md` 顯示的訂閱鏈接仍然指向原作者 (`sammy0101`) 的倉庫。
請務必編輯 `README.md`，將訂閱鏈接中的 `sammy0101` 替換為你的 GitHub 用戶名：

*   **jsDelivr 格式範例**:
    `https://cdn.jsdelivr.net/gh/<你的用戶名>/<倉庫名稱>@main/hk_live.m3u`

### ⚠️ 重要：Fork 後如何啟用自動更新
Fork 本項目後，GitHub Actions 默認是關閉的。你需要：
1.  進入你倉庫的 **Actions** 頁面。
2.  點擊綠色按鈕 **"I understand my workflows, go ahead and enable them"**。
3.  左側選擇 **Update IPTV Source** -> **Enable workflow**。

---

## ⚠️ 免責聲明 (Disclaimer)

1.  **僅供學習交流**: 本項目僅是一個網絡串流測試與自動化技術研究項目。
2.  **不存儲視頻**: 所有直播源鏈接均來自網際網路上的公開渠道，本倉庫不存儲、不託管、不轉發任何視頻流文件。
3.  **版權聲明**: 頻道版權歸相關電視台所有。若有權益問題請提 issue，我們將第一時間配合移除相關關鍵字。
4.  **地區限制**: 部分源（如 RTHK、HOY TV 官方直連）設有 Geo-block，需使用香港本地網絡或香港網絡節點觀看。

**Last Update:** 每天自動更新
