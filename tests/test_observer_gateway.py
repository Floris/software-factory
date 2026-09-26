"""Offline synthetic fixtures only: no installed config, token or API access."""
import base64
from copy import deepcopy
import errno
import json
import os
from pathlib import Path
import socket
import ssl
import stat
import struct
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


def api_version(kind):
    return {'Application': 'argoproj.io/v1alpha1', 'Pod': 'v1',
            'Job': 'batch/v1', 'CronJob': 'batch/v1'}.get(kind, 'apps/v1')


def collection(kind, items=(), continuation=''):
    return {'kind': kind + 'List', 'apiVersion': api_version(kind),
            'items': list(items), 'metadata': {'continue': continuation}}


def wire_item(obj):
    obj = deepcopy(obj)
    obj.pop('kind')
    obj.pop('apiVersion')
    return obj


def fixture(kind, resource_name, number, parent=None, namespace='sample-dev'):
    obj = {'kind': kind, 'apiVersion': api_version(kind),
           'metadata': {'name': resource_name, 'namespace': namespace,
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
                     gateway.api_path('ReplicaSet', 'sample-dev') + '?limit=64': collection('ReplicaSet', children),
                     gateway.api_path('Pod', 'sample-dev') + '?limit=64': collection('Pod', pods)}

    def __call__(self, path, absent=False):
        self.calls.append((path, absent))
        return deepcopy(self.data[path])


def jwt(**changes):
    claims = {'sub': 'system:serviceaccount:argocd:factory-observer', 'exp': int(time.time()) + 600,
              'kubernetes.io': {'namespace': 'argocd', 'serviceaccount': {'name': 'factory-observer'}}}
    claims.update(changes)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
    return 'eyJhbGciOiJSUzI1NiJ9.' + payload + '.c3ludGhldGljLW5vdC1hLXNpZ25hdHVyZQ'


SERVICE_UID = 61867
UNDEFINED_ID = 0xffffffff


def credential_acl(directory=False, entries=None, version=2):
    access = 5 if directory else 4
    if entries is None:
        entries = [(1, access, UNDEFINED_ID), (2, access, SERVICE_UID),
                   (4, 0, UNDEFINED_ID), (16, access, UNDEFINED_ID),
                   (32, 0, UNDEFINED_ID)]
    return struct.pack('<I', version) + b''.join(struct.pack('<HHI', *entry) for entry in entries)


class CredentialMetadata(unittest.TestCase):
    def validate(self, mode, acl, owner=0, directory=False, service_uid=SERVICE_UID):
        info = SimpleNamespace(st_uid=owner, st_mode=mode)
        lookup = {'side_effect': acl} if isinstance(acl, Exception) else {'return_value': acl}
        with patch.object(gateway.os, 'fstat', return_value=info) as metadata, \
                patch.object(gateway.os, 'getxattr', **lookup) as xattr:
            result = gateway.credential_metadata(17, service_uid, directory)
            metadata.assert_called_once_with(17)
            xattr.assert_called_once_with(17, 'system.posix_acl_access')
            self.assertIs(result, info)

    def test_diagnosed_root_owned_acl_and_root_operator_explicit_uid(self):
        with patch.object(gateway.os, 'geteuid', return_value=0) as caller_uid, \
                patch.object(gateway.os, 'read') as read:
            self.validate(stat.S_IFDIR | 0o550, credential_acl(True), directory=True)
            self.validate(stat.S_IFREG | 0o440, credential_acl())
            caller_uid.assert_not_called()
            read.assert_not_called()

    def test_private_layout_only_for_absent_or_unsupported_acl(self):
        for error in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP):
            for owner in (0, SERVICE_UID):
                for directory, mode in ((True, 0o500), (True, 0o700), (False, 0o400)):
                    with self.subTest(error=error, owner=owner, mode=mode):
                        self.validate((stat.S_IFDIR if directory else stat.S_IFREG) | mode,
                                      OSError(error, 'synthetic'), owner, directory)
            for directory, mode in ((True, 0o550), (False, 0o440), (True, 0o750), (False, 0o404)):
                with self.subTest(error=error, mode=mode), self.assertRaises(gateway.Denied):
                    self.validate((stat.S_IFDIR if directory else stat.S_IFREG) | mode,
                                  OSError(error, 'synthetic'), directory=directory)

    def test_lookup_and_stat_failures_never_allow_private_mode_fallback(self):
        for error in (errno.EACCES, errno.EPERM, errno.EIO, errno.EINVAL):
            with self.subTest(error=error), self.assertRaises(gateway.Denied):
                self.validate(stat.S_IFREG | 0o400, OSError(error, 'synthetic'))
        with patch.object(gateway.os, 'fstat', side_effect=OSError(errno.EBADF, 'synthetic')), \
                patch.object(gateway.os, 'getxattr') as xattr, self.assertRaises(gateway.Denied):
            gateway.credential_metadata(17, SERVICE_UID)
        xattr.assert_not_called()

    def test_wrong_identity_owner_type_mode_and_special_bits_are_denied(self):
        for expected_uid in (0, -1, True, '61867', UNDEFINED_ID, UNDEFINED_ID + 1, SERVICE_UID + 1):
            with self.subTest(uid=expected_uid), self.assertRaises(gateway.Denied):
                self.validate(stat.S_IFREG | 0o440, credential_acl(), service_uid=expected_uid)
        for owner in (1000, SERVICE_UID):
            with self.subTest(owner=owner), self.assertRaises(gateway.Denied):
                self.validate(stat.S_IFREG | 0o440, credential_acl(), owner=owner)
        with self.assertRaises(gateway.Denied):
            self.validate(stat.S_IFREG | 0o400, OSError(errno.ENODATA, 'synthetic'), owner=1000)
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFDIR):
            with self.subTest(kind=kind), self.assertRaises(gateway.Denied):
                self.validate(kind | 0o440, credential_acl())
        for directory, mode in ((False, 0o400), (False, 0o460), (False, 0o441), (False, 0o450),
                                (True, 0o500), (True, 0o570), (True, 0o551)):
            with self.subTest(mode=mode), self.assertRaises(gateway.Denied):
                self.validate((stat.S_IFDIR if directory else stat.S_IFREG) | mode,
                              credential_acl(directory), directory=directory)
        for special in (stat.S_ISUID, stat.S_ISGID, stat.S_ISVTX):
            for directory, mode, acl in ((False, 0o440, credential_acl()),
                                         (True, 0o550, credential_acl(True)),
                                         (False, 0o400, OSError(errno.ENODATA, 'synthetic')),
                                         (True, 0o700, OSError(errno.ENODATA, 'synthetic'))):
                with self.subTest(special=special, mode=mode), self.assertRaises(gateway.Denied):
                    self.validate((stat.S_IFDIR if directory else stat.S_IFREG) | mode | special,
                                  acl, directory=directory)

    def test_acl_rejects_extra_principals_rights_ids_masks_and_malformed_data(self):
        for directory in (False, True):
            entries = list(struct.iter_unpack('<HHI', credential_acl(directory)[4:]))
            bad_entries = [entries + [(2, 0, SERVICE_UID + 1)],
                           entries + [(8, 0, 1000)], entries + [entries[1]],
                           entries[:-1], list(reversed(entries))]
            for index, replacements in ((0, [(1, 7, UNDEFINED_ID), (1, 4, 0)]),
                                        (1, [(2, 7, SERVICE_UID), (2, 8, SERVICE_UID), (2, 4, 0),
                                             (2, 4, SERVICE_UID + 1), (8, 4, SERVICE_UID)]),
                                        (2, [(4, 4, UNDEFINED_ID), (4, 0, 1000)]),
                                        (3, [(16, 7, UNDEFINED_ID), (16, 0, UNDEFINED_ID),
                                             (16, 4, 1000), (64, 4, UNDEFINED_ID)]),
                                        (4, [(32, 4, UNDEFINED_ID), (32, 0, 1000)])):
                for replacement in replacements:
                    changed = entries.copy()
                    changed[index] = replacement
                    bad_entries.append(changed)
            bad_acls = [credential_acl(entries=bad) for bad in bad_entries]
            good = credential_acl(directory)
            bad_acls += [b'', good[:3], good[:-1], good + b'x',
                         credential_acl(directory, version=1), good.decode('latin1')]
            for acl in bad_acls:
                with self.subTest(directory=directory, acl=acl), self.assertRaises(gateway.Denied):
                    self.validate((stat.S_IFDIR | 0o550) if directory else (stat.S_IFREG | 0o440),
                                  acl, directory=directory)


