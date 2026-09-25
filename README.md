# 个人博客

使用 Jekyll 的 [Chirpy](https://chirpy.cotes.page/) 主题，通过 GitHub Actions 构建并部署到免费的 GitHub Pages。站点地址：[qhchen96.github.io](https://qhchen96.github.io/)。

## 栏目方向

- 作者统一署名“小陈”，正文以小陈和领导的对话推进；对话之外可用工单回放、审稿记录、权限听证和时间线等形式，避免篇篇一个模子。
- 每篇文章聚焦一个具体问题：领导的灵魂拷问，或公司开发 Agent 时遇到的大麻烦。
- 标题可以有吸引力，但正文要交代真实问题、解决过程、适用边界和可执行的结论。
- 口语要自然，幽默服务于理解；产品功能等可变事实要链接到官方资料。
- 图、表和例子围绕同一条故事线，不为了凑热闹堆术语。

## 发布一篇文章

1. 在 `_posts` 目录新建 `年-月-日-英文标题.md`，例如 `2026-09-24-my-first-post.md`。
2. 文件开头写入：

   ```yaml
   ---
   layout: post
   permalink: /posts/:year/:month/:day/:title/
   title: "文章标题"
   description: "一句话摘要"
   author: 小陈
   categories: [AI, Agent基础]
   tags: [Agent, 入门]
   ---
   ```

3. 在第二个 `---` 后用 Markdown 写正文。
4. 提交到 `main` 分支，GitHub Actions 会构建、检查并部署。也可以直接在 GitHub 网页上创建或编辑文件。

文章的日期不要写在未来，否则 Jekyll 默认不会显示。

## 修改网站

- 网站名称和描述：`_config.yml`
- 关于页面：`_tabs/about.md`
- 基础入门目录：`_tabs/agents-basics.md`
- 智能客服目录：`_tabs/customer-service.md`
- 颜色和排版：`assets/css/xiaochen.css`
- 导航、文章页及其他主题功能：Chirpy 主题；优先通过 `_config.yml` 与站点样式配置

本地预览可安装 Ruby 3.4 后执行 `bundle install` 和 `bundle exec jekyll serve`。部署工作流在 `.github/workflows/pages-deploy.yml`。文章逐篇指定原有日期式 permalink，避免主题迁移改变已发布链接。提交前请检查文章中的私人信息，因为博客仓库是公开的。
