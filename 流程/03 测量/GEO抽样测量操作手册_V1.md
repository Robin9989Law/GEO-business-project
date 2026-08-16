# GEO 抽样测量操作手册 V1

按本手册从第 0 天做到出第一张基线表。不要跳步。  
原则：金标准是手机 App 冷会话；官方联网 API 只当日更哨兵；两套数分开报。

配套文件：

- 共享配置（只作复制源）：`流程/03 测量/配置/`
- 本案冻结 / 样本 / 台账 / 出数：`流程/03 测量/案件/{case_id}/`
- 报告模板：`流程/03 测量/出数/报告模板.md`
- API 哨兵脚本：`流程/03 测量/工具/api_sentinel.py`
- 提示词：`流程/03 测量/提示词/`（派单 / 入库 / 抽取 / 打分 / 抽检 / 出数 / 校准）
- 短版原理：`GEO抽样与测量方案_V1.md`
- 文献补强 V1：`研究/文献精读_测量方案补强_V1.md`
- 文献库（50 论文 + 32 博客）：`研究/测量文献/`
- 第二轮对照补丁：`研究/测量文献/对照补丁_V2.md`
- 出数脚本：`流程/03 测量/工具/metrics_rollup.py`（点估计 + bootstrap 95% CI）
- 项目目标卡：`流程/03 测量/配置/project.csv`
- 资产沉淀：`流程/03 测量/工具/asset_deposit.py` → `流程/03 测量/资产库/`

---

## 0. 怎么用

| 你是谁 | 先读 | 当天只做 |
|---|---|---|
| 负责人 | 第 1、13、14、**18** 节 | 定项目目标卡、定谁操作/谁抽检、定本轮要沉淀的资产 |
| 操作员 | 第 2、4、6、11 节 | 按当日清单冷问、截图、丢文件 |
| 评分员 | 第 3、7、8、9 节 | 打开原文打分，不改问法 |
| 编排 / Agent | 第 5、6、10、12 节 | API 一次一问、入库、出表 |

每次开测前用 `make_checklist.py --case-id` 生成本案清单，打开 `流程/03 测量/案件/{case_id}/清单/` 下当日文件，填日期后打印或投屏。

---

## 1. 角色、工时、四种任务

### 1.1 角色（最小 2 人）

| 角色 | 人数 | 不能合并的时候 |
|---|---|---|
| 操作员 | 建议 2（App≥5 时） | 一个人连打 7 个 App 会串会话 |
| 评分员 | 1，可兼操作员 | 基线周、复测周必须另有抽检 |
| 抽检 | 1 | 基线 / 复测的 Core 必须有第二人 |
| 编排 | 1，可兼评分员 | — |

### 1.2 四种任务，不要混着采

| 任务代码 | 何时做 | App 轮次 | API | 目的 | 数据等级 |
|---|---|---|---|---|---|
| `noise` | 正式基线前 5–7 个工作日，**禁止干预** | P0 每天 1 轮；P1 至少 2 天各 1 轮 | 日更 **7** request | 先量自然波动 | 定向级噪声底 |
| `baseline` | 噪声周之后、干预前 | **P0 × 3 轮**；**P1 × 1 轮** | 同日 **7** request | 正式基线 | P0 可冲决策级滚动；P1 默认定向级 |
| `weekly` | 之后每周固定日 | P0+P1 各 **1 轮** | 日更 **7** request | 看有没有异常 | 看 14 日滚动，不看单日点 |
| `calib` | 每周与 weekly 同一天 | 有等价 API 的 P0：12 问 × 1 轮 | 这 12 问 **7** request | 估 API–App 偏差 | 只判哨兵；无等价 API 的不写 gap |
| `retest` | 干预完成并等 3–7 天后 | 与 baseline 完全同口径 | 同日 **7** request | 监测组复测 | 默认受控前后描述；确认性 L1 须隔离对照且主终点 DiD CI 不含 0 |

平台名单以 `流程/03 测量/配置/platforms.csv` 为准，见第 1.3 节。**默认最小档：P0=4，P1 关闭。** 8 条 Core（N01–N03）+ 12 条同品类监测问（H01–H06 各 2 条释义）：

- `noise` 一周：P0 约 20×4×5=**400**；P1 约 20×3×2=**120**（两人分 App）
- `baseline` / `retest`：P0 20×4×3=**240** + P1 20×3×1=**60** ≈ **300 次**（约 3 人日）
- `weekly`：20×7×1=**140 次**（约 6–7 小时，建议两名操作员）
- `calib`：12 ×（豆包/通义/DeepSeek）× 1，可与 weekly 共用
- API：只打 `platforms.csv` 里 `has_equiv_api=1` 的通道，各 7 轮

合同若点名某一 P1 平台，该平台 baseline/retest 升到与 P0 相同的 3 轮。P2 默认 `active=0`，每月最多轮换 1 个，不进合同主表。

人手不够时：`noise` 可改成「连续 2 个半天各打 1 轮」而不是天天打，但 **干预前至少要有两天无干预样本**。Core 与 Holdout 都必须有，一经冻结本轮不改字。

**等级（对外必须写）：**

- **定向级**：App 单日 3 轮。能描述「大概在哪」，SE 常 >0.10，不能单独签效果合同。
- **决策级**：同一冻结词表下，App 连续 ≥7 日各 1 轮（或单日 7 轮）。只描述估计精度，不含效果判定。来源结论还要再加轮次（见第 9.4 节）。

### 1.3 测哪些 App（不能只三家）

名单冻结在 `流程/03 测量/配置/platforms.csv`。月活口径：QuestMobile 2026 年 6 月 AI 原生 App。只收**用户会拿来问「在哪报名 / 哪家正规」的综合助手或搜索助手**。

