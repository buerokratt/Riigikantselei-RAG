.ONESHELL:
.SHELLFLAGS = -euc


install:
	conda env update -f conda-environment.yaml --prune

check:
	conda run -n riigikantselei pre-commit run --all-files

# TODO here: revert to all tests
test:
	cd src && conda run -n riigikantselei python manage.py test core.tests.test_text_search_chat


makemigrations:
	cd src && conda run -n riigikantselei python manage.py makemigrations

migrate:
	cd src && conda run -n riigikantselei python manage.py migrate


superuser:
	cd src && conda run -n riigikantselei DJANGO_SUPERUSER_PASSWORD=password python manage.py createsuperuser --username admin --email admin@email.com --noinput

run:
	cd src && conda run -n riigikantselei python manage.py runserver 0.0.0.0:8000


build:
	docker compose build

up: build
	docker compose up -d

down:
	docker compose down
