# Functions that simulate the claim and placement processes

import sqlalchemy as sa
from sqlalchemy import func

import consumer
import exception
import lookup
import metadata
import provider
import resource_models

UNLIMITED = -1


class ResourceConstraint(object):
    def __init__(self, resource_type, min_amount, max_amount,
                 capability_constraint=None):
        self.resource_type = resource_type
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.capability_constraint = capability_constraint

    def __repr__(self):
        return (
            "ResourceConstraint(resource_type=%s,min_amount=%d,"
            "max_amount=%d,capabilities=%s)" % (
                self.resource_type,
                self.min_amount,
                self.max_amount,
                self.capability_constraint,
            )
        )


class CapabilityConstraint(object):
    def __init__(self, require_caps=None, forbid_caps=None, any_caps=None):
        self.require_caps = require_caps
        self.forbid_caps = forbid_caps
        self.any_caps = any_caps

    def __repr__(self):
        return "CapabilityConstraint(require=%s,forbid=%s,any=%s)" % (
            self.require_caps, self.forbid_caps, self.any_caps,
        )


class ProviderGroupConstraint(object):
    def __init__(self, require_groups, forbid_groups, any_groups):
        self.require_groups = require_groups
        self.forbid_groups = forbid_groups
        self.any_groups = any_groups


class DistanceConstraint(object):
    def __init__(self, provider, minimum=None, maximum=None):
        self.provider = provider
        self.minimum = minimum
        self.maximum = maximum


class ClaimRequestGroupOptions(object):
    def __init__(self, single_provider=True, isolate_from=None):
        self.single_provider = single_provider
        self.isolate_from = isolate_from


class ClaimRequestGroup(object):
    def __init__(self, options=None, resource_constraints=None,
            capability_constraints=None, provider_group_constraints=None,
            distance_constraints=None):
        self.options = options or ClaimRequestGroupOptions()
        self.resource_constraints = resource_constraints
        self.capability_constraints = capability_constraints
        self.provider_group_constraints = provider_group_constraints
        self.distance_constraints = distance_constraints


class ClaimRequest(object):
    def __init__(self, consumer, request_groups, acquire_time=None,
            release_time=None):
        self.consumer = consumer
        self.request_groups = request_groups
        self.acquire_time = acquire_time
        self.release_time = release_time


class Claim(object):
    def __init__(self, acquire_time, release_time, allocation_items,
            alloc_item_group_map):
        self.acquire_time = acquire_time
        self.release_time = release_time
        self.allocation_items = allocation_items
        self.allocation_item_to_request_groups = alloc_item_group_map

    def __repr__(self):
        return "Claim(allocation_items=%s)" % self.allocation_items


def process_claim_request(ctx, claim_request):
    """Given a claim request object, ask the resource database to construct
    Claim objects that meet the request's constraints.

    :param ctx: the RunContext object
    :param claim_request: the ClaimRequest object
    """
    alloc_items = []
    item_to_group_map = {}
    item_index = 0
    for group_index in range(len(claim_request.request_groups)):
        group_alloc_items = _process_claim_request_group(
            ctx, claim_request, group_index)
        for _ in range(len(group_alloc_items)):
            item_to_group_map[item_index] = group_index
            item_index += 1
        alloc_items.extend(group_alloc_items)
    return [
        Claim(
            claim_request.acquire_time,
            claim_request.release_time,
            alloc_items,
            item_to_group_map,
        ),
    ]


class MatchContext(object):
    """An object that is passed to matching functions to keep state during the
    constraint solving process.
    """

    def __init__(self, claim_request, group_index):
        self.claim_request = claim_request

        # The first time the matches dict is updated with a set of filtered
        # providers, this is set to True
        self.started_filtering = False

        # The ClaimRequestGroup being tracked
        self.request_group = claim_request.request_groups[group_index]

        # dict, keyd by internal provider ID, of provider UUIDs that have
        # matched all of the applied filters from constraints contained in the
        # request group
        self.matches = {}

        # dict, keyed by internal provider ID, of provider UUIDs that matched
        # an "exclusion filter" in a constraint and must be excluded when
        # considering other constraints in the request group.
        self.exclude = {}

    def match_or(self, new_matches):
        """If the matching has begun, updates the match context's matching
        provider dict with the supplied matches using a set union. If
        matching has not begun, sets the match context's matching provider dict
        to the supplied matches.

        Returns True if there are any matches after the operation, False
        otherwise.
        """
        if self.started_filtering:
            self.matches.update(new_matches)
        else:
            self.matches = new_matches
            self.started_filtering = True
        return len(self.matches) > 0

    def match_and(self, new_matches):
        """If the matching has begun, updates the match context's matching
        provider dict with the supplied matches using a set intersection. If
        matching has not begun, sets the match context's matching provider dict
        to the supplied matches.

        Returns True if there are any matches after the operation, False
        otherwise.
        """
        if self.started_filtering:
            in_both = set(self.matches) & set(new_matches)
            self.matches = {
                k: v for k, v in self.matches.items()
                if k in in_both
            }
        else:
            self.matches = new_matches
            self.started_filtering = True
        return len(self.matches) > 0

    def exclude_or(self, new_exclude):
        """Updates the context's dict of to-be-excluded provider information
        with a supplied dict, keyed by internal provider ID, of provider UUIDs
        to exclude.
        """
        self.exclude.update(new_exclude)