| 档 | 通道 | 产品 | 2026-06 月活 | 官方等价联网 API |
|---|---|---|---|---|
| **P0 必测** | `app_doubao` | 豆包 | 3.82 亿 | `api_doubao_search`（≠ App） |
| **P0 必测** | `app_tongyi` | 通义千问 | 1.67 亿 | `api_qwen_search`（≠ App） |
| **P0 必测** | `app_deepseek` | DeepSeek | 1.30 亿 | `api_deepseek_search`（网页/API ≠ App） |
| **P0 必测** | `app_yuanbao` | 腾讯元宝 | 0.50 亿 | 无，只报 App |
| **P1 扩展必测** | `app_kimi` | Kimi | 729 万 | 无 |
| **P1 扩展必测** | `app_wenxiaoyan` | 文小言 | 未进原生 TOP10 | 无；百度系搜索分发仍要覆盖 |
| **P1 扩展必测** | `app_qingyan` | 智谱清言 | 未进原生 TOP10 | 无；禁止与 GLM 云 API 混报 |
| P2 轮换 | `app_spark` / `app_nami` / `app_quark` | 星火 / 纳米AI / 夸克 | — | 默认关闭；夸克是搜索产品，单独成簇 |

**不进主表：** 蚂蚁阿福、豆包爱学、即梦、快对、LoveKey——垂直工具，不是通用发现入口。  
**禁止：** 七个 App 平均成一条「国内可见性」；用网页或小程序冒充对应 App；漏测 DeepSeek 还写「已覆盖主流」。

对外主表必须出现全部 **active=1** 的平台。默认四家 P0；少一家写「覆盖不全」。P1 打开后才要求七家。

---

## 2. 第 0 天：建环境

做完本节全部勾选，才能填表、才能开采。

### 2.1 建目录

在本项目下应已有：

```text
流程/03 测量/
  配置/     queries.csv  aliases.csv  facts.csv  owned_sources.csv  runs_plan.csv  platforms.csv
  清单/     操作员当日清单.md  评分员清单.md
  样本/     （按日自动建）
  台账/     samples.csv
  出数/     metrics_daily.csv  报告模板.md  calibration.csv
  工具/     api_sentinel.py
```

若缺失，按同名文件补齐，不要改列名。

所有 CSV 使用 **UTF-8 带 BOM**，用 Excel / WPS 直接打开即可。若仍乱码：用「数据 → 自文本/CSV」选 UTF-8，不要按系统默认 GBK 导入。用记事本另存时请选 UTF-8。`api_sentinel.py` 写入 `samples.csv` 也会带 BOM。

### 2.2 手机

- [ ] 2 台真机（建议 1 安卓 + 1 iPhone），不要用日常主力机。
- [ ] 关闭系统自动更新 App（或更新后必须重记版本并重做校准）。
- [ ] 能把系统定位切到**目标城市**（设置里的模拟定位仅用于测试城市；正式属地词必须与客户市场一致）。
- [ ] 电量、存储够放当天全部截图。
- [ ] 电脑与手机能互传文件（隔空投送 / 数据线 / 网盘均可）。

### 2.3 账号（每平台一个干净号）

| 平台 | 安装（`store_name`） | 账号要求 |
|---|---|---|
| 豆包 | 豆包 | 新号；不要用日常刷抖音的号 |
| 通义千问 | 通义千问 | 新号或极少历史 |
| DeepSeek | DeepSeek | 新号；不要用网页端登录态代替 App |
| 腾讯元宝 | 腾讯元宝 | 尽量独立微信，不要用生活主号 |
| Kimi | Kimi | 新号 |
| 文小言 | 文小言 | 新号；不要用百度 App 内嵌对话冒充 |
| 智谱清言 | 智谱清言 | 新号；不要用开放平台 API 冒充 |

P2 当月 `active=1` 才安装。每个 App 打开一次，版本抄进 `环境登记.txt`。

每个 App 打开一次，记到 `流程/03 测量/配置/环境登记.txt`（可手写后拍照）：

```text
（字段以 `流程/03 测量/配置/环境登记.txt` 为准，P0+P1 七个版本都要填。）
```

升级任一 App：当天停止用旧基线对比，先做一次 `calib`，再决定要不要重打 `baseline`。

### 2.4 官方 API（哨兵，第 0 天开通，第 1 天跑通即可）

用**公司自己的**云账号，按官网文档开通，密钥只放环境变量，不要写进仓库。

| 通道 | 去哪开通 | 手册要求 |
|---|---|---|
| `api_qwen_search` | 阿里云百炼，开通模型联网搜索 | 强制搜索；用能返回 `search_results` 的协议（DashScope） |
| `api_doubao_search` | 火山引擎「豆包搜索」控制台 | 按官方文档；记住这不是豆包 App |
| `api_deepseek_search` | DeepSeek 开放平台，且开启 web_search | 对照用 |

环境变量（本机）：

```text
DASHSCOPE_API_KEY=
ARK_API_KEY=
DEEPSEEK_API_KEY=
```

第 0 天只需开通并各打通 **1 条试问**。批量日更见第 5 节。

### 2.5 第 0 天完成标准

- [ ] 目录在  
- [ ] `platforms.csv` 里 active 的 P0+P1 都能新建对话  
- [ ] 环境登记已写  
- [ ] 至少一个联网 API 试问成功并留下 JSON  
- [ ] 指定了操作员、评分员、抽检人  

---

## 3. 第 0 天：填配置表

打开 `流程/03 测量/配置/` 里的文件，按列填。**列名不要改。**

### 3.1 `queries.csv`

