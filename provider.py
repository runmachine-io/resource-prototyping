# functions for getting and setting information about a provider of resources

import sqlalchemy as sa

import exception
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


def increment_generation(sess, provider):
    """Increments the provider's generation, ensuring that the supplied
    provider is still at the known generation.

    :raises exception.GenerationConflict if the provider's current generation
            is different from the supplied generation, which indicates another
            thread changed the provider's state
    """
    p_tbl = resource_models.get_table('providers')

    upd = p_tbl.update().where(
        sa.and_(
            p_tbl.c.id == provider.id,
            p_tbl.c.generation == provider.generation,
        ),
    ).values(
        generation=provider.generation + 1,
    )
    res = sess.execute(upd)
    if res.rowcount != 1:
        raise exception.GenerationConflict(
            object_type='runm.provider', object_uuid=provider.uuid)

    # NOTE(jaypipes): Deliberately not commit()ing the transaction because this
    # routine is used from within a broader transaction context
