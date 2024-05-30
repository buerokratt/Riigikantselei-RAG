.ONESHELL:
.SHELLFLAGS = -euc


install:
	conda env update -f conda-environment.yaml --prune

check:
	conda run -n riigikantselei pre-commit run --all-files


build:
	docker compose build

up: build
	docker compose up -d

down:
	docker compose down