def _process_claim_request_group(ctx, claim_request, group_index):
    """Given an index to a single claim request group, returns a list of
    AllocationItem objects that would be satisfied by the request group after
    determining the providers matching the request group's constraints.
    """
    mctx = MatchContext(claim_request, group_index)

    # First thing we do is limit to the providers that match the request
    # group's general capabilities constraints. Note that there may be
    # capabilities constraints on individual resources involved in a resource
    # constraint. Those are applied while satisfying a resource constraint
    # itself.
    if not _process_capability_constraints(ctx, mctx):
        return []

    # Then find the providers that have the capacity for one or more resource
    # constraints
    if not _process_resource_constraints(ctx, mctx):
        return []

    alloc_items = []

    # Now add an allocation item for the first provider that is in the
    # matches set for each resource type in the constraint
    chosen_id = iter(mctx.matches).next()
    chosen = resource_models.Provider(
        id=chosen_id,
        uuid=mctx.matches[chosen_id],
    )
    for rc_constraint in mctx.request_group.resource_constraints:
        # Add the first provider supplying this resource type to our
        # allocation
        alloc_item = resource_models.AllocationItem(
            resource_type=rc_constraint.resource_type,
            provider=chosen,
            used=rc_constraint.max_amount,
        )
        alloc_items.append(alloc_item)
    return alloc_items


def _process_capability_constraints(ctx, mctx):
    """Returns True if the capability constraints in the request group could be
    satisfied by one or more providers, False otherwise.

    Returns True if there were no capability constraints on the request group.

    :param ctx: RunContext
    :param mctx: MatchContext
    """
    if not mctx.request_group.capability_constraints:
        return True

    for cap_constraint in mctx.request_group.capability_constraints:
        if not any([
                cap_constraint.require_caps,
                cap_constraint.forbid_caps,
                cap_constraint.any_caps]):
            continue

        res = _providers_matching_capability_constraint(ctx, cap_constraint)
        if res == NoMatches:
            print "No matching providers for capability constraint %s" % (
                cap_constraint
            )
            return False
        elif res == NoExclude:
            # Constraint only contained exclusion filters (forbid) and there
            # were no providers matching those forbidden capabilities, so just
            # continue
            continue

        if res.exclude:
            # Make sure we save providers that were marked for exclusion by a
            # previous constraint pass. When we exit out of this funtion and
            # perform resource constraints, we will need to pass the providers
            # that should be excluded from consideration by the resource
            # constraints
            mctx.exclude_or(res.exclude)

        if res.matches:
            # Within a claim request group, the list of capability constraint
            # objects is OR'd together.
            mctx.match_or(res.matches)

    return True


class ConstraintMatchResult(object):
    """Describes the matches and anti-matches (exclusion filters) that were
    determined for a constraint.
    """
    def __init__(self):
        # dict, keyed by internal provider ID, of provider UUIDs that matched
        # one of the positive filters in the constraint
        self.matches = {}

        # dict, keyed by internal provider Id, of provider UUIDs that should be
        # excluded from matches in other constraints. These are the providers
        # that matched a "forbid" constraint (an exclusion filter).
        #
        # No providers in 'excludes' shall exist in 'matches', as these are
        # fully disjoint sets.
        self.exclude = {}

