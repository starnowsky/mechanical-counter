.PHONY: help install install-dev test lint format clean build publish stl animate ci

help:
	@echo "Доступные команды:"
	@echo "  make install       — установка пакета"
	@echo "  make install-dev   — установка с dev-зависимостями"
	@echo "  make test          — запуск pytest"
	@echo "  make lint          — flake8 + mypy"
	@echo "  make format        — black + isort"
	@echo "  make stl           — генерация STL (3 разряда)"
	@echo "  make animate       — полная анимация"
	@echo "  make clean         — очистка артефактов"
	@echo "  make build         — сборка wheel"
	@echo "  make ci            — всё для CI"

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
