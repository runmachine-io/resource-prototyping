# runm-resource data model testing

This repository contains Python and SQL code that tests the database schema and
modeling for the `runm-resource` service. The `runm-resource` service is a
critical component in `runmachine` and is responsible for resource accounting,
scheduling/placement and resource reservation. Therefore, we want to ensure
that the underlying database modeling is sound and that the queries required by
the service are performant, utilize indexes appropriately, and work well at
varying scales (of deployment size).

We test the data model and schema in Python because it's quick and easy to
prototype things and run tests. We're not interested in comparing the raw speed
of Golang versus Python. Rather, we're simply interested in quickly loading up
a DB with varying scale scenarios, running claim and placement tests against
that DB, and tearing it all down.

We use MySQL for the tests, though there's nothing preventing the use of
PostgreSQL or another DB system. Again, we're not comparing MySQL vs
PostgreSQL. We're only interested in how the data model stands up under varying
query scenarios and deployment scales.

## What we're prototyping

This repository is exploring the data model and database queries necessary for
implementing the following functionality in the `runm-resource` service:

* How do we describe the relationships between providers of resources in a
  system?
* How do we describe the consumption of resources from those providers of
  resources?
* How do we describe the capabilities of providers of resources?
* How do we describe a request to list providers that meet certain resource and
  capability constraints?
* How do we efficiently partition queries in a large multi-partition system?
* How do we transactionally consume resources from multiple providers in an
  efficient and safe manner?
* How do we describe a request that things providing resources are some
  distance close or far away from each other? (failure domains and availability
  groups)

## How to use this code

**PREREQUISITES**: Install MySQL on your test machine. Make a note of the root
database password.

First, create a `virtualenv` so that you don't need to worry about Python
package dependencies on your local testing machine:

```
virtualenv .venv
```

Then activate your virtualenv and export your local database :

```
source .venv/bin/activate
```

Install the Python package dependencies into your virtualenv:

```
pip install -r requirements.txt
```

Export the password for the `root` user of your database:

```
export RUNM_TEST_RESOURCE_DB_PASS=foo
```

Run the resource data model test:

```
python run.py --reset
```

**NOTE**: The `--reset` argument reloads the resource database. You only need
to run with `--reset` when you want to load (or re-load) a certain deployment
configuration (the `--deployment-config` CLI option can be used to switch
deployment configuration profiles)

The tool will load the database up with the deployment configuration described
by a YAML file and selected with the `--deployment-config` CLI option and
execute a single claim request described by a YAML file and selected with the
`--claim-config` CLI option.

Example output:

```
(.venv) [jaypipes@uberbox resource-prototyping]$ python run.py --reset \
    --deployment-config 1k-shared-compute \
    --claim-config 1cpu-64M-10G
action: loading deployment config ... ok
action: resetting resource PoC database ... ok
action: creating object types ... ok
action: creating provider types ... ok
action: creating resource types ... ok
action: creating consumer types ... ok
action: creating capabilities ... ok
action: creating distance types ... ok
action: creating distances ... ok
action: creating partitions ... ok
action: creating provider groups ... ok
action: caching provider group internal IDs ... ok
action: caching resource type and capability internal IDs ... ok
action: caching partition, distance type and distance internal IDs ... ok
action: creating providers ... ok
action: loading claim config ... ok
info: found 50 providers matching ResourceConstraint(resource_type=runm.block_storage,min_amount=1000000000,max_amount=1000000000,capabilities=None)
info: found 50 providers matching ResourceConstraint(resource_type=runm.memory,min_amount=67108864,max_amount=67108864,capabilities=None)
info: found 50 providers matching ResourceConstraint(resource_type=runm.cpu.shared,min_amount=1,max_amount=1,capabilities=None)
info: found 1 claims
info: claim 0: Claim(allocation_items=[
        AllocationItem(provider=Provider(uuid=7aa084e6b80b4ca6a00b36a6b37255fd),resource_type=runm.block_storage,used=1000000000),
        AllocationItem(provider=Provider(uuid=7aa084e6b80b4ca6a00b36a6b37255fd),resource_type=runm.memory,used=67108864),
        AllocationItem(provider=Provider(uuid=7aa084e6b80b4ca6a00b36a6b37255fd),resource_type=runm.cpu.shared,used=1)])
```

To execute the claim that is returned, pass the `--execute-claim` CLI option:

```
(.venv) [jaypipes@uberbox resource-prototyping]$ python run.py --execute-claim
action: loading claim config ... ok
info: found 50 providers matching ResourceConstraint(resource_type=runm.block_storage,min_amount=1000000000,max_amount=1000000000,capabilities=None)
info: found 50 providers matching ResourceConstraint(resource_type=runm.memory,min_amount=67108864,max_amount=67108864,capabilities=None)
info: found 50 providers matching ResourceConstraint(resource_type=runm.cpu.shared,min_amount=1,max_amount=1,capabilities=None)
info: found 1 claims
info: claim 0: Claim(allocation_items=[
        AllocationItem(provider=Provider(uuid=ce983fd54faf4bcfadbffba8d238cc14),resource_type=runm.block_storage,used=1000000000),
        AllocationItem(provider=Provider(uuid=ce983fd54faf4bcfadbffba8d238cc14),resource_type=runm.memory,used=67108864),
        AllocationItem(provider=Provider(uuid=ce983fd54faf4bcfadbffba8d238cc14),resource_type=runm.cpu.shared,used=1)])
action: executing claim 0 ... ok
```
