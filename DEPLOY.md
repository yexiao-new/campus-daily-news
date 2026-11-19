
发布只需做一次，以后 GitHub 自己每天更新。给你两条路，推荐第一条（图形界面，不用配 token）。

方法一：GitHub Desktop（推荐）
1. 准备

打开 https://github.com 注册/登录（邮箱要验证，不然 Actions 跑不了）
下载安装 https://desktop.github.com ，打开后用 GitHub 账号登录
2. 把项目变成仓库

菜单 File → Add Local Repository…
选文件夹：/Users/apple/Desktop/project/campus-daily-news
如果提示 “This directory does not appear to be a Git repository”，点 create a repository：
Name 保持 campus-daily-news
不要勾 “Initialize this repository with a README”
Git ignore 选 None，License 选 None
点 Create Repository
3. 提交 + 发布

左边 Changes 会列出几十个文件（.venv 不会出现，放心）
底部 Summary 填 校园每日快讯 → Commit to main
顶部 Publish repository → 取消勾选 “Keep this code private”（必须 Public）→ Publish repository
菜单 Repository → View on GitHub 打开仓库网页
4. 开 Pages

仓库页 → 顶部 Settings → 左侧 Pages
Build and deployment → Source 选 GitHub Actions
5. 跑第一次

顶部 Actions → 左侧「每日更新」→ 右侧 Run workflow → 分支 main → Run workflow
等 1–3 分钟，看到绿色勾
6. 拿网址

回到 Settings → Pages，顶部会显示：

https://<你的用户名>.github.io/campus-daily-news/

点开就是你的公开页面。

方法二：命令行（不想装软件就用这个）
GitHub 网页 + → New repository：名称 campus-daily-news、Public、不要勾 README
终端执行：
bash


cd /Users/apple/Desktop/project/campus-daily-news
git init
git add .
git commit -m "校园每日快讯"
git branch -M main
git remote add origin https://github.com/<你的用户名>/campus-daily-news.git
git push -u origin main
第一次 push 的密码不是 GitHub 密码，要 Personal Access Token：
头像 → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)
勾 repo 和 workflow（少了 workflow 会推不上去）
生成后复制 ghp_...，粘贴到 Password
然后同样做上面第 4、5、6 步（开 Pages、Run workflow、拿网址）
成功的三个标志
Actions →「每日更新」最近一次是绿色勾
Settings → Pages 显示 Your site is live at …
打开网址能看到消息列表和「下载 Word
