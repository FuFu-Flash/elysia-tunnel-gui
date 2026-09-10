"""Atomic local profiles with Windows user-bound protection for saved tokens."""
import base64
import ctypes
import json
import os
from pathlib import Path
import tempfile


class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def crypt_token(value, decrypt=False):
    if not value:
        return ''
    raw = base64.b64decode(value, validate=True) if decrypt else value.encode('utf-8')
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    name = 'CryptUnprotectData' if decrypt else 'CryptProtectData'
    function = getattr(crypt, name)
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        result = ctypes.string_at(output.data, output.size)
        return result.decode('utf-8') if decrypt else base64.b64encode(result).decode('ascii')
    finally:
        kernel.LocalFree(output.data)


class ProfileStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Invalid tunnel profile file; the original file was preserved.')
        for row in data.get('tunnels', []) + data.get('servers', []):
            fields = row.get('fields', {})
            fields['token'] = crypt_token(fields.pop('protected_token', ''), decrypt=True)
        return data

    def save(self, data):
        # Copy before transforming so credentials in running sessions are unchanged.
        copy = json.loads(json.dumps(data))
        for row in copy['tunnels'] + copy['servers']:
            fields = row['fields']
            fields['protected_token'] = crypt_token(fields.pop('token', ''))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix='profiles-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(copy, stream, ensure_ascii=False, indent=2)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
