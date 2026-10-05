"""Authored SFNT fixtures for the IPA font adapter."""
from io import BytesIO
import struct
from types import SimpleNamespace
import unittest

from PIL import ImageFont

from exp_runtime.fonts import layout_text, TextStyle
from exp_runtime.ios_fonts import _design_metrics, render_font


class IOSFontMetricsTests(unittest.TestCase):
    def test_each_game_supplies_its_own_name_colors_with_the_same_font_metrics(self):
        data = ImageFont.load_default().font_bytes
        fonts = {}
        for game, asset, expected in (('shs', 505, (41, 104, 221, 255)),
                                       ('cod', 291, (139, 0, 0, 255))):
            library = SimpleNamespace(game_id=game, base_members={asset}, read_asset=lambda _: data)
            for name in ('PajamaHip26', 'PajamaHipG26', 'PajamaHipY26') if game == 'cod' else ('PajamaHip26',):
                font, atlas = render_font(library, name)
                colors = {color for _, color in atlas.getcolors(atlas.width * atlas.height)}
                self.assertIn(expected, colors)
                self.assertIn((255, 255, 255, 255), colors)  # Supplied-face outline stays white.
            fonts[game] = font
        self.assertEqual(fonts['shs'].glyphs, fonts['cod'].glyphs)

    def font_file(self, cap=None):
        head, hhea, os2 = bytearray(54), bytearray(36), bytearray(90 if cap else 86)
        struct.pack_into('>H', head, 18, 1000)
        struct.pack_into('>h', hhea, 6, -225)
        struct.pack_into('>H', os2, 0, 2 if cap else 1)
        if cap:
            struct.pack_into('>h', os2, 88, cap)
        tables = [(b'head', head), (b'hhea', hhea), (b'OS/2', os2)]
        data = bytearray(struct.pack('>I4H', 0x10000, len(tables), 0, 0, 0))
        offset = 12 + len(tables) * 16
        for tag, table in tables:
            data += struct.pack('>4sIII', tag, 0, offset, len(table))
            offset += len(table)
        return BytesIO(data + b''.join(table for _, table in tables))

    def test_cap_height_and_descent_use_font_design_units(self):
        design = SimpleNamespace(getbbox=lambda c, **_: (0, -701 if c == 'H' else -722, 500, 0),
                                 getlength=lambda c: 333)
        font = SimpleNamespace(font_variant=lambda **kwargs: design)
        for supplied, expected in ((725, 725), (None, 711)):
            actual, units, cap, descent = _design_metrics(font, self.font_file(supplied), 0)
            self.assertIs(actual, design)
            self.assertEqual((units, cap, descent), (1000, expected, 225))

    def test_collection_metrics_use_the_selected_face(self):
        faces = [bytearray(self.font_file(cap).getvalue()) for cap in (725, 800)]
        offsets = [20, 20 + len(faces[0])]
        for data, offset in zip(faces, offsets):
            for i in range(3):
                pos = 12 + i * 16 + 8
                struct.pack_into('>I', data, pos, struct.unpack_from('>I', data, pos)[0] + offset)
        collection = BytesIO(struct.pack('>4s4I', b'ttcf', 0x10000, 2, *offsets) + b''.join(faces))
        font = SimpleNamespace(font_variant=lambda **_: None)
        self.assertEqual(_design_metrics(font, collection, 1)[1:], (1000, 800, 225))

    def test_rendered_atlas_retains_fractional_advances_for_wrapping(self):
        # Pillow's own freely supplied font is already used by the authored
        # CoD importer fixtures; no proprietary face is included in the test.
        data = ImageFont.load_default().font_bytes
        library = SimpleNamespace(game_id='cod', base_members={291}, read_asset=lambda _: data)
        font, atlas = render_font(library, 'PajamaHip26')
        rounded = ImageFont.truetype(BytesIO(data), 26, layout_engine=ImageFont.Layout.BASIC)
        glyph = next(g for g in font.glyphs.values() if chr(g.code).isalpha()
                     and 32 < g.code < 127 and g.advance < rounded.getlength(chr(g.code)))
        text = chr(glyph.code) * 10
        width = glyph.advance * 10 + .01
        self.assertLess(width, rounded.getlength(chr(glyph.code)) * 10)
        self.assertEqual(len(layout_text(font, text, width, TextStyle(font.cap_height)).lines), 1)
        self.assertTrue(atlas.getbbox())
