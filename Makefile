FLAKE8_CONFIG := $(shell \
	if python -c "import toml" 2>/dev/null; then \
		python -c "import toml; data = toml.load('pyproject.toml'); flake8 = data.get('tool', {}).get('flake8', {}); max_line_length = flake8.get('max-line-length', 128); ignores = ' '.join(['--ignore=' + i for i in flake8.get('ignore', [])]); print(f'--max-line-length {max_line_length} {ignores}')"; \
	else \
		echo "--max-line-length 128"; \
	fi)

target:
	@echo -e "\033[1mdiscord.http v$(shell grep -oP '(?<=__version__ = ")[^"]*' discord_http/__init__.py)\033[0m" \
	"\nUse 'make \033[0;36mtarget\033[0m' where \033[0;36mtarget\033[0m is one of the following:"
	@awk -F ':|##' '/^[^\t].+?:.*?##/ { printf " \033[0;36m%-15s\033[0m %s\n", $$1, $$NF }' $(MAKEFILE_LIST)

# Production tools
install:  ## Install the package
	pip install .

uninstall:  ## Uninstall the package
	pip uninstall -y discord.http

reinstall: uninstall install  ## Reinstall the package

# Development tools
install_dev:	 ## Install the package in development mode
	pip install .[dev]

install_docs:  ## Install the documentation dependencies
	pip install .[docs]

create_docs:	## Create the documentation
	@cd docs && make html

venv:  ## Create a virtual environment
	python -m venv .venv

flake8:  ## Run flake8 on the package
	@flake8 $(FLAKE8_CONFIG) discord_http
	@echo -e "\033[0;32mNo errors found.\033[0m"

type:  ## Run pyright on the package
	@pyright discord_http --pythonversion 3.11

lint:  ## Run ruff linter
	@ruff check --config pyproject.toml

clean:  ## Clean the project
	@rm -rf build dist *.egg-info .venv docs/_build
	@rm uv.lock

# Maintainer-only commands
upload_pypi:  ## Maintainer only - Upload latest version to PyPi
	@echo Uploading to PyPi...
	uv build
	uvx uv-publish
	@echo Done!
