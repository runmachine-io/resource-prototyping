# Simple functions for getting heavily-cached simple lookups for type/class
# information

import sqlalchemy as sa

import db
import metadata
import models

_PROVIDER_TYPE_MAP = None
_CONSUMER_TYPE_MAP = None
_RESOURCE_TYPE_MAP = None
_CAPABILITIES_MAP = None

def _get_provider_type_map():
    """Returns a dict, keyed by provider type string code, of internal provider
    type ID.
    """
    global _PROVIDER_TYPE_MAP
    if _PROVIDER_TYPE_MAP is not None:
        return _PROVIDER_TYPE_MAP
    tbl = db.get_table('provider_types')
    sel = sa.select([tbl.c.id, tbl.c.code])
    sess = db.get_session()
    _PROVIDER_TYPE_MAP = {r[1]: r[0] for r in sess.execute(sel)}
    return _PROVIDER_TYPE_MAP


def provider_type_id_from_code(code):
    return _get_provider_type_map()[code]


def _get_consumer_type_map():
    """Returns a dict, keyed by consumer type string code, of internal consumer
    type ID.
    """
    global _CONSUMER_TYPE_MAP
    if _CONSUMER_TYPE_MAP is not None:
        return _CONSUMER_TYPE_MAP
    tbl = db.get_table('consumer_types')
    sel = sa.select([tbl.c.id, tbl.c.code])
    sess = db.get_session()
    _CONSUMER_TYPE_MAP = {r[1]: r[0] for r in sess.execute(sel)}
    return _CONSUMER_TYPE_MAP


def consumer_type_id_from_code(code):
    return _get_consumer_type_map()[code]


def _get_resource_type_map():
    """Returns a dict, keyed by resource type string code, of internal resource
    type ID.
    """
    global _RESOURCE_TYPE_MAP
    if _RESOURCE_TYPE_MAP is not None:
        return _RESOURCE_TYPE_MAP
    tbl = db.get_table('resource_types')
    sel = sa.select([tbl.c.id, tbl.c.code])
    sess = db.get_session()
    _RESOURCE_TYPE_MAP = {r[1]: r[0] for r in sess.execute(sel)}
    return _RESOURCE_TYPE_MAP


def resource_type_id_from_code(code):
    return _get_resource_type_map()[code]


def _get_capability_map():
    """Returns a dict, keyed by capability string code, of internal capability
    ID.
    """
    global _CAPABILITIES_MAP
    if _CAPABILITIES_MAP is not None:
        return _CAPABILITIES_MAP
    tbl = db.get_table('capabilities')
    sel = sa.select([tbl.c.id, tbl.c.code])
    sess = db.get_session()
    _CAPABILITIES_MAP = {r[1]: r[0] for r in sess.execute(sel)}
    return _CAPABILITIES_MAP


def capability_id_from_code(code):
    return _get_capability_map()[code]