| 列 | 必填 | 怎么填 |
|---|---|---|
| `query_id` | 是 | `Q01`… 递增，一旦发布不换号 |
| `text` | 是 | 用户会打的**原话**。鼓励残句、错字、口语，禁止关键词堆砌和「如何办理指南」 |
| `set` | 是 | `core` / `holdout` / `explore` |
| `intent` | 是 | `category` / `locale` / `compare` / `qualify` / `risk` |
| `locale` | 是 | 城市或「全国」 |
| `treat` | 是 | `1` 本轮要优化；`0` 不优化。Holdout / explore 必须为 0 |
| `active` | 是 | `1` 本轮在测 |
| `style` | 是 | `tidy` 较完整 / `fragment` 残句 / `typo` 错字 / `slang` 口语 / `voice` 像语音转写 / `mix` 多意图混一句 / `groupchat` 群聊 |
| `branded` | 是 | `0` 问法里**没有**客户品牌名（主验收只用这个）；`1` 点名客户，另表，测的是「点名后是否说对」 |
| `kumar_cat` | 是 | `discovery` / `problem_solution` / `comparison` / `use_case` / `expert` / `brand_research`。与 `intent` 对照：locale→discovery，risk→problem_solution，compare→comparison，category→use_case，qualify→expert，带品牌→brand_research |
| `need_id` | 是 | 同一信息需求共用一个号（如 `N01` = 在哪报名）。每个需求冻结 3–5 条释义 |
| `paraphrase_id` | 是 | 该需求下的第几条原话（`1`/`2`/`3`…）。出数按 need×释义分层，禁止合成一条 |
| `persona` | 是 | `default` / `group` / `voice` / 其他客群码。城市、角色、客群前缀不同 = 不同 `query_id`，禁止跨人格平均 SOV |
| `asset_class` | 是 | `vertical_public` 无品牌、可进资产库；`client_only` 点名客户或含客户事实，禁止沉淀 |

写法（乱问是资产，不是噪音）：

- **Core 15–20 条**：必须像真人随手打的，其中至少一半是 fragment/typo/slang/voice/mix。**主验收只统计 `branded=0`。** 本轮一个字不改。App 金标准只打这些 + Holdout。每个 `need_id` 至少 2 条不同 `style` 的释义。
- **Holdout 8–10 条**：同样要乱，同品类，本轮不优化。不要做成「更工整的对照」。
- **Explore**：乱问池，只给 API 哨兵（`--include-explore`）。App 每周最多抽 5 条轮换，不进合同主表。出数按 `style` 分层，残句不要和完整句合成一条。
- 扩写用 `流程/03 测量/提示词/08_问法扩写.md`，产出一律 explore，禁止自动升 core。
- 禁止：把「这次没问出来再换个说法」写进 Core；禁止把 SEO 标题当问法。

乱问要覆盖的形态：没问号、错别字、语音腔、价格+靠谱+地点挤一句、用错品类词（驾照/上岗证）、群里「有人知道吗急」。

### 3.2 `aliases.csv`

| 列 | 怎么填 |
|---|---|
| `entity_id` | `self` / `excl_01` / `comp_01` |
| `surface` | 会出现在答案里的字符串（含错名、简称） |
| `type` | `self` 自己 / `exclude` 同名异地或无关主体 / `competitor` 竞品 |
| `note` | 可选 |

规则：

- `self` 命中且未命中 `exclude` → 才允许 `mention=1`
- 只命中 `exclude`（例如外地同名机构）→ `mention=0`，`notes` 写「同名排除」
- `competitor` 命中 → `competitor_hit=1`（与 mention 独立）

### 3.3 `facts.csv`

| 列 | 怎么填 |
|---|---|
| `field` | `legal_name` / `address` / `phone` / `license_org` / `not_who` / `fingerprint` |
| `value` | 对外可公开的值 |
| `status` | `confirmed` 或 `pending` |
| `match_hint` | 答案里可能出现的片段，供核对 |

`pending` **不参与** `accuracy` 对错。没有客户勾选，不要把价格、通过率写成 confirmed。

`fingerprint`：本轮你打算写进证据页的可核验细节（例如许可机关全称）。复测时若答案出现它，记事实指纹命中。

### 3.4 `owned_sources.csv`

自有资产，用于 `source_owned`：

| 列 | 例 |
|---|---|
| `source_id` | `site_01` |
| `pattern` | 官网域名、公众号名、头条号名 |
| `type` | `domain` / `account` |

来源字符串包含任一 `pattern` 才 `source_owned=1`。百科、媒体、竞品站都是 0。

### 3.5 `runs_plan.csv`

一行一天：

```text
date,task,channels,run_n,city,operator,notes
2026-08-18,noise,"app_doubao;app_tongyi;app_deepseek;app_yuanbao;app_kimi;app_wenxiaoyan;app_qingyan;api_qwen_search;api_deepseek_search",1,示例市,张三,P0+P1；API 只打有等价通道的
```

`channels` 用分号。`run_n` 只约束 App：`noise`/`weekly`=1，`baseline`/`retest`=3。API 日更固定 **7**（脚本默认），不要把 App 的 1 或 3 传给 API。

### 3.6 配置冻结

四张表填完，跑 `freeze_config.py --case-id --date YYYY-MM-DD`，复制到 `流程/03 测量/案件/{case_id}/冻结/YYYY-MM-DD/`。本轮测量只认本案冻结副本。共享 `配置/` 不能当运行时回退。改问法 = 新一轮，必须重打 baseline。

---

## 4. 操作员手册：App 冷问

每次开测先打开 `流程/03 测量/案件/{case_id}/清单/` 下当日操作员清单，抄好今日 `query_id` 顺序。

### 4.1 开测前（5 分钟）

1. 看 `runs_plan` 今日 `task`、`city`、`run_n`。  
2. 手机定位切到该城市。打开地图确认。  
3. 今日要打的 App 更新已关。把 P0+P1 版本抄到清单抬头。  
4. 电脑建好目录：`流程/03 测量/案件/{case_id}/样本/YYYY-MM-DD/app_doubao/`（元宝、通义同样）。  
5. 通知编排：今日开始，API 哨兵同日跑。

### 4.2 一次有效样本（必须整段做完）

对清单上的每一行 `(query_id, channel, run_index)`：

1. 打开对应 App。  
2. 点 **新建对话 / 新话题**。旧对话里问 = 废样本。  
3. 打开 `queries.csv`，复制 `text`，**一个字不改**贴进输入框。  
4. 只发这一句。不要加「请联网」「请列出机构」。  
5. 等生成结束。滑到最底。  
6. 看完：**聊天气泡 + 所有卡片 / 模块 / 小程序 / 店铺条 + 来源/引用入口**。  
7. 保存，文件名必须是：

```text
{query_id}_r{run_index}.txt
{query_id}_r{run_index}_01.png
{query_id}_r{run_index}_02.png   （一屏不够就继续）
```

   txt 里按这个模板：

