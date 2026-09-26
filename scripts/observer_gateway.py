"""Socket-activated, credential-isolated status projection; Python stdlib only."""
import base64
import ctypes
from datetime import datetime, timezone
import errno
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import socket
import ssl
import stat
import struct
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit

INSTALLED = Path('/usr/local/lib/software-factory/observer_gateway.py')
CREDENTIAL_DIR = '/run/credentials/software-factory-observer.service'
SOCKET = '/run/software-factory-observer/status.sock'
REQUEST_LIMIT, OUTPUT_LIMIT, BODY_LIMIT = 256, 65536, 262144
PAGE_SIZE, PAGE_LIMIT, OBJECT_LIMIT = 64, 4, 256
REQUEST_SECONDS, FRAME_SECONDS, IDLE_SECONDS = 10, 2, 30
KINDS = {'Deployment': 'deployments', 'ReplicaSet': 'replicasets',
         'StatefulSet': 'statefulsets', 'Job': 'jobs', 'CronJob': 'cronjobs'}
ERRORS = {'invalid_request', 'unavailable', 'access_denied', 'limit_exceeded', 'rate_limited'}
NAME = re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\Z')
UID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')
IMAGE = re.compile(
    r'(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?/)?'
    r'[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*'
    r'(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?(?:@sha256:[0-9a-f]{64})?\Z'
)


class Denied(Exception):
    def __init__(self, code='unavailable'):
        self.code = code if code in ERRORS else 'unavailable'


def require(value, code='unavailable'):
    if not value:
        raise Denied(code)


def strict_json(data, limit=BODY_LIMIT):
    require(len(data) <= limit, 'limit_exceeded')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result

    def invalid(value):
        raise Denied()

    try:
        result = json.loads(data, object_pairs_hook=unique, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise Denied() from None
    require(isinstance(result, dict))
    return result


def name(value):
    require(isinstance(value, str) and NAME.fullmatch(value))
    return value


def integer(value):
    require(type(value) is int and 0 <= value <= 1000000000)
    return value


def request(data):
    try:
        require(data == data.strip())
        value = strict_json(data, REQUEST_LIMIT)
        require(set(value) == {'version', 'op', 'application'})
        require(type(value['version']) is int and value['version'] == 1 and value['op'] == 'status')
        name(value['application'])
        return value
    except Denied:
        raise Denied('invalid_request') from None


def policy(document):
    require(set(document) == {'version', 'applications'} and type(document['version']) is int
            and document['version'] == 1)
    apps = document['applications']
    require(isinstance(apps, list) and 1 <= len(apps) <= 32)
    result = {}
    for app in apps:
        require(isinstance(app, dict) and set(app) == {'id', 'argocd_namespace', 'namespace', 'workloads'})
        for key in ('id', 'argocd_namespace', 'namespace'):
            name(app[key])
        require(app['id'] not in result)
        require(isinstance(app['workloads'], list) and len(app['workloads']) <= 16)
        identities = set()
        for workload in app['workloads']:
            require(isinstance(workload, dict) and set(workload) == {'kind', 'name'})
            require(workload['kind'] in KINDS)
            name(workload['name'])
            identity = (workload['kind'], workload['name'])
            require(identity not in identities)
            identities.add(identity)
        result[app['id']] = app
    return result


def connection(document):
    require(set(document) == {'version', 'server', 'ca_data'} and type(document['version']) is int
            and document['version'] == 1)
    require(isinstance(document['server'], str) and len(document['server']) <= 512)
    url = urlsplit(document['server'])
    require(url.scheme == 'https' and url.hostname and url.path in ('', '/')
            and not url.username and not url.password and not url.query and not url.fragment)
    try:
        port = url.port or 443
        require(1 <= port <= 65535)
        ca = base64.b64decode(document['ca_data'], validate=True).decode('ascii')
        require(len(ca) <= 65536 and '-----BEGIN CERTIFICATE-----' in ca)
        context = ssl.create_default_context(cadata=ca)
    except (ValueError, TypeError, UnicodeError, ssl.SSLError):
        raise Denied() from None
    return url.hostname, port, context


def check_metadata(info, kind, owner, mode=None):
    require(info.st_uid == owner and kind(info.st_mode))
    if mode is None:
        require(not info.st_mode & 0o022)
    else:
        require(stat.S_IMODE(info.st_mode) == mode)


def credential_metadata(fd, service_uid, directory=False):
    """Validate an opened credential inode, without reading credential bytes.

    Operator verifiers must pass the verified service UID, even when run as
    root. The Linux ACL's group mode bits describe its mask, not group access.
    """
    require(type(service_uid) is int and 0 < service_uid < 0xffffffff)
    try:
        info = os.fstat(fd)
    except OSError:
        raise Denied() from None
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    require(kind(info.st_mode) and info.st_uid in (0, service_uid))
    mode = stat.S_IMODE(info.st_mode)
    try:
        acl = os.getxattr(fd, 'system.posix_acl_access')
    except OSError as failure:
        # Only an absent/unsupported ACL permits the strictly private fallback.
        require(failure.errno in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP))
        require(mode in ((0o500, 0o700) if directory else (0o400,)))
    else:
        require(info.st_uid == 0 and mode == (0o550 if directory else 0o440))
        # Linux posix_acl_xattr: little-endian version 2, five canonical entries
        # (tag, permissions, ID). Unqualified tags must use ACL_UNDEFINED_ID.
        require(isinstance(acl, bytes) and len(acl) == 44
                and struct.unpack_from('<I', acl)[0] == 2)
        access, undefined = (5 if directory else 4), 0xffffffff
        require(tuple(struct.iter_unpack('<HHI', acl[4:])) == (
            (0x01, access, undefined), (0x02, access, service_uid),
            (0x04, 0, undefined), (0x10, access, undefined),
            (0x20, 0, undefined),
        ))
    return info


