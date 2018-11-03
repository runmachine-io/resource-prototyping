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