```text
query_id: Q01
channel: app_doubao
run_index: 1
time: 2026-08-18 10:21
city: 示例市
app_version: 填写
fresh_session: 1
logged_in: 1
answer:
（粘贴气泡全文）
cards:
（卡片里出现的机构名、电话、按钮文字，气泡没有也要写）
sources:
（来源标题 | 链接或账号；没有则 unknown）
```

8. **结束对话。不要追问。**  
9. 在当日清单该行打勾。  
10. 下一条：再从第 2 步新建对话。同一问法的 r2、r3 也是新对话，不要在同一窗口再问一遍。

建议顺序：先把一个 App 的全部 query×轮次做完，再换 App，减少切错。累了就停，不要为赶工在旧对话里接着问。

### 4.3 废样本（当场作废，重做）

- 问法被输入法改了、少了字  
- 在旧对话里问  
- 定位不是计划城市  
- 只截了半屏卡片  
- 回答未完成就截图  
- 自己追问了第二句  

作废文件改名为 `Q01_r1_VOID.png`，清单该行重做，`run_index` 不变。

### 4.4 当日收工

- [ ] 清单每一行有勾或 VOID+重做  
- [ ] 每个有效样本有 txt + 至少 1 张 png  
- [ ] 文件已到电脑对应目录  
- [ ] 告知评分员可以打分  
- [ ] 不要自己在脑子里总结「今天豆包表现好」——那不是数据  

---

## 5. 编排手册：API 哨兵

### 5.1 规则

- 问法与 App **同一张冻结 `queries.csv`**。  
- 每个 `(query_id, channel, run_index)` **独立请求**，`messages` 只有这一轮 user。  
- 强制联网 / 强制搜索。模型自己决定「要不要搜」= 废。  
- 失败：记 `limited=1`，保存错误 JSON，**禁止换词重试**。可在 10 分钟后用**同一原话**重试 1 次，仍失败则 limited。  
- 存：`流程/03 测量/案件/{case_id}/样本/YYYY-MM-DD/{channel}/{query_id}_r{n}.json`

### 5.2 怎么跑

在项目根目录（已配置环境变量）：

```bash
python3 "流程/03 测量/工具/api_sentinel.py" --date 2026-08-18 --channels api_qwen_search --case-id 本案 --project-id 本案项目号
```

脚本会读冻结配置，按 `active=1` 的 core+holdout 各打 `run_n` 次（**默认 7**，对应品牌检测 SE<0.10；来源分析用 `--run-n 8`），写入 JSON，并追加 `samples.csv` 里通道为 `api_*` 的行（打分列先空着）。

未开通的通道不要写进命令。不要把 `app_*` 传给这个脚本。

### 5.3 试跑通过标准

打开一个 JSON，能看到：

- 原话与 `queries.csv` 一致  
- 有答案文本  
- 若协议支持，有搜索来源列表  

没有来源：`source_raw=unknown`，不是作废。

---

## 6. 入库

### 6.1 `samples.csv` 一行 = 一次独立试验

列名以仓库里的表头为准。2026-08 补强后增加了 `search_triggered` / `position` / `sov_eligible` / `fingerprint_hit`。旧冻结表没有这些列时，用附表计算，不要改已经在采的旧列名。可在 `notes` 写说明。

`sample_id` 建议：`{date}_{channel}_{query_id}_r{n}`  
例如：`20260818_app_doubao_Q01_r1`

### 6.2 路径规则

- App：`answer_text_path` 和 `screenshot_path` 都要有。多张图用分号。  
- API：`raw_json_path` 必有；`screenshot_path` 空。  
- `fresh_session` App 必须为 `1`，否则该行 `limited=1` 且不进正式出数。  
- `logged_in` 如实记。干净号登录记 1，不是废样。

### 6.3 正式出数资格

同时满足才进 `metrics_daily.csv`：

1. `limited=0`  
2. App 有 txt+图，或 API 有 json  
3. `query_id` 在冻结表且 `active=1`  
4. `fresh_session=1`  
5. 五指标已打完（抽检完成前可先出「待审稿」，标题必须写待审）

---

## 7. 评分手册

打开 `流程/03 测量/案件/{case_id}/清单/` 下评分员清单（若尚未生成，先用模板按本案路径抄）。一次只评一行。先看 txt 和全部截图，再填本案 `台账/samples.csv`。

### 7.1 `mention`（0/1）

1. 在答案+卡片全文里找 `aliases` 中 `type=self` 的任一 `surface`。  
2. 若同时出现 `type=exclude` 的主体，且无法判断说的是客户：`mention=0`，`notes=同名排除`。  
3. 只在卡片出现、气泡没有：`mention=1` 且 `card_mention=1`。  
4. 模糊「当地有培训机构」但无任何 self 字符串：`mention=0`。

### 7.2 `recommend`（0/1/2）

在 `mention=0` 时仍可打（例如只推荐了竞品，自己 mention=0、recommend=0）。

| 值 | 标准 | 例子 |
|---|---|---|
| 0 | 未点名为可选项；或仅中性出现 | 「有一家叫XX的机构」 |
| 1 | 出现在名单/对比表/「可以考虑」 | 列表第 2 个 |
| 2 | 明确推荐、点名可报名、唯一主推 | 「建议去XX报名」 |

拿不准：先标 `1` 并 `notes=待裁定`，抽检时定，回写本表「例子」。不要用 3 或 0.5。

### 7.3 `accuracy`

只核 `facts.csv` 里 `status=confirmed` 的字段。

| 值 | 标准 |
|---|---|
| `absent` | 未提及这些字段 |
| `correct` | 提到的字段与台账一致（允许简称，若简称在 aliases.self） |
| `wrong` | 至少一项与台账冲突（地址、电话、许可、把客户说成 exclude 主体） |
| `conflict` | 同一答案里既有对的又有错的 |

`mention=0` 且未陈述客户事实 → `absent`（不要打 wrong）。

### 7.4 `source_raw` / `source_owned`

