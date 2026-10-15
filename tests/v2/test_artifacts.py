import hashlib
import io
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

from worker_v2.artifacts import ArtifactRedirect, DEFAULT_BINARY_HOSTS, check_url
from worker_v2.runtime import DockerRuntime
from worker_v2.state import StateError
from test_worker import assignment


MEDIA = 'https://media.githubusercontent.com/media/tig-foundation/tig-monorepo/main/algorithms/fixture.tar.gz'
IMAGE = 'ghcr.io/tig-foundation/tig-monorepo/satisfiability/runtime@sha256:' + 'a' * 64


def archive(arch='amd64', *, symlink=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as output:
        item = tarfile.TarInfo(arch + '/fixture_algo.so')
        if symlink:
            item.type, item.linkname = tarfile.SYMTYPE, '/etc/passwd'
            output.addfile(item)
        else:
            item.size = 3
            output.addfile(item, io.BytesIO(b'bin'))
    return buffer.getvalue()


class ArtifactTests(unittest.TestCase):
    def test_default_sources_and_explicit_legacy_pool_source(self):
        for url in (MEDIA, 'https://mainnet-api.tig.foundation/get-binary-blob?algorithm_id=c001_a001'):
            check_url(url, DEFAULT_BINARY_HOSTS)
        check_url('https://pool.example/api/v2/artifacts/' + 'a' * 64, {'pool.example'})

    def test_disallowed_sources_ports_and_repository_traversal_are_rejected(self):
        for url in (
            MEDIA.replace('https:', 'http:'),
            MEDIA.replace('media.githubusercontent.com', 'attacker.example'),
            MEDIA.replace('media.githubusercontent.com', 'user:password@media.githubusercontent.com'),
            MEDIA + '#fragment',
            MEDIA.replace('media.githubusercontent.com', 'media.githubusercontent.com:444'),
            MEDIA.replace('media.githubusercontent.com', 'media.githubusercontent.com:bad'),
            MEDIA.replace('/tig-foundation/tig-monorepo/', '/someone/other-repository/'),
            MEDIA.replace('/main/', '/../../someone/other-repository/'),
            MEDIA.replace('/main/', '/%2e%2e/%2e%2e/someone/other-repository/'),
            MEDIA.replace('/main/', '/%2e%2e%2fsomeone/'),
        ):
            with self.subTest(url=url), self.assertRaises(StateError):
                check_url(url, DEFAULT_BINARY_HOSTS)

    def test_redirects_use_public_get_and_drop_all_original_headers(self):
        handler = ArtifactRedirect(DEFAULT_BINARY_HOSTS)
        original = Request('https://mainnet-api.tig.foundation/get-binary-blob', headers={
            'Authorization': 'Bearer fixture-execution-token', 'Cookie': 'fixture-cookie',
            'X-InnoPool-Version': '2.0', 'User-Agent': 'original-client'})
        redirected = handler.redirect_request(original, None, 302, 'found', {}, MEDIA)
        self.assertEqual(redirected.full_url, MEDIA)
        self.assertEqual(redirected.get_method(), 'GET')
        self.assertEqual(dict(redirected.header_items()), {'User-agent': 'innopool-v2-member/2.0'})
        with self.assertRaises(StateError):
            handler.redirect_request(Request(original.full_url, data=b'fixture'), None, 302, 'found', {}, MEDIA)
        with self.assertRaises(StateError):
            handler.redirect_request(original, None, 302, 'found', {}, 'https://attacker.example/archive')

    def test_direct_download_checks_hash_and_architecture_before_docker_start(self):
        for machine, arch, compute in (('x86_64', 'amd64', 'aws_c7a'), ('aarch64', 'arm64', 'aws_c7g')):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory, \
                    patch('platform.machine', return_value=machine):
                payload = archive(arch)
                value = {**assignment(), 'compute_type': compute, 'binary_url': MEDIA,
                         'binary_sha256': hashlib.sha256(payload).hexdigest()}
                runtime = DockerRuntime(directory, {'c001': IMAGE})
                runtime.validate(value, {'resource': 'CPU', 'compute_type': compute})
                with patch('worker_v2.runtime.build_opener') as opener, \
                        patch.object(runtime, '_inspect', return_value=None), patch.object(runtime, '_run') as run:
                    opener.return_value.open.return_value = io.BytesIO(payload)
                    runtime.prepare(value)
                    request = opener.return_value.open.call_args.args[0]
                    self.assertEqual(request.full_url, MEDIA)
                    self.assertNotIn('Authorization', request.headers)
                    self.assertIsInstance(opener.call_args.args[0], ArtifactRedirect)
                    self.assertEqual((runtime._paths(value)[0] / 'c001_a001.so').read_bytes(), b'bin')
                    self.assertIn('--network', run.call_args.args[0])
                    run.reset_mock()
                    value['binary_sha256'] = 'b' * 64
                    opener.return_value.open.return_value = io.BytesIO(payload)
                    with self.assertRaises(StateError):
                        runtime.prepare(value)
                    run.assert_not_called()

    def test_wrong_architecture_and_symlink_archives_never_start_docker(self):
        for payload in (archive('arm64'), archive(symlink=True)):
            with self.subTest(sha=hashlib.sha256(payload).hexdigest()), tempfile.TemporaryDirectory() as directory, \
                    patch('platform.machine', return_value='x86_64'):
                value = {**assignment(), 'binary_url': MEDIA, 'binary_sha256': hashlib.sha256(payload).hexdigest()}
                runtime = DockerRuntime(directory, {'c001': IMAGE})
                with patch('worker_v2.runtime.build_opener') as opener, patch.object(runtime, '_run') as run:
                    opener.return_value.open.return_value = io.BytesIO(payload)
                    with self.assertRaises(StateError):
                        runtime.prepare(value)
                    run.assert_not_called()
                    self.assertFalse((runtime._paths(value)[0] / 'archive.sha256').exists())