# A singleton ConstraintMatch used to signal that the constraint contained
# either 'require' or 'any' constraint specifiers but that no matching
# providers could be found. This is a negative match and will prevent the
# matching process from proceeding any further.
NoMatches = ConstraintMatchResult()
# A singleton ConstraintMatch used to signal that the constraint only contained
# exclusion filters (forbid specs) and there were no matches on these exclusion
# filters. So, unlike NoMatches, this is a positive match that won't prevent
# the matching process from proceeding further.
NoExclude = ConstraintMatchResult()


def _providers_matching_capability_constraint(ctx, cap_constraint):
    """Returns a ConstraintMatch that describes the providers having the
    required, forbidden or any capabilities in supplied capability constraint.
    """
    res = ConstraintMatchResult()
    # A hashmap of provider internal ID to provider object for providers
    cap_providers = {}
    # The set of provider internal ID, that have been matched for previous
    # iterations of constraints
    matched_provs = set()
    if cap_constraint.require_caps:
        required_caps = cap_constraint.require_caps
        providers = _find_providers_with_all_caps(ctx, required_caps)
        if not providers:
            ctx.info(
                "failed to find provider with required caps %s",
                required_caps,
            )
            return NoMatches

        ctx.info(
            "found %d providers with required caps %s",
            len(providers),
            required_caps,
        )
        cap_provider_ids = set(providers)
        matched_provs = cap_provider_ids
        cap_providers.update(providers)

    if cap_constraint.any_caps:
        any_caps = cap_constraint.any_caps
        providers = _find_providers_with_any_caps(ctx, any_caps)
        if not providers:
            ctx.info(
                "failed to find provider with any caps %s",
                any_caps,
            )
            return NoMatches

        ctx.info(
            "found %d providers with any caps %s",
            len(providers),
            any_caps,
        )
        cap_provider_ids = set(providers)
        if matched_provs:
            matched_provs &= cap_provider_ids
            if not matched_provs:
                return NoMatches
        else:
            matched_provs = cap_provider_ids
        cap_providers.update(providers)

    if cap_constraint.forbid_caps:
        forbid_caps = cap_constraint.forbid_caps
        # Because we pass excludes on to other iterations and constraints, we
        # cannot limit the number of excluded providers that match...
        providers = _find_providers_with_any_caps(
            ctx, forbid_caps, limit=UNLIMITED)
        if providers:
            ctx.info(
                "excluding %d providers with forbidden caps %s",
                len(providers),
                forbid_caps,
            )
            cap_provider_ids = set(providers)
            if matched_provs:
                # Remove previously matched providers that have a forbidden
                # capability
                matched_provs -= cap_provider_ids
                if not matched_provs:
                    return NoMatches
            else:
                res.excludes = providers
        else:
            # If we matched no providers having forbidden capabilities, AND
            # this constraint specified no required or any capabilities, then
            # return NoExclude to indicate that there was actually a positive
            # result from the constraint matching.
            if not cap_constraint.require_caps and not cap_constraint.any_caps:
                ctx.info(
                    "found 0 providers matching %s."
                    "\n\t(constraint only contains a forbid section "
                    "and no matches were found for those forbidden "
                    "capabilities)",
                    cap_constraint,
                )
                return NoExclude

    res.matches = {
        k: v for k, v in cap_providers.items() if k in matched_provs
    }
    return res


def _process_resource_constraints(ctx, mctx):
    """Returns a dict, keyed by internal provider ID, of providers that have
    capacity for ALL resources listed in the supplied claim request group.

    Returns True if the constraints were able to be satisfied, False otherwise

    :param ctx: RunContext
    :param mctx: MatchContext
    """
    for rc_constraint in mctx.request_group.resource_constraints:
        providers = _find_providers_with_resource(
            ctx,
            mctx.claim_request.acquire_time,
            mctx.claim_request.release_time,
            rc_constraint,
            exclude=mctx.exclude,
        )
        if not mctx.match_and(providers):
            ctx.info("failed to find provider matching %s", rc_constraint)
            return False

        ctx.info(
            "found %d providers matching %s",
            len(providers),
            rc_constraint,
        )

    return True


def _cap_id_from_code(ctx, cap):
    cap_tbl = resource_models.get_table('capabilities')
    sel = sa.select([cap_tbl.c.id]).where(cap_tbl.c.code == cap)

    sess = resource_models.get_session()
    res = sess.execute(sel).fetchone()
    if not res:
        raise ValueError("Could not find ID for capability %s" % cap)
    return res[0]


