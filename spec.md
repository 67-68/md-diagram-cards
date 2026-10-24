# Diagram 卡片系统 — Spec

> 状态：草案 v0.14
> v0.14 变更：`@exclude` 现在**列也支持** —— 表头写 `列头@exclude`（或 `列头@[exclude]`），这一列整列不出卡，只当辅助理解；行上的 `@exclude` 照旧（见 §3.5）。
> v0.13 变更：媒体列的 `@[...]` 标注**两个方向都支持** —— 除了 `@[front, back=频段]`（本列值进题面、答案取另一列），还可以写 `@[back, front=频段(y)]`（本列值是答案、题面从别的列拼出来），见 §3.4。
> v0.12 变更：正交表新增**媒体列** —— 表头写 `列头@[front, back=列头]`，本列的值（音频/图片文件名）进题面、答案取同一行另一列；该列**不再**出普通的 `in [...] [...]'s [列头] is?` 卡（见 §3.4）。新增 **`@exclude`** —— 某一行第 1 列写上它，整行只当辅助理解、不出卡（见 §3.5）。
> v0.11 变更：Category 表新增 `ability` / `position` / `name`（v0.8 删掉的 ability 以显式模板回归）；`{key}` / `{value}` 占位符正式化；支持在插件设置页自定义 category（按 key 覆盖内置），模板非法占位符 → 警告。
> v0.10 变更：Information 块新增专属标记 `### [information]`；文档里所有 Information 块会**合并**成一个全局字典；旧的纯 `## Information` 标题仍兼容。
> v0.9 变更：`[d-tree]` 确认为**嵌套**无序列表，产「父问子」卡片。
> v0.8 变更：修正 `[d-state]` 与 `[d-tree]` 的关系（时间线=状态机，树状图是另一类）；表格确认为标准单行 CommonMark（行尾 `|` 必须），删除跨行单元格规则；删除 `ability` category；警告仅提示。

---

## 0. 核心对象

| 术语 | 定义 | 例子 |
| --- | --- | --- |
| **Diagram** | 一个结构容器，由带类型标记的标题声明 | `Before 7 week war` |
| **项 (Item)** | Diagram 内一条被记录的内容 | `Zollverein`、`Biarritz meeting`、`Austria` |
| **key** | 项的全局寻址名 | `Zollverein` |
| **description** | 项的可选正文 | `the economic trade union Prussia lead` |
| **外链 (Link)** | 挂在项上的 `@...` 字段，本身也是可寻址的 key | `@member_amount` |
| **Information** | 全局字典，`项 → {外链 → 值}` 的嵌套 K-V | — |

**项的书写结构：**

```
key : description @link1 @link2
```

- `:` 分隔 key 与 description
- 空格分隔 description 与外链
- **外链之后不能再有散文**（内联 `@cat: value` 的 value 吃到行尾或下一个 `@`）

> **统一记法**：Information 里的赋值统一用 `:`，不用 `=`。
> 单值 `- member_amount: 35` / 多值 `- Nap 3 want:` + 缩进块。

---

## 1. 标题层级与类型标记

| 形态 | 语义 |
| --- | --- |
| `### 普通标题` / `#### 普通标题` | 纯组织用途，**不出卡** |
| `### [d-state] <title>` | 时间线 / 状态机 |
| `### [d-tree] <title>` | 树状图 |
| `### [d-orthogonal] <title>` | 正交表 |
| `#### [key] ...` | 普通卡片。`[key]` 只是恰好出现在问题文本开头的引用，不是语法 |
| `#### [cloze] <title>` | 生成产物，不是输入语法 |

**时间线与状态机是同一个东西**（原文档标题就是 "Timeline & State Log"），共用 `[d-state]`。

树状图 `[d-tree]` 是**另一类**。它与 `[d-state]` 的解析逻辑共用程度待确认。

类型标记写在标题开头，紧跟 `###` / `####`。层级不限定。

`[d]` 存在的意义：和普通 H3 标题、以及普通卡片标题区分开。

---

## 2. Diagram 形态

### 2.1 时间线 / 状态机 — `[d-state]`

时间线与状态机是同一个东西。正文是 bullet 列表，条目可带 `[时间]` 前缀，行间可夹 `=> ... =>` 推论行。

