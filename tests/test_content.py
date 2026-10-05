import json
import lzma
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
from zipfile import BadZipFile, ZipFile

from exp_runtime.content import (ContentError, ContentLibrary, ExpArchive, NATIVE_MEMBER,
                              digest, import_game)
from test_vm import program


def metadata(title='An original test episode'):
    result = struct.pack('>HH', 7, 2)
    for text in (title, 'École', 'Scuola', 'Schule', 'Escuela'):
        data = text.encode('utf-8')
        result += struct.pack('>H', len(data)) + data
    return result


def archive(records, *, compressed=(), aliases=None):
    aliases = aliases or {}
    start = 9 + 6 * (len(records) + len(aliases))
    entries, bodies = {}, bytearray()
    for resource_id, data in records.items():
        entries[resource_id] = start + len(bodies)
        if resource_id in compressed:
            alone = lzma.compress(data, format=lzma.FORMAT_ALONE,
                                  filters=[dict(id=lzma.FILTER_LZMA1, dict_size=4096)])
            encoded = alone[:5] + struct.pack('<II', len(data), len(data)) + alone[13:]
        else:
            encoded = data
        bodies += struct.pack('>III', len(encoded), len(data), int(resource_id in compressed)) + encoded
    for alias, original in aliases.items():
        entries[alias] = entries[original]
    return (b'CSPUD' + struct.pack('>I', len(entries))
            + b''.join(struct.pack('>HI', key, offset) for key, offset in sorted(entries.items())) + bodies)


def compressed_archive(body, decoded_size, *, properties=0x5D, dictionary=4096):
    wrapper = struct.pack('<BIII', properties, dictionary, decoded_size, decoded_size) + body
    return (b'CSPUD' + struct.pack('>IHI', 1, 42, 15)
            + struct.pack('>III', len(wrapper), decoded_size, 1) + wrapper)


FAKE_NATIVE = b'authored native-profile test fixture, never executed'


def make_apk(path, episode):
    with ZipFile(path, 'w') as apk:
        apk.writestr(NATIVE_MEMBER, FAKE_NATIVE)
        apk.writestr('assets/Assets/Test.exp', episode)
        apk.writestr('assets/Assets/42', b'base image')
        apk.writestr('assets/Assets/images/42.png', b'UI atlas with the same number')
        apk.writestr('assets/Assets/0042', b'noncanonical resource name')
        apk.writestr('assets/Assets/audio/music/nested/8201.mp3', b'wrong audio namespace')
        apk.writestr('assets/Assets/audio/music/8201.mp3', b'music bytes')
        apk.writestr('../escape', b'this ZIP path must never be extracted')