def _find_providers_with_all_caps(ctx, caps, limit=50):
    """Returns providers that have all of the supplied capabilities.

    The SQL that is generated looks like this:

    SELECT p.id, p.uuid
    FROM providers AS p
    JOIN provider_capabilities AS pc
      ON p.id = pc.provider_id
    WHERE pc.capability_id IN ($CAPABILITIES)
    GROUP BY p.id
    HAVING COUNT(pc.capability_id) == $NUM_CAPABILITIES
    """
    p_tbl = resource_models.get_table('providers')
    p_caps_tbl = resource_models.get_table('provider_capabilities')

    cap_ids = [
        _cap_id_from_code(ctx, cap) for cap in caps
    ]

    p_to_p_caps = sa.join(
        p_tbl, p_caps_tbl,
        p_tbl.c.id == p_caps_tbl.c.provider_id,
    )
    cols = [
        p_tbl.c.id,
        p_tbl.c.uuid,
    ]
    sel = sa.select(cols).select_from(
        p_to_p_caps
    ).where(
        p_caps_tbl.c.capability_id.in_(cap_ids)
    ).group_by(
        p_caps_tbl.c.provider_id
    ).having(
        func.count(p_caps_tbl.c.capability_id) == len(caps)
    )
    if limit != UNLIMITED:
        sel = sel.limit(limit)
    sess = resource_models.get_session()
    return {
        r[0]: r[1] for r in sess.execute(sel)
    }


def _find_providers_with_any_caps(ctx, caps, limit=50):
    """Returns providers that have any of the supplied capabilities.

    The SQL that is generated looks like this:

    SELECT p.id, p.uuid
    FROM providers AS p
    JOIN provider_capabilities AS pc
      ON p.id = pc.provider_id
    WHERE pc.capability_id IN ($CAPABILITIES)
    """
    p_tbl = resource_models.get_table('providers')
    p_caps_tbl = resource_models.get_table('provider_capabilities')

    cap_ids = [
        _cap_id_from_code(ctx, cap) for cap in caps
    ]

    p_to_p_caps = sa.join(
        p_tbl, p_caps_tbl,
        p_tbl.c.id == p_caps_tbl.c.provider_id,
    )
    cols = [
        p_tbl.c.id,
        p_tbl.c.uuid,
    ]
    sel = sa.select(cols).select_from(
        p_to_p_caps
    ).where(
        p_caps_tbl.c.capability_id.in_(cap_ids)
    )
    if limit != UNLIMITED:
        sel = sel.limit(limit)
    sess = resource_models.get_session()
    return {
        r[0]: r[1] for r in sess.execute(sel)
    }


def _rt_id_from_code(sess, resource_type):
    rc_tbl = resource_models.get_table('resource_types')
    sel = sa.select([rc_tbl.c.id]).where(rc_tbl.c.code == resource_type)

    res = sess.execute(sel).fetchone()
    if not res:
        raise ValueError("Could not find ID for resource type %s" %
                         resource_type)
    return res[0]