```markdown
### [d-state] Before 7 week war

- [1865 Oct] Biarritz meeting: Bismarck met with Nap III at France @condition: France neutralized
=> 普奥双头垄断，奥地利外部强援被剥离 =>
- [1866 Apr] Italy Prussian Alliance
```

### 2.2 树状图 — `[d-tree]`

正文是**嵌套**的无序列表 —— 一个巨大的树，缩进深度表示层级。

缩进量不敏感，按**相对深度**判定层级（在实际文档里用 Tab 或 2/4 空格均可）。

树状图**没有** `[时间]` 前缀，也**没有** `=> ... =>` 推论行。

```markdown
### [d-tree] root

- A
  - B
  - C
    - D
```

卡片形态是**父问子**：

```markdown
#### root
- A

#### [cloze] A
- B
- C

#### C
- D
```

diagram title 就是根节点。每个节点出一张「我有哪些子节点」的卡，问题就是节点自身。

### 2.3 正交表 — `[d-orthogonal]`

正文是标准单行 CommonMark 表格。表题取标记后面的标题文本。

```markdown
### [d-orthogonal] the situation before 7 week war

| 竞争者 | 战略目标 | 硬实力优势 |
| --- | --- | --- |
| Austria | preserve dominance | |
| Prussia | - settle the fate of duchies<br>- decide who should control Germany | 6times steel production<br>3 times coal production |
```

---

## 3. 表格

### 3.1 行

标准单行 CommonMark 表格。**每行必须以 `|` 开头和结尾。**

```markdown
|       | TEST |     |      |
| ----- | ---- | --- | ---- |
|       |      |     | TEST |
| TESTE |      |     |      |
```

空表格同样合法：

```markdown
|     |     |     |     |
| --- | --- | --- | --- |
|     |     |     |     |
```

### 3.2 单元格内的多值

用 `<br>` 分隔。

1. 按 `<br>` 切分
2. **丢弃空片段** —— 连续的 `<br>` 会产生空片段
3. 剥掉每片前导的 `- ` / `* ` / `+ `

```markdown
TEST<br><br><br>LINE4
```

→ `["TEST", "LINE4"]`

### 3.3 空值

表头为空、或行实体（第 1 列）为空、或单元格内容为空 → **跳过**。

### 3.4 媒体列（表头标注 `@[...]`）

表头单元格可以在列名后面跟一个标注，把这一列标成**媒体列** —— 音频、图片这类「例子」。
标注里写的是「题面（front）和答案（back）分别从哪儿来」，**两个方向都支持**：

```markdown
| 效果 | 频段 | 例子音频@[front, back=频段] |      ← 本列的值进题面，答案取「频段」列
```
```markdown
| 效果 | 频段 | 例子音频@[back, front=频段(y)] |    ← 本列的值当答案，题面由「频段」列拼出来
```

标注里的一侧有三种写法：

| 写法 | 意思 |
| --- | --- |
| `front` / `back` | 用**本列**的单元格 |
| `front=列头` / `back=列头` | 用**同一行、那一列**的单元格（题面里带列名前缀） |
| `front=列头(模板)` | 用那一列的值套模板；`y` 是值占位符（也可以写 `{value}`） |

题面 = front 那一侧的文字 + `'s ` + back 那一侧的**列名** + ` is?`；
答案 = back 那一侧的值。于是：

| 标注 | 题面 | 答案 |
| --- | --- | --- |
| `@[front, back=频段]` | `例子音频muddy-01.mp3's 频段 is?` | 频段列的值 |
| `@[back, front=频段(y)]` | `频段(低频)'s 例子音频 is?` | 本列（音频文件名） |
| `@[front=频段(y), back=效果]` | `频段(低频)'s 效果 is?` | 效果列的值 |

```markdown
| 效果 | 频段 | 例子音频@[back, front=频段(y)] |
| --- | --- | --- |
| 沉闷 | 低频 | muddy-01.mp3 |
```

产出：

```markdown
#### 频段(低频)'s 例子音频 is?
- muddy-01.mp3
```

规则：

- 标注只对**表头**生效，和正文里的 `@cat` 外链是两套语法，互不影响；
- `front` / `back` 两侧都要写，缺任一侧 → **警告 + 该列不出卡**；
- `=` 后面的列名要能对上**同一张表的某个列头**；对不上、或指到第 1 列（行实体）
  → **警告 + 该列不出卡**；
- 媒体列**不再出**普通的 `in [表题] [行实体]'s [列头] is?` 卡 ——
  不会有「效果's 例子音频 is?」这种卡；
