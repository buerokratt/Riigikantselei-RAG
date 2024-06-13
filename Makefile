.ONESHELL:
.SHELLFLAGS = -euc


install:
	conda env update -f conda-environment.yaml --prune

check:
	conda run -n riigikantselei pre-commit run --all-files

# TODO here: get them to pass for user_profile
# TODO here: run everywhere
test:
	cd src && conda run -n riigikantselei ./manage.py test user_profile.tests

makemigrations:
	cd src && conda run -n riigikantselei ./manage.py makemigrations

migrate:
	cd src && conda run -n riigikantselei ./manage.py migrate


test:
	cd src && conda run -n riigikantselei python manage.py test

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
