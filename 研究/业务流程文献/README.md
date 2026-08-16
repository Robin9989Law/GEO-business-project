# 业务流程文献（八站，不含 03）

03 测量文献仍在 `研究/测量文献/`，本目录不重复计数、不改测量算法。

时间窗：**重点近三年**（2023-08 至 2026-08）。更早文献仅当不可替代经典。

检索分工：

- **OpenAlex**（`OPENALEX_API_KEY`）：论文/报告元数据与 OA 定位。  
- **Crossref**：第二学术索引，只计 2023-08 后期刊论文数；见 `第二库与引文追踪.json`。  
- **Semantic Scholar**：锚点篇的前向被引 / 参考文献计数。  
- **Tavily**（`TAVILY_API_KEY`）：技术博客与官方手册。LinkedIn / Wiki / YouTube / Stack Exchange 不计 20 篇名额。  
- 付费墙不绕过。密钥只放环境变量。

现行登记：`登记schema.md` + 各站 `*.统一.json`。硬门禁资格：`硬门禁资格表.csv`。整改说明：`审计整改_2026-08-16.md`。

论文 PDF、抽取 TXT 和博客原文在各站 `全文/`，只留本机，不进 git。采集脚本会按登记重新落盘。

```bash
export OPENALEX_API_KEY=...
export TAVILY_API_KEY=...
python3 研究/业务流程文献/_tools/collect_openalex.py
python3 研究/业务流程文献/_tools/collect_tavily.py
```
