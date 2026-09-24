# 个人博客

使用 GitHub Pages 自带的 Jekyll 构建，无需租服务器或购买域名。

## 发布一篇文章

1. 在 `_posts` 目录新建 `年-月-日-英文标题.md`，例如 `2026-09-24-my-first-post.md`。
2. 文件开头写入：

   ```yaml
   ---
   layout: post
   title: "文章标题"
   description: "一句话摘要"
   category: 技术
   ---
   ```

3. 在第二个 `---` 后用 Markdown 写正文。
4. 提交到 `main` 分支，GitHub Pages 会自动重新构建。也可以直接在 GitHub 网页上创建或编辑文件。

文章的日期不要写在未来，否则 Jekyll 默认不会显示。

## 修改网站

- 网站名称和描述：`_config.yml`
- 关于页面：`about.md`
- 首页布局：`index.html`
- 颜色和排版：`assets/css/style.css`

修改 `_config.yml` 后，GitHub Pages 构建可能需要几分钟才会更新。提交前请检查文章中的私人信息，因为免费 GitHub Pages 使用公开仓库。
