PROJECT := tab
DATABASE := test_analysis_bot_dev
IMAGE := test-analysis-bot

.PHONY: all
all: check test ## CI | Run all validation targets

.PHONY: dev
dev: install ## CI | Rerun all validation targets in a loop
	@ rm -rf $(FAILURES)
	@ sleep 1 && touch $(PROJECT)/__init__.py &
	poetry run watchmedo shell-command --command="clear; make test check; echo Done!" --recursive --drop

# SYSTEM DEPENDENCIES #########################################################

.PHONY: setup
setup: .envrc bootstrap doctor ## Run the one-time initial setup
	createdb $(DATABASE)

.PHONY: bootstrap
bootstrap: ## Attempt to install system dependencies
	asdf plugin add python || asdf plugin update python
	asdf plugin add poetry || asdf plugin update poetry
	asdf install

.PHONY: doctor
doctor: ## Check for required system dependencies
	bin/verchew --exit-code

.envrc:
	echo export DATABASE_URL=postgresql://localhost/$(DATABASE) >> $@
	echo export REDIS_URL=redis://localhost:6379/0 >> $@
	- direnv allow

# PROJECT DEPENDENCIES ########################################################

VIRTUAL_ENV ?= .venv
DEPENDENCIES = $(VIRTUAL_ENV)/.poetry-$(shell bin/checksum pyproject.toml poetry.lock)

.PHONY: install
install: $(DEPENDENCIES) ## Install project dependencies

$(DEPENDENCIES): poetry.lock
	@ mkdir -p staticfiles
	@ poetry config virtualenvs.in-project true
	poetry install --without=docs
	@ touch $@

ifndef CI
poetry.lock: pyproject.toml
	poetry lock
	@ touch $@
endif

.PHONY: clean
clean: ## Delete all generated and temporary files
	rm -rf .cache .coverage htmlcov staticfiles test-results
	rm -rf $(VIRTUAL_ENV)

# RUNTIME DEPENDENCIES ########################################################

.PHONY: migrations
migrations: install ## Database | Generate database migrations
	./manage.py makemigrations

.PHONY: migrate
migrate: install ## Database | Run database migrations
	./manage.py migrate

.PHONY: data
data: install migrate ## Database | Seed data for manual testing
	./manage.py gendata
	./manage.py loaddata projects

.PHONY: reset
reset: install ## Database | Create a new database, migrate, and seed it
	- dropdb $(DATABASE)
	createdb $(DATABASE)
	make data

# VALIDATION TARGETS ##########################################################

PACKAGES := config $(PROJECT)
FAILURES := .cache/pytest/v/cache/lastfailed

.PHONY: check
check: install format ## Run static analysis
	poetry run mypy $(PACKAGES) tests

.PHONY: format
format: install
	poetry run isort $(PACKAGES) tests
	poetry run black $(PACKAGES) tests
	poetry run djlint --reformat templates

ifdef DISABLE_COVERAGE
PYTEST_OPTIONS := --no-cov --disable-warnings
endif

.PHONY: test
test: test-all ## Run all tests

.PHONY: test-unit
test-unit: install
	@ ( mv $(FAILURES) $(FAILURES).bak || true ) > /dev/null 2>&1
	poetry run pytest $(PACKAGES) --markers="not django_db" $(PYTEST_OPTIONS)
	@ ( mv $(FAILURES).bak $(FAILURES) || true ) > /dev/null 2>&1
ifndef DISABLE_COVERAGE
	poetry run coveragespace update unit
endif

.PHONY: test-integration
test-integration: install
	@ if test -e $(FAILURES); then poetry run pytest tests --last-failed; fi
	@ rm -rf $(FAILURES)
	poetry run pytest tests $(PYTEST_OPTIONS)
	poetry run coveragespace update integration

.PHONY: test-all
test-all: install
	@ if test -e $(FAILURES); then poetry run pytest $(PACKAGES) tests --last-failed; fi
	@ rm -rf $(FAILURES)
	poetry run pytest $(PACKAGES) tests $(PYTEST_OPTIONS)
	poetry run coveragespace update overall

.PHONY: test-e2e
test-e2e: install
	mkdir -p test-results
	cp tests/files/junit.xml test-results/junit.xml
	@ echo

	TAB_API_URL=$${TAB_API_URL:-http://localhost:8000} \
	TAB_API_KEY=$${TAB_API_KEY:-localhost} \
	GITHUB_SERVER_URL=https://github.com \
	GITHUB_REPOSITORY=KittyCAD/modeling-app \
	GITHUB_RUN_ID=999999 \
	GITHUB_HEAD_REF=tab-test \
	CI_COMMIT_SHA=$$(date +%m-%d) \
	CI_PR_NUMBER=9999 \
	time ./docs/examples/junit/upload-results.sh || true
	@ echo

	TAB_API_URL=$${TAB_API_URL:-http://localhost:8000} \
	TAB_API_KEY=$${TAB_API_KEY:-localhost} \
	GITHUB_SERVER_URL=https://github.com \
	GITHUB_REPOSITORY=KittyCAD/modeling-app \
	GITHUB_RUN_ID=999999 \
	GITHUB_HEAD_REF=main \
	CI_COMMIT_SHA=$$(date +%m-%d) \
	time ./docs/examples/junit/upload-results.sh || true
	@ echo

	./manage.py cleandata

# SERVER TARGETS ##############################################################

.PHONY: run
run: .envrc install migrate ## Run the application
	./manage.py runserver

.PHONY: run-production
run-production: .envrc
	docker build --tag $(IMAGE):latest .
	docker run --env SECRET_KEY=local --env DATABASE_URL=$(DATABASE_URL) --env REDIS_URL=$(REDIS_URL) --publish=8000:8000 --rm $(IMAGE):latest

# DOCUMENTATION TARGETS #######################################################

.PHONY: uml
uml: install
	poetry install --with=docs
	@ echo
	poetry run pyreverse $(PROJECT) -p $(PROJECT) -a 1 -f ALL -o png --ignore admin.py,migrations,management,tests
	mv -f classes_$(PROJECT).png docs/classes.png
	mv -f packages_$(PROJECT).png docs/packages.png
	./manage.py graph_models --all-applications --group-models --output=docs/tables.png --exclude-models=AbstractUser,AbstractBaseSession,Session

# HELP ########################################################################

.PHONY: help
help: install
	@ grep -E '^[^[:space:]]+:.*## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
