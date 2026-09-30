# 個人記帳與股票被動收入管理系統｜Web 版

這是將原本 Tkinter 桌面程式改寫成 Flask Web 應用程式的完整專案。

## 功能
- 每日收支記帳、年份／月份篩選、收入／支出統計
- 股票交易、損益、股數、股利與每月平均股利
- FinMind TaiwanStockInfo 股票名稱查詢
- 收支類別、股票交易類型、配息週期管理
- 個人淨資產、股票資金與預估月股利總覽
- 手機／平板／桌面瀏覽器響應式介面
- SQLite 資料庫

## 啟動
### Windows
雙擊 `run.bat`，或：
```powershell
python -m pip install -r requirements.txt
python app.py
```
瀏覽器開啟 `http://127.0.0.1:5000`

### Linux / macOS / WSL
```bash
chmod +x run.sh
./run.sh
```
然後開啟 `http://127.0.0.1:5000`

## 使用既有資料
把原桌面程式產生的 `accounting.db` 放到本專案根目錄即可。Web 版會使用相同的 SQLite 表格名稱與欄位結構。

## 區網手機使用
在執行程式的電腦上啟動後，查看電腦區網 IP，例如 `192.168.1.20`，手機與電腦連同一 Wi-Fi 後開啟：
`http://192.168.1.20:5000`

正式部署時請改用 production WSGI server（例如 waitress），並自行設定安全的 secret key、登入驗證與 HTTPS。
