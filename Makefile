# Local-dev convenience targets — they wrap `docker compose` so the
# same image + DB stack we ship to Hetzner is what we actually run
# locally. No `manage.py runserver`; if it doesn't work in the
# container, it doesn't work.
#
# Usage:
#   make up         # build, start db, migrate, start web+proxy
#   make down       # stop everything (volumes survive)
#   make wipe       # stop + delete volumes (full reset)
#   make logs       # tail web logs
#   make shell      # Django shell inside the web container
#   make psql       # psql inside the db container
#   make migrate    # run migrations
#   make superuser  # create the default local superuser (admin@kasia.local / heslo1234)
#   make seed       # seed walkthrough data (users, catalogue, sample movements)
#   make test       # run pytest inside the web container

COMPOSE ?= docker compose

# Local dev serves the app on http(s)://localhost via Caddyfile.dev (per 0083),
# so `make up` works out of the box on a fresh clone with no .env editing. The
# committed prod ./Caddyfile (kasia.cz + Let's Encrypt) is used only when
# CADDYFILE is set otherwise. Override with `make up CADDYFILE=./Caddyfile`.
#
# ⚠️  DO NOT run `make` targets on the production box. Prod deploys via
# .github/workflows/deploy.yml, which runs `docker compose` directly and never
# uses `make`. Running `make up` on the box would recreate the proxy with this
# dev Caddyfile (localhost-only, auto_https off) and break kasia.cz TLS. The
# `up` target echoes which Caddyfile it uses so this can never be silent.
CADDYFILE ?= ./Caddyfile.dev
export CADDYFILE

.PHONY: up down wipe build logs shell psql migrate superuser seed test ps

build:
	$(COMPOSE) build

up:
	@echo "→ Caddy config: $(CADDYFILE)  (dev = localhost; prod = ./Caddyfile — never run make on the box)"
	$(COMPOSE) up -d db
	@echo "Waiting for db to be healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' kasia-db-1 2>/dev/null)" = "healthy" ]; do sleep 2; done
	$(COMPOSE) run --rm web python manage.py migrate --noinput
	$(COMPOSE) up -d
	@echo ""
	@echo "Stack is up:"
	@echo "  app via Caddy → http://localhost"
	@echo "  Django admin  → http://localhost/admin/"
	@echo ""
	@echo "If this is a fresh setup, run: make superuser"

down:
	$(COMPOSE) down

wipe:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f web

shell:
	$(COMPOSE) exec web python manage.py shell

psql:
	$(COMPOSE) exec db psql -U kasia -d kasia

migrate:
	$(COMPOSE) run --rm web python manage.py migrate --noinput

superuser:
	$(COMPOSE) run --rm \
		-e DJANGO_SUPERUSER_EMAIL=admin@kasia.local \
		-e DJANGO_SUPERUSER_PASSWORD=heslo1234 \
		web python manage.py createsuperuser --noinput || true
	@echo "Superuser: admin@kasia.local / heslo1234"

seed:
	# Idempotent: users + catalogue always upserted; movement history
	# seeded only when the DB has no Movement rows yet. Re-run on
	# `make wipe` + `make up` + `make seed` to regenerate.
	$(COMPOSE) run --rm -e DJANGO_DEBUG=1 web python manage.py seed_walkthrough_data

test:
	# Tests run on the host (uv) against SQLite — the production image is
	# built with --no-dev and has no pytest. `make up` for the runtime
	# stack; `make test` for the test suite.
	uv run pytest -q

ps:
	$(COMPOSE) ps
