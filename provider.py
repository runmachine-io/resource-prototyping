# functions for getting and setting information about a provider of resources

import sqlalchemy as sa

import resource_models


def providers_by_uuids(uuids):
    """Returns a dict, keyed by provider UUID, of Provider objects having one
    of the supplied UUIDs
    """
    p_tbl = resource_models.get_table('providers')
    cols = [
        p_tbl.c.id,
        p_tbl.c.uuid,
        p_tbl.c.generation,
    ]
    sel = sa.select(cols).where(p_tbl.c.uuid.in_(uuids))
    sess = resource_models.get_session()
    return {
        r[0]: resource_models.Provider(
            id=r[0],
            uuid=r[1],
            generation=r[2],
        ) for r in sess.execute(sel)
    }
