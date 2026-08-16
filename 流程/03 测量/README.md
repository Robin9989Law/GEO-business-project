# GEO 测量工作区

这是 GEO 商业项目的**测量系统入口**。按天执行的细则在 [GEO抽样测量操作手册_V1.md](GEO抽样测量操作手册_V1.md)。本页说明：测什么、不能声称什么、目录怎么走、命令怎么跑。

**当前状态（2026-08-16）**

- 协议、配置、脚本、冻结副本已齐。单元测试 `工具/test_measure.py` 已通过。
- 共享 `配置/` 只是复制源。演示词表在 `配置/`；本案冻结必须由 `freeze_config.py --case-id` 写到 `案件/{case_id}/冻结/{日期}/`。默认最小档：P0 四家 App，8 条处理问 + 12 条同品类监测问（H01–H06 各 2 条释义）。
- **还没有真机正式样本。** 在采满噪声底并出第一张基线表之前，对外只称「方案框架 / 定向诊断准备」，不称「已完成 GEO 基线」或「L1 有效果」。

---

## 1. 这一套在测什么

金标准是中国消费级**手机 App 冷会话**：新建对话、原话只问一句、截图 + 全文入库。官方联网 API 只当日更哨兵，必须和 App 分表，禁止画成一条「可见性」。

合同主终点只有 **L1**：在**不带客户品牌名**的发现问上，客户被提到 / 被列为可选项的概率。咨询量、报名量是 L2，只观察，不写进因果结论。

默认估计目标写在 [配置/project.csv](配置/project.csv)：

| 字段 | 默认值 | 含义 |
|---|---|---|
| `estimand` | `platform_need_equal_ATT` | 每个平台单独估；need 等权，不按问法条数加权 |
| `query_population` | 冻结词表均值 | **不是**全市用户总体 |
| `primary_endpoint` | `p_mention` | 主终点；`p_recommend` 是次要终点 |
| `control_design` | `same_category_unmatched_jobs` | 同品类监测组，本轮不优化；不是反事实 |
| `causal_claim` | `descriptive_until_isolation` | 未做城市或分阶段隔离前，**不能叫确认性 DiD** |

对照为什么这样改、何时才能勾确认性 L1：见 [配置/对照设计.md](配置/对照设计.md)。

---

## 2. 现在允许写、禁止写

| 阶段 | 允许 | 禁止 |
|---|---|---|
| 诊断（`noise` + `baseline`） | 各 App 现在长什么样；Issue 清单 | 「已经优化成功」 |
| 冲刺（一类证据 + `retest`） | 「受控前后描述」 | 两组独立 CI 错开就当效果 |
| 确认性 L1 | 仅当 `causal_claim=did_isolated` 且 `出数/did.csv` 主终点 95% CI **不含 0** | 把 API、网页、平均七家当成用户所见 |
| 续约（`weekly`） | 14 日滚动异常报警 | 用周报重开因果结论 |
| 任何阶段 | 选引与指纹命中分报；覆盖不全就写覆盖不全 | 保证会被推荐；报名因此增长；情感当主 KPI |

诊断、冲刺、续约的验收规则在 `project.csv` 的 `success_rule_diagnosis` / `success_rule_sprint` / `success_rule_retain`，不要混用。

---

## 3. 目录

```text
流程/03 测量/
  README.md                 本页
  GEO抽样测量操作手册_V1.md 按天操作（角色、冷问、评分、红线）
  配置/                     活动表（只作复制源；改完必须重新冻结到本案）
    project.csv             这一单目标卡
    queries.csv             问法；active=1 才采
    platforms.csv           App / API 档位
    aliases.csv             客户 / 竞品 / 同名排除
    facts.csv               已确认事实与 fingerprint
    owned_sources.csv       自有域名 / 账号
    intervention_ledger.csv 干预台账（Issue、URL、等待天数）
    对照设计.md             Holdout 与因果声明
    环境登记.txt            机型、版本、产品模式
  案件/{case_id}/           本案唯一运行时
    冻结/{日期}/            本轮只认这里（freeze_config 从配置/复制）
    清单/                   操作员当日清单
    样本/{日期}/{通道}/     App 的 txt+图；API 的 JSON
    台账/samples.csv        一行一次独立试验
    出数/                   metrics_daily / did / coverage
  出数/报告模板.md          报告模板（不是本案出数）
  工具/                     冻结、派单、哨兵、出数、沉淀、测试
  资产库/                   脱敏后的跨单资产（不是客户报告）
  提示词/                   Agent 用；问法本身不是提示词
  文献.md                   指向仓库根 `研究/`（论文不放本目录）
```

