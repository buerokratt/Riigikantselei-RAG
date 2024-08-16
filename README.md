# Riigikantselei API

![Python](https://img.shields.io/badge/python-3.10-blue.svg)

Aggregating the public data of various Estonian institutions for the purpose of aiding in decision-making processes by
allowing users to use the natural language of LLM's but with additional stability by providing segments of public documents
through RAG as context.

Ran with Python 3.10 and Django as the web service, Elasticsearch for the vector search to get relevant segments for RAG,
MySQL for data storage and Redis + Celery for an asynchronous workflow for search and ChatGPT communication.

## Developer setup

Setup pre-commit hooks (optional) for developments:

```
conda run -n riigikantselei pre-commit install
```

## Deployment setup

***NB!*** If you deploy this and do not change the default environmental variables within the .env file, not only will
the application not work because of security features like Allowed-Hosts, but I will personally hunt you down with a
spatula since it means you're using the UNSECURE admin password and cryptographic keys along with DEBUG mode...

### Local
1. Create an account for ChatGPT and copy down its API key.
1. Populate the environment variables within local.env based on the instructions on the README and the deployment environment.
1. Install the Python environment with ```conda env install -f conda-environment.yaml```
1. Activate the Python environment with ```conda activate riigikantselei```.
1. Ensure you have the dependency services (Elasticsearch 8+, Redis, MySQL) running beforehand.
1. Enter the source directory ```cd src```.
1. Run ```python migrate.py``` to create the initial admin account and to apply the database migrations to MySQL.
1. Run ```python manage.py compilemessages -l et``` to compile the translations for the Estonian language. Missing this step will mean only default legacy translations will be used.
1. Set the environment variable of RK_ENV_FILE to the path of the .env file in use and launch Celery (the async workers) with ```celery -A api.celery_handler worker --max-tasks-per-child=%(ENV_RK_MAX_TASKS)s --concurrency=%(ENV_RK_WORKERS)s -Ofair -l warning -Q celery ```
    * --max-tasks-per-child determines how many tasks a single Celery worker does before restarting itself and creating a new fresh worker (good to release memory in long running tasks). Value around a 100 should be ok.
    * --concurrency sets how many Celery processes are created. Since the process of using Vectorization models for vectorsearch is quite CPU heavy, this number should be conservative, 2-5 depending on the system specs.
1. Run the webserver of choice. For the development server you can use ```python manage.py runserver```. Similar to Celery, it is recommended to set the RK_ENV_FILE environment variable to the path of the .env file in use.
1. Configure the datasets in the /api/v1/dataset endpoint or 'Andmestikud' in the user interface. Without these the application will not work. Not that when setting the index value of a dataset, wildcard patterns are allowed for ex: rk_riigiteataja_*


### Docker
1. Create an account for ChatGPT and copy down its API key.
1. Set the environment variables in local.env file.
1. Build the image with ```docker-compose build rk_api```
1. Set up the dependency services MySQL, Redis and Elasticsearch clusters to your liking (alternatively, you can use the services in the docker-compose, however for production its recommended to use a proper Elasticsearch cluster as it does some heavy lifting and a single node Docker instance isn't enough).
1. Run the service with ```docker-compose up -d rk_api```
1. Configure the datasets in the /api/v1/dataset endpoint or 'Andmestikud' in the user interface. Without these the application will not work. Not that when setting the index value of a dataset, wildcard patterns are allowed for ex: rk_riigiteataja_*


## Environment Variables

Every environmental variable explained in this section determines a value inside src/api/settings.py. Although most are configurable through environmental variables, some are not and can/should be changed directly if they so wish or need.

Although this section is semantically split into sub-sections, to avoid over-saturation and confusion the subsections will only have their most important variables while the other good-to-haves will be in the Miscellaneous category, the changing of which isn't illegal but I will wish you'd stub a toe against a mildly misaligned cupboard if you do.

Additionally, some of these settings can be changed on the run through the database from the api/v1/core_settings endpoint.

### Important

* RK_SECRET_KEY - Cryptographic key for Djangos several security features. Set this to something sufficiently random.
* RK_DEBUG - Whether to launch the application in DEBUG mode. Security risk to set this to true in production.
* RK_ALLOWED_HOSTS - A comma separated list of strings representing the host/domain names that this Django site can serve. This is a security measure to prevent HTTP Host header attacks, which are possible even under many seemingly-safe web server configurations. Example: rk-demo.texta.ee,riigikantselei.texta.ee. [Documentation](https://docs.djangoproject.com/en/5.0/ref/settings/#allowed-hosts).
* RK_CORS_ALLOWED_ORIGINS - A comma separated list of string origins that are authorized to make cross-site HTTP requests. The origins in this setting will be allowed. Example: https://rk-demo.texta.ee,http://riigikantselei.texta.ee:3000. [Documentation](https://github.com/adamchainz/django-cors-headers).
* RK_BASE_URL - Base domain name without trailing slash under which the application runs, used to create links for password resets etc. Example: http://rk-demo.texta.ee
* RK_ENV_FILE - Path to an .env file which the application automatically loads into its memory. Don't really need to set this unless you're running the application and its workers barebones.
* RK_DATA_DIR - Directory into which all the models are downloaded into. Don't need to touch this unless you're running the application barebones and want some finer control for model locations.
* HF_HOME - Sadly Huggingface can be incredibly annoying, demanding some of its files be cached at a folder in the /home directory, which it may not have access to.

### Elasticsearch
* RK_ELASTICSEARCH_URL - URI for where the Elasticsearch cluster is located at. Example: http://localhost:9200
* RK_ELASTICSEARCH_TIMEOUT - How many seconds until the application throws an error when connecting to Elasticsearch (Default: 10).

### OpenAI
* RK_OPENAI_API_KEY - API key to access ChatGPT.
* RK_OPENAI_API_TIMEOUT -  How many seconds until the application throws an error when connecting to ChatGPT (Default: 10)
* RK_OPENAI_API_MAX_RETRIES - How many times to retry when reaching a connection error or a rate limit (Default: 5).
* RK_OPENAI_API_CHAT_MODEL - Which OpenAI model to use (Default: gpt-4o).

* RK_DEFAULT_USAGE_LIMIT_EUROS - How much is the default spending limit for each user (Default: 50).
* RK_EURO_COST_PER_INPUT_TOKEN - Cost of input tokens per ChatGPT model as defined by OpenAI's pricetable. Made dynamic since their pricetables can change at times.
* RK_EURO_COST_PER_OUTPUT_TOKEN - Cost of output tokens per ChatGPT model as defined by OpenAI's pricetable. Made dynamic since their pricetables can change at times.

### Database
* RK_DATABASE_ENGINE - Which database engine to use. Defaults to using SQLite3. Set to django.db.backends.mysql for MySQL.
* RK_DATABASE_NAME - Name of the database to use or the filename for SQLite3 depending on the engine.
* RK_DATABASE_USER - Username to access the MySQL database.
* RK_DATABASE_PASSWORD - Password to access the MySQL database.
* RK_DATABASE_HOST - Host address at which to access the MySQL database.
* RK_DATABASE_PORT - Port at which to access the MySQL database.
* RK_DATABASE_CONN_MAX_AGE - For how long to keep open database connections in seconds (Default: 30).

### Celery
* RK_CELERY_BROKER_URL - Where to keep the task queue, for this application we use Redis (Default: redis://localhost:6379/1).
* RK_CELERY_RESULT_BACKEND - Where to keep the results of every task, for this application we use Redis (Default: redis://localhost:6379/1)
* RK_WORKERS - How many subprocesses to create for Celery, heavily dependent on system hardware, amount of cores, CPU strength etc.
* RK_MAX_TASKS - How many tasks should each subprocess make before restarting itself, good to avoid memory leaks for long running processes.

### Email
* RK_EMAIL_HOST - Host of the SMTP server.
* RK_EMAIL_PORT - Port of the SMTP server.
* RK_EMAIL_HOST_USER - Username with which to connect to the SMTP server.
* RK_DISPLAY_NAME - Which text value to display to the customer as the sender when receiving an email. Without this the sender would be set to the EMAIL_HOST_USER (example@foo.com) instead of a neat name like (Semantiline otsing).
* RK_EMAIL_HOST_PASSWORD - Password of the user we use to connect to the SMTP server.
* RK_EMAIL_TIMEOUT_IN_SECONDS - How many seconds until the attempt to send an email throws an error.
* RK_EMAIL_USE_TLS - Whether to use TLS.
* RK_EMAIL_USE_SSL - Whether to use SSL.


### Miscellaneous

* RK_ELASTICSEARCH_VECTOR_FIELD - Elasticsearch field at which we search the vectors at. Change only after dataset changes.
* RK_ELASTICSEARCH_TEXT_CONTENT_FIELD - Elasticsearch field at which we get the full text from for full previews. Change only after dataset changes.
* RK_ELASTICSEARCH_YEAR_FIELD - Elasticsearch field at which we apply date restrictions. Change only after dataset changes.
* RK_ELASTICSEARCH_URL_FIELD - Elasticsearch field which we use to point users to the original document. Change only after dataset changes.
* RK_ELASTICSEARCH_TITLE_FIELD - Elasticsearch field which value we use to display a neat reference to the user. Change only after dataset changes.
* RK_ELASTICSEARCH_PARENT_FIELD - Elasticsearch field we use to give the front end a reference to the parent document the searched segments of the references are from. Change only after dataset changes.
* RK_ELASTICSEARCH_ID_FIELD - Elasticsearch field from which we pull the id of a segment. Change only after dataset changes.


* RK_OPENAI_SYSTEM_MESSAGE - Which system message we use to give ChatGPT a personality (Default: You are a helpful assistant.)
* RK_OPENAI_MISSING_CONTEXT_MESSAGE - What text value to return to the user when ChatGPT determines that the provided context is not relevant to the question (Default: Teadmusbaasis info puudub!).
* RK_OPENAI_SOURCES_TEXT - What piece of text ChatGPT should use to present various sources for the question (Default: Allikad:)
* RK_OPENAI_OPENING_QUESTION - What question to present to ChatGPT which takes input from the users question along with context from the vector search. Setting this, the user should be aware that for any context etc to be applied {} brackets need to be set in order or have their numeric order in them. Please use the example inside the settings file.
* RK_OPENAI_API_TEMPERATURE - Which temperature to send towards ChatGPT. Lower values make responses more concise to the question while higher values allow for more creativity.
* RK_OPENAI_CONTEXT_MAX_TOKEN_LIMIT - How many tokens from the results of the vector-searched segments to send towards ChatGPT which is necessary due to token based rate limits along with a max token limit.


* RK_TIME_ZONE - Which timezone the application lives at.
* RK_LOGS_DIR - Directory under which logs are saved at.
* RK_DOWNLOAD_DATA - Whether to download the necessary models or not. Only really needed during the Docker build process. Otherwise, not needed to change as the application tries to check whether the models exist before downloading them.


* RK_CELERY_TASK_ALWAYS_EAGER - Whether to run the asynchronous tasks synchronously. Do not touch this unless you want to run the application in development.
* RK_CELERY_TIMEZONE - Which timezone Celery should use internally.
* RK_CELERY_PREFETCH_MULTIPLIER - How many tasks should be sent towards Celery workers at once to reduce communication overhead. Even if set to 1 or 0, every worker gets a task and another one waiting for the first to end.
* RK_WORKER_QUEUE - Name of the queue inside the Broker which Celery listens to.


### Known issues ###

On Windows there has been problem with conda environment for pre-commit tests hooks:
` UnicodeEncodeError: 'charmap' codec can't encode character`.
If this occurs, you may need to set system environment variable `PYTHONIOENCODING` with value `utf-8`
using this Microsoft guide:
[Saving environment variables with the System Control Panel](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables?view=powershell-7.3#saving-environment-variables-with-the-system-control-panel)
