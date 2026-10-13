#!/usr/bin/env bash
# 把 md-diagram-cards 装进一个 Obsidian vault。
#
# 本仓库分两半：
#   1) Python 脚本（src/md_diagram_cards）—— 真正的解析与出卡逻辑，零第三方依赖
#   2) Obsidian 插件（obsidian-plugin）—— 薄壳，负责扫描文件夹并调用上面的脚本
#
# 部署内容：
#   1) 检查 Python 3.9+
#   2) 构建插件（obsidian-plugin/main.js 不存在时才构建）
#   3) main.js + manifest.json + styles.css -> <vault>/.obsidian/plugins/md-diagram-cards/
#   4) data.json -> 仅在该插件还没有设置文件时写入，指向本仓库的 src
#
# 用法：
#   ./install.sh                          # 自动探测 vault
#   ./install.sh "/path/to/vault"         # 指定 vault
#   MDC_VAULT=/path ./install.sh          # 用环境变量指定 vault
#   MDC_PYTHON=python3.11 ./install.sh    # 指定 Python 解释器
#   ./install.sh --skip-build             # 跳过插件构建
#   ./install.sh --help
#
# 说明：
#   部署目标是运行时副本，不要直接改副本；改动在本仓库内做，再跑本脚本同步。
#   已存在的 data.json 不会覆盖 —— 那是 Obsidian 存插件设置的地方。
#   如果 mkdir 报 "Operation not permitted"，是 macOS 在保护 iCloud 目录，
#   给终端开「完全磁盘访问权限」，或者用 Finder 手动拷贝。

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$HERE/obsidian-plugin"
PLUGIN_ID="md-diagram-cards"

MDC_VAULT="${MDC_VAULT:-}"
MDC_PYTHON="${MDC_PYTHON:-python3}"
SKIP_BUILD=0

usage() {
  sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --skip-build) SKIP_BUILD=1 ;;
    -*) echo "未知参数：$1（用 --help 查看用法）" >&2; exit 2 ;;
    *) MDC_VAULT="$1" ;;
  esac
  shift
done

# --- 探测 vault --------------------------------------------------------------
# vault 探测。这里刻意不用 find / glob —— macOS 的 TCC 拒绝遍历 iCloud 目录
# （报 "Operation not permitted"），但读已知路径是允许的。
# 所以优先读 Obsidian 自己的 obsidian.json，那里面有完整的 vault 列表。
detect_vault() {
  local cfg="$HOME/Library/Application Support/obsidian/obsidian.json"

  if [ -f "$cfg" ]; then
    "$MDC_PYTHON" - "$cfg" <<'PYEOF'
import json, pathlib, sys

try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text())
except Exception:
    raise SystemExit(1)

vaults = [v for v in (data.get("vaults") or {}).values() if isinstance(v, dict) and v.get("path")]
vaults.sort(key=lambda v: v.get("ts", 0), reverse=True)

for vault in vaults:
    path = pathlib.Path(vault["path"])
    if (path / ".obsidian").is_dir():
        print(path)
        raise SystemExit(0)