class CredentialReads(unittest.TestCase):
    def synthetic_runtime(self, acl_layout=False, invalid_fd=None, oversize=False, grow=False,
                          bad_acl=None):
        policy = json.dumps({'version': 1, 'applications': [APP]}).encode()
        connection = b'{"version":1}'
        token = jwt().encode()
        contents = {31: policy, 32: connection, 33: token}
        offsets, reads, closes, opens = {}, [], [], []

        def open_file(path, flags, **kwargs):
            opens.append((path, flags, kwargs))
            if path == gateway.CREDENTIAL_DIR:
                return 30
            return {'observer-policy': 31, 'observer-connection': 32, 'observer-token': 33}[path]

        def fstat(fd):
            mode = (0o550 if acl_layout else 0o500) if fd == 30 else (0o440 if acl_layout else 0o400)
            if fd == invalid_fd:
                mode |= 0o002
            return SimpleNamespace(st_uid=0, st_mode=(stat.S_IFDIR if fd == 30 else stat.S_IFREG) | mode,
                                   st_size=gateway.BODY_LIMIT + 1 if oversize else len(contents.get(fd, b'')))

        def getxattr(fd, key):
            self.assertEqual(key, 'system.posix_acl_access')
            if fd == 31 and bad_acl is not None:
                if isinstance(bad_acl, Exception):
                    raise bad_acl
                return bad_acl
            if acl_layout:
                return credential_acl(fd == 30)
            raise OSError(errno.ENODATA, 'synthetic')

        def read(fd, count):
            reads.append((fd, count))
            offset = offsets.get(fd, 0)
            value = b'x' * (gateway.BODY_LIMIT + 1) if grow and fd == 31 else contents[fd]
            chunk = value[offset:offset + min(count, 19)]
            offsets[fd] = offset + len(chunk)
            return chunk

        with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': gateway.CREDENTIAL_DIR}), \
                patch.object(gateway.os, 'geteuid', return_value=SERVICE_UID), \
                patch.object(gateway.os, 'open', side_effect=open_file), \
                patch.object(gateway.os, 'fstat', side_effect=fstat), \
                patch.object(gateway.os, 'getxattr', side_effect=getxattr), \
                patch.object(gateway.os, 'read', side_effect=read), \
                patch.object(gateway.os, 'close', side_effect=closes.append), \
                patch.object(gateway, 'connection', return_value=('synthetic', 443, None)):
            if invalid_fd or oversize or grow or bad_acl is not None:
                with self.assertRaises(gateway.Denied):
                    gateway.runtime()
            else:
                configured, transport, result_token = gateway.runtime()
                self.assertEqual(configured, {APP['id']: APP})
                self.assertEqual(transport, ('synthetic', 443, None))
                self.assertEqual(result_token.encode(), token)
        return opens, reads, closes

    def test_both_layouts_read_validated_descriptors_with_fixed_names_and_flags(self):
        for layout in (False, True):
            with self.subTest(acl=layout):
                opens, reads, closes = self.synthetic_runtime(layout)
                self.assertEqual(opens[0], (gateway.CREDENTIAL_DIR,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, {}))
                self.assertEqual(opens[1:], [(filename,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, {'dir_fd': 30})
                    for filename in ('observer-policy', 'observer-connection', 'observer-token')])
                self.assertEqual({fd for fd, _ in reads}, {31, 32, 33})
                self.assertEqual(closes, [31, 32, 33, 30])

    def test_bad_directory_or_file_and_oversize_fail_before_credential_reads(self):
        for layout in (False, True):
            for invalid_fd in (30, 31):
                with self.subTest(acl=layout, fd=invalid_fd):
                    _, reads, closes = self.synthetic_runtime(layout, invalid_fd)
                    self.assertEqual(reads, [])
                    self.assertEqual(closes, [30] if invalid_fd == 30 else [31, 30])
        _, reads, closes = self.synthetic_runtime(oversize=True)
        self.assertEqual(reads, [])
        self.assertEqual(closes, [31, 30])

    def test_invalid_or_inaccessible_acl_is_denied_before_reading(self):
        for acl in (b'', credential_acl()[:-1], OSError(errno.EACCES, 'synthetic'),
                    OSError(errno.EPERM, 'synthetic'), OSError(errno.EIO, 'synthetic')):
            with self.subTest(acl=acl):
                _, reads, closes = self.synthetic_runtime(bad_acl=acl)
                self.assertEqual(reads, [])
                self.assertEqual(closes, [31, 30])

    def test_growth_after_stat_still_has_bounded_reads(self):
        _, reads, closes = self.synthetic_runtime(grow=True)
        self.assertEqual(sum(min(count, 19) for _, count in reads), gateway.BODY_LIMIT + 1)
        self.assertTrue(all(fd == 31 and 0 < count <= gateway.BODY_LIMIT + 1 for fd, count in reads))
        self.assertEqual(closes, [31, 30])

    def test_real_synthetic_file_replacement_reads_the_opened_inode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            policy_path = path / 'observer-policy'
            policy_path.write_text(json.dumps({'version': 1, 'applications': [APP]}))
            (path / 'observer-connection').write_text('{"version":1}')
            (path / 'observer-token').write_text(jwt())
            for filename in path.iterdir():
                filename.chmod(0o400)
            real_fstat = os.fstat
            replaced = False

            def metadata(fd):
                info = real_fstat(fd)
                return SimpleNamespace(st_uid=0, st_mode=info.st_mode, st_size=info.st_size)

            def getxattr(fd, key):
                nonlocal replaced
                if stat.S_ISREG(real_fstat(fd).st_mode) and not replaced:
                    replacement = path / 'replacement'
                    replacement.write_text('invalid replacement must never be read')
                    replacement.chmod(0o400)
                    os.replace(replacement, policy_path)
                    replaced = True
                raise OSError(errno.ENODATA, 'synthetic')

            # Fake only directory mode/owner; the actual file descriptors and
            # inode replacement remain real synthetic filesystem operations.
            def directory_metadata(fd):
                info = metadata(fd)
                if stat.S_ISDIR(info.st_mode):
                    info.st_mode = stat.S_IFDIR | 0o500
                return info

            with patch.object(gateway, 'CREDENTIAL_DIR', directory), \
                    patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': directory}), \
                    patch.object(gateway.os, 'geteuid', return_value=SERVICE_UID), \
                    patch.object(gateway.os, 'fstat', side_effect=directory_metadata), \
                    patch.object(gateway.os, 'getxattr', side_effect=getxattr), \
                    patch.object(gateway, 'connection', return_value=('synthetic', 443, None)):
                self.assertEqual(gateway.runtime()[0], {APP['id']: APP})
            self.assertTrue(replaced)

    def test_symlink_directory_file_and_nonblocking_fifo_are_denied_without_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            linked = path / 'linked'
            linked.symlink_to(path, target_is_directory=True)
            real_open = os.open
            real_validator = gateway.credential_metadata

            def safe_open(filename, flags, **kwargs):
                if filename == 'observer-policy':
                    self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(filename, flags, **kwargs)

            for target in (linked, path):
                for object_type in ('symlink', 'fifo'):
                    credential = path / 'observer-policy'
                    if object_type == 'symlink':
                        credential.symlink_to(path / 'missing')
                    else:
                        os.mkfifo(credential, 0o400)
                    try:
                        with patch.object(gateway, 'CREDENTIAL_DIR', str(target)), \
                                patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': str(target)}), \
                                patch.object(gateway.os, 'geteuid', return_value=SERVICE_UID), \
                                patch.object(gateway.os, 'open', side_effect=safe_open), \
                                patch.object(gateway.os, 'read') as read, \
                                patch.object(gateway, 'credential_metadata', wraps=gateway.credential_metadata) as validate:
                            # Permit the temporary directory's synthetic owner/mode
                            # while retaining the real validator for the FIFO.
                            validate.side_effect = lambda fd, service_uid, directory=False: (
                                os.fstat(fd) if directory else real_validator(fd, service_uid))
                            with self.assertRaises((gateway.Denied, OSError)):
                                gateway.runtime()
                            read.assert_not_called()
                    finally:
                        credential.unlink()

    def test_production_root_and_factory_uid_remain_denied(self):
        for service_uid in (0, 1000):
            with self.subTest(uid=service_uid), \
                    patch.object(gateway, 'installed_source'), patch.object(gateway, 'disable_dumping'), \
                    patch.object(gateway.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000)), \
                    patch.object(gateway.os, 'geteuid', return_value=service_uid), \
                    patch.object(gateway, 'runtime') as runtime, self.assertRaises(gateway.Denied):
                gateway.main()
            runtime.assert_not_called()


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


