.ONESHELL:
.SHELLFLAGS = -euc


install:
	conda env update -f conda-environment.yaml --prune

check:
	conda run -n riigikantselei pre-commit run --all-files

test:
	cd src && conda run -n riigikantselei python manage.py test


makemigrations:
	cd src && conda run -n riigikantselei python manage.py makemigrations --noinput

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

logs:
	docker compose logs


celery:
	cd src && celery -A api.celery_handler worker -l DEBUG
