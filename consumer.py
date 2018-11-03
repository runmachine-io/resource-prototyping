# functions for getting and setting information about a consumer of resources

import sqlalchemy as sa

import db
import lookup
import metadata
import models


def create_if_not_exists(sess, consumer):
    """Creates a record of the supplied consumer in the database and sets the
    consumer's internal id attribute.
    """
    if consumer.id is not None:
        return

    c_tbl = db.get_table('consumers')

    cols = [
        c_tbl.c.id,
        c_tbl.c.uuid,
        c_tbl.c.owner_project_uuid,
        c_tbl.c.owner_user_uuid,
    ]
    sel = sa.select(cols).where(c_tbl.c.uuid == consumer.uuid)

    res = sess.execute(sel).fetchone()
    if not res:
        metadata.create_object(
            sess, 'runm.machine', consumer.uuid, consumer.name)

        type_id = lookup.consumer_type_id_from_code('runm.machine')
        ins = c_tbl.insert().values(
            uuid=consumer.uuid,
            type_id=type_id,
            owner_project_uuid=consumer.project,
            owner_user_uuid=consumer.user,
            generation=1,
        )
        res = sess.execute(ins)
        if res.rowcount == 1:
            c_id = res.inserted_primary_key[0]
            consumer.id = c_id
        # NOTE(jaypipes): Deliberately not committing, as this is done as part
        # of the overall claim execution transaction.
    else:
        consumer.id = res['id']
