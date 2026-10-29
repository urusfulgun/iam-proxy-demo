.DEFAULT_GOAL := help
.PHONY: help init secrets keys up down logs apply export reset

COMPOSE := docker compose

help: ## List targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

init: .env secrets keys up ## Create .env if missing, fill in secrets and keypairs, then start the stack

# Never overwrites an existing .env, so secrets survive `make reset`.
.env:
	cp .env.example .env

# NAME:bytes of `openssl rand -hex`. The demo password is short enough to type in a browser.
SECRETS := KC_BOOTSTRAP_ADMIN_PASSWORD:24 POSTGRES_PASSWORD:24 DEMO_USER_PASSWORD:6

secrets: .env ## Generate any password that .env lacks or leaves empty
	@for entry in $(SECRETS); do \
	  name=$${entry%%:*}; \
	  if grep -q "^$$name=." .env; then continue; fi; \
	  value=$$(openssl rand -hex $${entry#*:}); \
	  if grep -q "^$$name=" .env; then sed -i "s|^$$name=.*|$$name=$$value|" .env; \
	  else echo "$$name=$$value" >> .env; fi; \
	  echo "secrets: generated $$name"; \
	done

# One pinned SAML signing keypair per home realm, written as one-line base64 bodies (no PEM
# header). A pair is regenerated only if its key or cert is empty or missing; values are never
# printed.
HOME_REALMS := home-fau home-bamberg

keys: .env ## Generate a home realm keypair wherever .env lacks one
	@for realm in $(HOME_REALMS); do \
	  p=$$(echo $$realm | tr a-z- A-Z_)_SAML; \
	  if grep -q "^$${p}_PRIVATE_KEY=." .env && grep -q "^$${p}_CERT=." .env; then continue; fi; \
	  dir=$$(mktemp -d); \
	  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=$$realm" \
	    -keyout $$dir/key.pem -out $$dir/cert.pem 2>/dev/null || exit 1; \
	  for var in PRIVATE_KEY:key CERT:cert; do \
	    name=$${p}_$${var%%:*}; \
	    value=$$(sed '1d;$$d' $$dir/$${var#*:}.pem | tr -d '\n'); \
	    if grep -q "^$$name=" .env; then sed -i "s|^$$name=.*|$$name=$$value|" .env; \
	    else echo "$$name=$$value" >> .env; fi; \
	  done; \
	  rm -rf $$dir; \
	  echo "keys: generated a keypair for $$realm"; \
	done

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
