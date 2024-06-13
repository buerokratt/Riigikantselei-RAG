# Riigikantselei API

## How do I get set up? ##

To create the environment or update it after adding a new dependency:

```
make install
# OR
conda env update -f conda-environment.yml --prune
```

Setup pre-commit hooks (optional):

```
conda run -n riigikantselei pre-commit install
```

## Migrations

```
make makemigrations migrate
```

## Checks and tests

```
make check
# OR
conda run -n riigikantselei pre-commit run --all-files
```

## Execution

1. Ensure you have all the services up and running through ```docker-compose up```
1. Ensure you have run the migrations.
1. Run the Celery workers for asynchronous tasks with ```conda run -n riigikantselei celery -A api.celery_handler worker -l debug```
1. Run the development web server with ```make run```.

### Known issues ###

On Windows there has been problem with conda environment for pre-commit tests hooks:
` UnicodeEncodeError: 'charmap' codec can't encode character`.
If this occurs, you may need to set system environment variable `PYTHONIOENCODING` with value `utf-8`
using this Microsoft guide:
[Saving environment variables with the System Control Panel](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables?view=powershell-7.3#saving-environment-variables-with-the-system-control-panel)
