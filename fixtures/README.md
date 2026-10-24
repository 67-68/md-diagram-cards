# Fixtures

每组的形态是 `input.md`（源文件）+ `expected.md`（期望产出的卡片）。

`expected.md` 只是给人看的清单，不是最终输出格式 —— 真正的输出形态（写进 md 还是直接推 Anki）还没定。

## 清单

| # | 目录 | 测什么 |
| --- | --- | --- |
| 01 | `01-timeline-minimal` | 最小 `[d-state]`：只有 key + 日期。1 项 → 分组卡不加 cloze |
| 02 | `02-timeline-with-description` | key + description，出 `means` 卡 |
| 03 | `03-timeline-with-links` | 内联 `@condition:` + `@custom(KEY)`，含 Information 多值 |
| 04 | `04-timeline-group` | 2 项 → 分组卡加 cloze；日期卡逐条出 |
| 05 | `05-timeline-inference` | 推论行 `=> X =>` 出卡 |
| 06 | `06-table-basic` | 正交表：单值 / 多值 / 空单元格 / 第 1 列不出卡 |
| 07 | `07-tree-basic` | `[d-tree]` 标记 + 裸引用 `@member_amount` + 内联 `@effect:` |
| 08 | `08-unresolved-link` | 外链在 Information 里查不到 → 警告 |
| 09 | `09-heading-levels` | 普通标题不出卡；`#### [d-state]` 也能声明 |
| 10 | `10-link-from-information` | 裸引用取值；多值 → cloze |
| 11 | `11-inference-at-start` | 推论行前项为空 → 警告 + 跳过 |
| 12 | `12-real-situation-1865` | 5 列正交表的真实形态 |
| 13 | `13-real-before-7-week-war` | 5 列正交表 + 较长单元格内容 |
| 14 | `14-cell-linebreak` | 连续 `<br>` 丢弃空片段；全空行跳过 |
| 15 | `15-tree-nested` | `[d-tree]` 嵌套缩进 → 父问子卡片 + `means` 卡 |
| 16 | `16-multi-information` | `### [information]` 标记；多个 Information 块合并（含旧 `## Information` 兼容） |
| 17 | `17-builtin-extra-categories` | 内置 `ability` / `position` / `name` category 出卡 |
| 18 | `18-table-media-column` | 表头 `@[front, back=列头]` 媒体列：值进题面、答案取另一列、不出普通表格卡 |

## 已澄清（无待定项）

- **三种标记**：`[d-state]` / `[d-tree]` / `[d-orthogonal]`
  - `[d-state]` = 时间线 / 状态机 —— **两者是同一个东西**
  - `[d-tree]` = **嵌套**无序列表，产「父问子」卡片；无 `[时间]`、无 `=>` 推论行
  - 三者共用同一个 `parse_item` 解析每个条目
- **`#### [key] ...` 是普通卡片**，`[key]` 只是恰好出现在问题开头的引用，不是独立语法
- **合法指针只有三种**：`@cat` / `@cat: value` / `@custom(KEY)`
  - `@[KEY]` 与 `@time: [KEY]` 非法
  - `cat` 必须是内置或用户自定义的 category，否则 → 警告
- **内置 category**：`condition` / `member_amount` / `place` / `effect` / `ability` / `position` / `name`
  - 模板里 `{key}` = 项名、`{value}` = 外链值；非法占位符（如 `{foo}`）→ 警告 + 跳过该卡
  - 可在插件设置页或 `--categories-json` 里**按 key 覆盖**内置、或新增自定义
- **Information 块**：推荐 `### [information]` 专属标记；一份文档可写多个，解析时**合并成一个全局字典**
  - 同名项的不同外链取并集，同名外链后者覆盖前者
  - 旧的纯 `## Information` 标题仍兼容
- **表格是标准单行 CommonMark**：每行以 `|` 开头和结尾；单元格内换行用 `<br>`
- **媒体列**：表头 `列头@[front, back=列头]` —— 本列的值进题面、答案取同一行另一列，
  该列不出普通表格卡（`@[...]` 只对表头生效，与正文里的 `@cat` 外链无关）
- **警告仅提示**：不阻断同步，不写回源文件
- **推论行任一侧为空 → 警告 + 跳过**
- **空值一律跳过**：表头空 / 行实体空 / 单元格空

## 说明

`12` / `13` 源自作者的真实文档。原文中的 `@time: [KEY]` / `@[KEY]` 已确认为非法语法，
故这两组已清理为合法内容，保留其**表格形态**（5 列 + `<br>` 分隔）作为参考。