def installed_source():
    require(Path(__file__) == INSTALLED)
    for path in (*reversed(INSTALLED.parents), INSTALLED):
        check_metadata(path.lstat(), stat.S_ISREG if path == INSTALLED else stat.S_ISDIR, 0)


def disable_dumping():
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    prctl.restype = ctypes.c_int
    require(prctl(4, 0, 0, 0, 0) == 0)  # Linux PR_SET_DUMPABLE=0, before private reads.


def validate_token(token):
    require(re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token))
    payload = token.split('.')[1]
    try:
        claims = strict_json(base64.b64decode(payload + '=' * (-len(payload) % 4), altchars=b'-_', validate=True), 8192)
        require(claims.get('sub') == 'system:serviceaccount:argocd:factory-observer')
        kubernetes = claims.get('kubernetes.io', {})
        require(kubernetes.get('namespace') == 'argocd'
                and kubernetes.get('serviceaccount', {}).get('name') == 'factory-observer')
        require(type(claims.get('exp')) is int and claims['exp'] > time.time())
        for key in ('nbf', 'iat'):
            if key in claims:
                require(type(claims[key]) is int and claims[key] <= time.time() + 5)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        raise Denied('access_denied') from None
    except Denied:
        raise Denied('access_denied') from None
    # This is identity/expiry consistency checking, not JWT signature validation.
    # The verified TLS Kubernetes API remains the authentication authority.
    return token


def runtime():
    require(os.environ.get('CREDENTIALS_DIRECTORY') == CREDENTIAL_DIR)
    service_uid = os.geteuid()
    directory_fd = os.open(CREDENTIAL_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)

    def read(filename, limit):
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=directory_fd)
        try:
            info = credential_metadata(fd, service_uid)
            require(0 <= info.st_size <= limit)
            chunks, size = [], 0
            while True:
                chunk = os.read(fd, limit + 1 - size)
                if not chunk:
                    return b''.join(chunks)
                chunks.append(chunk)
                size += len(chunk)
                require(size <= limit)
        finally:
            os.close(fd)

    try:
        credential_metadata(directory_fd, service_uid, directory=True)
        configured = policy(strict_json(read('observer-policy', BODY_LIMIT)))
        transport = connection(strict_json(read('observer-connection', BODY_LIMIT)))
        try:
            token = read('observer-token', 16384).decode('ascii').strip()
        except UnicodeError:
            raise Denied() from None
    finally:
        os.close(directory_fd)
    require(token and len(token) <= 16384 and all(33 <= ord(c) <= 126 for c in token))
    return configured, transport, validate_token(token)


