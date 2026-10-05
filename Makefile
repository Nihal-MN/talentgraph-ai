# TalentGraph AI — developer commands

.PHONY: up down logs ps seed reembed test eval bench lint fe-install fe-test fe-build fe-lint api-shell

up:            ## build + start the whole stack (api, web, pgvector db)
	docker compose up --build -d

down:          ## stop the stack (keeps the database volume)
	docker compose down

logs:          ## tail all service logs
	docker compose logs -f --tail=100

ps:            ## service status
	docker compose ps

seed:          ## (re)seed the synthetic dataset (200 profiles) + benchmark
	docker compose exec api python -m app.seed --reset

reembed:       ## recompute embeddings for every candidate (after model/provider change)
	docker compose exec api python -m app.seed --reembed

test:          ## backend test suite (incl. the named eval suite)
	docker compose exec api pytest -q

eval:          ## named retrieval eval suite only
	docker compose exec api pytest tests/evals -q

bench:         ## run + persist the retrieval benchmark (Evaluation page data)
	docker compose exec api python scripts/run_benchmark.py --persist

lint:          ## backend lint
	docker compose exec api ruff check app tests

api-shell:     ## shell inside the api container
	docker compose exec api sh

fe-install:    ## install frontend deps (local dev without Docker)
	cd frontend && npm ci

fe-test:       ## frontend tests
	cd frontend && npm run test

fe-build:      ## frontend production build
	cd frontend && npm run build

fe-lint:       ## frontend lint + typecheck
	cd frontend && npm run lint && npm run typecheck
