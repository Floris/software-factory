"""Offline synthetic fixtures only: no installed config, token or API access."""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import ssl
import stat
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

from scripts import observer_gateway as gateway
from scripts import observer_client as client

ROOT = Path(__file__).resolve().parents[1]
APP = {'id': 'sample-app', 'argocd_namespace': 'argocd', 'namespace': 'sample-dev',
       'workloads': [{'kind': 'Deployment', 'name': 'sample-web'}]}
REQUEST = b'{"version":1,"op":"status","application":"sample-app"}'
GOOD = {'version': 1, 'ok': True, 'status': {'application': {'name': 'sample-app'}}}
SECRET = 'synthetic-secret-never-publish'


def uid(number):
    return f'00000000-0000-0000-0000-{number:012d}'


def fixture(kind, resource_name, number, parent=None, namespace='sample-dev'):
    obj = {'kind': kind, 'metadata': {'name': resource_name, 'namespace': namespace,
                                     'uid': uid(number), 'generation': 1},
           'spec': {'template': {'spec': {'containers': [{'name': 'web', 'image': 'example.invalid/team/web:sha-test'}]}}},
           'status': {'observedGeneration': 1, 'replicas': 1, 'readyReplicas': 1}}
    if parent:
        obj['metadata']['ownerReferences'] = [{'kind': parent[0], 'name': parent[1], 'uid': uid(parent[2]), 'controller': True}]
    if kind == 'Pod':
        obj['status'] = {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True', 'message': SECRET}],
                         'containerStatuses': [{'name': 'web', 'image': 'example.invalid/team/web:sha-test',
                                               'imageID': 'containerd://sha256:' + 'a' * 64,
                                               'restartCount': 2, 'ready': True}]}
    if kind == 'CronJob':
        obj['spec'] = {'jobTemplate': {'spec': {'template': obj['spec']['template']}}}
        obj['status'] = {'active': []}
    return obj


def application():
    obj = fixture('Application', 'sample-app', 1, namespace='argocd')
    obj['status'] = {'health': {'status': 'Healthy', 'message': SECRET},
                     'sync': {'status': 'Synced', 'revision': 'a' * 40}, 'resources': [{'secret': SECRET}]}
    obj['metadata']['annotations'] = {'secret': SECRET}
    return obj


class Transport:
    def __init__(self, workload=None, children=(), pods=()):
        self.calls = []
        self.data = {gateway.api_path('Application', 'argocd', 'sample-app'): application(),
                     gateway.api_path('Deployment', 'sample-dev', 'sample-web'): workload or fixture('Deployment', 'sample-web', 2),
                     gateway.api_path('ReplicaSet', 'sample-dev') + '?limit=64': {'kind': 'ReplicaSetList', 'items': list(children)},
                     gateway.api_path('Pod', 'sample-dev') + '?limit=64': {'kind': 'PodList', 'items': list(pods)}}

    def __call__(self, path, absent=False):
        self.calls.append((path, absent))
        return deepcopy(self.data[path])


def jwt(**changes):
    claims = {'sub': 'system:serviceaccount:argocd:factory-observer', 'exp': int(time.time()) + 600,
              'kubernetes.io': {'namespace': 'argocd', 'serviceaccount': {'name': 'factory-observer'}}}
    claims.update(changes)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
    return 'eyJhbGciOiJSUzI1NiJ9.' + payload + '.c3ludGhldGljLW5vdC1hLXNpZ25hdHVyZQ'


