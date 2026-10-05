"""Authored stored-member RAR fixtures; no game or third-party archive data."""
import struct
from zlib import crc32


def rar4(members):
    def header(kind, flags, data=b''):
        body = struct.pack('<BHH', kind, flags, 7 + len(data)) + data
        return struct.pack('<H', crc32(body) & 0xffff) + body
    result = bytearray(b'Rar!\x1a\x07\0' + header(0x73, 0, b'\0' * 6))
    for name, data in members:
        name = name.encode('utf-8')
        info = struct.pack('<IIBIIBBHI', len(data), len(data), 3, crc32(data), 0,
                           20, 0x30, len(name), 0o100644) + name
        result += header(0x74, 0x8000, info) + data
    return bytes(result + header(0x7b, 0))


def rar5(members):
    def vint(value):
        result = bytearray()
        while value > 127:
            result.append((value & 127) | 128)
            value >>= 7
        return bytes(result + bytes([value]))
    def header(body):
        data = vint(len(body)) + body
        return struct.pack('<I', crc32(data)) + data
    result = bytearray(b'Rar!\x1a\x07\x01\0' + header(b'\x01\0\0'))
    for name, data in members:
        name = name.encode('utf-8')
        info = (b'\x02\x02' + vint(len(data)) + b'\x04' + vint(len(data))
                + vint(0o100644) + struct.pack('<I', crc32(data)) + b'\0\x01'
                + vint(len(name)) + name)
        result += header(info) + data
    return bytes(result + header(b'\x05\0\0'))