- 抄来源标题与链接/账号，原文粘贴，多条用分号。  
- 没有入口：`unknown`。  
- `owned_sources.pattern` 任一命中 → `source_owned=1`，否则 0。  
- 「好像依据官网」但无链接：`source_owned=0`。

### 7.5 `competitor_hit`

卡片或正文命中任一 `type=competitor` → 1，否则 0。与 mention 独立。

### 7.6 `limited`

出现任一则 `1`，且该行不进正式 P()：

- 缺图 / 缺 txt / 缺 json  
- 非新对话  
- 定位错城市  
- 问法被改  
- API 失败  
- 回答明显截断且未重做  

### 7.7 `search_triggered` / `position` / `fingerprint_hit`

| 字段 | 取值 | 怎么打 |
|---|---|---|
| `search_triggered` | 0/1/blank | API：协议里能看到本次触发了搜索 → 1，明确未搜 → 0。App：截图或卡片能判断则填，看不出留空，**不要猜**。未联网与已联网是两个通道，禁止混报。 |
| `position` | 1/2/3/99 | 客户在名单/对比表中的位次；不在前三但被提到 → 99；没有名单 → 空。`recommend=2` 且唯一主推可记 1。 |
| `fingerprint_hit` | 0/1 | 答案出现 `facts.csv` 里任一条 `fingerprint` → 1。这是**指纹命中 / 预埋事实回传**，不是 `source_owned`。 |
| `sov_eligible` | 0/1 | 本行出现客户 **或** 合格竞品（`aliases` 里 type=competitor，且该竞品在本切片至少出现 2 次）。一次幻觉店名不进分母。出数脚本可按切片回填，评分员也可先空着。 |

`source_owned=1` 只说明「引了自有源」（选引）。`fingerprint_hit=1` 才说明「答案复述了预埋台账事实」（指纹命中）。两者不要合成一个数。

情感 / 正负评价：**不要打进主表**，比提及不稳定约 6–7 倍，需要时另开观察表并加宽 CI。

### 7.8 评分员当日完成标准

- [ ] 今日所有有效行五指标填完  
- [ ] 能判断的行补了 `search_triggered` / `position` / `fingerprint_hit`  
- [ ] `rater` 填了自己的名字  
- [ ] 待裁定行告诉抽检  
- [ ] 没有根据「整体感觉」改某一指标  

---

## 8. 抽检手册

| 任务 | 抽检比例 |
|---|---|
| baseline / retest 的 Core | **100%** |
| baseline / retest 的 Holdout | 20% |
| weekly | 20% |
| api 哨兵 | 10%（重点看问法是否被改、是否联网） |

抽检人独立打一套（可在 `notes` 写 `audit:`），与评分不一致：

1. 两人一起打开原文。  
2. 对照本手册 7.x，改的是**规则或别名表**，不是「这题我感觉提到了」。  
3. 更新 `aliases` / 本手册例子后，**整批重跑该字段**，不要只改这一行。

抽检完成前，报告标题必须带「待审」。

基线 / 复测的 Core 抽检时，另抽不少于 10 句：这句话是否被 `source_raw` 里某条来源托住（句级选引）。只记抽检表，不进主 KPI。指纹命中看 `fingerprint_hit`，需要更细时在 `facts.csv` 把 fingerprint 拆成原子事实（对 / 错 / 缺）。

---

## 9. 出数

优先跑：

```bash
python3 "流程/03 测量/工具/metrics_rollup.py" --date 2026-08-18 --case-id 本案 --project-id 本案项目号
```

主验收切片再加：`branded=0`（只统计不带客户品牌名的问法）。残句与完整句按 `style` 分层看，不要合成一条对外结论。

### 9.1 每天

用正式行（第 6.3 节）按下面切片汇总，写入 `流程/03 测量/案件/{case_id}/出数/metrics_daily.csv`：

切片键：`date, platform, channel, query_set`（core 与 holdout 分开；**不要**把 app 和 api 加在一起；**不要**把多个 App 平均成一个数）。

| 列 | 算法 |
|---|---|
| `n_valid` | 正式行条数（门禁后） |
| `n_limited` | 当日该切片 limited 行（只注释，不进分母） |
| `n_unscored` | 未打完五指标的行（不当 0） |
| `p_mention` | 同一 `query_id` 先平均，再按 `need_id` 等权（只计 `branded=0`）。**不是** mention=1 行 / n_valid |
| `p_mention_lo` / `p_mention_hi` | **need 簇** cluster bootstrap 95% CI（同一 need 抽到两次计两次；B=1000，种子固定）。**不是**响应级 bootstrap |
| `p_mention_p` / `p_mention_p_holm` | 簇 bootstrap 对 0 的单侧 p；P0 切片再做 Holm（`multiple_testing` 含 holm 时） |
| `p_recommend` | 与 `p_mention` 同一套 need 等权；query 内 recommend≥1 再平均（IAB Prominence 代理） |
| `p_recommend_lo` / `p_recommend_hi` | 与提及同一套 need 簇 cluster bootstrap |
| `p_wrong` | 与 `p_mention` 同一套 need 等权（accuracy=wrong 或 conflict） |
| `p_owned` | 与 `p_mention` 同一套 need 等权（**选引**） |
| `p_fingerprint` | 与 `p_mention` 同一套 need 等权（**指纹命中**，预埋事实回传） |
| `p_sov` | 响应加权：mention=1 的行 / 合格竞品分母行（自己或合格竞品至少出现一个）。与 P(提及) 不可直接比 |
| `p_competitor` | 与 `p_mention` 同一套 need 等权 |
| `jaccard_brand_vs_prev` | 本日 mention=1 的 query_id 集合 vs 上一日，Jaccard |
| `jaccard_source_sameday` | 同日不同 `run_index` 的来源域名集合 Jaccard（随机性） |
| `jaccard_source_24h` | 与上一日来源域名集合 Jaccard（漂移）。两窗分开报，禁止混写成「变了」 |
| `p_mention_roll14` | 同一切片过去最多 14 个已出数日的 need 等权 P(提及) 平均 |
| `n_bootstrap` | 实际 bootstrap 次数；need 簇 < 2 则 CI 为空 |
| `n_clusters` | 进入等权平均的 need 数 |

