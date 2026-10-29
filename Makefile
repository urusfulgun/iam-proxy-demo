.DEFAULT_GOAL := help
.PHONY: help init up down logs apply export reset

COMPOSE := docker compose

help: ## List targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

init: .env up ## Create .env if missing, then start the stack

# Never overwrites an existing .env, so secrets survive `make reset`.
.env:
	cp .env.example .env
	sed -i "s/^KC_BOOTSTRAP_ADMIN_PASSWORD=$$/&$$(openssl rand -hex 24)/" .env
	sed -i "s/^POSTGRES_PASSWORD=$$/&$$(openssl rand -hex 24)/" .env

up: ## Build and start; returns once realms are applied and the app is healthy
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack (keeps the database)
	$(COMPOSE) down

logs: ## Follow all logs
	$(COMPOSE) logs -f

apply: ## Re-apply keycloak/realms/*.json
	$(COMPOSE) run --rm --build keycloak-config

export: ## Dump the live realms to export/ (copy into keycloak/realms/ by hand)
	rm -rf export
	$(COMPOSE) exec keycloak rm -rf /tmp/export
	# A second JVM next to the running server: it needs its own management port, as 9000 is taken.
	$(COMPOSE) exec keycloak /opt/keycloak/bin/kc.sh export --dir /tmp/export --users realm_file \
		--http-management-port=9001
	$(COMPOSE) cp keycloak:/tmp/export ./export

reset: ## Drop the database volume and start from scratch (keeps .env)
	$(COMPOSE) down -v --remove-orphans
	$(MAKE) init
