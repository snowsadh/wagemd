# WAGE.md — one-command operations. Run `make help` for the list.
# Python backend uses uv (provides Python 3.11+). Frontend uses npm (Next.js 14).

AGENT_DIR := agent
FRONTEND_DIR := frontend
API_PORT ?= 8000

.DEFAULT_GOAL := help
.PHONY: help setup setup-agent setup-frontend ingest seed normalize publish investigate \
        api frontend demo test schema clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: setup-agent setup-frontend ## Install all deps + scaffold env
	@test -f .env.local || (cp .env.example .env.local && echo "Created .env.local — fill in your keys")

setup-agent: ## Install Python deps via uv (provisions Python 3.11+)
	cd $(AGENT_DIR) && uv sync

setup-frontend: ## Install frontend deps
	cd $(FRONTEND_DIR) && npm install

ingest: ## Run the Scout agent once (autonomous source poll)
	cd $(AGENT_DIR) && uv run python -m src.agents.scout

seed: ## Load FY2026 Q3 DOL PERM+LCA + CA WARN into Tiger Data, then normalize + seed levels
	cd $(AGENT_DIR) && uv run python -m src.ingestion.dol_flag --file PERM_Disclosure_Data_FY2026_Q3.xlsx --case-type PERM
	cd $(AGENT_DIR) && uv run python -m src.ingestion.dol_flag --file LCA_Disclosure_Data_FY2026_Q3.xlsx --case-type LCA
	cd $(AGENT_DIR) && uv run python -m src.ingestion.warn_ca --ingest
	cd $(AGENT_DIR) && uv run python -m src.normalization.title_normalizer
	cd $(AGENT_DIR) && uv run python -m src.normalization.seed_levels

normalize: ## Run the title/level normalization batch
	cd $(AGENT_DIR) && uv run python -m src.normalization.title_normalizer

publish: ## Generate company briefs and store them in Tiger Data
	cd $(AGENT_DIR) && uv run python -m src.publishing.publish_briefs --min-sample 5

investigate: ## Run the Investigator on the latest open anomaly (Amazon WARN demo by default)
	cd $(AGENT_DIR) && uv run python -m src.agents.investigator

api: ## Start the FastAPI server
	cd $(AGENT_DIR) && uv run uvicorn src.api.server:app --host 0.0.0.0 --port $(API_PORT) --reload

frontend: ## Start the Next.js dev server
	cd $(FRONTEND_DIR) && npm run dev

schema: ## Apply the TimescaleDB schema
	cd $(AGENT_DIR) && uv run python -m src.core.tiger_client --apply-schema

test: ## Run the Python test suite
	cd $(AGENT_DIR) && uv run pytest

demo: ## Boot everything for video recording (API + frontend)
	@echo "Booting WAGE.md demo: FastAPI on :$(API_PORT), Next.js on :3000"
	$(MAKE) -j2 api frontend

clean: ## Remove caches + build artifacts
	rm -rf $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/node_modules/.cache
	find $(AGENT_DIR) -type d -name __pycache__ -prune -exec rm -rf {} +