def fetcher(transport, token):
    host, port, context = transport

    def get(path, absent=False):
        # HTTPConnection uses neither proxy environment nor redirects.
        channel = http.client.HTTPSConnection(host, port, context=context, timeout=3)
        try:
            channel.request('GET', path, headers={'Authorization': 'Bearer ' + token,
                                                'Accept': 'application/json'})
            response = channel.getresponse()
            if response.status in (401, 403):
                raise Denied('access_denied')
            if response.status == 404 and absent:
                return None
            require(response.status == 200)
            data = response.read(BODY_LIMIT + 1)
            return strict_json(data)
        finally:
            channel.close()
    return get


def api_path(kind, namespace, resource_name=None):
    require(kind in KINDS or kind in ('Pod', 'Application'))
    name(namespace)
    if kind == 'Application':
        prefix, plural = '/apis/argoproj.io/v1alpha1', 'applications'
    elif kind == 'Pod':
        prefix, plural = '/api/v1', 'pods'
    else:
        prefix = '/apis/' + ('batch' if kind in ('Job', 'CronJob') else 'apps') + '/v1'
        plural = KINDS[kind]
    path = f'{prefix}/namespaces/{namespace}/{plural}'
    return path + '/' + name(resource_name) if resource_name is not None else path


def objects(get, kind, namespace):
    result, seen = [], set()
    continuation = ''
    for _ in range(PAGE_LIMIT):
        path = api_path(kind, namespace) + f'?limit={PAGE_SIZE}'
        if continuation:
            path += '&continue=' + quote(continuation, safe='')
        page = get(path)
        require(page.get('kind') == kind + 'List' and isinstance(page.get('items'), list))
        require(len(page['items']) <= PAGE_SIZE, 'limit_exceeded')
        result.extend(page['items'])
        require(len(result) <= OBJECT_LIMIT, 'limit_exceeded')
        continuation = page.get('metadata', {}).get('continue', '')
        require(isinstance(continuation, str) and len(continuation) <= 2048)
        if not continuation:
            return result
        require(continuation not in seen, 'limit_exceeded')
        seen.add(continuation)
    raise Denied('limit_exceeded')


def identity(obj, kind, namespace, expected_name=None):
    require(isinstance(obj, dict) and obj.get('kind') == kind)
    metadata = obj['metadata']
    require(metadata['namespace'] == namespace)
    value = {'name': name(metadata['name']), 'uid': metadata['uid']}
    require(isinstance(value['uid'], str) and UID.fullmatch(value['uid']))
    if expected_name is not None:
        require(value['name'] == expected_name)
    return value


def owner(obj, parents):
    references = obj.get('metadata', {}).get('ownerReferences', [])
    require(isinstance(references, list) and len(references) <= 8)
    for ref in references:
        require(isinstance(ref, dict) and isinstance(ref.get('uid'), str) and UID.fullmatch(ref['uid']))
        name(ref.get('name'))
        require(isinstance(ref.get('kind'), str) and re.fullmatch(r'[A-Z][A-Za-z0-9]{0,63}', ref['kind']))
        require('controller' not in ref or type(ref['controller']) is bool)
    controllers = [r for r in references if r.get('controller') is True]
    require(len(controllers) <= 1)
    if not controllers:
        return False
    ref = controllers[0]
    return (ref.get('kind'), ref.get('name'), ref.get('uid')) in parents


def image(value):
    require(isinstance(value, str) and len(value) <= 256 and IMAGE.fullmatch(value))
    return value


