# 统一登记 schema

八站论文 / 博客 / 标准共用同一套字段。旧文件保留；现行以各站 `论文登记.json` `博客登记.json` `标准登记.json` 为准。

## 必填

| 字段 | 含义 |
|---|---|
| `id` | 站码-类型序号，如 `01-P03` `05-B09` `07-S02` |
| `title` | 题名 |
| `authors` | 作者或机构列表 |
| `year` | 四位年份，未知为空 |
| `url` | 规范化 URL |
| `doi` | DOI，无则空 |
| `kind` | `paper` / `blog` / `standard` |
| `stage` | 八站之一 |
| `fulltext_status` | `local_pdf_and_txt` / `local_txt` / `excluded` |
| `peer_reviewed` | 论文：是/否；博客与标准：否 |
| `quality` | `high` / `medium` / `low` |
| `directness` | `直接` / `同构迁移` / `规范性` / `商业经验` |
| `design` | 如 SLR / 实验 / 案例 / 标准条文 / 实践手册 |
| `blog_grade` | 仅博客：`official` / `researcher` / `professional` / `vendor` |
| `adoptable` | 可采用条款 |
| `do_not_copy` | 不可照搬 |
| `checksum_sha256` | 全文文件哈希；无全文则空 |
| `review_status` | `close_read` / `background` / `excluded` / `anchor_reread` |
| `counts_toward_quota` | 是否计入 30/20 名额 |

## 博客不得计入 20 的来源

LinkedIn 个人帖、Wikipedia、YouTube、Stack Exchange / Stack Overflow，以及与本站标准登记同一 URL 的页面。

## 质量尺

- `high`：同行评议或正式标准，方法可复核。  
- `medium`：预印本全文、官方机构手册、有交叉核对的专业博客。  
- `low`：可疑期刊、厂商营销、无方法的短文；只作背景，不单独支撑硬门禁。