所有 CSV 用 **UTF-8 带 BOM**，Excel / WPS 可直接打开。

---

## 4. 谁干什么

| 角色 | 先读 | 当天只做 |
|---|---|---|
| 负责人 | 手册第 1、13、14、18 节；`project.csv`；对照设计 | 定城、定档、定阶段、禁改问法 |
| 操作员 | 手册第 2、4、11 节；当日生成清单 | 真机冷问、截图、丢文件 |
| 评分员 / 抽检 | 手册第 7、8 节 | 打开原文打分；基线 / 复测 Core 必须第二人 |
| 编排 | 手册第 5、9、10 节 | 冻结、API 哨兵、出数、沉淀 |

问法从冻结 `queries.csv` **原样**取出。禁止润色、补「请联网」、在旧对话里追问、未授权自动点消费级 App。

---

## 5. 默认最小档（现在就按这个采）

**App（P0，必测）**

| 通道 | 产品 | 官方等价联网 API |
|---|---|---|
| `app_doubao` | 豆包 | `api_doubao_search`（不是豆包 App） |
| `app_tongyi` | 通义千问 | `api_qwen_search`（不是通义 App） |
| `app_deepseek` | DeepSeek | `api_deepseek_search`（网页 / API ≠ App） |
| `app_yuanbao` | 腾讯元宝 | 无，只报 App |

Kimi / 文小言 / 清言在 `platforms.csv` 里是 P1，默认 `active=0`。标准档再打开。不要只采豆包 / 元宝 / 通义三家还写「已覆盖国内主流」——DeepSeek 是 P0。

**问法（`queries.csv` 里 `active=1`）**

- 处理组 Core：Q01–Q05、Q08、Q11、Q12（need N01 / N02 / N03）
- 监测组 Holdout：Q17–Q22 与 Q25–Q30（need H01–H06 各 2 条释义，仍是叉车证、同城）
- Explore：只给 API 乱问池，不进合同主表，不得自动升 Core

**任务与轮次**

| 任务 | 何时 | App | API | 对外等级 |
|---|---|---|---|---|
| `noise` | 干预前 5–7 日，至少两天 | 每天 1 轮 | 7 轮 | 噪声底，不解释涨跌 |
| `baseline` | 噪声周之后 | P0 × 3 轮 | 7 轮 | 定向级描述 |
| `weekly` | 固定周 | 1 轮 | 7 轮 | 看 14 日滚动 |
| `retest` | 干预 + 等待之后 | 与 baseline 同口径 | 7 轮 | 默认「受控前后描述」 |
| 确认性 L1 | 对照已隔离且预注册 | 7 日滚动或单日 7 轮（写死一种） | 7 轮 | 看 `did.csv` 是否跨 0 |

3 轮只够定向诊断。厂商「每问 30 次」和博客把 Schulte 写成「3 次 / 7 天」都不进合同。

---

## 6. 从第 0 天到出数

在项目根目录执行。把日期换成当天。已有冻结日 `2026-08-16` 可先沿用，**改问法后必须新冻结**。

### 6.1 第 0 天：建档

1. 改 `配置/project.csv`（阶段、城市、品类、`client_code` 用代号）。
2. 把 `queries.csv` / `aliases.csv` / `facts.csv` / `owned_sources.csv` 换成真实客户，不要留「示例培训」。
3. 写 `配置/环境登记.txt`（四 App 版本、是否深度搜索、是否联网）。
4. 冻结：