def pod_summary(pod, namespace, parents):
    result = identity(pod, 'Pod', namespace)
    require(owner(pod, parents))
    controller, = [ref for ref in pod['metadata']['ownerReferences'] if ref.get('controller') is True]
    result['controller'] = {key: controller[key] for key in ('kind', 'name', 'uid')}
    deletion = pod['metadata'].get('deletionTimestamp')
    require(deletion is None or isinstance(deletion, str) and 1 <= len(deletion) <= 64)
    result['deleting'] = deletion is not None
    status = pod.get('status', {})
    phase = status.get('phase', 'Unknown')
    require(phase in ('Pending', 'Running', 'Succeeded', 'Failed', 'Unknown'))
    conditions = status.get('conditions', [])
    require(isinstance(conditions, list) and len(conditions) <= 32)
    ready = [c['status'] for c in conditions if isinstance(c, dict) and c.get('type') == 'Ready']
    require(len(ready) <= 1 and all(v in ('True', 'False', 'Unknown') for v in ready))
    result.update(phase=phase, ready=None if not ready or ready[0] == 'Unknown' else ready[0] == 'True')
    containers = status.get('containerStatuses', [])
    require(isinstance(containers, list) and len(containers) <= 16)
    result['containers'] = []
    for container in containers:
        require(type(container['ready']) is bool)
        raw_digest = container.get('imageID', '')
        require(isinstance(raw_digest, str) and len(raw_digest) <= 512)
        digest = re.search(r'sha256:[0-9a-f]{64}\Z', raw_digest) if raw_digest else None
        require(not raw_digest or digest)
        result['containers'].append({'name': name(container['name']), 'image': image(container['image']),
                                     'digest': digest.group() if digest else None,
                                     'restarts': integer(container['restartCount']), 'ready': container['ready']})
    return result


def snapshot(app, get):
    namespace = app['namespace']
    application = get(api_path('Application', app['argocd_namespace'], app['id']))
    app_identity = identity(application, 'Application', app['argocd_namespace'], app['id'])
    status = application.get('status', {})
    health = status.get('health', {}).get('status', 'Unknown')
    sync = status.get('sync', {}).get('status', 'Unknown')
    revision = status.get('sync', {}).get('revision')
    require(health in ('Healthy', 'Progressing', 'Degraded', 'Suspended', 'Missing', 'Unknown'))
    require(sync in ('Synced', 'OutOfSync', 'Unknown'))
    require(revision is None or isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{40}', revision))
    app_identity.update(namespace=app['argocd_namespace'], health=health, sync=sync, revision=revision)
    result = {'application': app_identity, 'workloads': [],
              'observedAt': datetime.now(timezone.utc).isoformat()}
    cache = {}

    def listing(kind):
        if kind not in cache:
            cache[kind] = objects(get, kind, namespace)
        return cache[kind]

    for configured in app['workloads']:
        kind, configured_name = configured['kind'], configured['name']
        raw = get(api_path(kind, namespace, configured_name), absent=True)
        item = {'kind': kind, 'namespace': namespace, 'name': configured_name, 'present': raw is not None}
        result['workloads'].append(item)
        if raw is None:
            continue
        item.update(identity(raw, kind, namespace, configured_name))
        item['generation'] = integer(raw['metadata']['generation'])
        workload_status = raw.get('status', {})
        item['status'] = {key: integer(workload_status[key]) for key in
                          ('observedGeneration', 'replicas', 'readyReplicas', 'availableReplicas', 'active', 'succeeded', 'failed')
                          if key in workload_status and not (kind == 'CronJob' and key == 'active')}
        if kind == 'CronJob' and 'active' in workload_status:
            active = workload_status['active']
            require(isinstance(active, list) and len(active) <= PAGE_SIZE, 'limit_exceeded')
            references = set()
            for ref in active:
                require(isinstance(ref, dict) and ref.get('kind', 'Job') == 'Job')
                identity({'kind': 'Job', 'metadata': ref}, 'Job', namespace)
                reference = (ref['name'], ref['uid'])
                require(reference not in references)
                references.add(reference)
            item['status']['active'] = len(active)
        spec = raw['spec']
        if kind in ('Deployment', 'StatefulSet'):
            item['desiredReplicas'] = integer(spec['replicas']) if 'replicas' in spec else None
        if kind in ('CronJob', 'Job'):
            require('suspend' not in spec or type(spec['suspend']) is bool)
            item['suspend'] = spec.get('suspend')
        template = spec['jobTemplate']['spec']['template'] if kind == 'CronJob' else spec['template']
        containers = template['spec']['containers']
        require(isinstance(containers, list) and 1 <= len(containers) <= 16)
        item['images'] = [{'name': name(c['name']), 'image': image(c['image'])} for c in containers]
        parents = {(kind, configured_name, item['uid'])}
        if kind in ('Deployment', 'CronJob'):
            child_kind = 'ReplicaSet' if kind == 'Deployment' else 'Job'
            children = []
            for child in listing(child_kind):
                identity(child, child_kind, namespace)
                if owner(child, parents):
                    children.append(identity(child, child_kind, namespace))
            parents = {(child_kind, c['name'], c['uid']) for c in children}
            item['controllers'] = children
        item['pods'] = []
        for pod in listing('Pod'):
            identity(pod, 'Pod', namespace)
            if owner(pod, parents):
                item['pods'].append(pod_summary(pod, namespace, parents))
    return result


def encoded(value, token=None):
    data = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    require(len(data) <= OUTPUT_LIMIT, 'limit_exceeded')
    require(token is None or token.encode() not in data)
    return data


def error(code='unavailable'):
    return encoded({'version': 1, 'ok': False, 'error': code if code in ERRORS else 'unavailable'})


def collect(data):
    configured, transport, token = runtime()
    value = request(data)
    require(value['application'] in configured, 'invalid_request')
    summary = snapshot(configured[value['application']], fetcher(transport, token))
    return encoded({'version': 1, 'ok': True, 'status': summary}, token)


def run_collector(data):
    try:
        completed = subprocess.run(
            ['/usr/bin/python3', '-I', '-B', '-S', str(INSTALLED), '--collect'],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={'CREDENTIALS_DIRECTORY': CREDENTIAL_DIR}, close_fds=True,
            timeout=REQUEST_SECONDS, check=False,
        )
        require(completed.returncode == 0 and len(completed.stdout) <= OUTPUT_LIMIT)
        value = strict_json(completed.stdout, OUTPUT_LIMIT)
        require(type(value.get('version')) is int and value['version'] == 1 and type(value.get('ok')) is bool)
        if value['ok']:
            require(set(value) == {'version', 'ok', 'status'} and isinstance(value['status'], dict))
        else:
            require(set(value) == {'version', 'ok', 'error'} and value['error'] in ERRORS)
        return completed.stdout
    except (Exception,):
        return error()


def frame(channel, limit=REQUEST_LIMIT, seconds=FRAME_SECONDS):
    deadline, chunks, size = time.monotonic() + seconds, [], 0
    while True:
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'invalid_request')
        channel.settimeout(remaining)
        chunk = channel.recv(min(4096, limit - size + 1))
        if not chunk:
            return b''.join(chunks)
        size += len(chunk)
        require(size <= limit, 'invalid_request')
        chunks.append(chunk)


