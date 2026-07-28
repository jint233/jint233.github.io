#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly target_dir="${1:-$project_root/site}"

mkdir -p "$target_dir/stylesheets" "$target_dir/javascripts"
rsync --archive --delete "$project_root/overrides/stylesheets/" "$target_dir/stylesheets/"
rsync --archive --delete "$project_root/overrides/javascripts/" "$target_dir/javascripts/"
