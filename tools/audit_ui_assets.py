"""Inventory original APK UI art and bitmap-font metadata without extracting art."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import PurePosixPath
import shlex
from zipfile import ZipFile

from PIL import Image

from exp_runtime.content import NATIVE_MEMBER, NATIVE_SHA256, PROFILE, ContentError
from exp_runtime.fonts import BitmapFont


def audit(apk_path):
    with ZipFile(apk_path) as apk:
        native_hash = sha256(apk.read(NATIVE_MEMBER)).hexdigest()
        if native_hash != NATIVE_SHA256:
            raise ContentError('This UI audit describes the SHS Android 1.0.9 native profile')
        fonts, discrepancies, images = [], [], []
        for name in sorted(apk.namelist()):
            if name.startswith('assets/Assets/fonts/') and name.endswith('.fnt'):
                data = apk.read(name)
                parsed = BitmapFont.parse(data)
                rows = []
                for line in data.decode('utf-8-sig').splitlines():
                    tokens = shlex.split(line)
                    if tokens:
                        rows.append((tokens[0], dict(token.split('=', 1) for token in tokens[1:])))
                info = next(row for kind, row in rows if kind == 'info')
                common = next(row for kind, row in rows if kind == 'common')
                page = next(row for kind, row in rows if kind == 'page')
                chars = [row for kind, row in rows if kind == 'char']
                kernings = [row for kind, row in rows if kind == 'kerning']
                declared = int(next(row['count'] for kind, row in rows if kind == 'chars'))
                atlas = apk.read(str(PurePosixPath(name).parent / page['file']))
                png = apk.read(name.removesuffix('.fnt') + '.png')
                with Image.open(BytesIO(atlas)) as image:
                    actual_size, image_format = list(image.size), image.format
                declared_size = [int(common['scaleW']), int(common['scaleH'])]
                if declared != len(chars):
                    discrepancies.append(f'{name}: declared {declared} glyphs, contains {len(chars)}')
                if actual_size != declared_size:
                    discrepancies.append(f'{name}: declared atlas {declared_size}, actual {actual_size}')
                if any(float(c['x']) < 0 or float(c['y']) < 0
                       or float(c['x']) + float(c['width']) > actual_size[0]
                       or float(c['y']) + float(c['height']) > actual_size[1] for c in chars):
                    discrepancies.append(f'{name}: glyph rectangle outside actual atlas')
                fractional = [dict(character=int(c['id']), fields={k: v for k, v in c.items() if '.' in v})
                              for c in chars if any('.' in v for v in c.values())]
                fonts.append(dict(file=PurePosixPath(name).name, face=info['face'], size=int(info['size']),
                                  line_height=int(common['lineHeight']), base=int(common['base']),
                                  atlas_size=actual_size, declared_atlas_size=declared_size,
                                  atlas_format=image_format, characters=len(chars),
                                  declared_characters=declared, kernings=len(kernings), page=page['file'],
                                  parsed_characters=len(parsed.glyphs), unique_kerning_pairs=len(parsed.kernings),
                                  png_dat_identical=atlas == png, fractional_glyph_metrics=fractional,
                                  descriptor_sha256=sha256(data).hexdigest(), atlas_sha256=sha256(atlas).hexdigest()))
            elif name.startswith('assets/Assets/images/') and not name.endswith('/'):
                data = apk.read(name)
                with Image.open(BytesIO(data)) as image:
                    images.append(dict(file=PurePosixPath(name).name, size=list(image.size),
                                       format=image.format, sha256=sha256(data).hexdigest()))
        return dict(profile=PROFILE, native_sha256=native_hash, font_sets=len(fonts), fonts=fonts,
                    named_images=images, metadata_discrepancies=discrepancies,
                    native_parser_notes=[
                        'FUN_0017874c does not use chars count to limit the char records it reads.',
                        'FUN_00175f90 stores lineHeight but only copies/discards scaleW, scaleH and pages tokens.',
                        'FUN_00176abc uses floats for glyph rectangles and integers for offsets/advance; yoffset=6.5 is read as 6.',
                        'FUN_0004d3f8 wraps with unkerned advances; FUN_0004cb90 applies kerning only to glyph placement.',
                        'TrebuchetMS_Bold14 repeats kerning pair (118,46) with amount -2; 1443 records yield 1442 distinct per-font pairs.',
                    ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk')
    args = parser.parse_args()
    print(json.dumps(audit(args.apk), indent=2))
