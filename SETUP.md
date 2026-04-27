# 🚀 Dashboard 全自動上線步驟

做完下面 3 步，這個 dashboard 就會每天早上 08:00 自動更新並上線，你完全不用管。

---

## 📋 你只要做 3 件事

### 1️⃣ 安裝 Git（5 分鐘，一次性）

下載並安裝 **Git for Windows**：
👉 https://git-scm.com/download/win

- 一路按 Next 用預設即可
- 裝完後關掉並重開 PowerShell
- 打 `git --version` 看得到版本號就 OK

---

### 2️⃣ 建 GitHub Repo 並上傳（5 分鐘）

**(a) 註冊 / 登入 GitHub**：https://github.com

**(b) 建新 Repo**：
- 點右上角 `+` → `New repository`
- Repository name：`amazon-tw-seller-dashboard`（或任何你想要的名字）
- 選 **Public**（最簡單）
- **不要**勾 Add README / .gitignore / license
- 按 `Create repository`

**(c) 複製 GitHub 給你的網址**（長這樣：`https://github.com/你的帳號/amazon-tw-seller-dashboard.git`）

**(d) 在 PowerShell 裡 cd 到這個專案根目錄（目前的工作區）**，然後一次貼下面指令（把 `你的帳號` 換成實際帳號）：

```powershell
git init
git add .github .gitignore scripts netlify.toml SETUP.md amazon-tw-seller-dashboard
git commit -m "initial: dashboard + auto-update pipeline"
git branch -M main
git remote add origin https://github.com/你的帳號/amazon-tw-seller-dashboard.git
git push -u origin main
```

第一次會跳出 GitHub 登入視窗，用瀏覽器授權即可。

---

### 3️⃣ 連 Netlify 自動部署（2 分鐘）

1. 打開 https://app.netlify.com → `Sign up` → 選 `GitHub` 登入
2. 進入 Dashboard 後點 **`Add new site`** → **`Import an existing project`**
3. 選 **GitHub** → 找到你剛剛建的 repo → 點進去
4. 設定頁保留預設（我已經幫你寫好 `netlify.toml`），直接按 **`Deploy`**
5. 等 30 秒，你的 dashboard 就上線了，網址長這樣：
   `https://某隨機字串.netlify.app`

想改網址？在 Netlify 該 site 的 `Site configuration` → `Change site name`，改成你要的，例如 `amazon-tw-dashboard`，網址就變 `https://amazon-tw-dashboard.netlify.app`。

---

## ✅ 完成！之後會發生什麼？

- **每天台灣時間 08:00**，GitHub Actions 會自動：
  1. 從 Google News 抓最新 25 則 Amazon / 電商 / 關稅新聞
  2. 寫入 `newsdata.js`
  3. git commit 並 push
- **Netlify 偵測到 push**，30 秒內自動重新部署
- 你**打開 dashboard 網址**永遠是最新內容 🎉

---

## 🧪 想馬上測試一次？

到你的 GitHub repo 頁面 → 點 **`Actions`** tab → 左側選 `Daily News Update` → 右邊按 **`Run workflow`** → `Run workflow`。

約 1 分鐘後完成，會自動 commit。再過 30 秒 Netlify 會 redeploy，打開 dashboard 就是最新新聞。

---

## 🤖 （可選）加上 AI 中文翻譯

目前沒有 API key 的話，新聞標題會直接用英文。如果想自動翻成繁體中文：

1. 到 https://platform.openai.com/api-keys 註冊並建一把 key（預存 $5 就夠用很久，每天 25 則翻譯約 $0.002）
2. 到你的 GitHub repo → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`
3. Name：`OPENAI_API_KEY`  Value：你的 key
4. 下次自動執行就會翻譯成繁中了

---

## 🔧 想改什麼？

| 我想… | 改哪裡 |
|---|---|
| 改執行時間 | `.github/workflows/daily-news.yml` 的 `cron` 欄位 |
| 加 / 移除關注主題 | `scripts/update_news.py` 的 `TOPICS` 列表 |
| 改新聞筆數 | `scripts/update_news.py` 的 `MAX_ITEMS`（目前 25） |
| 強制手動更新 | GitHub → Actions → Run workflow |

---

## ❓ 問題排除

**GitHub Actions 跑失敗？**
到 repo → Actions → 點失敗那次 → 看紅色錯誤訊息貼回來我幫你看。

**Netlify 沒自動 redeploy？**
到 Netlify → 你的 site → `Deploys` → 看有沒有新的 deploy。沒有的話檢查 `Site configuration` → `Build & deploy` → `Continuous deployment` 是不是連到對的 repo。

**新聞沒更新？**
- 檢查 GitHub Actions 有沒有成功跑
- 檢查 `newsdata.js` 最後 commit 日期
- 開瀏覽器 DevTools 按 `Ctrl+Shift+R` 強制清 cache
