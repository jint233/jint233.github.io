MODULE ?= all
JOBS ?= $(shell ./scripts/module-configs.sh list | awk 'END { if (NR > 20) print 20; else print NR }')
PORT ?= 8000
PYTHON ?= python3
VENV_DIR ?= .venv
VENV_BIN := $(VENV_DIR)/bin
DEPENDENCY_STAMP := $(VENV_DIR)/.requirements-installed

.PHONY: setup build preview serve

setup: $(DEPENDENCY_STAMP)

$(DEPENDENCY_STAMP): requirements.txt
	$(PYTHON) -m venv "$(VENV_DIR)"
	"$(VENV_BIN)/python" -m pip install --upgrade pip
	"$(VENV_BIN)/python" -m pip install -r requirements.txt
	touch "$(DEPENDENCY_STAMP)"

build: setup
	@set +e; \
	PATH="$(CURDIR)/$(VENV_BIN):$$PATH" JOBS="$(JOBS)" ./scripts/build-modules.sh "$(MODULE)"; \
	status=$$?; \
	if [ "$$status" -eq 75 ] || [ "$$status" -eq 130 ]; then exit 0; fi; \
	exit "$$status"

preview:
	@test -f site/index.html || { echo "未找到构建产物，请先执行 make build" >&2; exit 2; }
	$(PYTHON) scripts/preview.py --port "$(PORT)" --directory site

serve: setup
	@if [ "$(MODULE)" = "all" ]; then \
		set +e; \
		PATH="$(CURDIR)/$(VENV_BIN):$$PATH" JOBS="$(JOBS)" ./scripts/build-modules.sh all; \
		status=$$?; \
		if [ "$$status" -eq 75 ] || [ "$$status" -eq 130 ]; then exit 0; fi; \
		[ "$$status" -eq 0 ] || exit "$$status"; \
		$(PYTHON) scripts/preview.py --port "$(PORT)" --directory site; \
	elif [ "$(MODULE)" = "portal" ]; then \
		config_file="$$(PREVIEW_URL="http://127.0.0.1:$(PORT)/" ./scripts/module-configs.sh portal)"; \
		./scripts/sync-shared-assets.sh && \
		PREVIEW_URL="http://127.0.0.1:$(PORT)/" \
			PATH="$(CURDIR)/$(VENV_BIN):$$PATH" mkdocs serve --dirty \
			--dev-addr "127.0.0.1:$(PORT)" \
			--config-file "$$config_file"; \
		status=$$?; [ "$$status" -eq 130 ] && exit 0; exit "$$status"; \
	else \
		config_file="$$(PREVIEW_URL="http://127.0.0.1:$(PORT)/" ./scripts/module-configs.sh runtime $(MODULE))"; \
		./scripts/sync-shared-assets.sh && \
		PREVIEW_URL="http://127.0.0.1:$(PORT)/" \
			PATH="$(CURDIR)/$(VENV_BIN):$$PATH" mkdocs serve --dirty \
			--dev-addr "127.0.0.1:$(PORT)" \
			--config-file "$$config_file"; \
		status=$$?; [ "$$status" -eq 130 ] && exit 0; exit "$$status"; \
	fi
