.PHONY: seed serve test lint

seed:
	cd backend && python seed.py

serve:
	cd backend && uvicorn main:app --reload --port 8000

test:
	pytest tests/ -v

lint:
	ruff check backend/ agent/
