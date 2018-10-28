# Loads up the runm-resource database with records that we then use in our PoC
# scenarios

import argparse
import datetime
import os
import sys
import time

import claim
import load
import claim_config
import deployment_config
import provider_profile
import resource_models

_LOG_FORMAT = "%(level)s %(message)s"
_DEPLOYMENT_CONFIGS_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'deployment-configs',
)
_DEFAULT_DEPLOYMENT_CONFIG = '1k-shared-compute'
_CLAIM_CONFIGS_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'claim-configs',
)
_DEFAULT_CLAIM_CONFIG = '1cpu-64M-10G'
_PROVIDER_PROFILES_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'provider-profiles',
)


class RunContext(object):
    def __init__(self, args):
        self.args = args
        self.deployment_config = None

    def status(self, msg):
        if self.args.quiet:
            return
        sys.stdout.write("action: " + msg + " ... ")
        sys.stdout.flush()

    def status_ok(self, ):
        if self.args.quiet:
            return
        sys.stdout.write("ok\n")
        sys.stdout.flush()

    def status_fail(self, err):
        sys.stdout.write("FAIL\n")
        sys.stdout.flush()
        sys.stderr.write(" error: %s\n" % err)
        sys.stderr.flush()

    def info(self, msg, *msg_args):
        if self.args.quiet:
            return
        if msg_args:
            msg = msg % msg_args
        sys.stdout.write("info: %s\n" % msg)

    def out(self, msg, *msg_args):
        if msg_args:
            msg = msg % msg_args
        sys.stdout.write("%s\n" % msg)


def find_claims(ctx):
    ctx.status("loading claim config")
    fp = os.path.join(_CLAIM_CONFIGS_DIR, args.claim_config)
    ctx.claim_config = claim_config.ClaimConfig(fp)
    ctx.status_ok()
    consumer = resource_models.Consumer(name="instance0")
    claim_time = datetime.datetime.utcnow()
    claim_time = int(time.mktime(claim_time.timetuple()))
    release_time = sys.maxint
    cr = claim.ClaimRequest(
        consumer, ctx.claim_config.claim_request_groups, claim_time,
        release_time)
    claims = claim.process_claim_request(ctx, cr)
    ctx.info("found %d claims", len(claims))
    for x, c in enumerate(claims):
        ctx.out("claim %d: %s", x, c)


def setup_opts(parser):
    parser.add_argument('--quiet', action='store_true',
                        default=False, help="Only print critical output.")

    parser.add_argument('--reset', action='store_true',
                        default=False, help="Reset and reload the database.")

    deployment_configs = []
    for fn in os.listdir(_DEPLOYMENT_CONFIGS_DIR):
        fp = os.path.join(_DEPLOYMENT_CONFIGS_DIR, fn)
        if os.path.isfile(fp) and fn.endswith('.yaml'):
            deployment_configs.append(fn[0:len(fn) - 5])

    parser.add_argument('--deployment-config',
                        choices=deployment_configs,
                        default=_DEFAULT_DEPLOYMENT_CONFIG,
                        help="Deployment configuration to use.")
    claim_configs = []
    for fn in os.listdir(_CLAIM_CONFIGS_DIR):
        fp = os.path.join(_CLAIM_CONFIGS_DIR, fn)
        if os.path.isfile(fp) and fn.endswith('.yaml'):
            claim_configs.append(fn[0:len(fn) - 5])
    parser.add_argument('--claim-config',
                        choices=claim_configs,
                        default=_DEFAULT_CLAIM_CONFIG,
                        help="Claim configuration to use.")


def main(ctx):
    prov_profiles = {}
    for fn in os.listdir(_PROVIDER_PROFILES_DIR):
        fp = os.path.join(_PROVIDER_PROFILES_DIR, fn)
        if os.path.isfile(fp) and fn.endswith('.yaml'):
            prof_name = fn[0:len(fn) - 5]
            prov_profiles[prof_name] = provider_profile.ProviderProfile(fp)
    if ctx.args.reset:
        ctx.status("loading deployment config")
        fp = os.path.join(_DEPLOYMENT_CONFIGS_DIR, args.deployment_config)
        ctx.deployment_config = deployment_config.DeploymentConfig(
            fp, prov_profiles)
        ctx.status_ok()
        load.load(ctx)
    find_claims(ctx)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Load up resource database.')
    setup_opts(p)
    args = p.parse_args()
    ctx = RunContext(args)
    main(ctx)