分母 < 3 的切片：表上保留，报告里写「轮次不足，不能下结论」。  
**两条 CI 重叠 → 禁止写「A 比 B 高」或「比基线提升了」。** 小于 5–7 个百分点的 citation / 提及差距，先当噪声。

监测看 **14 日滚动 P(提及)**，不把昨天一个点画成趋势。来源集合日际 Jaccard 低（文献约 0.34–0.42）是系统属性，不是采集事故；**不要用 1 天 3 轮下「来源变了」的结论。**

### 9.2 一页纸

复制 `流程/03 测量/出数/报告模板.md`，只填 App 三通道主表。API 放附表。必须写数据等级（定向 / 决策）和采集架构（主动冷问，不是面板/平台原生）。结论用语见模板，禁止写「保证会被推荐」。

### 9.3 干预后（retest）

默认 `causal_claim=descriptive_until_isolation`。**禁止**再用「两组 CI 错开」判断效果。

1. 确认 `intervention_ledger.csv` 有完成日，再加等待天数。  
2. 同一冻结词表、城市、产品模式。确认性 L1 用预先写死的 7 日滚动或单日 7 轮；3 轮只够定向描述。  
3. 处理组 / 对照按 `project.csv` 的 `treat_need_ids` / `holdout_need_ids`，必须同品类。旧的「电工对照叉车」作废。  
4. 跑：

```bash
python3 "流程/03 测量/工具/metrics_rollup.py" --freeze-id 冻结日 --did-pre 基线日 --did-post 复测日 --require-coverage --case-id 本案 --project-id 本案项目号
```

5. 看 `案件/{case_id}/出数/did.csv`：估计量是 `DiD = mean(Δ_treat) − mean(Δ_hold)`，推断看 **DiD 的 95% CI 是否含 0**。  
6. 仅当 `causal_claim=did_isolated` 且主终点 mention 的 CI 不含 0，才允许写确认性 L1。否则只写「受控前后描述」。  
7. 缺多期 pre、缺对照、混通道、覆盖不全：`verdict=insufficient_clusters` 或「不能下结论」。

### 9.4 轮次与窗口（不要抄厂商「30 次」）

| 目标 | 最低协议 | 出处 |
|---|---|---|
| 品牌提及 SE 大约 <0.10 | 每问每天约 **7** 轮，或 3 轮 × 连续 7–10 日滚动 | Schulte 2026 |
| 来源覆盖较稳 | 约 **8** 轮；来源结论禁止用单日 3 轮 | Schulte 2026 |
| 滚动 SE<0.10 / 0.05 | 约 10 日 / 24 日窗 | Schulte 2026 |
| 何时停采 | 看秩稳定，不看固定 N | Sielinski 2026-07 |
| 厂商博客 30 次 | **不作合同门槛** | Maximus 等，营销口径 |
| 问法条数 | Core+Holdout **<50 条问法**只是探索级（IAB：这是问法数，不是轮次） | IAB 配套稿 |

无品牌类目问（`kumar_cat=discovery` 或 `use_case`，且 `branded=0`）另报 **P0 四 App top-1 一致率**（四条答案第一名是否同一家）。P1 另附，不与 P0 合成。文献量级约四成，低不是事故；**禁止用一个 App 的名次外推其余。**

---

## 10. 校准（App vs API）

每周与 `weekly` 同一天。

1. 取 12 个 core 的 `query_id`（写在当日清单「校准子集」）。  
2. 用**当天已采的** App 1 轮，不必重问。  
3. 用当天 API **7** 轮的 `p_mention`（及其 CI）。  
4. 按「平台族」对齐：  
   - 豆包 App ↔ `api_doubao_search`  
   - 通义 App ↔ `api_qwen_search`  
   - DeepSeek App ↔ `api_deepseek_search`（仍分表，只看同向）  
   - 元宝 / Kimi / 文小言 / 清言：**没有官方等价 API 就不要硬对齐**，只报 App。  
5. `gap = api_p_mention - app_p_mention`，写入 `流程/03 测量/案件/{case_id}/出数/calibration.csv`。  
6. 另记引用面板：App 可见来源条数 / 域名集合 vs API 的 `search_results` 或 annotations。API 面板通常更窄，**窄不等于 App 没引用**。  
7. 豆包 annotations、千问 `search_results`、OpenAI `sources`（看过的）与 `citations`（写进答案的）语义不同，禁止加总后排名。  
8. 判定：

| 连续 3 周 | 行动 |
|---|---|
| 同向且 gap 波动小于 15 个百分点 | 该 API 可当哨兵；对外仍报 App |
| 反向，或单周 gap 变化超过 20 个百分点 | 停用该 API 趋势 |
| App 或 API 改版 | 当周重校准，旧 gap 作废 |

---

## 11. 五种任务的当日剧本

### 11.0 noise 日

操作员 A：豆包 + 通义 + DeepSeek。操作员 B：元宝 + Kimi + 文小言 + 清言。各 1 轮。禁止改产品页、发新文、改问答。  
编排：有等价 API 的通道各 7 轮。  
出数：只描述波动和 CI 宽度，标题写「噪声底」，禁止写涨跌原因。P1 本周至少出现 2 天。

### 11.1 baseline 日（建议拆成 2 人 × 2 天）

第 1 天：P0 四 App 全表 3 轮（两人对打）。  
第 2 天：P1 三 App 全表 1 轮；P0 缺轮次补齐。  
编排：同日 API **7** 轮。  
晚上或次日：评分 → 抽检 Core 100% → `metrics_rollup.py --case-id 本案 --project-id 本案项目号` → 出待审一页纸。主表必须有 7 行平台，少一家写「覆盖不全」。  
全部抽检完，去掉「待审」，冻结为 `基线_YYYY-MM-DD.md`。

### 11.2 weekly 日

