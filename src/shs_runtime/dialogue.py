"""Dialogue geometry and pagination in the original 320 by 480 coordinates."""
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache

from .fonts import load_font, TextLayout, TextStyle, layout_text
from .ui_assets import LayoutBank, Rect, read_ui
from .speaker_names import NAME_FONTS, SpeakerNames, fit_speaker_ink, preview_speaker, speaker_label


BODY_FONT = 'ArialRoundedMTBold16'
NARRATOR_FONT = 'TrebuchetMS_Italic16'
BLUE = (41, 104, 221)


def dialogue_styles(theme: int, *, narrator: bool = False, emphasis_theme: int = 1):
    if narrator:
        body_font = NARRATOR_FONT
        body = TextStyle(10, 7, (223, 163, 52), (('`', (125, 67, 0)),))
    else:
        body_font = BODY_FONT
        color = {1: BLUE, 2: (180, 78, 78), 3: (108, 108, 108)}.get(theme, (223, 163, 52))
        emphasis = BLUE if emphasis_theme == 2 else (254, 53, 0)
        body = TextStyle(14, 7, color, (('`', emphasis), (';', (1, 76, 215))))
    return NAME_FONTS.get(theme, 'PajamaHip26'), TextStyle(16, -16), body_font, body


@dataclass(frozen=True)
class DialoguePage:
    box: Rect  # The stretchable center; borders extend outside this rectangle.
    body_origin: tuple[float, float]
    body_font: str
    body: TextLayout
    portrait: Rect | None
    name_font: str
    name: TextLayout
    name_origin: tuple[float, float]
    name_scale: float
    start: int
    end: int


class DialogueLayout:
    def __init__(self, resources):
        self.resources = resources
        self.bank = LayoutBank.parse(read_ui(resources, 14))

    @lru_cache(maxsize=8)
    def font(self, name):
        return load_font(self.resources.library, name)

    def prepare_name(self, details, names: SpeakerNames):
        names.basis = deepcopy(names.fonts)
        label = speaker_label(details['speaker'], details['presentation_mode'], details['theme'],
                              self.bank, self.font, names.fonts)
        return label.text

    def page(self, details, start=0, *, names: SpeakerNames | None = None):
        mode, theme = details['presentation_mode'], details['theme']
        name_font, name_style, body_font, body_style = dialogue_styles(
            theme, narrator=mode == 4, emphasis_theme=details['emphasis_theme'])
        font = self.font(body_font)
        text = details['text'][start:]
        sizing_text = details['text']  # Page turns keep the original box size.
        portrait = None
        if mode == 4:
            name = layout_text(self.font(name_font), '', 1, name_style)
            name_origin, name_scale = (0, 0), .9
            # FUN_000858cc configures state+0xd180 with registry font 5,
            # height 16 and gap 9. Narrator sizing and drawing deliberately
            # use different fonts. This measuring object has no color markers.
            measured = layout_text(self.font(BODY_FONT), sizing_text, 220, TextStyle(16, 9))
            width = max(120, (int(measured.width) + 2) // 2 * 2)
            height = (int(min(200, measured.height)) + 5) // 2 * 2
            box = Rect(25, 115, width + 10, height + 10)
            origin = (30, 120)
        else:
            label = preview_speaker(details, self.bank, self.font, names)
            name, name_origin, name_scale, extra = label.layout, label.origin, label.scale, label.extra
            rect = self.bank.rectangle(17, 8)
            if mode in (1, 2):
                portrait = self.bank.rectangle(17, 0x30 if mode == 1 else 0x4e)
                body_style = replace(body_style, indents=(85, 75, 0, 0) if mode == 1 else (-85, -75, 0, 0))
            measured = layout_text(font, sizing_text, rect.width, body_style)
            capacity = int((rect.height + body_style.gap) / (body_style.height + body_style.gap))
            count = min(capacity, max(3, len(measured.lines)))
            height = int(count * (body_style.height + body_style.gap) - body_style.gap + 7) if count else 8
            height += height % 2
            box = Rect(rect.x - 7, rect.y - extra, rect.width + 14, height + extra)
            origin = (rect.x - 7, rect.y - extra // 2)
        full = layout_text(font, text, box.width, body_style)
        capacity = max(1, int((box.height + body_style.gap) / (body_style.height + body_style.gap)))
        end = full.lines[capacity].start if len(full.lines) > capacity else len(text)
        body = layout_text(font, text[:end], box.width, body_style)
        if mode != 4:
            # Allow for any glyph becoming the first line on a later page.
            # The whole dialogue supplies one stable name position; neither
            # the native body box nor its byte offsets change for this fit.
            all_body = layout_text(font, sizing_text, box.width, body_style)
            ink_tops = (body_style.height - font.line_height + g.glyph.yoffset
                        for g in all_body.glyphs)
            body_top = origin[1] + min(ink_tops, default=0)
            left = portrait.x + portrait.width if mode == 1 else 0
            right = portrait.x if mode == 2 else 320
            name, name_origin, name_scale = fit_speaker_ink(label, body_top, left, right)
        return DialoguePage(box, origin, body_font, body, portrait, name_font,
                            name, name_origin, name_scale, start, start + end)