class ProtocolAndPolicy(unittest.TestCase):
    def test_strict_single_request_and_no_caller_routing(self):
        self.assertEqual(gateway.request(REQUEST)['application'], 'sample-app')
        for data in (REQUEST + b'{}', REQUEST + b'\n', b'[]', b'{', b'x' * 257,
                     b'{"version":1,"version":1,"op":"status","application":"sample-app"}',
                     b'{"version":true,"op":"status","application":"sample-app"}',
                     REQUEST[:-1] + b',"path":"/api/v1/secrets"}',
                     REQUEST.replace(b'status', b'logs'), REQUEST.replace(b'sample-app', b'../secrets')):
            with self.subTest(data=data):
                with self.assertRaises(gateway.Denied) as failure:
                    gateway.request(data)
                self.assertEqual(failure.exception.code, 'invalid_request')

    def test_policy_bounds_and_argo_only_are_explicit(self):
        app = deepcopy(APP)
        app['workloads'] = [{'kind': 'CronJob', 'name': f'sample-job-{i}'} for i in range(10)]
        self.assertEqual(len(gateway.policy({'version': 1, 'applications': [app]})['sample-app']['workloads']), 10)
        app['workloads'] = []
        self.assertEqual(gateway.policy({'version': 1, 'applications': [app]})['sample-app']['workloads'], [])
        for change in ({'namespace': '../other'}, {'workloads': [{'kind': 'Secret', 'name': 'secret'}]},
                       {'workloads': [APP['workloads'][0]] * 2}, {'url': 'https://attacker.invalid'}):
            bad = deepcopy(APP)
            bad.update(change)
            with self.assertRaises(gateway.Denied):
                gateway.policy({'version': 1, 'applications': [bad]})
        with self.assertRaises(gateway.Denied):
            gateway.policy({'version': 1, 'applications': [APP, APP]})

    def test_jwt_identity_expiry_not_signature_authority(self):
        self.assertEqual(gateway.validate_token(jwt()), jwt())
        for change in ({'sub': 'admin'}, {'exp': 0}, {'exp': True}, {'nbf': int(time.time()) + 600},
                       {'kubernetes.io': {'namespace': 'default', 'serviceaccount': {'name': 'factory-observer'}}},
                       {'kubernetes.io': {'namespace': 'argocd', 'serviceaccount': {'name': 'admin'}}}):
            with self.subTest(change=change), self.assertRaises(gateway.Denied):
                gateway.validate_token(jwt(**change))
        with self.assertRaises(gateway.Denied):
            gateway.validate_token('opaque-admin-token')

    def test_dumpability_failure_is_closed_before_private_reads(self):
        with patch.object(gateway.ctypes, 'CDLL') as library:
            library.return_value.prctl.return_value = -1
            with self.assertRaises(gateway.Denied):
                gateway.disable_dumping()
            library.return_value.prctl.assert_called_once_with(4, 0, 0, 0, 0)
        with patch.object(gateway, 'installed_source'), patch.object(gateway, 'disable_dumping', side_effect=gateway.Denied()), patch.object(gateway, 'runtime') as runtime:
            with self.assertRaises(gateway.Denied):
                gateway.main()
            runtime.assert_not_called()

    def test_immutable_source_and_socket_metadata_checks(self):
        regular = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644)
        gateway.check_metadata(regular, stat.S_ISREG, 0)
        for info in (SimpleNamespace(st_uid=1000, st_mode=regular.st_mode),
                     SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o664),
                     SimpleNamespace(st_uid=0, st_mode=stat.S_IFLNK | 0o777)):
            with self.assertRaises(gateway.Denied):
                gateway.check_metadata(info, stat.S_ISREG, 0)
        with self.assertRaises(gateway.Denied):
            gateway.installed_source()  # A worktree is intentionally not an installed trust root.
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'socket'
            with self.assertRaises(client.Unavailable):
                client.trusted_path(target, socket_path=True)


