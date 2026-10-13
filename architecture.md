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
├─ parse_diagrams(blocks)
│   └─ 对每个 [d-*] 标题，按标记分派:
│       │
│       ├─ [d-orthogonal] → parse_table(block, ctx)
│       │   ├─ ctx["表头"] = block.title          ← 往 context 加一行
│       │   └─ 对每个数据行:
│       │       ├─ ctx["行实体"] = cells[0]
│       │       └─ 对每个单元格:
│       │           ├─ ctx["列头"] = headers[i]
│       │           └─ parse_item(cell, ctx)      ← 复用
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
    └─ 对每个 (行实体, 列头, 单元格):
        make_card("in [{表题}] [{行实体}]'s [{列头}] is?", 单元格的值列表)
```

`format_list` 同时产「整张图的卡」和「每条项的卡」—— 这就是
「Timeline 这一整个文本的解析也可以算一张卡，然后它自己调用 formatting 函数之后
把具体的每个项交给更细的函数」。

`format_tree` 同理：每个节点自己产「父问子」卡，再递归下行。

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

**幂等的实现**：每次生成前先 `strip_generated` 剥掉所有受管理区块
**以及它前后由我们引入的空行**，然后重新插入。

清掉前后空行是关键 —— 只删标记本身的话，每跑一次空行就累积一层。

插入点上方的空行也要先规范化，否则文档末尾的空元素会让首尾两次结果不同。

```
render_inplace(text):
    stripped = strip_generated(text)          # 剥掉旧区块 + 周围空行
    ctx = parse_document(stripped)
    for diagram in ctx["diagrams"]:           # 从后往前插，避免行号偏移
        index = diagram.end_line
        while index > 0 and not lines[index-1].strip():   # 规范化上方空行
            del lines[index-1]; index -= 1
        lines[index:index] = ["", BEGIN, *cards, END, ""]
```

## 输出模式

| 模式 | 行为 |
| --- | --- |
| `stdout` | 打印卡片（默认） |
| `newfile` | 生成 `原文件名闪卡.md` |
| `inplace` | 就地插入，幂等 |

## 待定

1. **Obsidian 薄插件**：扫描文件夹（递归）驱动 Python 脚本。
   参考 Anki Heading Sync 的设置模式（`all` / `include` / `exclude`）。
