# 架构

**语言：Python**（通用，便于在 Obsidian 之外处理 md 文本）

目标：把 md 文本 parse 成一张张卡片，输出供 **Anki Heading Sync** 消费。

分两个阶段：**解析**（自上而下，累加 context）→ **格式化**（递归，任意层级可产卡）。

---

## 阶段一：解析 —— 自上而下，context 累加

不追求严格的层级 parser，按需拆分。每层函数把已知信息写进 **context dict**，
下层函数直接读，不需要通过参数层层传递。

```
parse_document(text) -> Context
├─ parse_information(blocks)          → ctx["information"] = {项: {外链: 值}}
│   └─ 收集「所有」### [information] 块，按顺序合并成同一个全局字典
├─ parse_diagrams(blocks)
│   └─ 对每个 [d-*] 标题，按标记分派:
│       │
│       ├─ [d-orthogonal] → parse_table(block, title, ctx)
│       │   ├─ 表头每个单元格 → parse_column(cell, ctx)
│       │   │   └─ `列头@[front, back=列头]` → Column(header, front, back)
│       │   │       └─ 只是表头标注，和正文的 @cat 外链两套语法
│       │   └─ 对每个数据行:
│       │       ├─ ctx["行实体"] = cells[0]
│       │       └─ 其余单元格 → split_cell_values: `<br>` 切多值
│       │
│       ├─ [d-state] → parse_list(block, ctx)     ← 扁平列表
│       │   └─ 对每个 bullet:
│       │       └─ parse_item(text, ctx)          ← 同一个 parse_item
│       │
│       └─ [d-tree] → parse_tree(block, ctx)      ← 嵌套列表
│           ├─ 先按行读 bullet，求缩进深度
│           ├─ 用栈按相对深度建树
│           └─ 每个节点:
│               └─ parse_item(text, ctx)          ← 同一个 parse_item
│
└─ parse_item(text, ctx) -> Item                 ← 最小单元的通用解析
    ├─ key      = 冒号前
    ├─ desc     = 冒号后、第一个 @ 前的部分
    └─ links    = 依次解析 @cat / @cat: value / @custom(KEY)
        └─ @cat 查 ctx["information"]，查不到 → 警告
```

**关键点**：`parse_item` 是唯一的「最小单元解析函数」。表格单元格、扁平 bullet、
嵌套树的节点，全都走它。上层函数不重复实现 KV 解析，只负责把 context 摆好。

---

## 阶段二：格式化 —— 递归，任意层级可产卡

**formatting 函数由上级调用，不对应最小单元。**任何层级都可以自己产一张卡，
然后把细节交给更下级。

```
format(ctx) -> Card[]
│
├─ [d-state] → format_list(d, ctx)
│   ├─ ① 整张 diagram 自己产一张卡
│   │      make_card("[cloze] {d.title}", [每个条目的 key])
│   ├─ ② 再逐条交给下级
│   │      对每个 item: format_item(item, ctx)
│   │          ├─ 有 [时间] → make_card("{名} at", [时间])
│   │          ├─ 有 desc   → make_card("{名} means", [desc])
│   │          └─ 每个 link → format_link(link, item, ctx)
│   └─ ③ 推论行: format_inference(prev, cur, next, ctx)
│
├─ [d-tree] → format_tree(d, ctx)
│   └─ 对每个节点: format_node(node, ctx)
│       ├─ ① 父问子: make_card(node.name, [每个直接子节点的 name])
│       │      ← 子节点 ≥2 时自动变 [cloze]
│       ├─ ② 有 desc → make_card("[{node}] in [{父节点}] means", [desc])
│       ├─ ③ 每个 link → format_link(link, node, ctx)
│       └─ ④ 递归处理每个子节点
│
└─ [d-orthogonal] → format_table(d, ctx)
    └─ 对每个 (行实体, 列, 单元格):
        ├─ 普通列: make_card("in [{表题}] [{行实体}]'s [{列头}] is?", 单元格的值列表)
        └─ 媒体列 (Column.is_media): format_media_column(row, column, ...)
            └─ make_card("{列头}{本列的值}'s {back 列头} is?", back 列同一行的值列表)
                ← 不出普通卡；一行多个媒体 → 一个媒体一张卡
```

`format_list` 同时产「整张图的卡」和「每条项的卡」—— 这就是
「Timeline 这一整个文本的解析也可以算一张卡，然后它自己调用 formatting 函数之后
把具体的每个项交给更细的函数」。

`format_tree` 同理：每个节点自己产「父问子」卡，再递归下行。

`format_table` 是「一列一种产卡方式」：普通列问「这一行的这列是什么」，
媒体列（表头标了 `@[front, back=列头]`）问「这个例子音频属于哪一档」——
音频不是表格的一个维度，不跟行实体组成卡片。

---

## 唯一出口：make_card

所有卡片都从这一个函数出去，保证规则只写一遍。

```python
def make_card(question, answers):
    if len(answers) >= 2:
        question = "[cloze] " + question        # R1
    return Card(question, answers)
```

---

## 分层是否合理

