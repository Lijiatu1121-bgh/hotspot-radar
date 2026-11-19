# 热点雷达 · 三渠道热点分析

每周更新 **B站 / 知乎 / GitHub** 的热点，自动剔除营销与低质内容，输出带分析框架的 HTML 报告，并发布成静态网站。

在线查看：`https://<你的用户名>.github.io/<仓库名>/`（首次部署后替换）

---

## 它解决什么问题

热点榜单本身没有价值——它们按流量排序，充斥着营销投放、娱乐八卦和刷量内容。真正难的是回答三个问题：

1. **哪些条目值得拆？**（而不是哪些条目热）
2. **它背后的知识内核是什么？**（而不是它讲了什么）
3. **我能用它做什么？**（选题、工具、判断）

这个项目对三个渠道分别做了对应的处理，而不是把榜单搬下来重新排版。

---

## 三个渠道各做什么

| 渠道 | 剔除什么 | 输出什么 |
|---|---|---|
| **B站** | 高中课程内容 | 综合爆款分析、知识区爆款、AI+硬件专项、**知识点拆解**（5 大方向 × 33 个知识点） |
| **知乎** | 营销导购、娱乐八卦、消费测评、情感树洞、生活琐事；价值分 <30 的软剔除 | 有价值议题清单、**逐条知识内核拆解**、热度×价值四象限图、领域级洞察 |
| **GitHub** | 刷星投放、资源合集、纯提示词包 | 赛道星速对比、**12 个项目技术路线拆解**、成熟度评级（可直接用/看思路/谨慎）、趋势归因 |

每份报告都包含：判断依据（可复核）、分析框架（可复用）、行动清单（可执行）。

### 几个实打实的设计细节

**刷星识别**：同一段描述被 ≥3 个仓库复用 → 批量投放；=2 个时，只有其中一个 fork/star < 0.02 才判定为克隆（因为真实项目之间也会抄描述）。实测每期能抓出三四十个刷星仓库。

**热度 ≠ 价值**：知乎报告用「热度排名 × 价值分」做象限图，把「热但空」和「冷门但有料（套利区）」分开——后者才是内容创作者的竞争空隙。

**不装懂**：单期数据只做横截面描述，不假装能看出趋势；分类是关键词启发式而非语义理解，每条都附命中依据供人工复核。

---

## 快速开始

### 每周更新（日常只需要这一条）

```bash
python scripts/update.py
```

它会依次完成：抓取三个渠道 → 生成报告 → 重建站点 → 提交并推送到 GitHub。推送完成后，Pages 会自动更新（约 1 分钟）。

常用参数：

```bash
python scripts/update.py --no-push        # 只到提交，先在本地看效果
python scripts/update.py --channel zhihu  # 只更新知乎这一个渠道
python scripts/update.py --site-only      # 不抓数据，只重建站点（改了模板后用）
```

### 分开执行

```bash
python scripts/run_all.py                # 只抓取+生成报告（可加 --dry-run 预演）
python scripts/build_site.py             # 只重建站点
```

`run_all.py` 支持按渠道单独运行，且**渠道之间互相隔离**——知乎抓取失败不会影响 B站和 GitHub 出报告，失败渠道会在首页标注。

---

## 每周自动运行

三种方式，按省心程度排序：

### 方式 1：双击批处理（最省事）

双击仓库根目录的 **`更新热点.bat`**。它会依次完成抓取、建站、提交、推送，窗口停住让你确认结果。

> ⚠️ **这个文件必须保持纯 ASCII**。Windows 的 cmd 按 GBK 代码页读取 `.bat`，文件里只要出现中文，就会把后面的命令行截断，报出 `'OENCODING' 不是内部或外部命令` 这类错误。改它的时候注释也请用英文。

### 方式 2：注册 Windows 计划任务（无人值守）

```bash
python scripts/setup_schedule.py                  # 每周五 09:00
python scripts/setup_schedule.py --time 21:30     # 改时间
python scripts/setup_schedule.py --day SAT --time 10:00
python scripts/setup_schedule.py --status         # 查看
python scripts/setup_schedule.py --remove         # 删除
```

如果提示权限不足或创建失败，用图形界面手动配置（一次搞定，永久生效）：

1. 按 `Win + R`，输入 `taskschd.msc`，回车
2. 右侧「创建基本任务」，名称填 `HotspotRadarWeekly`
3. 触发器选「每周」，勾选星期五，时间填 `09:00`
4. 操作选「启动程序」：
   - 程序或脚本：`C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python314\python.exe`
     （用 `where python` 可以查到确切路径）
   - 添加参数：`scripts\update.py`
   - 起始于：**仓库的完整路径**（这一步不能漏，否则找不到脚本）
5. 完成后在任务列表里右键 → 运行，测试一次

**两个限制要知道：**