操作员：P0+P1 七 App × 全表 × 1 轮（约 6–7 小时，两人分）。  
编排：API 日更 7 轮（若工作日已日更，当天不必加跑）。  
评分 + 20% 抽检。  
出 14 日滚动监测表，和基线比的是「有没有异常」，不是「已经优化成功」。CI 重叠则写无法区分。  
收工跑 `asset_deposit.py --case-id 本案 --project-id 本案项目号`。冲刺复测日还要在 `资产库/干预复盘/plays.csv` 补一行。

### 11.3 calib 日

与 weekly 合并：校准 12 问用 weekly 的 App 行。  
只给豆包 / 通义 / DeepSeek 写 API gap。元宝、Kimi、文小言、清言不写 gap。

### 11.4 retest 日

与 baseline **同一套动作**。  
报告必须有：等待天数、干预台账日期、处理组 vs 监测组的 Δ 与 CI、选引与指纹命中、版本是否变化、噪声底是否存在。

---

## 12. Agent 怎么按本手册做

Agent 只使用这 7 件事（详见方案第 10 节）：

1. 读冻结配置，生成当日清单（问法原样）。  
2. 跑 `api_sentinel.py`。  
3. 扫描当日目录，把齐套的 App 文件写成 `samples.csv` 行。  
4. 按第 7 节规则打分（或只填候选，等人确认 recommend）。  
5. 汇总第 9 节。  
6. 算第 10 节 gap。  
7. 列出 limited / 待裁定 / 缺文件。  

Agent **禁止**：改写问法、旧会话追问、自动操作任何消费级手机 App、把 App+API 合成一条可见性、宣布 GEO 成功。

人机一天：清单 → 人采 App → Agent 采 API 并入库打分 → 人只看冲突和抽检 → Agent 出一页纸。

落地顺序：第 1 周 Agent 只跑 API；第 2 周入库+规则分；第 3 周周报+校准。

---

## 13. 四周日历（按做）

**第 0 天（本手册第 2–3 节）**  
环境 + 配置表冻结（含 `branded` / `kumar_cat`）+ 书面披露合格竞品集合 + API 试问 1 条。

**第 1 周（噪声底，禁止干预）**  
任务 `noise`：P0 每天 1 轮，P1 至少两天各 1 轮 + API 日更 7 轮。只描述波动，不解释「涨了/跌了」。

**第 2 周（正式基线，仍禁止干预）**  
`baseline`：App 3 轮 + API 7 轮。Core 抽检 100%。出定向级一页纸。第一次校准。第 1–2 周合在一起才是变异基线。

**第 3 周**  
`weekly` + 第二次校准。**这时才允许开始一轮一类证据的干预。** Agent 可入库打分，人只抽检。

**第 4 周**  
继续 weekly / 第三次校准。若第 3 周已干预：等 3–7 天 → `retest` → 默认受控前后描述。仅当 `causal_claim=did_isolated` 且 `did.csv` 主终点 CI 不含 0 才勾确认性 L1。没有干预前噪声底，不允许把涨跌写成效果。

---

## 14. 红线与故障

### 14.1 红线

- 只采豆包/元宝/通义三家还对外写「已覆盖国内主流」。DeepSeek 是 P0，漏测即覆盖不全。  
- 网页或 API 数字写成「用户在手机上会看到」。  
- 连续对话、改写、换词重问当正式样本。  
- 缺轮次补假数据。  
- 未授权自动点击消费级 App、抓包、模拟器农场。  
- 合同主验收不认 `app_*` + Holdout。单日 3 轮只能写定向级，不能冒充决策级。  
- 用阅读量、发文量、总咨询、情感分代替本手册指标。  
- CI 重叠时宣布「比基线提升」或「A 优于 B」。  
- 没有干预前噪声底就解释环比。  
- 把选引（有链接）写成指纹命中（答案复述了预埋事实）。  
- 主表混入 `branded=1` 的点名问法。  
- 把同一 `need_id` 的多条释义合成一条 P(提及)。  
- 豆包「标准」与「深度搜索」混报；未联网与已联网混报。  
- 跨人格 / 跨城市平均 SOV。  
- 用 C-Eval、CMMLU 等闭卷分数代替开放冷问。  
- 把千问 `search_results`、豆包 annotations、OpenAI sources 加总成一个引用榜。  
- 未填 `project.csv`、未冻结配置、或 `causal_claim` 仍是 descriptive 时写「L1 有证据」。  
- 用两组独立 CI 错开代替 `DiD` 区间。  
- 正式出数后不跑 `asset_deposit.py`，或把 facts / 截图 / 客户全称推进资产库。  
- 把旧城品类面板抄成新客户基线。

### 14.2 故障

| 现象 | 处理 |
|---|---|
| App 要登录才能问 | 用干净号登录，`logged_in=1`，不要用主号 |
| 定位切不了 | 属地词当天改 `limited`，或换能切定位的设备 |
| 卡片复制不了 | 截图 + 在 txt 的 cards 手抄机构名 |
| API 429 / 额度 | 降频，未跑完标 limited，不换词 |
| 两人 mention 总打架 | 先补 aliases，再整批重评 |
| App 强制升级 | 记新版本，做 calib；基线对比降级 |

---

## 15. 现在立刻做的 10 步

1. 指定操作员、评分员、抽检、目标城市。  
2. 打开 `流程/03 测量/配置/queries.csv`，写入 15 条 core + 8 条 holdout。  
3. 填 `aliases.csv`、`facts.csv`、`owned_sources.csv`。  
4. 跑 `python3 "流程/03 测量/工具/freeze_config.py" --date 今天 --case-id 本案`，冻结写到 `流程/03 测量/案件/{case_id}/冻结/今日日期/`。  
5. 写 `runs_plan.csv` 第一行 `noise`。  
6. 真机安装 active 的 P0 四 App，写环境登记。  
7. 开通至少一个官方联网 API，跑：  
   `python3 "流程/03 测量/工具/api_sentinel.py" --date 今天 --freeze-id 今天 --channels api_qwen_search --smoke --case-id 本案 --project-id 本案项目号`  
