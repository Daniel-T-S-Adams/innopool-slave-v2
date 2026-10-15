import tempfile
import unittest

from worker_v2.client import ProtocolError
from worker_v2.fleet import FleetRuntime
from worker_v2.runner import Runner
from worker_v2.runtime import DockerRuntime
from worker_v2.state import StateError, Store, canonical, digest
from test_worker import FakePool, FakeRuntime, assignment

class CheckedRuntime(FakeRuntime):
    validate_release = DockerRuntime.validate_release
    def __init__(self, images):
        super().__init__()
        self.images = images

class ReleasePool(FakePool):
    def __init__(self, images):
        super().__init__(assignment())
        self.release = {'runtime_images': images}
        self.bad_digest = False
    def call(self, method, path, body=None):
        if path.endswith('/release'):
            return self.release
        result = super().call(method,path,body)
        if path.endswith('/capabilities'):
            result['release_digest'] = '0'*64 if self.bad_digest else digest(canonical(self.release))
        return result

class RuntimeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(self.directory.name)
        self.old = {'c003': 'old-immutable-runtime'}
        self.new = {'c003': 'current-immutable-runtime'}
    def tearDown(self):
        self.store.close()
        self.directory.cleanup()
    def runner(self,pool,runtime):
        return Runner(pool,self.store,runtime,resource='CPU',compute_type='aws_c7a',workers=2)

    def test_stale_runtime_refuses_offer_before_any_work_request(self):
        pool=ReleasePool(self.new)
        with self.assertRaisesRegex(StateError,'pool runtime changed'):
            self.runner(pool,CheckedRuntime(self.old)).step()
        self.assertEqual(pool.requests,[])
        self.assertIsNone(self.store.unfinished())

    def test_matching_runtime_can_offer_and_complete(self):
        pool=ReleasePool(self.new)
        runner=self.runner(pool,CheckedRuntime(self.new))
        runner.step()
        self.assertEqual(len(pool.requests),1)
        self.assertEqual(runner.step(drain=True),'active')

    def test_changed_release_digest_refuses_offer(self):
        pool=ReleasePool(self.new);pool.bad_digest=True
        with self.assertRaises(ProtocolError):
            self.runner(pool,CheckedRuntime(self.new)).step()
        self.assertEqual(pool.requests,[])

    def test_existing_handed_over_work_drains_after_manifest_change(self):
        pool=ReleasePool(self.old)
        runner=self.runner(pool,CheckedRuntime(self.old))
        runner.step()
        pool.release={'runtime_images':self.new}
        self.assertEqual(runner.step(drain=True),'active')
        self.assertEqual(len(pool.requests),1)

    def test_stale_unlinked_saved_request_cannot_be_posted(self):
        pool=ReleasePool(self.new)
        self.store.bind(pool.origin,'member-one')
        self.store.request({'resource':'CPU','compute_type':'aws_c7a','capacity':{'workers':2}})
        with self.assertRaises(StateError):
            self.runner(pool,CheckedRuntime(self.old)).step()
        self.assertEqual(pool.requests,[])

    def test_stale_queued_offer_cannot_be_refreshed(self):
        pool=ReleasePool(self.new)
        original=pool.call
        def queued(method,path,body=None):
            if path.endswith('/work-requests/request-one'):
                return {'state':'queued','benchmark_id':None}
            if path.endswith('/refresh'):
                self.fail('stale queued offer must not be refreshed')
            return original(method,path,body)
        pool.call=queued
        self.store.bind(pool.origin,'member-one')
        request=self.store.request({'resource':'CPU','compute_type':'aws_c7a','capacity':{'workers':2}})
        self.store.link_request(request['request_key'],'request-one')
        with self.assertRaises(StateError):
            self.runner(pool,CheckedRuntime(self.old)).step()
        self.assertEqual(pool.requests,[])

    def test_every_fleet_backend_must_match_the_pool_runtime(self):
        local=CheckedRuntime(self.new);local.arch='amd64'
        remote=CheckedRuntime(self.old);remote.workers=2
        fleet=FleetRuntime(local,self.store,local_workers=2,remotes=[remote],resource='CPU',compute_type='aws_c7a')
        with self.assertRaisesRegex(StateError,'every helper'):
            fleet.validate_release({'runtime_images':self.new})
        remote.images=self.new
        fleet.validate_release({'runtime_images':self.new})

if __name__=='__main__':unittest.main()