```bash
python3 "流程/03 测量/工具/freeze_config.py" --date 2026-08-16 --case-id 本案
python3 "流程/03 测量/工具/test_measure.py"
```

5. 开通至少一个官方联网 API（环境变量 `DASHSCOPE_API_KEY` 等，不要写进仓库），试跑：

```bash
python3 "流程/03 测量/工具/api_sentinel.py" --date 2026-08-16 --freeze-id 2026-08-16 --channels api_qwen_search --smoke --task noise --case-id 本案 --project-id 本案项目号
```

### 6.2 采集日

```bash
python3 "流程/03 测量/工具/make_checklist.py" --date 2026-08-16 --task noise --freeze-id 2026-08-16 --case-id 本案
```

按生成的 `流程/03 测量/案件/{case_id}/清单/操作员_2026-08-16_noise.md` 打。文件放到：

`流程/03 测量/案件/{case_id}/样本/2026-08-16/app_doubao/Q01_r1.txt` 与对应截图。

API 日更（有密钥再开；元宝不要编通道）：

```bash
python3 "流程/03 测量/工具/api_sentinel.py" --date 2026-08-16 --freeze-id 2026-08-16 --channels api_qwen_search --task noise --case-id 本案 --project-id 本案项目号
```

原始 JSON **不会覆盖**。重跑会另存 UUID 文件并在台账里记 `retry_of`。

### 6.3 评分与出数

打开原文，按手册第 7 节写入 `流程/03 测量/案件/{case_id}/台账/samples.csv`。缺任一主指标（mention / recommend / accuracy / source_owned / competitor_hit）的行**不进该指标分母**，不会再被当成 0。

```bash
python3 "流程/03 测量/工具/metrics_rollup.py" --freeze-id 2026-08-16 --date 2026-08-16 --require-coverage --case-id 本案 --project-id 本案项目号
python3 "流程/03 测量/工具/asset_deposit.py" --date 2026-08-16 --freeze-id 2026-08-16 --case-id 本案 --project-id 本案项目号
```

`--require-coverage`：P0 缺一家直接失败。报告只填 [出数/报告模板.md](出数/报告模板.md)，先 App 后 API。出数文件写在 `案件/{case_id}/出数/`。

复测（仍默认描述，不是确认性 L1）：

```bash
python3 "流程/03 测量/工具/metrics_rollup.py" --freeze-id 2026-08-16 --did-pre 2026-08-20 --did-post 2026-08-28 --require-coverage --case-id 本案 --project-id 本案项目号
```

看 `案件/{case_id}/出数/did.csv`：`DiD = 处理组 need 均值变化 − 对照 need 均值变化`，推断看 **DiD 区间是否含 0**。

---

## 7. 脚本一览

| 脚本 | 作用 |
|---|---|
| `工具/freeze_config.py` | 把活动配置复制到 `案件/{case_id}/冻结/日期/`，写 checksum |
| `工具/make_checklist.py` | 按冻结词表生成完整清单（含 Holdout，避免漏问） |
| `工具/api_sentinel.py` | 官方联网 API，一次一问；读冻结表 |
| `工具/metrics_rollup.py` | 正式行门禁、need 等权、cluster bootstrap、覆盖、DiD |
| `工具/asset_deposit.py` | 脱敏 upsert；空面板记 `needs_only`；泄漏则失败 |
| `工具/test_measure.py` | 门禁、SOV、等权、脱敏的最小测试 |
| `工具/schema.py` | 台账字段、冻结路径、正式行校验（被上面脚本引用） |

采集和出数**只认冻结目录**。改活动表却不重新冻结，前后不可比。

---

## 8. 出数怎么算

1. 先丢掉 `limited=1`、非新对话、文件不齐、问法未激活、五指标未打完的行。  
2. 同一 `query_id` 的多轮先平均，再按 `need_id` 等权。释义多的 need 不会自动占更大权重。  
3. 置信区间是 **need 簇** 的 bootstrap，不是把每条回答当成独立样本。  
4. SOV：自己和合格竞品同时出现时，分子分母各计一次，不再变成 100%。竞品在该切片出现少于 2 次，不进分母。  
5. 稳定性：品牌集合日际 Jaccard、来源同日 Jaccard、来源 +24h Jaccard、14 日滚动 P(提及) 分列。  
6. 七个 App **禁止平均**成一条「国内可见性」。