def _find_providers_with_resource(ctx, acquire_time, release_time,
        resource_constraint, exclude=None, limit=50):
    """Queries for providers that have capacity for the requested amount of a
    resource type and optionally meet resource-specific capability
    constraints. The query is done in a claim start/end window.

    The SQL generated for a resource constraint without the optional capability
    constraint ends up looking like this:

    SELECT p.id, p.uuid
    FROM providers AS p
    JOIN inventories AS i
      ON p.id = i.provider_id
    LEFT JOIN (
      SELECT ai.provider_id, SUM(ai.used) AS total_used
      FROM allocation_items AS ai
      JOIN (
        SELECT id AS allocation_id
        FROM allocations
        WHERE acquire_time >= $CLAIM_START
        AND release_time < $CLAIM_END
        GROUP BY id
      ) AS allocs_in_window
        ON ai.allocation_id = allocs_in_window
      WHERE ai.resource_type_id = $RESOURCE_TYPE
      GROUP BY ai.provider_id
    ) AS usages
      ON i.provider_id = usages.provider_id
    WHERE i.resource_type_id = $RESOURCE_TYPE
    AND ((i.total - i.reserved) * i.allocation_ratio) >=
         $RESOURCE_REQUEST_AMOUNT + COALESCE(usages.used, 0))
    AND i.min_unit <= $RESOURCE_REQUEST_AMOUNT
    AND i.max_unit >= $RESOURCE_REQUEST_AMOUNT
    AND $RESOURCE_REQUEST_AMOUNT % i.step_size = 0

    If the optional `exclude` argument is provided, we tack on a:

    WHERE p.id NOT IN ($EXCLUDE)

    clause. The `exclude` argument is populated when the capabilities
    constraints that may have been previously processed identified some
    providers that should be excluded (they met an "exclusion filter" -- i.e.
    they matched for a 'forbid' specification in a constraint).
    """
    p_tbl = resource_models.get_table('providers')
    inv_tbl = resource_models.get_table('inventories')
    alloc_tbl = resource_models.get_table('allocations')
    alloc_item_tbl = resource_models.get_table('allocation_items')

    sess = resource_models.get_session()

    rt_id = _rt_id_from_code(sess, resource_constraint.resource_type)
    alloc_window_cols = [
        alloc_tbl.c.id.label('allocation_id'),
    ]
    allocs_in_window_subq = sa.select(alloc_window_cols).where(
        sa.and_(
            alloc_tbl.c.acquire_time >= acquire_time,
            alloc_tbl.c.release_time < release_time,
        )
    ).group_by(alloc_tbl.c.id)
    allocs_in_window_subq = sa.alias(allocs_in_window_subq, "allocs_in_window")
    usage_cols = [
        alloc_item_tbl.c.provider_id,
        func.sum(alloc_item_tbl.c.used).label('total_used'),
    ]
    alloc_item_to_alloc_window = sa.outerjoin(
        alloc_item_tbl, allocs_in_window_subq,
        alloc_item_tbl.c.allocation_id == allocs_in_window_subq.c.allocation_id
    )
    usage_subq = sa.select(usage_cols).select_from(
        alloc_item_to_alloc_window
    ).where(
        alloc_item_tbl.c.resource_type_id == rt_id
    ).group_by(
        alloc_item_tbl.c.provider_id
    )
    usage_subq = sa.alias(usage_subq, "usages")

    join_to = p_tbl
    if resource_constraint.capability_constraint:
        cap_constraint = resource_constraint.capability_constraint
        join_to = _select_add_capability_constraint(ctx, p_tbl, cap_constraint)

    p_to_inv = sa.join(
        join_to, inv_tbl,
        sa.and_(
            p_tbl.c.id == inv_tbl.c.provider_id,
            inv_tbl.c.resource_type_id == rt_id,
        )
    )
    inv_to_usage = sa.outerjoin(
        p_to_inv, usage_subq,
        inv_tbl.c.provider_id == usage_subq.c.provider_id
    )
    cols = [
        p_tbl.c.id,
        p_tbl.c.uuid,
    ]
    sel = sa.select(cols).select_from(
        inv_to_usage
    ).where(
        sa.and_(
            inv_tbl.c.resource_type_id == rt_id,
            ((inv_tbl.c.total - inv_tbl.c.reserved)
                * inv_tbl.c.allocation_ratio)
            >= (resource_constraint.max_amount + func.coalesce(usage_subq.c.total_used, 0)),
            inv_tbl.c.min_unit <= resource_constraint.max_amount,
            inv_tbl.c.max_unit >= resource_constraint.max_amount,
            resource_constraint.max_amount % inv_tbl.c.step_size == 0,
        )
    )
    if exclude:
        sel = sel.where(~p_tbl.c.id.in_(set(exclude)))
    if limit != UNLIMITED:
        sel = sel.limit(limit)
    return {
        r[0]: r[1] for r in sess.execute(sel)
    }


