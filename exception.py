class GenerationConflict(Exception):
    def __init__(self, object_type, object_uuid):
        msg = "Generation conflict occurred. object_type=%s, object_uuid=%s"
        super(GenerationConflict, self).__init__(
            msg % (object_type, object_uuid))