---

## 9. 两本账

同一次冷问，出两个出口。缺一个，这一单在资产上等于零。

| | 项目账 | 资产账 |
|---|---|---|
| 问题 | 这个客户、这座城，L1 有没有可描述的变化 | 这个品类在这些 App 上怎么被问、谁出场、引哪些域 |
| 文件 | `project.csv` + `出数/` + 客户报告 | [资产库/](资产库/) |
| 能进 | 客户提及、事实对错、干预台账 | 无品牌问法、品类面板、来源域、校准史 |
| 不能进 | 保证报名 | `facts`、截图、电话、点名问法、fingerprint、客户自有域 |

资产只能当下一单脚手架：换 `{city}` 起草词表、用来源域决定先补哪类证据。旧城数字不能写成新客户基线。干预类型要多个可比项目才能谈先验，不能「满 5 单」自动升级成规律。

---

## 10. 商业阶段怎么接

对应仓库根目录的 `GEO项目执行SOP_V1.0.html`：

| SOP | 测量任务 | 交付 |
|---|---|---|
| Step 1–3 诊断 / 产品线 A | `noise` + `baseline` | 定向级一页纸 + Issue，不下干预结论 |
| 执行 + 复测 / 产品线 B | 一轮**一类**证据 + `retest` | 默认受控前后描述；确认性 L1 另有门槛 |
| 下一轮 / 续约 | `weekly` + `calib` | 滚动监测；校准史决定 API 哨兵能不能用 |

SOP 若并行多个 Issue，测量仍只认「一轮一类证据」。干预必须写入 `配置/intervention_ledger.csv`，复测才能对上日期。

---

## 11. 红线

- 网页或 API 数字写成「用户在手机上会看到」。  
- 未冻结、改了问法还和旧基线比。  
- 缺轮次补假数据；未评分当 0。  
- 未授权自动点击消费级 App、抓包、模拟器农场。  
- 电工 / 焊工当叉车证的反事实（已废止）。  
- 两组 CI 重叠规则代替 DiD。  
- `causal_claim` 仍是 `descriptive_until_isolation` 时写「L1 有证据」。  
- 把客户事实推进资产库。

---

## 12. 文献与进阶阅读

- 操作手册：[GEO抽样测量操作手册_V1.md](GEO抽样测量操作手册_V1.md)  
- 入口：[文献.md](文献.md)  
- 第一轮补强：[../../研究/文献精读_测量方案补强_V1.md](../../研究/文献精读_测量方案补强_V1.md)  
- 第二轮补丁：[../../研究/测量文献/对照补丁_V2.md](../../研究/测量文献/对照补丁_V2.md)  
- 全文笔记：[../../研究/测量文献/论文精读_50篇.md](../../研究/测量文献/论文精读_50篇.md)、[../../研究/测量文献/博客精读_30篇.md](../../研究/测量文献/博客精读_30篇.md)  

权威顺序：IAB 2026 ≈ KDD 2024 同行评议 > 预印本全文 > 厂商博客。Schulte 的 7/8 轮是其数据集上的经验数，不是全球功效门槛；本项目的确认性轮次要以噪声周估出的 ICC / MDE 再定。

---

## 13. 下一步（有人才能做完）

1. 把占位客户改成真实 `aliases` / `facts` / 城市。  
2. 两台真机、四个 P0 App、干净号，按 `案件/{case_id}/清单/操作员_2026-08-16_noise.md` 采**至少两天** `noise`。  
3. 评分 → `metrics_rollup.py --require-coverage --case-id 本案 --project-id 本案项目号` → 填报告模板（只勾「描述基线」）。  
4. 用这两天的方差估计 ICC，再决定 baseline 要不要加问法或日期。  
5. 没有第二份无干预日期之前，不要干预，也不要谈 L1。
