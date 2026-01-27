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