- 解析层没有「严格层级」——`parse_item` 被三个上层复用
- 警告形状只定义一份（`diagnostics.warn`）：解析层（表头标注写坏）和格式化层
  （外链查不到、模板占位符非法）都往里写同一种 `{message, line}`
- 格式化层刻意做成递归——层级高的函数可以超额产卡（整体卡、父问子卡）
- context 是普通 dict，任何层都能读写，不做类型约束

---

## 阶段三：输出 —— 幂等的就地插入

卡片紧跟在**它自己的 diagram 之后**，用一对 HTML 注释包裹：

```markdown
### [d-state] Before 7 week war
- [1865 Oct] Biarritz meeting

<!-- BEGIN GENERATED -->
#### [cloze] Before 7 week war
- [1865 Oct] Biarritz meeting
<!-- END GENERATED -->
```

**外科手术式更新**：每次生成前先扫描旧区块，再按 diagram 逐个比较。
没变化的 diagram 整块保留；变化的 diagram 只替换发生变化的卡片块。
卡片末尾已有的 `<!--ID: noteId-->`（以及旧版 AHS marker）会跟着卡片保留，
因此 Anki Heading Sync 下一次 sync 能按 noteId 增量更新，而不是新建重复卡。

旧的 `strip_generated` 仍然保留为扫描入口，但 `render_inplace` 不再“先全删再全插”：

```
render_inplace(text):
    stripped, blocks = scan_generated(text)   # 记录旧区块，同时剥掉它们
    ctx = parse_document(stripped)
    for diagram, cards in generated:
        if 旧区块没有变化:
            leave block untouched            # marker/空行都不动
        else:
            merge_card_chunks(旧区块, cards)   # 未变卡片连 marker 保留
    insert missing blocks bottom-up
```

合并规则（**只有能确认“是同一张卡”时才迁移 marker**）：

1. 正文完全相同 → 同一张卡，marker 原样保留；
2. 题面相同（忽略 `[cloze] ` 前缀）→ 同一张卡，只是答案被增删/改写，
   保留 marker（AHS 走 `toUpdate`）；
3. 答案完全相同、题面只是改名（例如表头改名）→ 保留 marker，但要求
   一对一、且题面相似度够高，避免把 marker 串给别的卡；
4. 其余一律算新卡：**新卡不继承任何 marker**。删掉的卡片才丢弃 marker，
   让 AHS 按 orphan 逻辑处理；
5. AHS 写在 `<!-- END GENERATED -->` 后面的最后一张卡 marker，也会被识别并归到最后一张旧卡上。块需要重建时，这个 marker 会被移回 END 之前，避免以后卡序变化时串号；
6. 同一个 noteId 只允许出现在一张卡上：旧块里万一有重复 marker，只留第一份。

> 为什么第 4 条要这么保守：新卡若顶了别人的 noteId，AHS 下次 sync 会
> `updateNoteFields` 把**别人那张卡**的内容覆盖掉，而真正被顶掉的那张卡
> 反而丢了身份、被重新 create 成重复卡。宁可让旧 note 变 orphan
> （丢一次复习记录），也绝不能串号。

## 与 Anki Heading Sync 的增量契约

Anki Heading Sync 当前主链使用 `<!--ID: noteId-->` 作为 durable identity：

1. 扫描标题卡片时，先找标题块尾部的合法 ID marker；
2. 找到就复用 marker 里的 noteId；找不到才按“同文件 + 同 rawBlockHash”
   从插件 state 里恢复；再找不到才当新卡；
3. 内容变化表现为 rawBlockHash 变化，但 noteId 不变，所以 planner 走
   `toUpdate`，执行 AnkiConnect `updateNoteFields` 覆盖同一个 note；
4. 如果 marker 丢了且内容也变了，state recovery 会失败，于是走
   `toCreate` 新建 note，旧 note 变成 orphan —— 这就是重复卡来源。

因此 `md-diagram-cards` 的职责不是自己覆盖 Anki，而是：

- 把 `<!--ID: ...-->` 当受保护内容，卡片没删就不丢；
- 只改正文发生变化的卡片，其他卡片和 marker 原样保留；
- 只有能确认是同一张卡时才迁移 marker：题面相同、或答案相同且题面只是
  改名。判不准的一律当新卡，**绝不让新卡继承别人的 noteId**；
- 表头/行列增删后，把 marker 跟到正确的卡片槽位，让 AHS 自己决定
  update、create 还是 orphan。

另外：AHS 的最后一张卡会把 `<!-- END GENERATED -->` 当成正文的一部分，
因此它的 `<!--ID: ...-->` 经常写在 END 后面。扫描器需要把 END 后的
marker 也归到最后一张卡，并在块重建时移回卡片正文末尾，避免串号。

## 输出模式

| 模式 | 行为 |
| --- | --- |
| `stdout` | 打印卡片（默认） |
| `newfile` | 生成 `原文件名闪卡.md` |
| `inplace` | 就地插入，幂等 |

## 待定

1. **Obsidian 薄插件**：扫描文件夹（递归）驱动 Python 脚本。
   参考 Anki Heading Sync 的设置模式（`all` / `include` / `exclude`）。
