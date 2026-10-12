"""One opt-in ntfy channel. Secrets stay in an ACL-protected local file."""
import json
import os
import re
import threading
import time
import httpx
from contextlib import contextmanager
from urllib.parse import urlparse

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from roll.accounts.ledger import encode
from roll.runtime.backups import private_directory, persist


class ChannelUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_version: int = Field(ge=0)
    enabled: bool
    server: str | None = Field(default=None, max_length=2048)
    topic: str | None = Field(default=None, max_length=64)
    app_base_url: str | None = Field(default=None, max_length=2048)
    token: str | None = Field(default=None, max_length=4096)
    clear_auth: bool = False


def origin(value):
    p = urlparse(value)
    try: return p.scheme.lower(), p.hostname.lower(), p.port or (443 if p.scheme == 'https' else 80)
    except (ValueError, AttributeError): raise HTTPException(422, 'CHANNEL_URL_INVALID')


def safe_url(value):
    try: p = urlparse(value)
    except ValueError: raise HTTPException(422, 'CHANNEL_URL_INVALID') from None
    if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise HTTPException(422, 'CHANNEL_URL_INVALID')
    origin(value)
    return value.rstrip('/')


class NotificationChannel:
    def __init__(self, directory, transport=None):
        self.directory = directory / 'notification-private'
        private_directory(self.directory)
        self.path, self.lock_path = self.directory / 'channel.json', self.directory / 'channel.lock'
        self.local_lock = threading.Lock()
        self.transport = transport

    @contextmanager
    def locked(self):
        with self.local_lock:
            with self.lock_path.open('a+b') as stream:
                stream.seek(0)
                if not stream.read(1): stream.write(b'0'); stream.flush()
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try: yield
                finally:
                    stream.seek(0)
                    if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def configuration(self):
        if not self.path.exists():
            return {'version': 0, 'enabled': False, 'server': '', 'topic': '', 'app_base_url': '', 'token': None}
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError): raise HTTPException(503, 'CHANNEL_CONFIGURATION_UNAVAILABLE')

    @staticmethod
    def masked(value):
        return {'adapter': 'NTFY_JSON_V1', 'version': value['version'], 'enabled': value['enabled'],
                'server': value['server'], 'topic_configured': bool(value['topic']), 'topic': '',
                'app_base_url': value['app_base_url'], 'auth_configured': bool(value['token']),
                'delivery_status': 'UNKNOWN', 'real_channel_acceptance': 'PENDING_USER_CONFIGURATION'}

    def get(self): return self.masked(self.configuration())

    def save(self, raw):
        try: command = ChannelUpdate.model_validate(raw)
        except ValidationError as error:
            # No input/context is returned: FastAPI's default validation detail
            # could otherwise echo the submitted authentication value.
            raise HTTPException(422, {'code': 'CHANNEL_CONFIG_INVALID', 'fields': sorted({str(e['loc'][0]) if e['loc'] and e['loc'][0] in ChannelUpdate.model_fields else 'unknown_field' for e in error.errors()})}) from None
        if command.token and (command.clear_auth or '\r' in command.token or '\n' in command.token):
            raise HTTPException(422, 'CHANNEL_AUTH_UPDATE_INVALID')
        with self.locked():
            value = self.configuration()
            if command.expected_version != value['version']: raise HTTPException(409, 'CHANNEL_CONFIG_VERSION_CONFLICT')
            new_server = safe_url(command.server) if command.server is not None else value['server']
            if value['token'] and value['server'] and new_server and origin(value['server']) != origin(new_server) and not command.clear_auth and not command.token:
                raise HTTPException(409, 'CHANNEL_ORIGIN_CHANGE_REQUIRES_NEW_OR_CLEARED_AUTH')
            topic = command.topic if command.topic is not None else value['topic']
            if topic and not re.fullmatch(r'[-_A-Za-z0-9]{1,64}', topic): raise HTTPException(422, 'CHANNEL_TOPIC_INVALID')
            app_base = safe_url(command.app_base_url) if command.app_base_url is not None else value['app_base_url']
            if command.enabled and (not new_server or not topic or not app_base): raise HTTPException(422, 'CHANNEL_CONFIG_INCOMPLETE')
            value = {'version': value['version'] + 1, 'enabled': command.enabled, 'server': new_server,
                     'topic': topic, 'app_base_url': app_base,
                     'token': None if command.clear_auth else command.token or value['token']}
            try: persist(self.path, encode(value).encode())
            except OSError: raise HTTPException(503, 'CHANNEL_CONFIG_SAVE_FAILED') from None
            return self.masked(value)

    def publish(self, configuration, body):
        # Test processes cannot accidentally use real destinations without an
        # explicitly injected transport. OS tests use only their owned loopback.
        if os.environ.get('ROLL_ENV') == 'test' and self.transport is None and origin(configuration['server'])[1] not in {'localhost', '127.0.0.1', '::1'}:
            return {'status': 'NOT_SENT', 'error_code': 'TEST_EXTERNAL_CHANNEL_REFUSED'}
        payload = {**body, 'topic': configuration['topic']}
        headers = {'authorization': 'Bearer ' + configuration['token']} if configuration['token'] else {}
        started = time.monotonic()
        try:
            with httpx.Client(transport=self.transport, timeout=httpx.Timeout(connect=2, read=3, write=2, pool=1), follow_redirects=False) as client:
                with client.stream('POST', configuration['server'] + '/', json=payload, headers=headers) as response:
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 65536 or time.monotonic() - started > 10:
                            return {'status': 'RESULT_UNKNOWN', 'error_code': 'CHANNEL_RESPONSE_LIMIT'}
                    if response.status_code not in {200, 201}:
                        return {'status': 'FAILED', 'error_code': 'CHANNEL_HTTP_REJECTED', 'http_status': response.status_code}
                    result = json.loads(raw)
                    if not isinstance(result, dict) or result.get('event') != 'message' or not isinstance(result.get('id'), str) or not re.fullmatch(r'[-_A-Za-z0-9]{1,128}', result['id']):
                        return {'status': 'RESULT_UNKNOWN', 'error_code': 'CHANNEL_RECEIPT_INVALID'}
                    if configuration['token'] and configuration['token'] in result['id']:
                        return {'status': 'RESULT_UNKNOWN', 'error_code': 'CHANNEL_RECEIPT_REDACTED'}
                    return {'status': 'CHANNEL_ACCEPTED', 'provider_id': result['id'],
                            'provider_time': result.get('time') if type(result.get('time')) is int and 0 <= result['time'] <= 253402300799 else None}
        except (httpx.ConnectError, httpx.ConnectTimeout): return {'status': 'NOT_SENT', 'error_code': 'CHANNEL_CONNECT_FAILED'}
        except (httpx.HTTPError, ValueError): return {'status': 'RESULT_UNKNOWN', 'error_code': 'CHANNEL_REQUEST_UNCERTAIN'}
        except Exception:
            # Transport/runtime failures must not bubble request headers or
            # credentials into the worker's generic exception log.
            return {'status': 'RESULT_UNKNOWN', 'error_code': 'CHANNEL_RUNTIME_ERROR'}