8. `python3 "流程/03 测量/工具/make_checklist.py" --date 今天 --task noise --freeze-id 今天 --case-id 本案`，按本案清单冷问。  
9. 当日文件进 `流程/03 测量/案件/{case_id}/样本/今天/app_*/`。  
10. 次日打分后：`metrics_rollup.py --freeze-id 今天 --require-coverage --case-id 本案 --project-id 本案项目号`，再 `asset_deposit.py --case-id 本案 --project-id 本案项目号`。没有本案冻结目录不准出数。

---

## 16. 文献补强从哪来

协议改动的依据与「不要抄错的博客数」见 `研究/文献精读_测量方案补强_V1.md`。  
权威顺序：IAB 2026 行业标准 ≈ KDD 2024 同行评议 > Schulte / Sielinski / Zhang / Kumar 预印本全文 > 厂商博客。  
厂商「每问 30 次」和部分博客把 Schulte 写成「3 次」——**以论文为准，以本手册第 9.4 节为准。**

第二轮（50 论文 + 32 博客）只吸收对照补丁里的新条款，全文见 `研究/测量文献/对照补丁_V2.md`。

---

## 17. 第二轮必须记进台账的三件事

1. **产品模式**：每次 App 冷问在环境登记和 `samples.product_mode` 写 `standard` / `deep_search` / `unspecified`。当天只允许一种。深度搜索与标准禁止混进同一张 P()。看不出是否联网则 `search_triggered` 留空，未联网不与已联网混报。  
2. **释义**：出数主表仍按 query_set；附一张 `need_id` 分层表。同一需求的 fragment 与 tidy 不要平均成一个数对外讲故事。  
3. **top-1**：weekly / baseline / retest 的无品牌类目问，P0 四 App 各取该问第一家机构名，报一致率。P1 另附。不一致是常态。

---

## 18. 战略双账：结这一单，同时留资产

测量有两个出口，缺一个都算这轮白做。

| 账本 | 回答什么 | 主文件 | 对应商业动作 |
|---|---|---|---|
| **项目账** | 这个客户、这座城、这轮干预，L1 有没有证据 | `project.csv` + 出数报告 | SOP 诊断 / 冲刺复测 / 续约 |
| **资产账** | 这个品类在这些 App 上，问法、谁被提到、引哪些域、App 和 API 差多少 | `流程/03 测量/资产库/` | 下一单复用词表、售前快检、产品线 A 自动化 |

两本账**共用同一次冷问**，不另采一套「研究样本」。差别只在出数时切哪些列、脱敏哪些列。

### 18.1 项目账：必须先写目标卡

开测前填 `流程/03 测量/配置/project.csv`，少这一行不准出「GEO 效果」四个字。

| 字段 | 这一单怎么填 |
|---|---|
| `sop_stage` | `诊断` / `冲刺` / `续约`（对 SOP 八步：1–3 诊断，执行+复测=冲刺，下一轮监测=续约） |
| `vertical` / `city` | 品类口头说法 + 城市，不要写客户品牌 |
| `primary_goal` | 只允许可见性原话，例如「在无品牌发现问上提高被正确提及/推荐的概率」 |
| `kpi` | 合同只认 `L1_mention_recommend`。咨询、报名是 L2，只观察 |
| `success_rule` | 必须可判定：哪些 need、哪些平台、DiD 主终点 CI 是否含 0、覆盖是否齐全 |
| `treat_need_ids` / `holdout_need_ids` | 处理组与对照的信息需求，不是文章篇数 |

阶段与任务对齐：

| 商业阶段 | 手册任务 | 项目账交付 | 资产账交付 |
|---|---|---|---|
| 诊断（产品线 A） | `noise` + `baseline` | 定向级基线一页纸，不下干预结论 | 词表池 + 首张品类面板 + 来源域 |
| 冲刺（产品线 B） | 一轮一类证据 + `retest` | L1 四选一；`plays.csv` 补一行 | 面板续写；不把客户 URL 写进资产 |
| 续约 | `weekly` + `calib` | 14 日滚动，异常才报警 | 校准史、来源域时间序列 |

没有噪声底的诊断，可以卖「现在长什么样」，不能卖「我们能优化」。  
复测不写 `plays.csv`，冲刺在资产账上等于没发生。

### 18.2 资产账：只存脱敏后仍值钱的

值钱的是**可迁移结构**，不是客户故事：

1. **问法形态库**：无品牌原话、`need_id`、style/persona。下一座城把 `{city}` 换掉就能开测。  
2. **品类面板**：各 App 上「有没有人被推荐、竞品出不出现、搜没搜」。不写谁是甲方。  
3. **来源域图**：这个品类各引擎爱引哪些站。下一单先看缺口再写内容。  
4. **校准史**：App 版本 × API gap。哨兵能不能用，靠这条时间序列。  
5. **干预类型复盘**：`owned_page` / `faq` / `listing` / `video` 等，只记类型和 L1 结论。满 5 个同品类项目才能谈「这类干预更常移动分布」。

**禁止进资产库：** `facts.csv`、截图、电话地址、`branded=1`、`fingerprint_hit`、客户 `self` 全称、treat 标记。  
细则：`流程/03 测量/配置/asset_policy.csv`。

每次正式出数后：

```bash
python3 "流程/03 测量/工具/asset_deposit.py" --date 当天 --case-id 本案 --project-id 本案项目号
```

结案检查：`资产库/登记/deposits.csv` 有本日；`plays.csv` 在冲刺阶段有一行。缺登记 = 项目账可能有了，资产账是空的。

### 18.3 资产怎么反哺下一单（不要抄错）

| 可以 | 不可以 |
|---|---|
| 用词表池当 explore / 新城 core 的草稿，仍要本地冻结 | 把旧城面板数字写成新客户基线 |
| 用来源域图决定「先补哪类证据」 | 把上一单 L1 成功保证给下一单 |
| 用校准史决定本周 API 密不加密 | 版本已变还沿用旧 gap |
| 用乱问形态覆盖率检查新词表 | 把客户点名问法留在公共池 |

资产是**先验和脚手架**，每一单的金标准仍是本城、本版本、本冻结词表的 App 冷问。

