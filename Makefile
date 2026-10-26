.PHONY: gate demo leakscan test

gate:
	pytest
	python scripts/leakscan.py
	cd console && npx vitest run

demo:
	python -m witness.demo.run_demo

leakscan:
	python scripts/leakscan.py

test:
	pytest