def serve(listener, allowed_uid, collector=run_collector, idle_seconds=IDLE_SECONDS):
    # Accept=no: one broker, one synchronous collector, bounded queued callers.
    listener.settimeout(idle_seconds)
    last_collection = -float('inf')
    while True:
        try:
            channel, _ = listener.accept()
        except socket.timeout:
            return
        with channel:
            try:
                _, uid, _ = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                require(uid == allowed_uid, 'invalid_request')
                data = frame(channel)
                request(data)
                require(time.monotonic() - last_collection >= 1, 'rate_limited')
                last_collection = time.monotonic()
                response = collector(data)
            except Denied as failure:
                response = error(failure.code)
            except Exception:
                response = error()
            try:
                channel.settimeout(FRAME_SECONDS)
                channel.sendall(response)
            except (OSError, TimeoutError):
                pass


def main():
    installed_source()
    disable_dumping()
    factory_uid = pwd.getpwnam('codex').pw_uid
    require(os.geteuid() not in (0, factory_uid))
    if sys.argv[1:] == ['--collect']:
        try:
            output = collect(sys.stdin.buffer.read(REQUEST_LIMIT + 1))
        except Denied as failure:
            output = error(failure.code)
        except Exception:
            output = error()
        sys.stdout.buffer.write(output)
        return
    require(sys.argv[1:] == [])
    require(os.environ.get('LISTEN_PID') == str(os.getpid()) and os.environ.get('LISTEN_FDS') == '1')
    listener = socket.socket(fileno=3)
    require(listener.family == socket.AF_UNIX and listener.type == socket.SOCK_STREAM)
    require(listener.getsockname() == SOCKET and listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 1)
    with listener:
        serve(listener, factory_uid)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Do not print tracebacks, upstream bodies, headers or credentials.
        sys.exit(1)
