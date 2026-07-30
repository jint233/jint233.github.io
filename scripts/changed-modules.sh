#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly docs_dir="$project_root/docs"

if [[ $# -ne 2 ]]; then
  printf '用法：%s <base-ref> <head-ref>\n' "$0" >&2
  exit 2
fi

cd "$project_root"
changed_modules=()
portal_changed=false
global_changed=false

add_module() {
  local module="$1"
  local changed_module

  [[ -d "$docs_dir/$module" && "$module" != "assets" ]] || return
  if [[ ${#changed_modules[@]} -gt 0 ]]; then
    for changed_module in "${changed_modules[@]}"; do
      [[ "$changed_module" == "$module" ]] && return
    done
  fi
  changed_modules+=("$module")
}

while IFS= read -r -d '' file; do
  case "$file" in
    docs/index.md|docs/assets/*|overrides/home.html|overrides/assets/*|overrides/stylesheets/*|overrides/javascripts/*)
      portal_changed=true
      ;;
    scripts/preview.py)
      ;;
    mkdocs.yml|requirements.txt|.github/workflows/*|overrides/*|scripts/*)
      global_changed=true
      ;;
    docs/*)
      top_level="${file#docs/}"
      top_level="${top_level%%/*}"
      if [[ -d "$docs_dir/$top_level" ]]; then
        add_module "$top_level"
      else
        global_changed=true
      fi
      ;;
  esac
done < <(git diff --name-only -z "$1" "$2")

if [[ "$global_changed" == true ]]; then
  printf 'all\n'
  exit 0
fi

result=()
if [[ "$portal_changed" == true ]]; then
  result+=(portal)
fi
if [[ ${#changed_modules[@]} -gt 0 ]]; then
  sorted_modules=()
  while IFS= read -r module; do
    sorted_modules+=("$module")
  done < <(printf '%s\n' "${changed_modules[@]}" | LC_ALL=C sort)
  changed_modules=("${sorted_modules[@]}")
  result+=("${changed_modules[@]}")
fi

if [[ ${#result[@]} -eq 0 ]]; then
  printf 'none\n'
else
  (IFS=','; printf '%s\n' "${result[*]}")
fi
