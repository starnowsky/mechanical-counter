.PHONY: help install install-dev test lint format clean build publish stl animate ci

help:
	@echo "Available commands:"
	@echo "  make install       — install the package"
	@echo "  make install-dev   — install with dev dependencies"
	@echo "  make test          — run pytest"
	@echo "  make lint          — flake8 + mypy"
	@echo "  make format        — black + isort"
	@echo "  make stl           — generate STL (3 digits)"
	@echo "  make animate       — full animation"
	@echo "  make clean         — remove build artifacts"
	@echo "  make build         — build a wheel"
	@echo "  make ci            — everything for CI"

install:
	pip install -e .

install-dev:
	pip install -e ".[all,dev]"

test:
	pytest

lint:
	flake8 counter tests
	mypy counter

format:
	black counter tests
	isort counter tests

stl:
	mc stl --digits 3 --out ./stl

animate:
	mc animate --digits 3 --layout lshape --out out/showreel.mp4

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build: clean
	python -m build

publish: build
	twine upload dist/*

ci: lint test