def _select_add_capability_constraint(ctx, relation, constraint):
    """Adds the following expression to the supplied SELECT statement:

    if "any" is in the constraint or if there's only one cap in "require":

        JOIN provider_capabilities AS pc
        ON providers.id = pc.provider_id
        AND pc.capability_id IN ($ANY_CAPS)

    if "require" is in the constraint and there's >1 required cap:

        JOIN (
            SELECT pc.provider_id, COUNT(*) AS num_caps
            FROM provider_capabilities AS pc
            GROUP BY pc.provider_id
            HAVING COUNT(*) = $NUM_REQUIRE_CAPS
        ) AS provs_having_all
        ON providers.id = provs_having_all.provider_id

    if "forbid" is in the constraint:

        JOIN provider_capabilities AS pc
        ON providers.id = pc.provider_id
        AND pc.capability_id NOT IN ($FORBID_CAPS)

    """
    p_tbl = resource_models.get_table('providers')
    p_caps_tbl = resource_models.get_table('provider_capabilities')
    p_caps_tbl = sa.alias(p_caps_tbl, name='pc')
    if constraint.require_caps:
        if len(constraint.require_caps) == 1:
            cap_id = _cap_id_from_code(ctx, constraint.require_caps[0])
            # Just join to placement_capabilities and be done with it. No need
            # to get more complicated than that.
            relation = sa.join(
                p_tbl, p_caps_tbl,
                sa.and_(
                    p_tbl.c.id == p_caps_tbl.c.provider_id,
                    p_caps_tbl.c.capability_id == cap_id
                )
            )
        else:
            # This is the complicated bit. We join to a derived table
            # representing the providers that have ALL of the required
            # capabilities.
            require_cap_ids = [
                _cap_id_from_code(ctx, cap) for cap in constraint.require_caps
            ]
            cols = [
                p_caps_tbl.c.provider_id,
                func.count(p_caps_tbl.c.capability_id).label('num_caps')
            ]
            derived = sa.select(cols).group_by(
                p_caps_tbl.c.provider_id
            ).where(
                p_caps_tbl.c.capability_id.in_(require_cap_ids)
            ).having(
                func.count(p_caps_tbl.c.capability_id) == len(require_cap_ids)
            )
            relation = sa.join(
                p_tbl, derived,
                p_tbl.c.id == derived.c.provider_id,
            )
    if constraint.forbid_caps or constraint.any_caps:
        conds = [
            p_tbl.c.id == p_caps.c.provider_id,
        ]
        if constraint.forbid_caps:
            forbid_cap_ids = [
                _cap_id_from_code(ctx, cap) for cap in constraint.forbid_caps
            ]
            conds.append(
                ~p_caps_tbl.c.capability_id.in_(forbid_cap_ds)
            )
        if constraint.any_caps:
            any_cap_ids = [
                _cap_id_from_code(ctx, cap) for cap in constraint.any_caps
            ]
            conds.append(
                p_caps_tbl.c.capability_id.in_(any_cap_ds)
            )
        relation = sa.join(
            relation, p_caps_tbl,
            sa.and_(conds),
        )
    return relation


def _create_allocation(sess, consumer, claim):
    """Creates the primary allocation table record and returns the internal ID
    of the created allocation.
    """
    alloc_tbl = resource_models.get_table('allocations')

    ins = alloc_tbl.insert().values(
        consumer_id=consumer.id,
        acquire_time=claim.acquire_time,
        release_time=claim.release_time,
    )
    res = sess.execute(ins)
    if res.rowcount != 1:
        raise Exception(
            "Expected to write a single row for allocation. Wrote %d rows" %
            res.rowcount)
    # NOTE(jaypipes): Deliberately not committing, as this is done as part of
    # the overall claim execution transaction.
    return res.inserted_primary_key[0]


class Usage(object):
    def __init__(self, total, reserved, min_unit, max_unit, step_size,
        allocation_ratio, total_used):
        self.total = total
        self.reserved = reserved
        self.min_unit = min_unit
        self.max_unit = max_unit
        self.step_size = step_size
        self.allocation_ratio = allocation_ratio
        self.total_used = total_used


class ProviderUsages(object):
    def __init__(self, provider):
        self.provider = provider
        # usages is a dict, keyed by resource type internal ID, of Usage
        # objects
        self.usages = {}


