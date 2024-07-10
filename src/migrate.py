#! /usr/bin/env python3
import argparse
import logging
import os
import uuid
from time import sleep

import django

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-u', '--username', help='Name of the admin user to create.', default='admin')
parser.add_argument(
    '-o',
    '--overwrite',
    action='store_true',
    help="Whether to overwrite the admin users password with what's set in 'TEXTA_ADMIN_PASSWORD'",
)
parser.set_defaults(overwrite=False)
args = parser.parse_args()

# Initialize django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()

# Import User object (this required the settings initialization)
# pylint: disable=import-outside-toplevel,wrong-import-position
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


# Get admin password from env
ADMIN_PASSWORD = os.getenv('RK_ADMIN_PASSWORD', uuid.uuid4().hex)


def create_admin(arguments: argparse.Namespace) -> bool:
    user, is_freshly_created = User.objects.get_or_create(username=arguments.username)
    user.is_superuser = True
    user.is_staff = True
    # Add profile configuration
    user.user_profile.is_manager = True
    user.user_profile.is_reviewed = True
    user.user_profile.is_accepted = True
    user.user_profile.is_allowed_to_spend_resources = True
    user.user_profile.save()

    # did we just create admin user?
    if is_freshly_created:
        user.set_password(ADMIN_PASSWORD)
        log_message = f'RK API: Admin user password is: {ADMIN_PASSWORD}'
        logger.info(log_message)
    # overwrite admin password if asked
    if arguments.overwrite and is_freshly_created is False:
        password = os.getenv('RK_ADMIN_PASSWORD', None)
        if password:
            user.set_password(password)
            log_message = f'RK API: New admin user password is: {password}'
            logger.info(log_message)
        else:
            log_message = 'RK API: No password was set inside RK_ADMIN_PASSWORD'
            logger.info(log_message)
    # save admin user object
    user.save()
    return is_freshly_created


def check_mysql_connection() -> bool:
    db_conn = django.db.connections['default']
    try:
        db_conn.cursor()
    except django.db.utils.OperationalError:
        connected = False
    else:
        connected = True
    return connected


def migrate(arguments: argparse.Namespace) -> bool:
    log_message = 'RK API: Applying existing migrations.'
    logger.info(log_message)
    sleep(2)
    django.core.management.call_command('migrate', verbosity=3)
    log_message = 'RK API: Creating Admin user if necessary.'
    logger.info(log_message)
    sleep(2)
    result = create_admin(arguments)
    log_message = f'RK API: Admin created: {result}'
    logger.info(log_message)
    return True


# CONNECT TO DATABASE & MIGRATE
CONNECTED = False

N_TRY = 0
while CONNECTED is False and N_TRY <= 10:
    CONNECTED = check_mysql_connection()
    if CONNECTED:
        migrate(args)
    else:
        N_TRY += 1
        log_msg = f'RK API attempt {N_TRY}: No connection to database. Sleeping for 10 sec...'
        logger.info(log_msg)
        sleep(10)
