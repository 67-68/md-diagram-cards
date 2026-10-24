# md-diagram-cards

把 Markdown 里的 diagram 结构转成 Anki 卡片，输出格式直接供
[Anki Heading Sync](https://github.com/panAtGitHub) 消费。

- 语法规格：[`spec.md`](spec.md)
- 架构与分层：[`architecture.md`](architecture.md)
- 回归基线：[`fixtures/`](fixtures/)（20 组）

## 语法速览

三种 diagram 标记：

```markdown
### [d-state] Before 7 week war      # 时间线 / 状态机
### [d-tree] Prussian dominance      # 树状图（嵌套列表）
### [d-orthogonal] situation 1865    # 正交表
```

产出：

```markdown
#### [cloze] Before 7 week war
- [1865 Oct] Biarritz meeting
- [1866 Apr] Italy Prussian Alliance
```

答案项数 ≥ 2 自动加 `[cloze]`。

### 正交表的媒体列

表头可以在列名后面跟一个 `@[front..., back...]` 标注，把这一列标成**媒体列**
（音频、图片这类「例子」）。标注说的是「题面和答案各自从哪来」，**两个方向都支持**：

```markdown
| 效果 | 频段 | 例子音频@[front, back=频段] |      # 本列的值进题面，答案取「频段」列
| 效果 | 频段 | 例子音频@[back, front=频段(y)] |    # 本列的值当答案，题面由「频段」列拼出来
```

一侧的三种写法：

| 写法 | 意思 |
| --- | --- |
| `front` / `back` | 用**本列**的单元格 |
| `front=列头` / `back=列头` | 用同一行、**那一列**的单元格 |
| `front=列头(模板)` | 用那一列的值套模板，`y` 是值占位符（也可以写 `{value}`） |

题面 = front 侧文字 + `'s ` + back 侧列名 + ` is?`；答案 = back 侧的值。所以：

```markdown
| 效果 | 频段 | 例子音频@[front, back=频段] |      → #### 例子音频muddy-01.mp3's 频段 is? / - 低频
| 效果 | 频段 | 例子音频@[back, front=频段(y)] |    → #### 频段(低频)'s 例子音频 is?   / - muddy-01.mp3
```

- 媒体列**不出**普通的 `in [表题] [行实体]'s [列头] is?` 卡 ——
  不会有「效果's 例子音频 is?」这种卡
- 一个单元格多个值（`<br>`）→ 一个值一张卡
- 标注写坏（缺 front / 缺 back / 列名对不上 / 模板里没有 `y`）→ 警告 + 该列不出卡

### 表格的辅助行（`@exclude`）

某一行只是写给自己看的备注、不想出卡？在第 1 列（行实体）末尾写 `@exclude`：

```markdown
| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | muddy-01.mp3 |
| 整体印象 @exclude | 记一笔：整体偏闷 | ambient.mp3 |
```

- 这一行**一张卡都不出**（普通卡和媒体卡都不出），只当辅助理解
- 只认第 1 列；写在别的列、或写在 `[d-state]` / `[d-tree]` 的条目上 → 警告（不生效）
- 报告里带 `excluded` 计数，一行都没出卡时会给出专门提示

没有 `[d-*]` 标记的标题只作组织用，**不出卡** —— 这是「提示成功但没有卡片」最常见的原因。
插件设置页顶部有一份同样的速查。

### Information 区（外链取值）

外链（`@...`）的值从 `[information]` 块里查。建议用专属标记 `### [information]`，
一份文档可以写**多个** `[information]` 块，解析时会自动合并成一个全局字典
（同名项的不同外链取并集，同名外链后者覆盖前者）：

```markdown
### [information]

- Zollverein
    - member_amount: 35

- Biarritz meeting
    - Nap 3 want:
        - neutral and mediating
        - wants Rhineland
```

- `- 项` 是父节点；`- 外链: 值` 是单值；`- 外链:` + 缩进列表是多值
- 引用只有三种合法写法：
  - `@cat` —— 用内置 category（`condition` / `member_amount` / `place` / `effect` / `ability` / `position` / `name`）
  - `@cat: value` —— 内联值
  - `@custom(KEY)` —— 引用 Information 里的任意外链，例如 `@custom(Nap 3 want)`

> 旧的纯 `## Information` 标题（不带 `[information]` 标记）仍会被识别，方便旧笔记平滑迁移。

### Category 问题模板（可自定义）

每个 category 对应一条问题模板，模板里 `{key}` = 项名、`{value}` = 外链值：

| category | 问题模板 |
| --- | --- |
| `condition` | `{key}'s condition is?` |
| `member_amount` | `Member count of [{key}]` |
| `place` | `[{key}]的地点是 {value}` |
| `effect` | `{key}'s effect is?` |
| `ability` | `{key}'s ability is?` |
| `position` | `{key}'s position is?` |
| `name` | `{key}'s name is?` |

插件设置页里可以**按 key 覆盖**内置模板、或新增自定义 category；改动存在 Obsidian 的
`data.json`，每次转换时作为 `--categories-json` 传给 Python（Python 无状态，不存在"存回 Python"）。
命令行同理：

```bash
python -m md_diagram_cards notes.md --categories-json '{"effect":"{key} 的影响是？"}'
python -m md_diagram_cards --list-categories    # 打印内置 category 表（JSON）
```

## Python 脚本

```bash
python -m md_diagram_cards notes.md                    # 打印卡片
python -m md_diagram_cards notes.md --mode newfile     # 生成 notes闪卡.md
python -m md_diagram_cards notes.md --mode inplace     # 就地插入（幂等）
python -m md_diagram_cards notes.md --mode inplace --dry-run
python -m md_diagram_cards notes.md --mode inplace --report json
```

`inplace` 模式把卡片包在 `<!-- BEGIN GENERATED -->` / `<!-- END GENERATED -->`
之间，插在各自 diagram 之后。重复执行结果一致。

更新时是按 diagram 做增量替换：没变的卡片块完全不动，已有
`<!--ID: noteId-->` / `<!-- AHS:...-->` marker 会保留，AHS 下一次 sync
可以按同一个 noteId 更新 Anki 内容，而不是重新建卡。

marker 只在确认“是同一张卡”时才迁移：题面相同（答案改了也算），或
答案不变、题面只是改名（表头改名）。判不准的一律当新卡，**新卡不会
继承任何旧 marker**——宁可让旧 note 变 orphan，也不能让新卡顶着别人的
noteId 去覆盖别人的卡。

诊断信息走 stderr（几个结构、几张卡片、警告、提示）：

```
md-diagram-cards: 0 个结构 → 0 张卡片（只预览，未写入）
提示: 没有找到任何 [d-state] / [d-tree] / [d-orthogonal] 结构。标记要写在标题开头…
```

`--report json` 额外往 stdout 吐一行 JSON 报告（插件靠它判断到底出了几张卡片）。

开发时用 `PYTHONPATH=src`，或 `pip install -e .`。

## Obsidian 插件（薄壳）

`obsidian-plugin/` 是对着 Anki Heading Sync 的工程模式写的薄插件：
扫描范围内文件 → 调用 Python 脚本 → 结果由脚本自己写盘。

### 一键安装

```bash
./install.sh                          # 自动探测 vault
./install.sh "/path/to/vault"         # 指定 vault
MDC_PYTHON=python3.11 ./install.sh    # 指定解释器
./install.sh --skip-build             # 跳过插件构建
```

脚本会做四件事：检查 Python 3.9+ → 构建插件（`main.js` 缺失时才构建）→
复制 `main.js` + `manifest.json` + `styles.css` → 首次写入 `data.json`（已存在则不动）。

装完在 Obsidian 里启用插件即可，命令面板会出现两条命令。

> **macOS 提示**：如果 `mkdir` 报 `Operation not permitted`，是系统在保护 iCloud 目录。
> 给终端开「完全磁盘访问权限」后重开终端，或者用 Finder 手动拷那三个文件
> （`main.js` / `manifest.json` / `styles.css`）。

### 手动安装

```bash
cd obsidian-plugin
npm install && npm run build
# 把 main.js + manifest.json + styles.css 拷进 <vault>/.obsidian/plugins/md-diagram-cards/
```

设置项：

| 项 | 说明 |
| --- | --- |
| 范围模式 | 全部 / 只含指定文件夹 / 排除指定文件夹 |
| 包含、排除的文件夹 | 搜索框里打字即从下拉列表筛选 vault 现有文件夹；选中后变成可删除的标签。留空 = 不限制 |
| 输出模式 | 就地插入 / 生成 `xxx闪卡.md` |
| Category 问题模板 | 只读展示 Python 内置 category；可增删改自定义 category（按 key 覆盖内置），改动自动保存 |
| 解释器路径 | 默认 `python3` |
| 脚本路径 | 本仓库的 `src` 目录（留空则依赖已安装的包） |

命令：`转换当前文件为卡片` / `转换整个库为卡片` / `查看转换日志`。

| 项 | 说明 |
| --- | --- |
| 转换日志 | 每次转换往 `<插件目录>/convert.log` 追加一行 JSON（结构数、卡片数、警告、提示）。点「查看最近日志」直接看 |

「提示成功但没产出卡片」先看这个日志：通常是文件里根本没有 `[d-*]` 标记，或者表格缺表头 / 第 1 列为空。

## 回归测试

```bash
python3 tools/check_fixtures.py      # 卡片产出是否与 expected 一致
python3 tools/check_idempotent.py    # inplace 模式是否幂等
python3 tools/check_report.py        # 报告里的卡片数是否和 expected 对得上
python3 tools/check_surgical.py      # 改表头/增删内容时 marker 是否按卡保留（新卡不继承）
python3 tools/check_table.py         # 正交表媒体列 + @exclude 辅助行：取对列、不出普通卡、写坏要警告
```

```bash
cd obsidian-plugin && npm test       # 运行范围 / 报告解析 / 插件↔Python 契约
```

`npm test` 里的契约用例会真跑一次 Python CLI，需要能执行 `python3`。