class ProjectionAndTransport(unittest.TestCase):
    def test_owner_uid_chains_filter_same_namespace_and_raw_secrets(self):
        rs = fixture('ReplicaSet', 'sample-web-rs', 3, ('Deployment', 'sample-web', 2))
        wrong = fixture('ReplicaSet', 'other-rs', 4, ('Deployment', 'sample-web', 99))
        good_pod = fixture('Pod', 'sample-web-pod', 5, ('ReplicaSet', 'sample-web-rs', 3))
        other_pod = fixture('Pod', 'other-pod', 6, ('ReplicaSet', 'other-rs', 4))
        same_label = fixture('Pod', 'label-only', 7)
        same_label['metadata']['labels'] = {'app': 'sample-web'}
        transport = Transport(children=[rs, wrong], pods=[good_pod, other_pod, same_label])
        result = gateway.snapshot(APP, transport)
        projected = result['workloads'][0]
        self.assertEqual([p['name'] for p in projected['pods']], ['sample-web-pod'])
        self.assertEqual(projected['pods'][0]['containers'][0]['restarts'], 2)
        self.assertEqual(projected['pods'][0]['containers'][0]['digest'], 'sha256:' + 'a' * 64)
        self.assertTrue(projected['pods'][0]['ready'])
        self.assertNotIn(SECRET, gateway.encoded(result).decode())
        self.assertEqual(len(transport.calls), 4)
        self.assertTrue(all('secrets' not in path and '/log' not in path and 'labelSelector' not in path for path, _ in transport.calls))

    def test_each_supported_owner_chain_and_absent_hooks(self):
        for kind in ('ReplicaSet', 'StatefulSet', 'Job', 'CronJob'):
            with self.subTest(kind=kind):
                app = deepcopy(APP)
                app['workloads'] = [{'kind': kind, 'name': 'sample-work'}]
                workload = fixture(kind, 'sample-work', 2)
                parent = (kind, 'sample-work', 2)
                transport = Transport()
                transport.data[gateway.api_path(kind, 'sample-dev', 'sample-work')] = workload
                if kind == 'CronJob':
                    job = fixture('Job', 'sample-child', 3, parent)
                    transport.data[gateway.api_path('Job', 'sample-dev') + '?limit=64'] = {'kind': 'JobList', 'items': [job]}
                    parent = ('Job', 'sample-child', 3)
                pod = fixture('Pod', 'sample-pod', 5, parent)
                transport.data[gateway.api_path('Pod', 'sample-dev') + '?limit=64']['items'] = [pod]
                self.assertEqual(len(gateway.snapshot(app, transport)['workloads'][0]['pods']), 1)
                transport.data[gateway.api_path(kind, 'sample-dev', 'sample-work')] = None
                missing = gateway.snapshot(app, transport)['workloads'][0]
                self.assertEqual(missing, {'kind': kind, 'namespace': 'sample-dev', 'name': 'sample-work', 'present': False})
        app = deepcopy(APP)
        app['workloads'] = []
        transport = Transport()
        self.assertEqual(gateway.snapshot(app, transport)['workloads'], [])
        self.assertEqual(len(transport.calls), 1)

    def test_malformed_or_reflected_values_never_become_success(self):
        for mutate in (lambda obj: obj['status'].update(replicas=True),
                       lambda obj: obj['metadata'].update(uid=SECRET),
                       lambda obj: obj['metadata'].update(namespace='other'),
                       lambda obj: obj['spec']['template']['spec']['containers'][0].update(image='https://user:password@example.invalid/web')):
            workload = fixture('Deployment', 'sample-web', 2)
            mutate(workload)
            with self.assertRaises(gateway.Denied):
                gateway.snapshot(APP, Transport(workload=workload))
        for value in ('https://user:pass@example.invalid/web', 'user:pass@example.invalid/web', SECRET + '\n', 'a' * 257):
            with self.assertRaises(gateway.Denied):
                gateway.image(value)
        with self.assertRaises(gateway.Denied):
            gateway.encoded({'field': jwt()}, jwt())
        with self.assertRaises(gateway.Denied):
            gateway.encoded({'field': 'x' * gateway.OUTPUT_LIMIT})
        pod = fixture('Pod', 'sample-pod', 5, ('ReplicaSet', 'sample-rs', 3))
        pod['status']['conditions'][0]['status'] = SECRET
        with self.assertRaises(gateway.Denied):
            gateway.pod_summary(pod, 'sample-dev', {('ReplicaSet', 'sample-rs', uid(3))})

    def test_each_projected_pod_retains_its_verified_controller_relationship(self):
        for kind, child_kind in (('Deployment', 'ReplicaSet'), ('CronJob', 'Job')):
            with self.subTest(kind=kind):
                app = deepcopy(APP)
                app['workloads'] = [{'kind': kind, 'name': 'sample-work'}]
                children = [fixture(child_kind, 'sample-one', 3, (kind, 'sample-work', 2)),
                            fixture(child_kind, 'sample-two', 4, (kind, 'sample-work', 2))]
                pods = [fixture('Pod', 'pod-one', 5, (child_kind, 'sample-one', 3)),
                        fixture('Pod', 'pod-two', 6, (child_kind, 'sample-two', 4)),
                        fixture('Pod', 'wrong-uid', 7, (child_kind, 'sample-one', 99))]
                pods[0]['metadata']['ownerReferences'][0]['annotation'] = SECRET
                transport = Transport()
                transport.data[gateway.api_path(kind, 'sample-dev', 'sample-work')] = fixture(kind, 'sample-work', 2)
                transport.data[gateway.api_path(child_kind, 'sample-dev') + '?limit=64'] = {'kind': child_kind + 'List', 'items': children}
                transport.data[gateway.api_path('Pod', 'sample-dev') + '?limit=64'] = {'kind': 'PodList', 'items': pods}
                result = gateway.snapshot(app, transport)['workloads'][0]
                self.assertEqual({p['name']: p['controller'] for p in result['pods']}, {
                    'pod-one': {'kind': child_kind, 'name': 'sample-one', 'uid': uid(3)},
                    'pod-two': {'kind': child_kind, 'name': 'sample-two', 'uid': uid(4)},
                })
                self.assertNotIn(SECRET, json.dumps(result))

    def test_cronjob_active_references_and_suspend_are_kind_specific(self):
        app = deepcopy(APP)
        app['workloads'] = [{'kind': 'CronJob', 'name': 'sample-cron'}]
        reference = {'kind': 'Job', 'apiVersion': 'batch/v1', 'name': 'sample-active',
                     'namespace': 'sample-dev', 'uid': uid(3)}
        for suspend in (True, False):
            for active in ([], [reference]):
                with self.subTest(suspend=suspend, active=active):
                    transport = Transport()
                    cronjob = fixture('CronJob', 'sample-cron', 2)
                    cronjob['spec']['suspend'] = suspend
                    cronjob['status']['active'] = active
                    transport.data[gateway.api_path('CronJob', 'sample-dev', 'sample-cron')] = cronjob
                    transport.data[gateway.api_path('Job', 'sample-dev') + '?limit=64'] = {'kind': 'JobList', 'items': []}
                    result = gateway.snapshot(app, transport)['workloads'][0]
                    self.assertEqual(result['suspend'], suspend)
                    self.assertEqual(result['status']['active'], len(active))
                    self.assertNotIn('sample-active', json.dumps(result))
        for active in (1, ['bad-ref'], [dict(reference, namespace='other')],
                       [dict(reference, uid=SECRET)], [dict(reference, name='../escape')],
                       [dict(reference, kind='Pod')], [reference, reference], [reference] * 65):
            with self.subTest(active=active):
                transport = Transport()
                cronjob = fixture('CronJob', 'sample-cron', 2)
                cronjob['status']['active'] = active
                transport.data[gateway.api_path('CronJob', 'sample-dev', 'sample-cron')] = cronjob
                with self.assertRaises(gateway.Denied):
                    gateway.snapshot(app, transport)
        job_app = deepcopy(APP)
        job_app['workloads'] = [{'kind': 'Job', 'name': 'sample-job'}]
        transport = Transport()
        job = fixture('Job', 'sample-job', 2)
        job['status'] = {'active': 2}
        transport.data[gateway.api_path('Job', 'sample-dev', 'sample-job')] = job
        self.assertEqual(gateway.snapshot(job_app, transport)['workloads'][0]['status']['active'], 2)

    def test_pagination_is_fixed_bounded_and_never_partial_success(self):
        calls = []
        def get(path):
            calls.append(path)
            return {'kind': 'PodList', 'items': [], 'metadata': {'continue': str(len(calls))}}
        with self.assertRaises(gateway.Denied) as failure:
            gateway.objects(get, 'Pod', 'sample-dev')
        self.assertEqual(failure.exception.code, 'limit_exceeded')
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[1], '/api/v1/namespaces/sample-dev/pods?limit=64&continue=1')
        with self.assertRaises(gateway.Denied):
            gateway.objects(lambda path: {'kind': 'PodList', 'items': [{}] * 65}, 'Pod', 'sample-dev')
        with self.assertRaises(gateway.Denied):
            gateway.strict_json(b'x' * (gateway.BODY_LIMIT + 1))

    def test_fixed_https_get_no_redirect_proxy_or_error_body(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        for code in (302, 401, 403, 500):
            with self.subTest(code=code), patch.object(gateway.http.client, 'HTTPSConnection') as connection:
                response = connection.return_value.getresponse.return_value
                response.status = code
                response.read.return_value = SECRET.encode()
                get = gateway.fetcher(('localhost', 443, context), jwt())
                with self.assertRaises(gateway.Denied):
                    get('/api/v1/namespaces/sample-dev/pods?limit=64')
                response.read.assert_not_called()
                self.assertEqual(connection.call_args.kwargs['context'].verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(connection.call_args.kwargs['context'].check_hostname)
                self.assertEqual(connection.return_value.request.call_args.args[0], 'GET')
        with patch.object(gateway.http.client, 'HTTPSConnection') as connection, patch.dict(os.environ, {'HTTPS_PROXY': 'https://attacker.invalid', 'HTTP_PROXY': 'http://attacker.invalid'}):
            connection.return_value.getresponse.return_value.status = 404
            self.assertIsNone(gateway.fetcher(('localhost', 443, context), jwt())('/named/job', absent=True))
            self.assertEqual(connection.call_args.args, ('localhost', 443))
            connection.return_value.request.side_effect = ssl.SSLCertVerificationError('synthetic-secret')
            with self.assertRaises(ssl.SSLCertVerificationError):
                gateway.fetcher(('localhost', 443, context), jwt())('/named/job')

    def test_connection_rejects_insecure_or_executable_fallbacks(self):
        document = {'version': 1, 'server': 'https://api.example.invalid:6443',
                    'ca_data': base64.b64encode(b'-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----').decode()}
        with patch.object(gateway.ssl, 'create_default_context', return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as context:
            self.assertEqual(gateway.connection(document)[:2], ('api.example.invalid', 6443))
            self.assertIn('cadata', context.call_args.kwargs)
            for change in ({'server': 'http://api.example.invalid'}, {'server': 'https://u:p@api.example.invalid'},
                           {'server': 'https://api.example.invalid/path'}, {'server': 'https://api.example.invalid?query=x'},
                           {'exec': 'kubectl'}, {'insecure-skip-tls-verify': True}, {'ca_file': '/root/admin-ca'}):
                bad = dict(document)
                bad.update(change)
                with self.assertRaises(gateway.Denied):
                    gateway.connection(bad)


class DeadlinesAndSockets(unittest.TestCase):
    def test_absolute_collector_timeout_kills_and_reaps_child(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'synthetic_collector.py'
            script.write_text('import time\ntime.sleep(5)\n')
            real_run, processes = subprocess.run, []
            real_popen = subprocess.Popen
            def popen(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                processes.append(process)
                return process
            with patch.object(gateway, 'INSTALLED', script), patch.object(gateway, 'CREDENTIAL_DIR', directory), patch.object(gateway, 'REQUEST_SECONDS', 0.08), patch.object(subprocess, 'Popen', side_effect=popen):
                started = time.monotonic()
                self.assertFalse(json.loads(gateway.run_collector(REQUEST))['ok'])
                self.assertLess(time.monotonic() - started, 1)
                self.assertIsNotNone(processes[0].poll())
            with patch.object(subprocess, 'run', wraps=real_run) as run:
                with patch.object(gateway, 'INSTALLED', script), patch.object(gateway, 'CREDENTIAL_DIR', directory), patch.object(gateway, 'REQUEST_SECONDS', 0.02):
                    gateway.run_collector(REQUEST)
                args, kwargs = run.call_args
                self.assertEqual(args[0][:4], ['/usr/bin/python3', '-I', '-B', '-S'])
                self.assertEqual(kwargs['env'], {'CREDENTIALS_DIRECTORY': directory})
                self.assertTrue(kwargs['close_fds'])
                self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)

    def test_absolute_eof_deadline_and_overflow(self):
        reader, writer = socket.socketpair()
        with reader, writer:
            writer.sendall(b'x' * 257)
            with self.assertRaises(gateway.Denied):
                gateway.frame(reader)
        reader, writer = socket.socketpair()
        def trickle():
            with writer:
                for _ in range(20):
                    try:
                        writer.sendall(b' ')
                    except OSError:
                        break
                    time.sleep(0.015)
        thread = threading.Thread(target=trickle, daemon=True)
        thread.start()
        with reader:
            started = time.monotonic()
            with self.assertRaises((gateway.Denied, TimeoutError)):
                gateway.frame(reader, seconds=0.06)
            self.assertLess(time.monotonic() - started, 0.2)
        thread.join(1)

    def test_serial_socket_eof_rate_limit_disconnect_and_idle_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'socket'
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(8)
            calls = []
            def collect(data):
                calls.append(data)
                return gateway.encoded(GOOD)
            thread = threading.Thread(target=gateway.serve, args=(listener, os.getuid(), collect, 0.08), daemon=True)
            thread.start()
            with patch.object(client, 'trusted_path'):
                self.assertTrue(client.status('sample-app', path)['ok'])
                self.assertEqual(client.status('sample-app', path)['error'], 'rate_limited')
            disconnected = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            disconnected.connect(str(path))
            disconnected.sendall(REQUEST)
            disconnected.shutdown(socket.SHUT_WR)
            disconnected.close()
            thread.join(1)
            listener.close()
            self.assertFalse(thread.is_alive())
            self.assertEqual([json.loads(data) for data in calls], [json.loads(REQUEST)])

    def test_client_deadline_and_malformed_response_are_closed(self):
        for response in (b'{"version":1,"ok":false,"error":"synthetic-secret"}',
                         b'{"version":1,"ok":true,"status":{},"token":"secret"}', b'{}{}'):
            with self.assertRaises((client.Unavailable, ValueError)):
                client.decode(response)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'socket'
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(1)
            def stall():
                peer, _ = listener.accept()
                with peer:
                    gateway.frame(peer)
                    peer.sendall(b'{')
                    time.sleep(0.15)
            thread = threading.Thread(target=stall, daemon=True)
            thread.start()
            with patch.object(client, 'trusted_path'), self.assertRaises((client.Unavailable, TimeoutError)):
                client.status('sample-app', path, seconds=0.04)
            thread.join(1)
            listener.close()

    def test_hardened_units_and_neutral_examples(self):
        directory = ROOT / 'examples/observer-gateway'
        service = (directory / 'software-factory-observer.service').read_text()
        for line in ('DynamicUser=yes', 'NoNewPrivileges=yes', 'LimitCORE=0', 'ProtectSystem=strict',
                     'ProtectHome=yes', 'PrivateDevices=yes', 'CapabilityBoundingSet=', 'AmbientCapabilities=',
                     'MemoryMax=128M', 'TasksMax=8', 'CPUQuota=10%', 'StandardError=null',
                     'ExecStart=/usr/bin/python3 -I -B -S /usr/local/lib/software-factory/observer_gateway.py',
                     'LoadCredential=observer-policy:/etc/software-factory/observer-policy.json'):
            self.assertIn(line, service)
        self.assertNotIn('SupplementaryGroups', service)
        self.assertNotIn('RuntimeDirectory=', service)
        socket_unit = (directory / 'software-factory-observer.socket').read_text()
        for line in ('Accept=no', 'Backlog=8', 'SocketUser=root', 'SocketGroup=codex', 'SocketMode=0660'):
            self.assertIn(line, socket_unit)
        self.assertIn('0750 root codex', (directory / 'software-factory-observer.conf').read_text())
        gateway.policy(json.loads((directory / 'policy.example.json').read_text()))
        workflow = (ROOT / '.github/workflows/validate-observer-gateway.yml').read_text()
        self.assertIn('contents: read', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertNotIn('secrets.', workflow)


if __name__ == '__main__':
    unittest.main()
