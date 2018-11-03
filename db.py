# Base model objects for resource database

import os

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

_TABLE_NAMES = (
    'allocation_items',
    'allocations',
    'capabilities',
    'consumer_types',
    'consumers',
    'distance_types',
    'distances',
    'inventories',
    'object_names',
    'object_types',
    'partitions',
    'provider_capabilities',
    'provider_distances',
    'provider_group_members',
    'provider_groups',
    'provider_trees',
    'provider_types',
    'providers',
    'resource_types',
)
_TABLES = {}


def get_engine():
    db_user = os.environ.get('RUNM_TEST_RESOURCE_DB_USER', 'root')
    db_pass = os.environ.get('RUNM_TEST_RESOURCE_DB_PASS', '')
    db_uri = 'mysql+pymysql://{0}:{1}@localhost/test_resources'
    db_uri = db_uri.format(db_user, db_pass)
    return sa.create_engine(db_uri)


def get_session():
    engine = get_engine()
    sess = sessionmaker(bind=engine)
    return sess()


def load_tables():
    if _TABLES:
        return

    engine = get_engine()
    meta = sa.MetaData(engine)
    for tbl_name in _TABLE_NAMES:
        _TABLES[tbl_name] = sa.Table(tbl_name, meta, autoload=True)


def get_table(tbl_name):
    load_tables()
    return _TABLES[tbl_name]
