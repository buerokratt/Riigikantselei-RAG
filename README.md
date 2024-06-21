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

## Preparations

To run tests or the app, you need supporting services up:

```
make up
```

You also have to run a Celery workers process in a __separate terminal window__:

```
make celery
```

## Checks and tests

Requires "Migrations" and "Preparations".

```
make check
```

## Execution

Requires "Migrations" and "Preparations".

```make run```

### Known issues ###

On Windows there has been problem with conda environment for pre-commit tests hooks:
` UnicodeEncodeError: 'charmap' codec can't encode character`.
If this occurs, you may need to set system environment variable `PYTHONIOENCODING` with value `utf-8`
using this Microsoft guide:
[Saving environment variables with the System Control Panel](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables?view=powershell-7.3#saving-environment-variables-with-the-system-control-panel)
