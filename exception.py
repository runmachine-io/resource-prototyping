class GenerationConflict(Exception):
    def __init__(self, object_type, object_uuid):
        msg = "Generation conflict occurred. object_type=%s, object_uuid=%s"
        super(GenerationConflict, self).__init__(
            msg % (object_type, object_uuid))


class MissingInventory(Exception):
    def __init__(self, provider, resource_type):
        msg = ("Expected provider %s to have inventory in %s, but found no "
               "inventory record." % (provider, resource_type))
        super(MissingInventory, self).__init__(msg)


class CapacityExceeded(Exception):
    def __init__(self, provider, resource_type, requested_amount, total,
            total_used, reserved, allocation_ratio):
        msg = (
            "A resource constraint was violated for provider %s and "
            "resource %s: requested amount of %d was greater than the "
            "provider's capacity. Capacity is calculated as ((total - used - "
            "reserved) * allocation_ratio) where total = %d, used = %d, "
            "reserved = %d and allocation_ratio = %f" % (
                provider, resource_type, requested_amount, total, total_used,
                reserved, allocation_ratio,
            )
        )
        super(CapacityExceeded, self).__init__(msg)


class MinUnitViolation(Exception):
    def __init__(self, provider, resource_type, min_unit, requested_amount):
        msg = ("A resource constraint was violated for provider %s and "
               "resource %s: min unit of %d was greater than requested "
               "amount of %d." % (
                   provider, resource_type, min_unit, requested_amount))
        super(MinUnitViolation, self).__init__(msg)


class MaxUnitViolation(Exception):
    def __init__(self, provider, resource_type, max_unit, requested_amount):
        msg = ("A resource constraint was violated for provider %s and "
               "resource %s: max unit of %d was less than requested "
               "amount of %d." % (
                   provider, resource_type, max_unit, requested_amount))
        super(MaxUnitViolation, self).__init__(msg)


class StepSizeViolation(Exception):
    def __init__(self, provider, resource_type, step_size, requested_amount):
        msg = ("A resource constraint was violated for provider %s and "
               "resource %s: requested amount of %d was not aligned with "
               "stepping size of %d." % (
                   provider, resource_type, requested_amount, step_size))
        super(StepSizeViolation, self).__init__(msg)
