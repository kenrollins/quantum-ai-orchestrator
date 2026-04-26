.PHONY: help venv install smoke smoke-numerical smoke-viz demo serve docs migrate clean

help:
	@echo "quantum-ai-orchestrator — make targets"
	@echo ""
	@echo "  venv              create .venv via uv (Python 3.11)"
	@echo "  install           install pinned dependencies into .venv"
	@echo "  smoke             run all 11 Phase-0 smoke tests (numerical + viz)"
	@echo "  smoke-numerical   run the 6 numerical Phase-0 gates"
	@echo "  smoke-viz         run the 5 visualization Phase-0 renders"
	@echo "  demo              end-to-end qec_decode demo (Phase 1)"
	@echo "  serve             start the FastAPI replay server + Next.js dashboard"
	@echo "  docs              build mkdocs site to ./site"
	@echo "  migrate           apply pending Postgres migrations against supabase-db"
	@echo "  clean             remove .venv and build artifacts"

venv:
	uv venv --python 3.11

install: venv
	uv pip install -e .[dev,docs]

smoke: smoke-numerical smoke-viz

smoke-numerical:
	uv run pytest tests/smoke -m numerical -v

smoke-viz:
	uv run pytest tests/smoke -m viz -v

demo:
	uv run python -m orchestrator.cli demo

serve:
	uv run uvicorn web.api.serve_replay:app --host 0.0.0.0 --port 8080 &
	cd web/ui && npm run dev

docs:
	uv run mkdocs build --strict

migrate:
	@for f in migrations/*.sql; do \
	  echo "applying $$f"; \
	  PGPASSWORD="$$POSTGRES_PASSWORD" psql -h "$$POSTGRES_HOST" -p "$$POSTGRES_PORT" -U "$$POSTGRES_USER" -f "$$f" || exit 1; \
	done

clean:
	rm -rf .venv .pytest_cache __pycache__ site
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
