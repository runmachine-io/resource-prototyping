# Utilities that mock the runm-metadata services functionality around object
# name-uuid and lookup objects

import sqlalchemy as sa

import resource_models

_OBJECT_TYPE_MAP = None
_PROVIDER_TYPE_MAP = None


def _insert_records(tbl, recs):
    sess = resource_models.get_session()
    for rec in recs:
        ins = tbl.insert().values(**rec)
        sess.execute(ins)
    sess.commit()


def create_object_types(ctx):
    ctx.status("creating object types")
    tbl = resource_models.get_table('object_types')

    recs = [
        dict(
            code="runm.partition",
            description="A division of resources. A deployment unit for runm",
        ),
        dict(
            code="runm.provider",
            description="A provider of some resources, e.g. a compute node or "
                        "an SR-IOV NIC",
        ),
        dict(
            code="runm.provider_group",
            description="A group of providers",
        ),
        dict(
            code="runm.image",
            description="A bootable bunch of bits",
        ),
        dict(
            code="runm.machine",
            description="Created by a user, a machine consumes compute "
                        "resources from one of more providers",
        ),
    ]
    try:
        _insert_records(tbl, recs)
        ctx.status_ok()
    except Exception as err:
        ctx.status_fail(err)


def _get_object_type_map():
    """Returns a dict, keyed by object type string code, of internal object
    type ID.
    """
    global _OBJECT_TYPE_MAP
    if _OBJECT_TYPE_MAP is not None:
        return _OBJECT_TYPE_MAP
    tbl = resource_models.get_table('object_types')
    sel = sa.select([tbl.c.id, tbl.c.code])
    sess = resource_models.get_session()
    _OBJECT_TYPE_MAP = {r[1]: r[0] for r in sess.execute(sel)}
    return _OBJECT_TYPE_MAP


def create_object(sess, obj_type, uuid, name):
    """Adds a new name-uuid pair to the object_names table."""
    obj_tbl = resource_models.get_table('object_names')
    object_type_id = _get_object_type_map()[obj_type]

    obj_rec = dict(
        object_type=object_type_id,
        uuid=uuid,
        name=name,
    )
    ins = obj_tbl.insert().values(**obj_rec)
    sess.execute(ins)
