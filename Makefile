.PHONY: up down logs simulate test

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

simulate:
	python scripts/simulate_drone.py

test:
	pytest -q
