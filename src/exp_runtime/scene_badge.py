"""Service 90's nonblocking scene label (FUN_0007b97c)."""
from dataclasses import dataclass


@dataclass
class SceneBadge:
    asset_id: int
    text: str
    blue: bool
    elapsed_ms: int = 0

    def tick(self, elapsed_ms):
        self.elapsed_ms = min(200, self.elapsed_ms + elapsed_ms)

    def validate(self):
        if not 0 <= self.asset_id <= 32767 or not 0 <= self.elapsed_ms <= 200:
            raise ValueError('Invalid scene label')

    @property
    def text_position(self):
        # Native label node centers in a 171x60 sprite (GL local coordinates).
        n = len(self.text)
        if 15 <= n <= 17:
            return 123, 55, 1.0
        if n < 13:
            x = {'Before Class': 120, 'Mascot Theft': 122, 'Driving Home': 120}.get(self.text, 125)
            return x, 45, 1.0
        if n < 19:
            x, y = {'Before School': (117, 45), "Chuck's Party": (120, 45),
                    'Football Game': (120, 45), 'After Practice': (120, 45),
                    "Counselor's Office": (123, 53), 'Unsupervised Study': (120, 53),
                    'Saturday Night': (119, 45)}.get(self.text, (117, 53))
            return x, y, .9 if self.text == 'Before School' else 1.0
        return 121, 55, 1.0

    @property
    def text_origin(self):
        # FUN_0007b97c: a 110x20 label with (.5,.5) anchor and flags 0x11
        # (wrapped, left/top aligned). Text draws downward from local zero;
        # converting the anchor to screen Y therefore adds half its height.
        x, y, scale = self.text_position
        return x - 55 * scale, 60 - y + 10 * scale, scale
