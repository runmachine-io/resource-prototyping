# model objects for resource service

import uuid as uuidlib

import sqlalchemy as sa

import db


class ProviderGroupDistance(object):
    def __init__(self, provider_group, distance_type, distance_code):
        self.provider_group = provider_group
        self.distance_type = distance_type
        self.distance_code = distance_code


class ProviderGroup(object):
    def __init__(self, name, uuid=None):
        self.name = name
        self.uuid = uuid or str(uuidlib.uuid4()).replace('-', '')
        self.distances = []

    @property
    def name_parts(self):
        name_parts = self.name.split('-')
        site_name = name_parts[0]
        row_id = None
        rack_id = None
        if len(name_parts) == 3:
            row_id = name_parts[1][len('row'):]
            rack_id = name_parts[2][len('rack'):]
        elif len(name_parts) == 2:
            row_id = name_parts[1][len('row'):]
        return site_name, row_id, rack_id

    @property
    def is_site(self):
        name_parts = self.name.split('-')
        return len(name_parts) == 1

    @property
    def is_row(self):
        name_parts = self.name.split('-')
        return len(name_parts) == 2

    @property
    def is_rack(self):
        name_parts = self.name.split('-')
        return len(name_parts) == 3

    def __repr__(self):
        return "ProviderGroup(name=%s,uuid=%s)" % (self.name, self.uuid)


class Partition(object):
    def __init__(self, name, uuid=None):
        self.name = name
        self.uuid = uuid or str(uuidlib.uuid4()).replace('-', '')

    def __repr__(self):
        return "Partition(name=%s,uuid=%s)" % (self.name, self.uuid)


class Provider(object):
    def __init__(self, name=None, partition=None, groups=None, profile=None, id=None, uuid=None, generation=None):
        self.id = id
        self.name = name
        self.partition = partition
        self.uuid = uuid or str(uuidlib.uuid4()).replace('-', '')
        self.generation = generation
        # Collection of provider group objects this provider is in
        self.groups = groups
        self.profile = profile

    @property
    def name_parts(self):
        name_parts = self.name.split('-')
        site_name = name_parts[0]
        row_id = None
        rack_id = None
        node_id = None
        if len(name_parts) == 4:
            row_id = name_parts[1][len('row'):]
            rack_id = name_parts[2][len('rack'):]
            node_id = name_parts[3][len('node'):]
        elif len(name_parts) == 3:
            row_id = name_parts[1][len('row'):]
            rack_id = name_parts[2][len('rack'):]
        elif len(name_parts) == 2:
            row_id = name_parts[1][len('row'):]
        return site_name, row_id, rack_id, node_id

    def __repr__(self):
        name_str = ""
        if self.name:
            name_str = ",name=" + self.name
        profile_str = ""
        if self.profile:
            profile_str = ",profile=%s" % self.profile
        return "Provider(uuid=%s%s%s)" % (
            self.uuid, name_str, profile_str)


class Consumer(object):
    def __init__(self, name, uuid=None, project=None, user=None):
        self.id = None
        self.name = name
        self.uuid = uuid or str(uuidlib.uuid4()).replace('-', '')
        self.project = project or str(uuidlib.uuid4()).replace('-', '')
        self.user = user or str(uuidlib.uuid4()).replace('-', '')

    def __repr__(self):
        uuid_str = ""
        if self.uuid:
            uuid_str = ",uuid=" + self.uuid
        project_str = ""
        if self.project:
            project_str = ",project=" + self.project
        user_str = ""
        if self.user:
            user_str = ",user=" + self.user
        return "Consumer(name=%s%s%s%s)" % (
            self.name,
            uuid_str,
            project_str,
            user_str,
        )


class AllocationItem(object):
    def __init__(self, provider, resource_type, used):
        self.provider = provider
        self.resource_type = resource_type
        self.used = used

    def __repr__(self):
        return "\n\t\tAllocationItem(provider=%s,resource_type=%s,used=%d)" % (
            self.provider,
            self.resource_type,
            self.used,
        )


class Allocation(object):
    def __init__(self, consumer, claim_time, release_time, items):
        self.consumer = consumer
        self.claim_time = claim_time
        self.release_time = release_time
        self.items = items

    def __repr__(self):
        return "\n\tAllocation(consumer=%s,claim_time=%s,release_time=%s,items=%s)" % (
            self.consumer,
            self.claim_time,
            self.release_time,
            self.items,
        )


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
