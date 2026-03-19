#!/usr/bin/env bash
# 比较 app/ 目录下的 .py 文件列表与快照，如有变化则提醒更新记忆文件
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SNAPSHOT="$PROJECT_DIR/.filelist"

if [ ! -f "$SNAPSHOT" ]; then
  exit 0
fi

CURRENT=$(cd "$PROJECT_DIR" && find app -name "*.py" | sort)
OLD=$(sort "$SNAPSHOT")

if [ "$CURRENT" != "$OLD" ]; then
  echo "$CURRENT" > "$SNAPSHOT"
  echo "⚠️  app/ 目录结构已变化，请记得更新记忆文件（MEMORY.md / architecture.md）。"
fi

# 同步记忆文件到全局目录，确保 Claude Code 新会话能读取
LOCAL_MEMORY="$PROJECT_DIR/.claude/memory"
GLOBAL_MEMORY="$HOME/.claude/projects/e--Work-Python-ResearchReportCenter/memory"
if [ -d "$LOCAL_MEMORY" ] && [ -d "$GLOBAL_MEMORY" ]; then
  cp "$LOCAL_MEMORY/MEMORY.md" "$GLOBAL_MEMORY/MEMORY.md" 2>/dev/null
  cp "$LOCAL_MEMORY/architecture.md" "$GLOBAL_MEMORY/architecture.md" 2>/dev/null
fi
