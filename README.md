# 📺 HK IPTV Auto Updater | 香港電視台直播源自動更新

![Update Status](https://github.com/sammy0101/hk-iptv-auto
/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

這是一個基於 **GitHub Actions** 的自動化 IPTV 聚合項目。
它每天定時從網路上抓取公開的直播源，自動過濾、檢測有效性、進行繁簡轉換與名稱修正，最終生成一份乾淨、可用的香港電視頻道列表 (`.m3u`)。

## 🚀 訂閱地址 (Subscription URL)

請在您的播放器 (TiviMate, TVBox, Kodi, PotPlayer 等) 中輸入以下鏈接：

| 線路 | 鏈接 (URL) | 推薦度 |
| :--- | :--- | :--- |
| **CDN 加速 (推薦)** | `https://cdn.jsdelivr.net/gh/<你的用戶名>/<倉庫名稱>@main/hk_live.m3u` | ⭐⭐⭐⭐⭐ |
| **GitHub Raw** | `https://raw.githubusercontent.com/<你的用戶名>/<倉庫名稱>/main/hk_live.m3u` | ⭐⭐⭐ |

> ⚠️ **注意**：請將 `<你的用戶名>` 和 `<倉庫名稱>` 替換為你實際的 GitHub ID 和倉庫名 (例如 `hk-tv-auto`)。

---

## 📺 收錄頻道 (Supported Channels)

本項目專注於香港本地頻道，並根據習慣進行了排序：

1.  **TVB 系列**: 翡翠台 (Jade), 明珠台 (Pearl), 無線新聞台 (News), J2, 財經體育資訊台
2.  **ViuTV 系列**: ViuTV (99台), ViuTVsix (96台)
3.  **HOY TV 系列**: HOY TV (77台), HOY 資訊台 (78台), 76台
4.  **RTHK 系列**: 港台電視 31, 32, 33
5.  **Now TV 系列**: Now 新聞台, Now 直播台
6.  **其他**: 有線新聞等

---

## ✨ 項目特點 (Features)

*   **🤖 全自動維護**: 利用 GitHub Actions 每天定時 (早/晚) 抓取最新源，無需人工干預。
*   **🔍 智能過濾**:
    *   **白名單機制**: 僅保留香港本地頻道。
    *   **黑名單攔截**: 自動剔除假冒頻道、非 24h 輪播內容、以及錯誤匹配的國外頻道 (如 FOX, Pluto, 澳門頻道等)。
*   **✅ 有效性檢測**: 自動測試直播源連接，剔除失效或無法播放的鏈接。
*   **📝 名稱標準化**:
    *   集成 `OpenCC` 進行 **簡體轉繁體**。
    *   強制修正用字（如將「臺」統一修正為「台」）。
*   **🔄 智能排序**: 依照香港觀眾習慣 (TVB -> Viu -> HOY -> RTHK) 自動排列頻道順序。

---

## 🛠️ 如何自行部署 (How to Deploy)

如果你想自己 Fork 這個項目進行修改：

1.  **Fork** 本倉庫到你的 GitHub。
2.  在你的倉庫設定中啟用 **Actions**。
3.  (可選) 修改 `main.py` 中的 `SOURCE_URLS` (來源) 或 `ORDER_KEYWORDS` (排序)。
4.  手動觸發一次 `Run workflow`，或者等待定時任務執行。
5.  獲取你自己的 `m3u` 訂閱鏈接。

### 依賴庫 (Requirements)
*   Python 3.9+
*   `requests`
*   `opencc-python-reimplemented`

---

## ⚠️ 免責聲明 (Disclaimer)

1.  **僅供學習交流**: 本項目僅是一個**技術研究項目**，用於測試 Python 爬蟲與 GitHub Actions 的自動化邏輯。
2.  **不存儲視頻**: 所有直播源鏈接均來自網際網路上的公開渠道 (Github, 各大論壇等)，本倉庫**不存儲、不直播、不轉發**任何視頻流文件。
3.  **版權聲明**: 頻道版權歸相關電視台所有。如果侵犯了您的權益，請提 issue 通知，我們會盡快移除相關關鍵字。
4.  **地區限制**: 部分官方源 (如 ViuTV, NowTV) 可能有 **Geo-block (地區限制)**，僅限香港 IP 播放。非香港地區用戶可能無法觀看部分頻道。

---

**Last Update:** 每天自動更新