def _check_provider_capacity(sess, claim_obj):
    """Verifies that providers have capacity for all resources listed in the
    supplied Claim object's list of allocations and returns a dict, keyed by
    provider UUID, of Provider objects that include the provider's generation
    at the time of the capacity check.
    """
    p_ids = set(
       alloc_item.provider.id for alloc_item in claim_obj.allocation_items
    )

    rt_ids = set(
        _rt_id_from_code(sess, alloc_item.resource_type)
        for alloc_item in claim_obj.allocation_items
    )

    # The SQL we generate here looks like this:
    #
    # SELECT
    #  p.id AS provider_id,
    #  p.uuid AS provider_uuid,
    #  p.generation AS provider_generation,
    #  i.resource_type_id,
    #  i.total,
    #  i.reserved,
    #  i.min_unit,
    #  i.max_unit,
    #  i.step_size,
    #  i.allocation_ratio,
    #  usages.total_used
    # FROM providers AS p
    # JOIN inventories AS i
    #   ON p.id = i.provider_id
    # LEFT JOIN (
    #   SELECT ai.provider_id, ai.resource_type_id, SUM(ai.used) AS total_used
    #   FROM allocation_items AS ai
    #   JOIN (
    #     SELECT id AS allocation_id
    #     FROM allocations
    #     WHERE acquire_time >= $CLAIM_START
    #     AND release_time < $CLAIM_END
    #     GROUP BY id
    #   ) AS allocs_in_window
    #     ON ai.allocation_id = allocs_in_window
    #   WHERE ai.resource_type_id = $RESOURCE_TYPE
    #   AND ai.provider_id IN ($PROVIDER_IDS)
    #   GROUP BY ai.provider_id, ai.resource_type_id
    # ) AS usages
    #   ON i.provider_id = usages.provider_id
    #   AND i.resource_type_id = usages.resource_type_id
    # WHERE i.resource_type_id IN ($RESOURCE_TYPES)
    # AND p.id IN ($PROVIDER_IDS)

    p_tbl = resource_models.get_table('providers')
    inv_tbl = resource_models.get_table('inventories')
    alloc_tbl = resource_models.get_table('allocations')
    alloc_item_tbl = resource_models.get_table('allocation_items')

    alloc_window_cols = [
        alloc_tbl.c.id.label('allocation_id'),
    ]
    allocs_in_window_subq = sa.select(alloc_window_cols).where(
        sa.and_(
            alloc_tbl.c.acquire_time >= claim_obj.acquire_time,
            alloc_tbl.c.release_time < claim_obj.release_time,
        )
    ).group_by(alloc_tbl.c.id)
    allocs_in_window_subq = sa.alias(allocs_in_window_subq, "allocs_in_window")
    usage_cols = [
        alloc_item_tbl.c.provider_id,
        alloc_item_tbl.c.resource_type_id,
        func.sum(alloc_item_tbl.c.used).label('total_used'),
    ]
    alloc_item_to_alloc_window = sa.outerjoin(
        alloc_item_tbl, allocs_in_window_subq,
        alloc_item_tbl.c.allocation_id == allocs_in_window_subq.c.allocation_id
    )
    usage_subq = sa.select(usage_cols).select_from(
        alloc_item_to_alloc_window
    ).where(
        sa.and_(
            alloc_item_tbl.c.resource_type_id.in_(rt_ids),
            alloc_item_tbl.c.provider_id.in_(p_ids)
        ),
    ).group_by(
        alloc_item_tbl.c.provider_id,
        alloc_item_tbl.c.resource_type_id,
    )
    usage_subq = sa.alias(usage_subq, "usages")

    p_to_inv = sa.join(
        p_tbl, inv_tbl,
        sa.and_(
            p_tbl.c.id == inv_tbl.c.provider_id,
            inv_tbl.c.resource_type_id.in_(rt_ids),
        )
    )
    inv_to_usage = sa.outerjoin(
        p_to_inv, usage_subq,
        sa.and_(
            inv_tbl.c.provider_id == usage_subq.c.provider_id,
            inv_tbl.c.resource_type_id == usage_subq.c.resource_type_id,
        ),
    )
    cols = [
        p_tbl.c.id.label('provider_id'),
        p_tbl.c.uuid.label('provider_uuid'),
        p_tbl.c.generation.label('provider_generation'),
        inv_tbl.c.resource_type_id,
        inv_tbl.c.total,
        inv_tbl.c.reserved,
        inv_tbl.c.min_unit,
        inv_tbl.c.max_unit,
        inv_tbl.c.step_size,
        inv_tbl.c.allocation_ratio,
        func.coalesce(usage_subq.c.total_used, 0).label('total_used'),
    ]
    sel = sa.select(cols).select_from(
        inv_to_usage
    ).where(
        sa.and_(
            inv_tbl.c.resource_type_id.in_(rt_ids),
            p_tbl.c.id.in_(p_ids),
        ),
    )
    recs = [dict(r) for r in sess.execute(sel)]

    # dict, keyed by provider_id, of ProviderUsage objects
    provider_usages = {}
    for rec in recs:
        p_id = rec['provider_id']
        if p_id not in provider_usages:
            p_obj = resource_models.Provider(
                id=p_id,
                uuid=rec['provider_uuid'],
                generation=rec['provider_generation'],
            )
            provider_usages[p_id] = ProviderUsages(provider=p_obj)

        rt_id = rec['resource_type_id']
        p_usage = provider_usages[p_id]

        p_usage.usages[rt_id] = Usage(
            total=rec['total'],
            reserved=rec['reserved'],
            min_unit=rec['min_unit'],
            max_unit=rec['max_unit'],
            step_size=rec['step_size'],
            allocation_ratio=rec['allocation_ratio'],
            total_used=rec['total_used'],
        )

    # Verify that all providers listed in our claim's allocation items have
    # inventory for the resource types we're going to allocate for. You never
    # know, an admin may have deleted an inventory record or something in
    # between when our claim was generated and when we try to execute it...
    for alloc_item in claim_obj.allocation_items:
        if alloc_item.provider.id not in provider_usages:
            raise exception.MissingInventory(
                resource_type=alloc_item.resource_type,
                provider=alloc_item.provider.uuid,
            )
        else:
            alloc_rt_id = _rt_id_from_code(sess, alloc_item.resource_type)
            alloc_p_id = alloc_item.provider.id
            if alloc_rt_id not in provider_usages[alloc_p_id].usages:
                raise exception.MissingInventory(
                    resource_type=alloc_item.resource_type,
                    provider=alloc_item.provider.uuid,
                )

    # Do the checks again that resource constraint amounts, step sizing, min
    # and max unit are not violated
    for alloc_item in claim_obj.allocation_items:
        alloc_rt_id = _rt_id_from_code(sess, alloc_item.resource_type)
        alloc_p_id = alloc_item.provider.id
        usage = provider_usages[alloc_p_id].usages[alloc_rt_id]
        amount_needed = alloc_item.used
        total = usage.total
        reserved = usage.reserved
        allocation_ratio = usage.allocation_ratio
        min_unit = usage.min_unit
        max_unit = usage.max_unit
        step_size = usage.step_size
        total_used = usage.total_used

        # check min_unit, max_unit, step_size
        if amount_needed < min_unit:
            raise exception.MinUnitViolation(
                provider=alloc_item.provider.uuid,
                resource_type=alloc_item.resource_type,
                min_unit=min_unit,
                requested_amount=amount_needed,
            )

        if amount_needed > max_unit:
            raise exception.MaxUnitViolation(
                provider=alloc_item.provider.uuid,
                resource_type=alloc_item.resource_type,
                max_unit=max_unit,
                requested_amount=amount_needed,
            )

        if amount_needed % step_size != 0:
            raise exception.StepSizeViolation(
                provider=alloc_item.provider.uuid,
                resource_type=alloc_item.resource_type,
                step_size=step_size,
                requested_amount=amount_needed,
            )

        capacity = (total - reserved) * allocation_ratio
        if (capacity < (total_used + amount_needed)):
            raise exception.CapacityExceeded(
                provider=alloc_item.provider.uuid,
                resource_type=alloc_item.resource_type,
                requested_amount=amount_needed,
                total=total,
                total_used=total_used,
                reserved=reserved,
                allocation_ratio=allocation_ratio,
            )

    # we return a dict, keyed by provider UUID, of Provider objects that
    # contain the generation that the provider was at when it passed capacity
    # checks
    return {
        p_usage.provider.uuid: p_usage.provider
        for p_usage in provider_usages.values()
    }