raise SystemExit(1)
PYEOF
    if [ "$?" -eq 0 ]; then
      return 0
    fi
  fi

  local candidate
  for candidate in \
    "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian" \
    "$HOME/Documents/obsidian" \
    "$HOME/Documents/Obsidian" \
    "$HOME/Obsidian"; do
    if [ -d "$candidate/.obsidian" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if [ -z "$MDC_VAULT" ]; then
  MDC_VAULT="$(detect_vault || true)"
fi

if [ -z "$MDC_VAULT" ]; then
  echo "没能自动找到 vault。请显式指定：" >&2
  echo "  ./install.sh \"/path/to/vault\"" >&2
  exit 1
fi

if [ ! -d "$MDC_VAULT/.obsidian" ]; then
  echo "不是 Obsidian vault（找不到 .obsidian）：$MDC_VAULT" >&2
  exit 1
fi

echo "md-diagram-cards install"
echo "  source   $HERE"
echo "  vault    $MDC_VAULT"
echo "  python   $MDC_PYTHON"

# --- 1) Python ---------------------------------------------------------------
if ! command -v "$MDC_PYTHON" >/dev/null 2>&1; then
  echo "    找不到解释器：$MDC_PYTHON" >&2
  exit 1
fi

if "$MDC_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "    python   $("$MDC_PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') (ok)"
else
  echo "    需要 Python 3.9 或更高版本：$MDC_PYTHON" >&2
  exit 1
fi

# --- 2) 构建插件 --------------------------------------------------------------
if [ "$SKIP_BUILD" -eq 1 ]; then
  echo "    plugin   跳过构建（--skip-build）"
elif [ -f "$PLUGIN_SRC/main.js" ]; then
  echo "    plugin   使用现有 main.js"
elif command -v npm >/dev/null 2>&1; then
  if [ ! -d "$PLUGIN_SRC/node_modules" ]; then
    (cd "$PLUGIN_SRC" && npm install --silent) || echo "    plugin   npm install 失败"
  fi
  if (cd "$PLUGIN_SRC" && npm run build); then
    echo "    plugin   已构建"
  else
    echo "    plugin   构建失败；请手动 cd obsidian-plugin && npm install && npm run build"
  fi
else
  echo "    plugin   缺少 main.js 且找不到 npm；请手动构建后再跑本脚本" >&2
  exit 1
fi

if [ ! -f "$PLUGIN_SRC/main.js" ]; then
  echo "    缺少 $PLUGIN_SRC/main.js，无法部署" >&2
  exit 1
fi

# --- 3) 复制插件文件 ----------------------------------------------------------
PLUGIN_DST="$MDC_VAULT/.obsidian/plugins/$PLUGIN_ID"

if ! mkdir -p "$PLUGIN_DST" 2>/dev/null; then
  echo "" >&2
  echo "    无法写入 $PLUGIN_DST" >&2
  echo "    macOS 在保护 iCloud 目录。二选一：" >&2
  echo "      1) 系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 勾上你的终端，重开终端再跑" >&2
  echo "      2) 用 Finder 手动把这些文件拷进去：" >&2
  echo "         $PLUGIN_SRC/main.js" >&2
  echo "         $PLUGIN_SRC/manifest.json" >&2
  echo "         $PLUGIN_SRC/styles.css" >&2
  echo "         → $PLUGIN_DST/" >&2
  exit 1
fi

cp "$PLUGIN_SRC/main.js" "$PLUGIN_DST/main.js"
cp "$PLUGIN_SRC/manifest.json" "$PLUGIN_DST/manifest.json"

if [ -f "$PLUGIN_SRC/styles.css" ]; then
  cp "$PLUGIN_SRC/styles.css" "$PLUGIN_DST/styles.css"
fi
echo "    plugin   $PLUGIN_DST (copied)"

# --- 4) 首次写入 data.json ----------------------------------------------------
DATA_JSON="$PLUGIN_DST/data.json"
if [ ! -f "$DATA_JSON" ]; then
  cat > "$DATA_JSON" <<JSON
{
  "settings": {
    "scopeMode": "all",
    "includeFolders": [],
    "excludeFolders": [],
    "outputMode": "inplace",
    "pythonPath": "$MDC_PYTHON",
    "scriptPath": "$HERE/src",
    "timeoutSeconds": 120
  }
}
JSON
  echo "    config   data.json 已初始化（scriptPath -> $HERE/src）"
else
  echo "    config   已存在 data.json，未改动"
fi

# --- 后续步骤 ----------------------------------------------------------------
cat <<NEXT

完成。接下来在 Obsidian 里：
  1. 设置 → 第三方插件 → 刷新 → 启用 "MD Diagram Cards"
     （如果 Obsidian 当时开着，先重启它，否则读不到新的 data.json）
  2. 打开该插件设置页，最上面是「语法速查」（写什么格式、出什么卡），确认：
       脚本路径 = $HERE/src
       范围模式 / 输出模式 按需调整
  3. 点「测试」按钮，确认 Python 能跑起来

然后就可以用命令面板（Cmd+P）：
  MD Diagram Cards: 转换当前文件为卡片
  MD Diagram Cards: 转换整个库为卡片
  MD Diagram Cards: 查看转换日志

提示「转换成功但没有卡片」时，先看转换日志（设置页底部 / 上面那条命令）：
多半是文件里没写 [d-state] / [d-tree] / [d-orthogonal] 标记 —— 不带标记的标题不出卡。
日志文件：<vault>/.obsidian/plugins/md-diagram-cards/convert.log

排查：
  PYTHONPATH=$HERE/src $MDC_PYTHON -m md_diagram_cards --help
NEXT
