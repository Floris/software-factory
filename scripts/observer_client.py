"""Non-root client of the fixed installed observer socket; no API credentials."""
import argparse
import grp
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import time

SOCKET = Path('/run/software-factory-observer/status.sock')
INSTALLED = Path('/usr/local/lib/software-factory/observer_client.py')
LIMIT, SECONDS = 65536, 15
ERRORS = {'invalid_request', 'unavailable', 'access_denied', 'limit_exceeded', 'rate_limited'}


class Unavailable(Exception):
    pass


def trusted_path(path, socket_path=False):
    for current in (*reversed(path.parents), path):
        info = current.lstat()
        final_socket = current == path and socket_path
        valid_kind = stat.S_ISSOCK(info.st_mode) if final_socket else (
            stat.S_ISREG(info.st_mode) if current == path else stat.S_ISDIR(info.st_mode))
        if info.st_uid != 0 or not valid_kind or (not final_socket and info.st_mode & 0o022):
            raise Unavailable()
        if final_socket and (stat.S_IMODE(info.st_mode) != 0o660 or info.st_gid != grp.getgrnam('codex').gr_gid):
            raise Unavailable()
        if socket_path and current == path.parent and (
            stat.S_IMODE(info.st_mode) != 0o750 or info.st_gid != grp.getgrnam('codex').gr_gid
        ):
            raise Unavailable()


def decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Unavailable()
            result[key] = value
        return result
    def invalid(value):
        raise Unavailable()
    value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1 or type(value.get('ok')) is not bool:
        raise Unavailable()
    if value['ok']:
        if set(value) != {'version', 'ok', 'status'} or not isinstance(value['status'], dict):
            raise Unavailable()
    elif set(value) != {'version', 'ok', 'error'} or value['error'] not in ERRORS:
        raise Unavailable()
    return value


def status(application, path=SOCKET, seconds=SECONDS):
    if not isinstance(application, str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', application):
        raise Unavailable()
    data = json.dumps({'version': 1, 'op': 'status', 'application': application}).encode()
    if len(data) > 256:
        raise Unavailable()
    trusted_path(path, socket_path=True)
    deadline = time.monotonic() + seconds
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
        channel.settimeout(max(0.001, deadline - time.monotonic()))
        channel.connect(str(path))
        channel.settimeout(max(0.001, deadline - time.monotonic()))
        channel.sendall(data)
        channel.shutdown(socket.SHUT_WR)
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Unavailable()
            channel.settimeout(remaining)
            chunk = channel.recv(min(4096, LIMIT - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > LIMIT:
                raise Unavailable()
            chunks.append(chunk)
    return decode(b''.join(chunks))


def main():
    parser = argparse.ArgumentParser(description='Read one configured application status through the observer gateway')
    parser.add_argument('--application', required=True)
    args = parser.parse_args()
    try:
        if Path(__file__) != INSTALLED or os.geteuid() == 0:
            raise Unavailable()
        trusted_path(INSTALLED)
        result = status(args.application)
    except Exception:
        result = {'version': 1, 'ok': False, 'error': 'unavailable'}
    print(json.dumps(result, separators=(',', ':')))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