class TypedCollections(unittest.TestCase):
    def test_wire_items_support_deployment_controller_chain(self):
        rs = wire_item(fixture('ReplicaSet', 'sample-rs', 3, ('Deployment', 'sample-web', 2)))
        stale_rs = wire_item(fixture('ReplicaSet', 'stale-rs', 4, ('Deployment', 'sample-web', 99)))
        pods = [wire_item(fixture('Pod', 'sample-pod', 5, ('ReplicaSet', 'sample-rs', 3))),
                wire_item(fixture('Pod', 'stale-pod', 6, ('ReplicaSet', 'stale-rs', 4))),
                wire_item(fixture('Pod', 'wrong-uid', 7, ('ReplicaSet', 'sample-rs', 99)))]
        transport = Transport(children=[rs, stale_rs], pods=pods)
        projected = gateway.snapshot(APP, transport)['workloads'][0]
        self.assertEqual(projected['controllers'], [{'name': 'sample-rs', 'uid': uid(3)}])
        self.assertEqual([pod['name'] for pod in projected['pods']], ['sample-pod'])
        self.assertEqual(projected['pods'][0]['controller'],
                         {'kind': 'ReplicaSet', 'name': 'sample-rs', 'uid': uid(3)})
        self.assertTrue(projected['pods'][0]['ready'])
        self.assertNotIn(SECRET, gateway.encoded(projected).decode())
        self.assertEqual(len(transport.calls), 4)

    def test_wire_items_support_cronjob_and_direct_controller_chains(self):
        for kind in ('CronJob', 'ReplicaSet', 'StatefulSet', 'Job'):
            with self.subTest(kind=kind):
                app = deepcopy(APP)
                app['workloads'] = [{'kind': kind, 'name': 'sample-work'}]
                transport = Transport()
                transport.data[gateway.api_path(kind, 'sample-dev', 'sample-work')] = fixture(kind, 'sample-work', 2)
                parent = (kind, 'sample-work', 2)
                if kind == 'CronJob':
                    job = wire_item(fixture('Job', 'sample-child', 3, parent))
                    stale_job = wire_item(fixture('Job', 'stale-child', 4, ('CronJob', 'sample-work', 99)))
                    transport.data[gateway.api_path('Job', 'sample-dev') + '?limit=64'] = collection('Job', [job, stale_job])
                    parent = ('Job', 'sample-child', 3)
                good_pod = wire_item(fixture('Pod', 'sample-pod', 5, parent))
                stale_pod = wire_item(fixture('Pod', 'stale-pod', 6, (parent[0], parent[1], 99)))
                transport.data[gateway.api_path('Pod', 'sample-dev') + '?limit=64'] = collection('Pod', [good_pod, stale_pod])
                projected = gateway.snapshot(app, transport)['workloads'][0]
                self.assertEqual([pod['name'] for pod in projected['pods']], ['sample-pod'])
                self.assertEqual(projected['pods'][0]['controller'],
                                 {'kind': parent[0], 'name': parent[1], 'uid': uid(parent[2])})
                if kind == 'CronJob':
                    self.assertEqual(projected['controllers'], [{'name': 'sample-child', 'uid': uid(3)}])

    def test_absent_partial_and_explicit_item_metadata_are_copied(self):
        for kind in ('Pod', 'ReplicaSet', 'Job'):
            for omit in ((), ('kind',), ('apiVersion',), ('kind', 'apiVersion')):
                with self.subTest(kind=kind, omit=omit):
                    raw = fixture(kind, 'sample-item', 3)
                    for field in omit:
                        raw.pop(field)
                    page = collection(kind, [raw])
                    before = deepcopy(page)
                    result = gateway.objects(lambda path: page, kind, 'sample-dev')
                    self.assertEqual(result, [fixture(kind, 'sample-item', 3)])
                    self.assertEqual(page, before)
                    self.assertIsNot(result[0], raw)
                    gateway.identity(result[0], kind, 'sample-dev', 'sample-item')

    def test_empty_and_paginated_typed_collections(self):
        for kind in ('Pod', 'ReplicaSet', 'Job'):
            with self.subTest(kind=kind):
                empty = collection(kind)
                empty.pop('metadata')  # ListMeta remains optional without pagination.
                self.assertEqual(gateway.objects(lambda path: empty, kind, 'sample-dev'), [])
                first = collection(kind, [wire_item(fixture(kind, 'sample-one', 3))], 'next/+?=')
                second = collection(kind, [wire_item(fixture(kind, 'sample-two', 4))])
                pages = [first, second]
                before = deepcopy(pages)
                calls = []

                def get(path):
                    calls.append(path)
                    return pages[len(calls) - 1]

                result = gateway.objects(get, kind, 'sample-dev')
                self.assertEqual([item['metadata']['name'] for item in result], ['sample-one', 'sample-two'])
                self.assertTrue(all(item['kind'] == kind and item['apiVersion'] == api_version(kind)
                                    for item in result))
                self.assertEqual(calls, [gateway.api_path(kind, 'sample-dev') + '?limit=64',
                                         gateway.api_path(kind, 'sample-dev') + '?limit=64&continue=next%2F%2B%3F%3D'])
                self.assertEqual(pages, before)

    def test_collection_type_metadata_must_match_endpoint_on_every_page(self):
        for kind in ('Pod', 'ReplicaSet', 'Job'):
            for field, bad in (('kind', None), ('kind', 'List'), ('kind', 'SecretList'),
                               ('apiVersion', None), ('apiVersion', ''), ('apiVersion', 'other/v1'),
                               ('apiVersion', 'v1' if api_version(kind) != 'v1' else 'apps/v1')):
                with self.subTest(kind=kind, field=field, bad=bad):
                    invalid = collection(kind)
                    invalid[field] = bad
                    for pages in ([invalid], [collection(kind, continuation='next'), invalid]):
                        with self.assertRaises(gateway.Denied) as failure:
                            gateway.objects(lambda path: pages.pop(0), kind, 'sample-dev')
                        self.assertEqual(failure.exception.code, 'unavailable')
            for field in ('kind', 'apiVersion'):
                with self.subTest(kind=kind, missing=field):
                    page = collection(kind)
                    page.pop(field)
                    with self.assertRaises(gateway.Denied):
                        gateway.objects(lambda path: page, kind, 'sample-dev')

    def test_conflicting_item_type_metadata_and_nonobjects_are_denied(self):
        for kind in ('Pod', 'ReplicaSet', 'Job'):
            for field, value in (('kind', None), ('kind', ''), ('kind', 'Secret'), ('kind', True),
                                 ('apiVersion', None), ('apiVersion', ''), ('apiVersion', 'other/v1'),
                                 ('apiVersion', ['v1'])):
                with self.subTest(kind=kind, field=field, value=value):
                    raw = wire_item(fixture(kind, 'sample-item', 3))
                    raw[field] = value
                    page = collection(kind, [raw])
                    before = deepcopy(page)
                    with self.assertRaises(gateway.Denied):
                        gateway.objects(lambda path: page, kind, 'sample-dev')
                    self.assertEqual(page, before)
            for raw in (None, [], 'Pod', True, 1):
                with self.subTest(kind=kind, item=raw), self.assertRaises(gateway.Denied):
                    gateway.objects(lambda path: collection(kind, [raw]), kind, 'sample-dev')

    def test_malformed_list_metadata_and_items_are_denied(self):
        for page in (None, [], 'PodList', {'kind': 'PodList', 'apiVersion': 'v1'},
                     dict(collection('Pod'), items=None), dict(collection('Pod'), items={}),
                     dict(collection('Pod'), metadata=None), dict(collection('Pod'), metadata=[]),
                     collection('Pod', continuation=None), collection('Pod', continuation=True),
                     collection('Pod', continuation='x' * 2049)):
            with self.subTest(page=page), self.assertRaises(gateway.Denied):
                gateway.objects(lambda path: page, 'Pod', 'sample-dev')

    def test_wire_items_keep_namespace_name_and_uid_validation(self):
        for kind, changes in (('ReplicaSet', {'namespace': 'other'}),
                               ('Pod', {'namespace': 'other'}),
                               ('ReplicaSet', {'name': '../escape'}),
                               ('Pod', {'name': '../escape'}),
                               ('ReplicaSet', {'uid': None}), ('Pod', {'uid': 'invalid-uid'})):
            with self.subTest(kind=kind, changes=changes):
                rs = wire_item(fixture('ReplicaSet', 'sample-rs', 3, ('Deployment', 'sample-web', 2)))
                pod = wire_item(fixture('Pod', 'sample-pod', 5, ('ReplicaSet', 'sample-rs', 3)))
                (rs if kind == 'ReplicaSet' else pod)['metadata'].update(changes)
                with self.assertRaises(gateway.Denied):
                    gateway.snapshot(APP, Transport(children=[rs], pods=[pod]))

    def test_named_objects_do_not_inherit_collection_type(self):
        for kind in ('Application', 'Deployment'):
            for changes in ({'kind': None}, {'kind': 'Pod'}, {'name': 'other'},
                            {'namespace': 'other'}, {'uid': 'invalid-uid'}, {'kind': 'missing'}):
                with self.subTest(kind=kind, changes=changes):
                    transport = Transport()
                    path = gateway.api_path(kind, 'argocd' if kind == 'Application' else 'sample-dev',
                                            'sample-app' if kind == 'Application' else 'sample-web')
                    raw = transport.data[path]
                    if 'kind' in changes:
                        if changes['kind'] == 'missing':
                            raw.pop('kind')
                        else:
                            raw['kind'] = changes['kind']
                    else:
                        raw['metadata'].update(changes)
                    with self.assertRaises(gateway.Denied):
                        gateway.snapshot(APP, transport)

    def test_wire_items_reject_invalid_controller_identity(self):
        for changes in ({'uid': 'invalid-uid'}, {'name': '../escape'}, {'kind': None},
                        {'controller': 1}):
            with self.subTest(changes=changes):
                rs = wire_item(fixture('ReplicaSet', 'sample-rs', 3, ('Deployment', 'sample-web', 2)))
                pod = wire_item(fixture('Pod', 'sample-pod', 5, ('ReplicaSet', 'sample-rs', 3)))
                pod['metadata']['ownerReferences'][0].update(changes)
                with self.assertRaises(gateway.Denied):
                    gateway.snapshot(APP, Transport(children=[rs], pods=[pod]))


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
                    transport.data[gateway.api_path('Job', 'sample-dev') + '?limit=64'] = collection('Job', [job])
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
                transport.data[gateway.api_path(child_kind, 'sample-dev') + '?limit=64'] = collection(child_kind, children)
                transport.data[gateway.api_path('Pod', 'sample-dev') + '?limit=64'] = collection('Pod', pods)
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
                    transport.data[gateway.api_path('Job', 'sample-dev') + '?limit=64'] = collection('Job')
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
            return collection('Pod', continuation=str(len(calls)))
        with self.assertRaises(gateway.Denied) as failure:
            gateway.objects(get, 'Pod', 'sample-dev')
        self.assertEqual(failure.exception.code, 'limit_exceeded')
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[1], '/api/v1/namespaces/sample-dev/pods?limit=64&continue=1')
        with self.assertRaises(gateway.Denied):
            gateway.objects(lambda path: collection('Pod', [{}] * 65), 'Pod', 'sample-dev')
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