- 本列这一格是空的 → 这一行没有例子，**安静跳过**；
- front 引用的列这行为空 / 答案那侧为空（有例子没答案，多半是漏填）
  → **警告 + 跳过**；
- 题面里的值有多个（`<br>`）→ **一个值一张卡**；答案多值 → 按 R1 加 `[cloze]`；
- 模板里如果没有 `y` / `{value}` → **警告**（值不会出现在题面里）；
- `back=` 那侧的模板没有意义（答案必须是原文）→ **警告 + 忽略模板**；
- 标注里不要再写 `|`（会被当成列分隔符）。

> 为什么单独拎出来：音频/图片这类「例子」不是表格的一个维度，
> 它和行实体（`效果`）没有对照关系，只跟某一列的值对得上。
> 而「值在题面还是在答案」取决于你想考什么：看着音频说频段，还是看着频段听音频。

### 3.5 `@exclude`（整列 / 整行不算进卡片）

`@exclude` 的语义只有一句话：**标了它的那一列或那一行不进卡片生成**，只当写给自己看的辅助说明。

#### 3.5.1 列

表头（第 2 列及以后）末尾写 `@exclude`，这一列整列不出卡：

```markdown
| 效果 | 频段 | 备注@exclude | 例子音频@[back, front=频段(y)] |
| --- | --- | --- | --- |
| 沉闷 | 低频 | 自己记的：这块偏闷 | muddy-01.mp3 |
```

- 这一列既不出普通的 `in [...] [...]'s [备注] is?` 卡，也不出媒体卡；
- 等价写法：`备注@[exclude]`（放进方括号里也行）；
- 和第 1 列（行实体）一样，被排除的列**照样可以当 `back=` / `front=` 的值来源** ——
  只是它自己不产卡；
- 写在第 1 列上 → **警告**（行实体本来就不出卡）；
- 和 `@[...]` 媒体列标注同时写 → **警告**：整列都不出卡，`@[...]` 不生效。

#### 3.5.2 行

行实体的末尾写 `@exclude`，这一行就**不算进表格**，**一张卡都不出**（普通列和媒体列都不出）：

```markdown
| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | muddy-01.mp3 |
| 整体印象 @exclude | 记一笔：这张表整体偏闷 | ambient.mp3 |
| 明亮 | 高频 | bright-01.mp3 |
```

- 只认**第 1 列**（行实体）上的 `@exclude`；写在别的列 → **警告**，那格的文字会被当成正文；
- 被排除的行不占行实体，也不参与产卡；
- 出现在列表条目上（`[d-state]` / `[d-tree]`）→ **警告**：`@exclude` 目前只对正交表生效。

#### 3.5.3 报告

- `--report json` 里每个结构带 `excluded`（行数）和 `excluded_columns`（列数）；
- stderr 摘要会写「另跳过 N 行 M 列 @exclude」；
- 一张卡都没产出、但确实标了 `@exclude` 时，提示会点明「这是有意跳过的」，
  免得把「自己标了 @exclude」误判成解析失败。

---

## 4. 卡片生成规则

### R1 — cloze 判定

**答案项数 ≥ 2 → 标题加 `[cloze]`；= 1 → 不加。**

所有答案统一渲染为 bullet list。判定**只看答案项数**，与层级、来源无关。

### R2 — 引用渲染

问题标题里每个被引用的 key 用 `[]` 包裹。

### R3 — 逐字保留

问题模板中的内容**逐字取原文**，不做改写。

### R4 — 日期卡

`[d-state]` 的条目**只要带 `[时间]` 前缀就出日期卡**，与有无 description 无关。
`[d-tree]` 无时间概念，不适用。

### R5 — 表格

第 1 列 = 实体轴，**不出卡**。
表头带 `@[...]` 标注的列是**媒体列**，也不出普通的表格卡，改按 §3.4 产卡。
表头标了 `@exclude` 的列整列不出卡；整行标了 `@exclude` 则该行一张卡都不出（§3.5）。

### R6 — 未解析外链

外链在 Information 区（`### [information]`）里查不到 → **警告，仅提示**（不阻断同步、不写回源文件）。

### R7 — 推论行边界

推论行前项或后项为空 → **警告 + 不处理该行**。

---

## 5. 问题模板总表

