#!/bin/bash

# Worker concurrency defaults.
export RK_WORKERS="${RK_WORKERS:-2}"

echo "Setting application permissions..."

# Data dir permissions to www-data
chown www-data:www-data -R /var/data/ && chmod 775 -R /var/data/
chown www-data:www-data -R /var/rk_api/ && chmod 775 -R /var/rk_api/

# Nginx permissions
chown www-data:www-data -R /opt/conda/envs/riigikantselei/var \
    && chmod 775 -R /opt/conda/envs/riigikantselei/var

# ACTIVATE & MIGRATE
source activate riigikantselei

echo "Migrating application..."

python migrate.py -o

# prepare front conf file
python create_front_config.py --path "/var/rk_api/front/assets/config/config.json"

exec "$@"