def execute(ctx, consumer_obj, claim):
    """Given a Consumer and Claim object, attempt to acquire the resources
    listed in the claim. Returns None on successful execution, otherwise raises
    an exception indicating what went wrong.
    """
    alloc_items_tbl = resource_models.get_table('allocation_items')

    sess = resource_models.get_session()

    # Before we start, grab the provider internal ID and generation for each
    # provider involved in our allocation items. We'll use these generations at
    # the end of the claim execution process as a safety-check to determine if
    # any of the involved providers were allocated against by another thread
    # during our claim execution process. If so, we'll simply re-try the
    # operation, verifying that the providers still have capacity for the
    # amounts of resources we're allocating in our claim.
    provider_map = _check_provider_capacity(sess, claim)

    consumer.create_if_not_exists(sess, consumer_obj)
    alloc_id = _create_allocation(sess, consumer_obj, claim)

    # Create each allocation item contained in the claim's list of
    # allocation items
    item_values = [
        {
            'allocation_id': alloc_id,
            'provider_id': alloc_item.provider.id,
            'resource_type_id': lookup.resource_type_id_from_code(
                alloc_item.resource_type),
            'used': alloc_item.used,
        }
        for alloc_item in claim.allocation_items
    ]
    ins = alloc_items_tbl.insert()
    sess.execute(ins, item_values)

    # increment the provider generations, ensuring that the providers involved
    # in our allocation did not change in between the time we read their
    # generations above and here.
    for p in provider_map.values():
        provider.increment_generation(sess, p)

    sess.commit()
