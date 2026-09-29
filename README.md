# 个人博客

使用 Jekyll 的 [Chirpy](https://chirpy.cotes.page/) 主题，通过 GitHub Actions 构建并部署到免费的 GitHub Pages。站点地址：[qhchen96.github.io](https://qhchen96.github.io/)。

## 栏目方向

- 作者统一署名“小陈”，正文以小陈和领导的对话推进；对话之外可用工单回放、审稿记录、权限听证和时间线等形式，避免篇篇一个模子。
- 每篇文章聚焦一个具体问题：领导的灵魂拷问，或公司开发 Agent 时遇到的大麻烦。
- 标题可以有吸引力，但正文要交代真实问题、解决过程、适用边界和可执行的结论。
- 口语要自然，幽默服务于理解；产品功能等可变事实要链接到官方资料。
- 图、表和例子围绕同一条故事线，不为了凑热闹堆术语。

## 写作与图解标准

- 正文沿着同一张工单或同一个业务案例逐层展开：先说现场和错误直觉，再说明对象、边界与数据口径，接着拆实现链路，最后给回放、故障恢复和负责人。技术原理要具体到输入、状态、关键字段、判断顺序与失败信号；适合时给一段可核对的伪代码或数据样例。
- 每张图回答一个明确的问题，图后正文解释它对应哪一步判断。优先用 HTML/CSS、SVG 等代码绘制可搜索、可缩放的流程图；需要动态效果时让着色器只负责氛围，关键数值与文字留在 HTML 中。无 WebGL、关闭 JavaScript、减少动态效果与手机窄屏时仍要能读懂。
- 指标算例要写清分子、分母、时间窗和集合重叠；候选数量不能冒充最终成功率。示例数据标明虚构，产品或标准的可变事实指向官方来源。
- 文章结尾交付能执行的解决办法与验收方式，不留给读者做“课后练习”。
- 图形需要读者亲手验证概念时，优先做“固定案例＋可调参数＋同步重算＋逐步回放”，而不只是给静态图加动画。一次性的轻量图可用原生 HTML/SVG/JavaScript；复杂的自定义数据图参考 [D3](https://github.com/d3/d3)，标准统计图参考 [Apache ECharts](https://github.com/apache/echarts)，跨多段正文同步推进的滚动叙事参考 [Scrollama](https://github.com/russellsamora/scrollama)。所有交互都要给无脚本的静态初始状态和清楚的分子、分母说明。

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
- 企业销售助手目录：`_tabs/sales-assistant.md`
- 颜色和排版：`assets/css/xiaochen.css`
- 导航、文章页及其他主题功能：Chirpy 主题；优先通过 `_config.yml` 与站点样式配置

本地预览可安装 Ruby 3.4 后执行 `bundle install` 和 `bundle exec jekyll serve`。部署工作流在 `.github/workflows/pages-deploy.yml`。文章逐篇指定原有日期式 permalink，避免主题迁移改变已发布链接。提交前请检查文章中的私人信息，因为博客仓库是公开的。
