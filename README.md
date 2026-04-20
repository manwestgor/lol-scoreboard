# 鬥快上韓服菁英2026 — Scoreboard

自動排名追蹤網站，每8小時自動截圖 lol.ps 並用 Gemini Vision 解析資料。

---

## 部署步驟（只需做一次）

### 第一步：上傳這個資料夾到 GitHub

1. 登入 [github.com](https://github.com)
2. 右上角 **+** → **New repository**
3. Repository name 填：`lol-scoreboard`
4. 選 **Public**
5. 按 **Create repository**
6. 在新頁面選 **uploading an existing file**
7. 把這個資料夾裡的所有東西拖進去上傳
8. 按 **Commit changes**

---

### 第二步：加入 Gemini API Key

1. 在你的 repo 頁面，點 **Settings**（頂部導航）
2. 左側選單 → **Secrets and variables** → **Actions**
3. 按 **New repository secret**
4. Name 填：`GEMINI_API_KEY`
5. Secret 填：你的 Gemini API Key
6. 按 **Add secret**

---

### 第三步：開啟 GitHub Pages

1. 在 repo 的 **Settings**
2. 左側選單 → **Pages**
3. Source 選 **Deploy from a branch**
4. Branch 選 **main**，資料夾選 **/docs**
5. 按 **Save**

幾分鐘後你的網站會在：
`https://manwestgor.github.io/lol-scoreboard`

---

### 第四步：手動觸發第一次更新

1. 在 repo 頁面點 **Actions**（頂部導航）
2. 左側選 **Update Scoreboard**
3. 右側按 **Run workflow** → **Run workflow**
4. 等約 2-3 分鐘，完成後重新整理網站

之後每8小時會自動執行，不需要任何操作。

---

## 資料夾結構

```
lol-scoreboard/
├── .github/
│   └── workflows/
│       └── update.yml      # 定時自動執行設定
├── scripts/
│   └── scrape.py           # 截圖 + Gemini 解析腳本
└── docs/
    ├── index.html          # 網站前端
    └── data.json           # 排名資料（自動更新）
```
