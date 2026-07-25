# oldfishVDL v2 結構

- `app/`：Python／Qt 後端原始碼與程式入口。
- `frontend/`：HTML、頁面片段、CSS、JavaScript 與圖像資源。
- `runtime/`：內嵌 Python、FFmpeg、設定、快取與下載資料；不作為功能原始碼維護。
- `tools/`：一次性或維護用工具。
- `tests/`：不需啟動 GUI 的自動檢查。

開發啟動請使用 `./run-dev.ps1` 或 `dev_tools_menu.ps1`；不要再使用舊的 `v2/main/...` 路徑。Windows 發佈前須以更新後的 `launcher.cpp` 重新編譯 `oldfishVDL.exe`，讓啟動器指向 `runtime/lib/python_embed` 與 `app/main.pyw`。
