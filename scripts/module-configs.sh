#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly docs_dir="$project_root/docs"
readonly runtime_dir="$project_root/.mkdocs-runtime"

list_modules() {
  local directory
  local module

  for directory in "$docs_dir"/*; do
    [[ -d "$directory" ]] || continue
    module="${directory##*/}"
    [[ "$module" == "assets" ]] && continue
    printf '%s\n' "$module"
  done | LC_ALL=C sort
}

first_module_url() {
  local first_module
  local first_page
  local relative_page
  local relative_url

  first_module="$(list_modules | head -n 1)"
  [[ -n "$first_module" ]] || {
    printf 'docs 下未找到可构建模块\n' >&2
    exit 2
  }

  # A module index is a section landing page, not the first article. Use the
  # first real article for the homepage CTA and keep the index as a fallback
  # for modules that contain no other Markdown files.
  first_page="$(find "$docs_dir/$first_module" -type f -name '*.md' ! -name 'index.md' | LC_ALL=C sort | head -n 1)"
  if [[ -z "$first_page" && -f "$docs_dir/$first_module/index.md" ]]; then
    first_page="$docs_dir/$first_module/index.md"
  fi
  [[ -n "$first_page" ]] || {
    printf '模块 %s 下未找到 Markdown 文档\n' "$first_module" >&2
    exit 2
  }

  relative_page="${first_page#"$docs_dir/"}"
  if [[ "$relative_page" == */index.md ]]; then
    relative_url="${relative_page%index.md}"
  else
    relative_url="${relative_page%.md}/"
  fi
  python3 -c 'import sys; from urllib.parse import quote; print(quote(sys.argv[1], safe="/"))' "$relative_url"
}

portal_config() {
  local home_url
  local target="$runtime_dir/portal.yml"
  local temporary

  home_url="$(first_module_url)"

  mkdir -p "$runtime_dir"
  temporary="$(mktemp "$runtime_dir/.portal.yml.XXXXXX")"
  printf '%s\n' \
    'INHERIT: ../mkdocs.yml' \
    'theme:' \
    '  custom_dir: ../overrides' \
    'docs_dir: ../docs' \
    'site_dir: ../site' > "$temporary"
  if [[ -n "${PREVIEW_URL:-}" ]]; then
    printf 'site_url: %s\n' "$PREVIEW_URL" >> "$temporary"
  fi
  printf '%s\n' \
    'extra:' \
    "  home_url: $home_url" >> "$temporary"
  mv "$temporary" "$target"
  printf '%s\n' "$target"
}

runtime_config() {
  local module="$1"
  local home_url
  local navigation_module
  local navigation_index
  local navigation_section
  local navigation_candidate
  local target="$runtime_dir/$module.yml"
  local temporary

  [[ -d "$docs_dir/$module" ]] || {
    printf '未知模块：%s\n' "$module" >&2
    exit 2
  }
  home_url="$(first_module_url)"
  mkdir -p "$runtime_dir"
  temporary="$(mktemp "$runtime_dir/.${module}.yml.XXXXXX")"
  printf '%s\n' \
    'INHERIT: ../mkdocs.yml' \
    'theme:' \
    '  custom_dir: ../overrides' \
    'docs_dir: ../docs' \
    'site_dir: ../site' > "$temporary"
  if [[ -n "${PREVIEW_URL:-}" ]]; then
    printf 'site_url: %s\n' "$PREVIEW_URL" >> "$temporary"
  fi
  printf '%s\n' \
    'extra:' \
    "  home_url: $home_url" \
    'exclude_docs: |' \
    '  */**' \
    "  !$module/**" \
    '  !assets/**' >> "$temporary"

  while IFS= read -r navigation_module; do
    [[ "$navigation_module" == "$module" ]] && continue
    if [[ -f "$docs_dir/$navigation_module/index.md" ]]; then
      printf '  !%s/index.md\n' "$navigation_module" >> "$temporary"
      continue
    fi
    for navigation_section in "$docs_dir/$navigation_module"/*; do
      [[ -d "$navigation_section" ]] || continue
      [[ "${navigation_section##*/}" == "assets" ]] && continue
      navigation_index=""
      while IFS= read -r navigation_candidate; do
        navigation_index="$navigation_candidate"
        break
      done < <(find "$navigation_section" -maxdepth 1 -type f -name '*.md' | LC_ALL=C sort)
      [[ -n "$navigation_index" ]] || continue
      navigation_index="${navigation_index#"$docs_dir/"}"
      printf '  !%s\n' "$navigation_index" >> "$temporary"
    done
  done < <(list_modules)

  printf '  **/.DS_Store\n' >> "$temporary"
  mv "$temporary" "$target"
  printf '%s\n' "$target"
}

case "${1:-list}" in
  list)
    list_modules
    ;;
  runtime)
    [[ $# -eq 2 ]] || {
      printf '用法：%s runtime <模块名>\n' "$0" >&2
      exit 2
    }
    runtime_config "$2"
    ;;
  portal)
    [[ $# -eq 1 ]] || {
      printf '用法：%s portal\n' "$0" >&2
      exit 2
    }
    portal_config
    ;;
  *)
    printf '用法：%s [list|portal|runtime <模块名>]\n' "$0" >&2
    exit 2
    ;;
esac
