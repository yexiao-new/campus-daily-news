# 在 GitHub 上发布（GitHub Pages）

发布成功后你会得到一个网址：

```
https://<你的用户名>.github.io/campus-daily-news/
```

别人打开就能看当天消息、下载 Word；GitHub 每天自动更新，**你不需要开电脑、不需要服务器**。

## 发布前确认

- 项目文件夹：`/Users/apple/Desktop/project/campus-daily-news`
- 仓库必须是 **Public**（免费版 Pages 只支持公开仓库）
- `.venv/`（虚拟环境，几十 MB）和 `data/`（本地运行数据）已经在 `.gitignore` 里，不会被上传
- `state/` 和 `docs/` 必须上传：前者是历史数据，后者是页面和日报

---

## 方法一：GitHub Desktop（推荐，不用敲命令、不用配 token）

### 1. 准备账号和软件

- 注册 / 登录 GitHub：<https://github.com>
- 下载 GitHub Desktop：<https://desktop.github.com>，安装后打开，用 GitHub 账号登录

### 2. 把本地项目变成一个仓库

1. 菜单 **File → Add Local Repository…**
2. 选择文件夹 `campus-daily-news`
3. 如果提示 “This directory does not appear to be a Git repository”，点 **create a repository**：
   - Name 保持 `campus-daily-news`
   - Local path 不要改
   - **不要**勾 “Initialize this repository with a README”
   - Git ignore 选 **None**（项目里已经有 `.gitignore`）
   - License 选 **None**
   - 点 **Create Repository**

### 3. 提交并发布

1. 左侧 **Changes** 会列出几十个文件（不会包含 `.venv`）
2. 底部 Summary 填 `校园每日快讯`，点 **Commit to main**
3. 顶部点 **Publish repository**：
   - Name：`campus-daily-news`
   - **取消勾选 “Keep this code private”**（必须公开）
   - 点 **Publish repository**
4. 等几十秒，菜单 **Repository → View on GitHub** 打开仓库网页

> 如果提示仓库已存在：你之前建过同名仓库，删掉它，或者把 Name 改成别的（网址也会跟着变）。

### 4. 去网页上开启 Pages

见下面「开启 Pages 并运行一次」。

---

## 方法二：命令行（macOS 自带 git）

### 1. 在 GitHub 网页上建空仓库

1. 右上角 **+ → New repository**
2. 名称 `campus-daily-news`，可见性选 **Public**
3. **不要**勾 Add a README / .gitignore / License
4. 点 **Create repository**

### 2. 推送代码

在终端执行（把 `<用户名>` 换成你的 GitHub 用户名）：

```bash
cd /Users/apple/Desktop/project/campus-daily-news
git init
git add .
git commit -m "校园每日快讯"
git branch -M main
git remote add origin https://github.com/<用户名>/campus-daily-news.git
git push -u origin main
```

### 3. 第一次 push 要登录

- Username：GitHub 用户名
- Password：**不能用登录密码**，要用 Personal Access Token（PAT）

生成 token：

1. GitHub 头像 → **Settings**
2. 左侧最下面 **Developer settings**
3. **Personal access tokens → Tokens (classic) → Generate new token (classic)**
4. Note 填 `campus-daily-news`，Expiration 选 30 days
5. 勾选 **`repo`** 和 **`workflow`** 两个权限（不勾 `workflow` 会推送失败）
6. **Generate token**，复制 `ghp_...`（只显示一次）
7. 回到终端，把 token 粘贴到 Password，回车

> 如果仓库里已经有 README（你勾了初始化），先执行 `git pull --rebase origin main` 再 push。

---

## 开启 Pages 并运行一次

1. 打开仓库网页 → 顶部 **Settings** → 左侧 **Pages**
2. **Build and deployment → Source** 下拉选择 **GitHub Actions**
3. 顶部 **Actions** 标签 → 左侧点「**每日更新**」→ 右侧 **Run workflow** → 分支 `main` → **Run workflow**
4. 等 1–3 分钟，刷新页面看到 **绿色勾** 就成功了
5. 回到 **Settings → Pages**，顶部会显示：

   ```
   Your site is live at https://<用户名>.github.io/campus-daily-news/
   ```

   点开就是你的公开网址。

---

## 发布之后

- 每天 4 次自动运行（北京时间 **07:20 / 12:10 / 18:10 / 22:10**）
- 每次运行会：抓取 → 生成当天 Word → 更新页面 → 自动提交数据，你不用做任何事
- 改数据源：直接在 GitHub 网页上改 `config.json` → Commit → Actions 手动跑一次
- 手动重跑：Actions →「每日更新」→ **Run workflow**

## 常见问题

### push 报 `Support for password authentication was removed`

用 PAT 当密码，不是 GitHub 登录密码。

### push 报 `refusing to allow a Personal Access Token to create or update workflow`

token 没勾 `workflow` 权限，重新生成一个勾上 `repo` + `workflow` 的。

### push 报 `remote origin already exists`

```bash
git remote set-url origin https://github.com/<用户名>/campus-daily-news.git
```

### 打开网址是 404

- Settings → Pages 的 Source 是否是 **GitHub Actions**
- Actions 里最近一次运行是否成功（绿色）
- 首次部署后等 1–2 分钟再刷新

### Actions 标签里没有「每日更新」

- 确认 `.github/workflows/daily.yml` 已经推上去（仓库根目录要能看到 `.github` 文件夹）
- 确认 GitHub 账号邮箱已验证
- Settings → Actions → General → 确认允许运行 Actions

### 页面有内容但一直不更新

GitHub Actions 跑在海外服务器上。如果学校网站限制海外访问，抓取会失败（日志里能看到 timeout / 连接失败），页面会继续显示已有数据。可以看 Actions 日志确认；如果是这个原因，建议改用国内云服务器部署 Flask 版。

### 不想公开代码

免费版 Pages 要求仓库 Public；如果需要私有，要 GitHub Pro，或改用国内云服务器。

## 本地预览（可选）

```bash
cd /Users/apple/Desktop/project/campus-daily-news
.venv/bin/python scripts/build_site.py
open docs/index.html
```
