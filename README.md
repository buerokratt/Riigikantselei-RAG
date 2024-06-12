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

```
make run
# OR
cd src
conda run -n riigikantselei python manage.py runserver 0.0.0.0:8000
```

### Known issues ###

On Windows there has been problem with conda environment for pre-commit tests hooks:
` UnicodeEncodeError: 'charmap' codec can't encode character`.
If this occurs, you may need to set system environment variable `PYTHONIOENCODING` with value `utf-8`
using this Microsoft guide:
[Saving environment variables with the System Control Panel](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables?view=powershell-7.3#saving-environment-variables-with-the-system-control-panel)
