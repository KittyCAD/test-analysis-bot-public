PROJECT := tab

.PHONY: all
all: check test ## CI | Run all validation targets

.PHONY: dev
dev: install ## CI | Rerun all validation targets in a loop
	@ rm -rf $(FAILURES)
	poetry run sniffer

# SYSTEM DEPENDENCIES #########################################################

.PHONY: bootstrap
bootstrap: ## Attempt to install system dependencies
	asdf plugin add python || asdf plugin update python
	asdf plugin add poetry || asdf plugin update poetry
	asdf install

.PHONY: doctor
doctor: ## Check for required system dependencies
	bin/verchew --exit-code

.envrc:
	echo export DJANGO_SETTINGS_MODULE=config.settings.local >> $@
	echo export DATABASE_URL=postgresql://localhost/test_analysis_bot_dev >> $@
	echo export REDIS_URL=redis://127.0.0.1:6379/0 >> $@
	- direnv allow

# PROJECT DEPENDENCIES ########################################################

VIRTUAL_ENV ?= .venv

BACKEND_DEPENDENCIES = $(VIRTUAL_ENV)/.poetry-$(shell bin/checksum pyproject.toml poetry.lock)
FRONTEND_DEPENDENCIES =

.PHONY: install
install: $(BACKEND_DEPENDENCIES) $(FRONTEND_DEPENDENCIES) ## Install project dependencies

$(BACKEND_DEPENDENCIES): poetry.lock
	@ poetry config virtualenvs.in-project true
	poetry install
	@ touch $@

ifndef CI
poetry.lock: pyproject.toml
	poetry lock
	@ touch $@
endif

$(FRONTEND_DEPENDENCIES):
	# TODO: Install frontend dependencies if applicable
	@ touch $@

.PHONY: clean
clean: ## Delete all generated and temporary files
	rm -rf .cache .coverage htmlcov staticfiles
	rm -rf $(VIRTUAL_ENV)
	# TODO: Delete compiled frontend dependencies if applicable

# RUNTIME DEPENDENCIES ########################################################

.PHONY: migrations
migrations: install ## Database | Generate database migrations
	./manage.py makemigrations

.PHONY: migrate
migrate: install ## Database | Run database migrations
	./manage.py migrate

.PHONY: data
data: install migrate ## Database | Seed data for manual testing
	# TODO: Load test data and fixtures
	# ./manage.py loaddata content

.PHONY: reset
reset: install ## Database | Create a new database, migrate, and seed it
	- dropdb test_analysis_bot_dev
	- createdb test_analysis_bot_dev
	make data

# VALIDATION TARGETS ##########################################################

PYTHON_PACKAGES := config $(PROJECT)
FAILURES := .cache/pytest/v/cache/lastfailed

.PHONY: check
check: check-backend ## Run static analysis

.PHONY: format
format: format-backend

.PHONY: check-backend
check-backend: install format-backend
	poetry run mypy $(PYTHON_PACKAGES) tests

.PHONY: check-frontend
check-frontend: install
	# TODO: Run frontend linters if applicable

format-backend: install
	poetry run isort $(PYTHON_PACKAGES) tests
	poetry run black $(PYTHON_PACKAGES) tests
	poetry run djlint --reformat templates

ifdef DISABLE_COVERAGE
PYTEST_OPTIONS := --no-cov --disable-warnings
endif

.PHONY: test
test: test-backend test-frontend ## Run all tests

.PHONY: test-backend
test-backend: test-backend-all
ifdef COVERALLS_REPO_TOKEN
	poetry run coveralls
endif

.PHONY: test-backend-unit
test-backend-unit: install
	@ ( mv $(FAILURES) $(FAILURES).bak || true ) > /dev/null 2>&1
	poetry run pytest $(PYTHON_PACKAGES) tests/unit -m "not django_db" $(PYTEST_OPTIONS)
	@ ( mv $(FAILURES).bak $(FAILURES) || true ) > /dev/null 2>&1
ifndef DISABLE_COVERAGE
	poetry run coveragespace update unit
endif

.PHONY: test-backend-integration
test-backend-integration: install
	@ if test -e $(FAILURES); then poetry run pytest tests/integration --last-failed; fi
	@ rm -rf $(FAILURES)
	poetry run pytest tests/integration $(PYTEST_OPTIONS)
	poetry run coveragespace update integration

.PHONY: test-backend-all
test-backend-all: install
	@ if test -e $(FAILURES); then poetry run pytest $(PYTHON_PACKAGES) tests/unit tests/integration  --last-failed; fi
	@ rm -rf $(FAILURES)
	poetry run pytest $(PYTHON_PACKAGES) tests/unit tests/integration $(PYTEST_OPTIONS)
	poetry run coveragespace update overall

.PHONY: test-frontend
test-frontend: test-frontend-unit

.PHONY: test-frontend-unit
test-frontend-unit: install
	# TODO: Run frontend tests if applicable

# SERVER TARGETS ##############################################################

.PHONY: run
run: .envrc install migrate ## Run the application
	./manage.py runserver

.PHONY: run-production
run-production: .envrc install
	./manage.py collectstatic --no-input
	# TODO: Emulate the production environment

# DOCUMENTATION TARGETS #######################################################

.PHONY: uml
uml: install
	poetry run pyreverse $(PROJECT) -p $(PROJECT) -a 1 -f ALL -o png --ignore admin.py,migrations,management,tests
	mv -f classes_$(PROJECT).png docs/classes.png
	# mv -f packages_$(PROJECT).png docs/packages.png
	# ./manage.py graph_models demo_app --group-models --output=docs/tables.png --exclude-models=TimeStampedModel

# HELP ########################################################################

.PHONY: help
help: install
	@ grep -E '^[^[:space:]]+:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
