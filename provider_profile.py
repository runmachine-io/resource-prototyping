import copy
import os

import yaml


class ProviderProfile(object):
    """A provider profile describes the inventory and capabilities for a
    provider.
    """
    def __init__(self, fp):
        """Loads the deployment configuration from a supplied filepath to a
        YAML file.
        """
        if not fp.endswith('.yaml'):
            fp = fp + '.yaml'
        if not os.path.exists(fp):
            raise RuntimeError("Unable to load provider profile %s. "
                               "File does not exist." % fp)

        with open(fp, 'rb') as f:
            try:
                config_dict = yaml.load(f)
            except yaml.YAMLError as err:
                raise RuntimeError("Unable to load provider profile "
                                   "%s. Problem parsing file: %s." % (fp, err))
        name = os.path.basename(fp).rstrip('.yaml')
        self.name = name
        # Simple list of capability names that the provider has
        self.capabilities = config_dict.get('capabilities', [])
        # dict, keyed by resource type name, of inventory information this
        # provider profile contains. The inventory information includes total,
        # reserved, min_unit, max_unit, step_size and allocation_ratio data
        # points for that resource type.
        self.inventory = self._load_inventory(config_dict['inventory'])

    def __repr__(self):
        return "ProviderProfile(name=%s)" % self.name

    def _load_inventory(self, block):
        all_inv = {}
        for rc_name, inv in block.items():
            if 'min_unit' not in inv:
                inv['min_unit'] = 1
            if 'max_unit' not in inv:
                inv['max_unit'] = inv['total']
            if 'step_size' not in inv:
                inv['step_size'] = 1
            if 'allocation_ratio' not in inv:
                inv['allocation_ratio'] = 1.0
            if 'reserved' not in inv:
                inv['reserved'] = 0
            all_inv[rc_name] = inv
        return all_inv