- 计划任务只在**电脑开机且已登录**时执行。周五没开机，那周就跳过，下次打开 `更新热点.bat` 手动补一次。
- 自动推送依赖已保存的凭据。**第一次请手动推送一次**，让 Git Credential Manager 记住令牌；之后才能免密推送。否则任务会在 `git push` 那一步卡住。

### 方式 3：只手动跑一条命令

```bash
python scripts/update.py
```

适合不想装任何计划任务的情况。每周记得跑一次即可。

---

## 第一次配置（只做一次）

**1. 在 GitHub 上建一个公开仓库**（Pages 免费版需要公开仓库）

**2. 关联远程仓库并推送**

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

**3. 开启 Pages**

仓库 → Settings → Pages → Source 选择 `Deploy from a branch` → Branch 选 `main`、目录选 **`/docs`** → Save。

等 1 分钟左右，访问 `https://<你的用户名>.github.io/<仓库名>/`。

> 仓库里的 `docs/` 就是网站根目录，由 `build_site.py` 生成。每次推送后 GitHub 自动发布，**不需要任何 GitHub Actions**。

---

## 目录结构

```
.
├── bilibili/                 # B站渠道
│   ├── fetch_all.py          #   抓全站榜单 + 全站热门
│   ├── fetch_knowledge.py    #   抓知识区（wbi 签名搜索）
│   ├── generate_*.py         #   4 份报告的生成脚本
│   ├── data/                 #   最新一次抓取的原始数据
│   └── reports/<日期>/       #   历史报告 + 数据快照
├── zhihu/                    # 知乎渠道
│   ├── fetch_zhihu.py
│   ├── zhihu_taxonomy.py     #   12 个知识域 + 排除规则 + 价值评分
│   ├── generate_zhihu_report.py
│   ├── data/
│   └── reports/<日期>/
├── github/                   # GitHub 渠道
│   ├── fetch_github.py
│   ├── github_taxonomy.py    #   10 条赛道 + 刷星识别 + 成熟度打分
│   ├── generate_github_report.py
│   ├── data/
│   └── reports/<日期>/
├── scripts/
│   ├── run_all.py            # 统一入口（按渠道隔离）
│   ├── build_site.py         # 生成 docs/ 静态站点
│   └── update.py             # 一键更新（抓取→建站→推送）
├── docs/                     # GitHub Pages 站点（由 build_site.py 生成）
└── reports/<日期>/status.json # 该批次各渠道成功/失败记录
```

### 不覆盖历史

每次运行都会新建 `reports/<YYYY-MM-DD>/` 文件夹，同一天再跑则自动变成 `_2`、`_3`。
同名报告文件也会自动加序号，**任何历史报告都不会被覆盖**。

---

## 设计取舍

**为什么不用 GitHub Actions 抓数据？**
Actions 跑在境外服务器上，知乎接口对境外 IP 有风控，B站部分接口也会拦截。改用「本地跑 + push」后，抓取环境和国内访问完全一致，成功率最高，同时省掉一整套 CI 配置。Pages 只负责发布静态文件，不需要 Actions。

**为什么报告里要写"局限"？**
因为分类是关键词启发式，不是语义理解。动漫、反讽、隐喻都会误判。把判定依据和局限写在报告里，才能被复核和修正——而不是让读者以为这是权威结论。

**为什么每期保留原始数据快照？**
单期数据只能看结构，两期以上才能看出变化。`reports/<日期>/data/` 里的 JSON 就是为将来做趋势对比留的。

---

## 数据源

| 渠道 | 接口 | 说明 |
|---|---|---|
| B站 | `api.bilibili.com/x/web-interface/ranking/v2`、`/popular`、`/x/web-interface/wbi/search/all/v2` | 公开接口，需要 wbi 签名（已在 `fetch_knowledge.py` 内实现） |
| 知乎 | `api.zhihu.com/topstory/hot-list`、`news-at.zhihu.com/api/4/news/latest` | 热榜固定返回 30 条 |
| GitHub | `api.github.com/search/repositories` | 未认证限速 10 次/分钟，只发 3 次请求 |

全部为公开接口，无需账号登录，不采集任何用户隐私数据。

**已知限制**

- 知乎热榜固定 30 条，样本量小，单期统计意义有限
- GitHub 搜索的 star 排序有滞后，真正"本周暴涨"的项目不一定在榜上
- 关键词分类会误判，报告内已标注命中依据
- B站知识区接口有匿名限流，密集运行会抓空（脚本已做重试与完整性校验，抓空即中止，不会用残缺样本出报告）

---

## 环境要求

- Python 3.9+（只用标准库，无第三方依赖）
- git（用于推送）

## 免责说明

本项目仅用于内容研究与选题参考。报告中的数据来自各平台公开接口，抓取时点决定数据状态，不构成对任何平台、项目或个人的评价。GitHub 项目的"刷星"判定为启发式识别，不能证明某个仓库一定刷星，只标出明显异常项。
