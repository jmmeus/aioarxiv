source := ${wildcard ./aioarxiv/*.py}
tests := ${wildcard tests/*.py}

.PHONY: all lint test audit docs clean install_deps

all: install_deps lint test docs

install_deps:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"

format: $(source) $(tests)
	ruff format .

lint: $(source) $(tests)
	ruff check .

test: $(source) $(tests)
	pytest

audit: install_deps
	python -m pip_audit --strict --requirement requirements.txt

docs: docs/index.html
docs/index.html: $(source) README.md
	pdoc --version
	pdoc --docformat "restructuredtext" ./aioarxiv/__init__.py -o docs

clean:
	rm -rf build dist
	rm -rf __pycache__ **/__pycache__
	rm -rf *.pyc **/*.pyc
	rm -rf aioarxiv.egg-info
