"""Saved dialogue presentation clocks, independent of the display.

Native evidence and the 30 Hz letter-scheduler policy are documented in
docs/UI_FIDELITY.md. Portrait/name tweens use elapsed time; drawing is pure.
"""
from dataclasses import dataclass

from .relationships import RelationshipAnimation, RelationshipChange


LETTER_HZ = 30
PORTRAIT_MS = 300
NAME_FADE_MS = 300


@dataclass(frozen=True)
class DialoguePortrait:
    character_id: int
    asset_id: int
    mode: int
    theme: int

    @classmethod
    def from_details(cls, details, variants):
        character = details['visible_character_id']
        if details['presentation_mode'] not in (1, 2) or character < 0:
            return None
        art = variants[character]
        return cls(character, art[details['expression'] % len(art)],
                   details['presentation_mode'], details['theme'])

    def validate(self):
        if self.character_id < 0 or self.asset_id < 0 or self.mode not in (1, 2):
            raise ValueError('Invalid dialogue portrait')


def progress(elapsed, duration):
    return min(1.0, max(0.0, elapsed / duration))


@dataclass
class DialogueAnimation:
    text_length: int
    portrait: DialoguePortrait | None = None
    previous: DialoguePortrait | None = None
    changed: bool = True
    page_turn: bool = False
    elapsed_ms: int = 0
    revealed: int = 0
    complete: bool = False
    finish_requested: bool = False
    finish_step: int = 0
    wobble_direction: int = 0
    relationship: RelationshipAnimation | None = None

    @classmethod
    def start(cls, details, variants, previous=None):
        portrait = DialoguePortrait.from_details(details, variants)
        old = previous.portrait if previous else None
        changed = previous is None or ((old.character_id if old else -1) !=
                                       (portrait.character_id if portrait else -1))
        motion = cls(len(details['text']) - details['page_start'], portrait,
                   old if changed else None, changed,
                   wobble_direction=(20 if details['presentation_mode'] == 2 else -20)
                   if details.get('box_wobble', False) else 0)
        if details.get('relationship') is not None:
            change = RelationshipChange(**details['relationship'])
            change.validate()
            motion.relationship = RelationshipAnimation(change, motion.portrait_delay_ms + PORTRAIT_MS if changed else 0)
        return motion

    @property
    def portrait_delay_ms(self):
        # FUN_000aaa40 waits for the outgoing portrait only on the same side.
        same_side = self.previous and self.portrait and self.previous.mode == self.portrait.mode
        return 250 + (PORTRAIT_MS if same_side else 0)

    @property
    def name_delay_ms(self):
        duration = PORTRAIT_MS if self.changed and self.portrait else 0
        same_side = self.previous and self.portrait and self.previous.mode == self.portrait.mode
        return 250 + (PORTRAIT_MS if same_side else 0) + duration + 120 + self.relationship_delay_ms

    @property
    def relationship_delay_ms(self):
        return self.relationship.change.extra_delay_ms if self.relationship and not self.page_turn else 0

    @property
    def text_delay_ms(self):
        if self.page_turn:
            return 350  # FUN_000a9868, next substring.
        return self.name_delay_ms - (120 if self.wobble_direction else 0) if self.changed else 250 + self.relationship_delay_ms

    @property
    def box_rotation(self):
        # FUN_0007c9e8: rotate to the opposite 20-degree angle in 70ms,
        # delay 2ms (right) / 5ms (other), then rotate to zero in 70ms.
        t, angle = self.elapsed_ms, self.wobble_direction
        pause = 2 if angle == 20 else 5
        if t < 70:
            return angle * (1 - 2 * t / 70)
        return -angle * (1 - progress(t - 70 - pause, 70))

    @property
    def duration_ms(self):
        return max(self.name_delay_ms + NAME_FADE_MS,
                   self.text_delay_ms + ((self.text_length + 2) * 1000 + LETTER_HZ - 1) // LETTER_HZ)

    @property
    def portrait_scale(self):
        return progress(self.elapsed_ms - self.portrait_delay_ms, PORTRAIT_MS) if self.changed else 1.0

    @property
    def previous_scale(self):
        return 1.0 - progress(self.elapsed_ms, PORTRAIT_MS)

    @property
    def name_alpha(self):
        return int(255 * progress(self.elapsed_ms - self.name_delay_ms, NAME_FADE_MS)) if self.changed else 255

    def _callbacks(self, elapsed_ms):
        # The native 3 ms selector reveals ONE source index per scheduler
        # update, discarding excess dt. Use its configured 30 fps cadence for
        # letters while allowing smooth portrait motion at any display rate.
        first = max(1, (self.text_delay_ms * LETTER_HZ + 999) // 1000)
        return max(0, elapsed_ms * LETTER_HZ // 1000 - first + 1)

    def tick(self, elapsed_ms):
        if self.relationship:
            self.relationship.tick(elapsed_ms)
        old = self._callbacks(self.elapsed_ms)
        self.elapsed_ms = min(self.duration_ms, self.elapsed_ms + elapsed_ms)
        due = self._callbacks(self.elapsed_ms) - old
        if self.complete or due <= 0:
            return
        if self.finish_requested:
            # Native input sets a flag. The next selector visits one index,
            # then a following callback unhides the whole label and completes.
            if self.finish_step + due >= 2 or self.revealed == self.text_length:
                self.revealed, self.complete = self.text_length, True
                self.finish_step = 0
            else:
                self.revealed = min(self.text_length, self.revealed + 1)
                self.finish_step = 1
        else:
            self.complete = self.revealed + due > self.text_length
            self.revealed = min(self.text_length, self.revealed + due)

    def finish(self):
        self.finish_requested = True

    def next_page(self, length):
        self.wobble_direction = 0
        self.text_length = length
        self.previous = None
        self.changed, self.page_turn = False, True
        self.elapsed_ms = self.revealed = self.finish_step = 0
        self.complete = self.finish_requested = False

    def settle(self):
        """Old saves showed all text; migrate without replaying the entrance."""
        self.elapsed_ms = self.duration_ms
        self.revealed, self.complete = self.text_length, True
        if self.relationship:
            self.relationship.settle()

    def validate(self):
        for portrait in (self.portrait, self.previous):
            if portrait:
                portrait.validate()
        if self.relationship:
            self.relationship.validate()
            if self.portrait is None or self.relationship.change.character_id != self.portrait.character_id:
                raise ValueError('Relationship indicators do not match the portrait')
        callbacks = self._callbacks(self.elapsed_ms)
        if (self.wobble_direction not in (-20, 0, 20)
                or self.text_length < 0 or not 0 <= self.elapsed_ms <= self.duration_ms
                or not 0 <= self.revealed <= self.text_length
                or self.finish_step not in (0, 1)
                or (self.finish_step and not self.finish_requested)
                or (self.complete and self.finish_step)
                or (self.complete and self.revealed != self.text_length)
                or (not self.changed and self.previous is not None)
                or (self.page_turn and self.changed)
                or (callbacks == 0 and (self.revealed or self.complete))
                or (not self.finish_requested and
                    (self.revealed != min(self.text_length, callbacks)
                     or self.complete != (callbacks > self.text_length)))):
            raise ValueError('Invalid dialogue animation state')