class ArchiveTests(unittest.TestCase):
    def test_compression_aliases_and_five_utf8_titles(self):
        payload = metadata()
        exp = ExpArchive(archive({1: payload, 25001: program(0x33).to_bytes()},
                                  compressed=(1,), aliases={9: 1}))
        self.assertEqual(exp.read(1), payload)
        self.assertEqual(exp.read(9), payload)
        self.assertEqual(exp.metadata().titles[1], 'École')
        self.assertEqual(len(exp.metadata().titles), 5)
        self.assertEqual(set(exp.programs()), {25001})

    def test_lzma_end_markers_and_property_combinations(self):
        for lc, lp, pb, dictionary in ((3, 0, 2, 4096), (1, 2, 0, 8192), (4, 0, 4, 65536)):
            for payload in (b'', b'Authored compressed resource. ' * 40):
                with self.subTest(lc=lc, lp=lp, pb=pb, dictionary=dictionary, size=len(payload)):
                    filters = [dict(id=lzma.FILTER_LZMA1, dict_size=dictionary, lc=lc, lp=lp, pb=pb)]
                    body = lzma.compress(payload, format=lzma.FORMAT_RAW, filters=filters)
                    data = compressed_archive(body, len(payload),
                                              properties=(pb * 5 + lp) * 9 + lc, dictionary=dictionary)
                    self.assertEqual(ExpArchive(data).read(42), payload)

    def test_lzma_without_an_end_marker(self):
        payload = b'Authored EXP payload without an end marker.'
        # Authored bytes encoded with liblzma's LZMA1EXT, preset 6,
        # dict_size=4096, lc=3, lp=0, pb=2, ext_flags=0 (no end marker).
        body = bytes.fromhex(
            '00209d4a869a6f72a1742c35d7e646a4a143ef922720aa1f6768'
            '0636cae34f2ca70b0395361c7b4f0e64e17454c006')
        self.assertEqual(ExpArchive(compressed_archive(body, len(payload))).read(42), payload)

    def test_lzma_stops_at_the_declared_output_boundary(self):
        payload = b'Declared EXP output.'
        body = lzma.compress(payload + b' More range-coded bytes beyond the declared output.',
                             format=lzma.FORMAT_RAW,
                             filters=[dict(id=lzma.FILTER_LZMA1, dict_size=4096)])
        self.assertEqual(ExpArchive(compressed_archive(body, len(payload))).read(42), payload)

    def test_invalid_and_short_lzma_bodies_are_rejected(self):
        payload = b'An authored complete payload.'
        body = lzma.compress(payload, format=lzma.FORMAT_RAW,
                             filters=[dict(id=lzma.FILTER_LZMA1, dict_size=4096)])
        for encoded, declared in ((b'', len(payload)), (body[:5], len(payload)),
                                  (b'\xFF' + body[1:], len(payload)), (body, len(payload) + 1)):
            with self.subTest(body=encoded, declared=declared), self.assertRaises(ContentError):
                ExpArchive(compressed_archive(encoded, declared)).read(42)

    def test_bad_offsets_flags_sizes_and_lzma_are_rejected(self):
        original = archive({1: metadata()}, compressed=(1,))
        offset, = struct.unpack_from('>I', original, 11)
        mutations = [(11, '>I', 0), (offset, '>I', len(original) + 1),
                     (offset + 8, '>I', 2), (offset + 12 + 5, '<I', 999)]
        for at, fmt, value in mutations:
            with self.subTest(at=at), self.assertRaises(ContentError):
                data = bytearray(original)
                struct.pack_into(fmt, data, at, value)
                ExpArchive(bytes(data)).read(1)
        with self.assertRaises(ContentError):
            ExpArchive(original[:-1])

    def test_missing_exact_resource_is_not_guessed_from_neighbors(self):
        exp = ExpArchive(archive({1: metadata(), 26000: b'an authored resource'}))
        with self.assertRaisesRegex(ContentError, 'grouped lookup is unsupported'):
            exp.read(26001)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = patch('exp_runtime.shs.content.NATIVE_SHA256', digest(FAKE_NATIVE))
        self.profile.start()
        self.addCleanup(self.profile.stop)
        self.data = archive({1: metadata(), 25001: program(0x33).to_bytes(),
                             42: b'episode low ID must not replace base art', 26000: b'episode art'})
        self.apk = self.root / 'user.apk'
        make_apk(self.apk, self.data)

    def test_import_deduplicates_and_remains_relocatable_without_sources(self):
        folder = self.root / 'episodes' / 'nested'
        folder.mkdir(parents=True)
        (folder / 'again.EXP').write_bytes(self.data)
        (folder / 'second.exp').write_bytes(archive({1: metadata('Another episode'), 25001: program(0x33).to_bytes()}))
        target = self.root / 'library'
        manifest = import_game(self.apk, [folder.parent], target)
        self.assertEqual(len(manifest['episodes']), 2)
        self.assertEqual(len(list((target / 'content').glob('*.exp'))), 1)
        self.assertFalse((self.root / 'escape').exists())
        moved = self.root / 'moved-library'
        target.rename(moved)
        self.apk.unlink()
        shutil.rmtree(folder.parent)
        with ContentLibrary(moved) as library:
            resources = library.open_episode('Test.exp')
            self.assertEqual(resources.read_asset(42), b'base image')
            self.assertEqual(library.read_ui_asset('images/42.png'), b'UI atlas with the same number')
            for invalid in ('42', '../42', 'fonts/../42', 'images//42.png', '/images/42.png'):
                with self.subTest(name=invalid), self.assertRaises(ContentError):
                    library.read_ui_asset(invalid)
            self.assertEqual(resources.read_asset(8201), b'music bytes')
            self.assertEqual(resources.read_asset(26000), b'episode art')
            self.assertEqual(resources.program(25001).instructions[0].opcode, 0x33)
            self.assertEqual(resources.identity['episode_sha256'], digest(self.data))

    def test_legacy_android_manifest_retains_profile_and_resources(self):
        target = self.root / 'legacy'
        manifest = import_game(self.apk, [], target)
        manifest.update(format='shs-content-library', version=1)
        del manifest['game']
        path = target / 'library.json'
        path.write_text(json.dumps(manifest))
        before = path.read_bytes()
        with ContentLibrary(target) as library:
            self.assertEqual((library.game_id, library.kind), ('shs', 'apk'))
            self.assertEqual(library.open_episode('Test.exp').read_asset(42), b'base image')
            self.assertEqual(library.read_asset(8201), b'music bytes')
        self.assertEqual(path.read_bytes(), before)

    def test_failed_import_is_atomic_and_preserves_existing_library(self):
        target = self.root / 'library'
        broken = self.root / 'broken.exp'
        broken.write_bytes(b'not an EXP')
        with self.assertRaises(ContentError):
            import_game(self.apk, [broken], target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob('.exp-import-*')))
        import_game(self.apk, [], target)
        original = (target / 'library.json').read_bytes()
        with self.assertRaisesRegex(ContentError, 'already exists'):
            import_game(self.apk, [], target)
        self.assertEqual((target / 'library.json').read_bytes(), original)

    def test_unknown_native_profile_and_modified_content_are_rejected(self):
        target = self.root / 'library'
        with patch('exp_runtime.shs.content.NATIVE_SHA256', '0' * 64), self.assertRaisesRegex(ContentError, 'Unsupported game APK'):
            import_game(self.apk, [], target)
        manifest = import_game(self.apk, [], target)
        with (target / manifest['apk']['file']).open('ab') as stream:
            stream.write(b'changed after import')
        with self.assertRaisesRegex(ContentError, 'content changed'):
            ContentLibrary(target)

    def test_manifest_cannot_point_outside_library(self):
        target = self.root / 'library'
        manifest = import_game(self.apk, [], target)
        manifest['apk']['file'] = '../user.apk'
        (target / 'library.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ContentError, 'Invalid content path'):
            ContentLibrary(target)

    def test_corrupt_lazy_asset_reports_content_error(self):
        target = self.root / 'library'
        import_game(self.apk, [], target)
        with ContentLibrary(target) as library:
            resources = library.open_episode('Test.exp')
            with patch.object(library.apk, 'read', side_effect=BadZipFile('CRC mismatch')):
                with self.assertRaisesRegex(ContentError, 'Cannot read APK member'):
                    resources.read_asset(42)