| 来源 | 模板 | 例子 |
| --- | --- | --- |
| 分组 / 根节点 | `[cloze] {diagram title}` | `[cloze] Before 7 week war` |
| 列表条目日期 | `{条目名} at` | `Biarritz meeting at` |
| 条目 description | `{条目名} means` | `Biarritz meeting means` |
| 表格单元格 | `in [{表题}] [{行实体}]'s [{列头}] is?` | `in [...] [Austria]'s [战略目标] is?` |
| 表格媒体列 | `{front 侧文字}'s {back 侧列名} is?` | `例子音频muddy-01.mp3's 频段 is?` / `频段(低频)'s 例子音频 is?` |
| 树条目 description | `[{条目}] in [{根节点名}] means` | `[Zollverein] in [...] means` |
| `@cat` / `@cat: value` | Category 表（预定义 K-V） | `Member count of [Zollverein]` |
| `@custom(KEY)` | `[cloze] [{KEY}] for [{父项}]` | `[cloze] [Nap 3 want] for [Biarritz meeting]` |
| 推论行 `=> X =>` | `{前项} 的什么推论导致了 {后项}？` | 见 §7 |

---

## 6. 指针系统

**合法语法只有以下三种。**

| 语法 | 值来源 | 说明 |
| --- | --- | --- |
| `@cat` | Information 区里 `项.cat` | 查不到 → 警告 |
| `@cat: value` | 内联，与写在 Information 等价 | value 吃到行尾或下一个 `@` |
| `@custom(KEY)` | Information 区里 `KEY` | `custom` 是关键字；`@foo(bar)` 不触发 |

> `@[KEY]` 与 `@time: [KEY]` **不是合法语法**，不实现。

### Category 表（预定义 K-V）

模板里 `{key}` 替换成**项名**，`{value}` 替换成**外链的值**。
未收录的 `@cat` 一律警告。

| category | 问题模板 |
| --- | --- |
| `condition` | `{key}'s condition is?` |
| `member_amount` | `Member count of [{key}]` |
| `place` | `[{key}]的地点是 {value}` |
| `effect` | `{key}'s effect is?` |
| `ability` | `{key}'s ability is?` |
| `position` | `{key}'s position is?` |
| `name` | `{key}'s name is?` |

### 6.1 自定义 category

Category 表可在**插件设置页**里自定义：按 key **覆盖**内置项，或新增自己的。
自定义表每次转换通过 `--categories-json` 传给 Python，Python 按
`{**内置, **自定义}` 合并（后者覆盖前者）。

- 模板里只认 `{key}` / `{value}` 两个占位符；写了别的（如 `{foo}`）→ **警告 + 跳过该卡**
- 命令行同理：`python -m md_diagram_cards notes.md --categories-json '{"effect":"{key} 的影响是？"}'`
- 插件可用 `--list-categories` 拉取内置表（设置页只读展示用，事实源始终在 Python）

---

## 7. 推论行

```markdown
- A
=> B effect =>
- C
```

产出：

```markdown
#### A 的什么推论导致了 C？
- B effect
```

前项 / 后项取**紧邻的上一条 / 下一条 bullet**。任一侧为空 → 警告 + 跳过该行。

---

## 8. Information 区块

Information 块用**专属标记** `[information]` 声明（层级不限，建议 `###`）：

```markdown
### [information]

- Zollverein
	- member_amount: 35

- Biarritz meeting
	- Nap 3 want:
		- neutral and mediating
		- wants Rhineland
```

- `- 项` 是父节点（深度 0）
- `- 外链: 值` 是单值
- `- 外链:` + 缩进列表 是列表值（值在更深一层）
- 空 bullet（如行尾多敲的 `- `）直接忽略

### 8.1 多个 Information 块会合并

一份文档里可以有**任意多个** `[information]` 块，解析时按出现顺序合并成
**同一个**全局字典 `项 → {外链 → 值}`：

- 同一个项分散在多个块里 → 不同外链取并集
- 同一个项的同一个外链重复出现 → **后出现的块覆盖先出现的**

```markdown
### [information]
- King of Prus
	- ability: declare war and make peace

### [information]
- King of Prus
	- position: president of the confederation
```

合并结果：

```text
{ "King of Prus": { "ability": "...", "position": "..." } }
```

> **兼容**：旧的纯 `## Information` 标题（不带 `[information]` 标记）仍然会被识别并合并，
> 但推荐一律写成 `### [information]`，避免和普通组织标题混淆。
