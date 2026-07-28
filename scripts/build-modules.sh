#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly docs_dir="$project_root/docs"
readonly site_dir="$project_root/site"
readonly portal_site_dir="$project_root/.site-portal"
readonly module_site_dir="$project_root/.site-modules"
readonly runtime_dir="$project_root/.mkdocs-runtime"
readonly build_lock_dir="$runtime_dir/build.lock"
readonly build_log_dir="$runtime_dir/build-logs"
readonly requested_jobs="${JOBS:-auto}"
readonly build_in_progress_exit_code=75
module_pids=()

release_build_lock() {
  rm -f "$build_lock_dir/pid"
  rmdir "$build_lock_dir" 2>/dev/null || true
}

cleanup_build_logs() {
  if [[ -d "$build_log_dir" ]]; then
    find "$build_log_dir" -type f -name '*.log' -delete
    rmdir "$build_log_dir" 2>/dev/null || true
  fi
}

stop_process_descendants() {
  local pid="$1"
  local signal="$2"
  local child

  while IFS= read -r child; do
    [[ "$child" =~ ^[0-9]+$ ]] || continue
    stop_process_descendants "$child" "$signal"
    kill -"$signal" "$child" 2>/dev/null || true
  done < <(pgrep -P "$pid" 2>/dev/null || true)
}

stop_module_builds() {
  local exit_code="$1"
  local pid

  trap - INT TERM
  if [[ ${#module_pids[@]} -gt 0 ]]; then
    for pid in "${module_pids[@]}"; do
      stop_process_descendants "$pid" TERM
    done
    for pid in "${module_pids[@]}"; do
      wait "$pid" 2>/dev/null || true
    done
  fi
  exit "$exit_code"
}

acquire_build_lock() {
  local owner_pid=""

  mkdir -p "$runtime_dir"
  if mkdir "$build_lock_dir" 2>/dev/null; then
    printf '%s\n' "$$" > "$build_lock_dir/pid"
    return
  fi

  [[ -f "$build_lock_dir/pid" ]] && owner_pid="$(<"$build_lock_dir/pid")"
  if [[ "$owner_pid" =~ ^[0-9]+$ ]] && kill -0 "$owner_pid" 2>/dev/null; then
    printf '已有文档构建正在运行（PID %s）\n' "$owner_pid" >&2
    exit "$build_in_progress_exit_code"
  fi

  release_build_lock
  mkdir "$build_lock_dir"
  printf '%s\n' "$$" > "$build_lock_dir/pid"
}

cd "$project_root"
acquire_build_lock
cleanup_build_logs
trap 'cleanup_build_logs; release_build_lock' EXIT
trap 'stop_module_builds 130' INT
trap 'stop_module_builds 143' TERM

modules=()
while IFS= read -r module; do
  modules+=("$module")
done < <("$project_root/scripts/module-configs.sh" list)

if [[ "$requested_jobs" == "auto" ]]; then
  jobs="${#modules[@]}"
  [[ "$jobs" -le 20 ]] || jobs=20
else
  jobs="$requested_jobs"
fi

[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || {
  printf 'JOBS 必须是正整数：%s\n' "$jobs" >&2
  exit 2
}
[[ "$jobs" -le 20 ]] || jobs=20
readonly jobs

is_known_module() {
  local candidate="$1"
  local known_module

  for known_module in "${modules[@]}"; do
    [[ "$known_module" == "$candidate" ]] && return 0
  done
  return 1
}

prefix_build_log() {
  local label="$1"
  local line

  while IFS= read -r line; do
    [[ "$line" == *"which is excluded from the built site"* ]] && continue
    if [[ "$line" =~ ^([A-Z]+)[[:space:]]+-[[:space:]]+(.*)$ ]]; then
      printf '%-7s [%s] - %s\n' \
        "${BASH_REMATCH[1]}" "$label" "${BASH_REMATCH[2]}"
    else
      printf '%s [%s]\n' "$line" "$label"
    fi
  done
}

run_mkdocs_build() {
  local label="$1"
  local config_file="$2"
  local output_dir="$3"
  local log_file="$build_log_dir/$label.log"
  local build_pid
  local build_status

  mkdir -p "$build_log_dir"
  rm -f "$log_file"
  mkdocs build \
    --config-file "$config_file" \
    --site-dir "$output_dir" \
    >"$log_file" 2>&1 &
  build_pid="$!"
  if wait "$build_pid" 2>/dev/null; then
    build_status=0
  else
    build_status="$?"
  fi

  if [[ "$build_status" -eq 130 || "$build_status" -eq 143 ]]; then
    rm -f "$log_file"
    return 130
  fi
  prefix_build_log "$label" < "$log_file"
  rm -f "$log_file"
  return "$build_status"
}

build_portal() {
  local config_file
  config_file="$("$project_root/scripts/module-configs.sh" portal)"
  run_mkdocs_build Portal "$config_file" "$portal_site_dir"
  "$project_root/scripts/sync-shared-assets.sh" "$portal_site_dir"
  mkdir -p "$site_dir"
  local rsync_args=(--archive --delete --exclude='/.git/' --exclude='/CNAME' --exclude='/search/')
  local module
  for module in "${modules[@]}"; do
    rsync_args+=("--exclude=/$module/")
  done
  rsync "${rsync_args[@]}" "$portal_site_dir/" "$site_dir/"
}

build_module() {
  local module="$1"
  local output_dir="$module_site_dir/$module"
  local config_file

  rm -rf "$output_dir"
  config_file="$("$project_root/scripts/module-configs.sh" runtime "$module")"
  run_mkdocs_build "$module" "$config_file" "$output_dir"
  mkdir -p "$site_dir/$module"
  rsync --archive --delete "$output_dir/$module/" "$site_dir/$module/"
}

build_modules() {
  local module
  local pid
  local failed=0
  local active=0
  local -a pids=()

  for module in "$@"; do
    build_module "$module" &
    pids+=("$!")
    module_pids+=("$!")
    active=$((active + 1))
    if [[ "$active" -ge "$jobs" ]]; then
      for pid in "${pids[@]}"; do
        wait "$pid" || failed=1
      done
      pids=()
      active=0
    fi
  done

  if [[ "$active" -gt 0 ]]; then
    for pid in "${pids[@]}"; do
      wait "$pid" || failed=1
    done
  fi
  [[ "$failed" -eq 0 ]]
}

target="${1:-all}"
if [[ "$target" == "none" ]]; then
  exit 0
fi

if [[ "$target" == "all" ]]; then
  build_portal
  build_modules "${modules[@]}"
  "$project_root/scripts/finalize-site.py" --reset "${modules[@]}"
  exit 0
fi

IFS=',' read -r -a requested_modules <<< "$target"
module_targets=()
portal_built=false
for module in "${requested_modules[@]}"; do
  if [[ "$module" == "portal" ]]; then
    build_portal
    portal_built=true
  elif ! is_known_module "$module"; then
    printf '未知模块：%s\n' "$module" >&2
    exit 2
  else
    module_targets+=("$module")
  fi
done

if [[ ${#module_targets[@]} -gt 0 ]]; then
  if [[ "$portal_built" == false ]]; then
    build_portal
  fi
  build_modules "${module_targets[@]}"
fi

if [[ "$portal_built" == true || ${#module_targets[@]} -gt 0 ]]; then
  "$project_root/scripts/finalize-site.py" "${module_targets[@]}"
fi
