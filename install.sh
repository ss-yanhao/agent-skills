#!/usr/bin/env bash
# 把本仓库的技能装到 ~/.workbuddy/skills/
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${HOME}/.workbuddy/skills"

list_skills() {
  # 顶层目录里含 SKILL.md 的，才算一个技能
  for d in "$SRC"/*/; do
    [ -f "${d}SKILL.md" ] && basename "$d"
  done
}

usage() {
  echo "用法:"
  echo "  ./install.sh              安装全部技能"
  echo "  ./install.sh <技能名>      只装指定的一个"
  echo
  echo "已收录技能:"
  list_skills | sed 's/^/  - /'
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  usage
  exit 0
fi

if [ -n "$1" ]; then
  targets="$1"
else
  targets="$(list_skills)"
fi

if [ -z "$targets" ]; then
  echo "没有找到任何技能。"
  exit 1
fi

mkdir -p "$DEST"

for name in $targets; do
  if [ ! -f "$SRC/$name/SKILL.md" ]; then
    echo "跳过 $name（不是技能目录，或没有 SKILL.md）"
    continue
  fi

  if [ -d "$DEST/$name" ]; then
    printf "已存在 %s，覆盖？[y/N] " "$name"
    read -r ans
    if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
      echo "跳过 $name"
      continue
    fi
    rm -rf "$DEST/$name"
  fi

  cp -R "$SRC/$name" "$DEST/"
  echo "已安装 $name  ->  $DEST/$name"
done

echo
echo "装完重开一次会话，WorkBuddy 才会扫到新技能。"
echo "首次使用会引导你填资料（品牌资料 / 往期文案），"
echo "填在各技能自己的 user/ 目录里，例如："
echo "  $DEST/moments-copy/user/"
