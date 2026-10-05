"""Desktop application lifecycle: import, menu, episode sessions and shutdown.

The executable starts here with no game data. pygame is confined to the UI;
imports run on a worker and publish a complete validated library atomically.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import logging
import os
from pathlib import Path
import tempfile

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame

from .content import ContentError, ContentLibrary, import_game, is_bundled
from .desktop import Desktop, SIZE
from .desktop_menu import MenuRenderer
from .menu import (EPISODE_HEADER_HEIGHT, EPISODE_ROW_HEIGHT, MenuState,
                   default_library, group_episodes, remember_library)
from .runtime import SaveError, Session
from .vm import VMError


ERRORS = (ContentError, SaveError, VMError, OSError, ValueError, pygame.error)


class Application:
    def __init__(self, directory=None, *, audio=True):
        pygame.display.init()
        pygame.font.init()
        self.window = pygame.display.set_mode(SIZE, pygame.RESIZABLE)
        pygame.display.set_caption('Surviving High School')
        self.remember_location = directory is None
        self.directory = Path(directory) if directory is not None else default_library()
        self.library = self.state = self.game = None
        self.renderer = MenuRenderer()
        self.screen = 'setup'
        self.history = []
        self.message = ''
        self.scope = 'all'
        self.selected = None
        self.saved = set()
        self.query = ''
        self.scroll = 0
        self.episode_scroll = 0
        self.expanded_groups = set()
        self.focus = None
        self.pressed = None
        self.focus_index = 0
        self.active = True
        self.intro = True
        self.menu_age = 0
        self.transition_age = 200
        self.transition_from = None
        self.buttons = []
        self.viewport = pygame.Rect(0, 0, *SIZE)
        self.browser_kind = None
        self.folder = Path.cwd()
        self.path_text = str(self.folder)
        self.files = []
        self.dropped_files = []
        self.dropping = False
        self.audio = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='shs-content')
        self.job = None
        self.job_kind = None
        if audio:
            try:
                pygame.mixer.init()
                self.audio = True
            except pygame.error as error:
                logging.warning('Audio unavailable: %s', error)
        if self.directory.exists():
            try:
                self.open_library(self.directory)
            except ERRORS as error:
                self.message = str(error)

    @property
    def busy(self):
        return self.job is not None

    @property
    def ready(self):
        return (not self.busy and self.transition_age >= 200
                and (self.screen != 'main' or self.menu_age >= (3000 if self.intro else 500)))

    def open_library(self, directory, *, remember=False):
        library = ContentLibrary(directory)
        try:
            library.ensure_builtin_episodes()
            state = MenuState(library)
            renderer = MenuRenderer(library)
            if remember and self.remember_location:
                remember_library(directory)
        except Exception:
            library.close()
            raise
        if self.library:
            self.library.close()
        self.directory, self.library = Path(directory), library
        self.state, self.renderer, self.game = state, renderer, None
        self.expanded_groups = {'saved'}
        self.episode_scroll = 0
        if hasattr(self, 'click_sound'):
            del self.click_sound
        self.screen, self.history, self.selected = 'main', [], state.selected
        self.menu_age, self.intro = 0, True
        self.message = state.warning
        self.refresh_saves()

    def refresh_saves(self):
        self.saved = {e['id'] for e in self.library.episodes if self.state.resume_path(e['id'])}
        if self.game and not self.game.session.episode_exited:
            self.saved.add(self.game.session.resources.record['id'])

    def can_resume(self, episode=None):
        return (episode or self.state.selected) in self.saved

    def visible_episodes(self):
        records = self.library.episodes
        if self.scope == 'weekly':
            records = [e for e in records if not is_bundled(e)]
        if self.query:
            query = self.query.casefold()
            matching_groups = {e['id'] for section in self._episode_sections(records)
                               if query in section.title.casefold() for e in section.episodes}
            records = [e for e in records if query in e['titles'][0].casefold() or query in e['name'].casefold()
                       or any(query in alias.casefold() for alias in e.get('aliases', []))
                       or e['id'] in matching_groups]
        def key(record):
            title = record['titles'][0].casefold()
            identity = record['pack_id'], record['episode_id']
            # Distinct versions retain their content identity; bundle first
            # when their numeric IDs and titles coincide.
            tie = not is_bundled(record), record['name'].casefold(), record['id']
            return (title, *identity, *tie) if self.state.order == 'title' else (*identity, title, *tie)
        return sorted(records, key=key)

    def episode_sections(self):
        return self._episode_sections(self.visible_episodes())

    def _episode_sections(self, records):
        return group_episodes(records, self.library.catalog,
                             mega_label=self.renderer.strings[82], novel_label=self.renderer.strings[302],
                             saved_label=self.renderer.strings[238],
                             saved=self.saved if self.scope == 'play' else ())

    def episode_rows(self):
        rows, y = [], 0
        for section in self.episode_sections():
            rows.append((y, EPISODE_HEADER_HEIGHT, section, None))
            y += EPISODE_HEADER_HEIGHT
            if self.query or section.key in self.expanded_groups:
                for record in section.episodes:
                    rows.append((y, EPISODE_ROW_HEIGHT, section, record))
                    y += EPISODE_ROW_HEIGHT
        return rows, y

    def show(self, screen, *, remember=True):
        if self.screen == 'episodes':
            self.episode_scroll = self.scroll
        self.transition_from = self.renderer.canvas.copy()
        if remember and screen != self.screen:
            self.history.append(self.screen)
        self.screen = screen
        self.scroll = self.episode_scroll if screen == 'episodes' else 0
        self.focus_index = 0
        self.pressed = self.focus = None
        pygame.key.stop_text_input()
        self.transition_age = 0
        if screen == 'main':
            self.menu_age, self.intro = 0, False
        self.buttons = []

    def back(self):
        if self.message:
            self.message = ''
        elif self.history:
            screen = self.history.pop()
            self.show(screen, remember=False)
        elif self.library and self.screen != 'main':
            self.show('main', remember=False)

    def _attempt(self, operation):
        try:
            return operation()
        except ERRORS as error:
            self.message = str(error)
            logging.warning('%s', error)

    def _click_sound(self):
        if self.audio and self.library and self.state.sound:
            try:
                if not hasattr(self, 'click_sound'):
                    self.click_sound = pygame.mixer.Sound(file=BytesIO(self.library.read_asset(8010)))
                self.click_sound.play()
            except (ContentError, pygame.error) as error:
                logging.debug('Menu sound unavailable: %s', error)

    def start(self, *, resume=True, load_path=None):
        episode = self.selected
        if self.game and resume and not load_path and self.game.session.resources.record['id'] == episode:
            self.game.menu_open = False
        else:
            if load_path:
                session = Session.load(self.library.open_episode(episode), load_path)
                self.state.selected = episode
                self.state.persist()
            else:
                session = self.state.session(episode, resume=resume)
            # A fresh renderer per episode prevents local image IDs from
            # accidentally reusing the previous episode's cached artwork.
            self.game = Desktop(session, audio=self.audio, window=self.window, on_main_menu=self.return_to_menu)
        self.game.music_enabled, self.game.sound_enabled = self.state.music, self.state.sound
        self.game.active = self.active
        self.screen, self.history, self.focus = 'game', [], None
        self.game.screen_token = None
        pygame.key.stop_text_input()
        if self.game.session.episode_exited:
            self.return_to_menu()
            return
        self.game._sync_music()
        self.refresh_saves()

    def return_to_menu(self):
        # Keep the live session even if a filesystem error prevents a checkpoint.
        if self.game.session.engine.word_grid:
            self.game.session.grid_pointer('cancel')
        checkpoint = self._attempt(lambda: self.state.checkpoint(self.game.session))
        # A live session retains its mixer stream and playhead through menu
        # navigation. A fresh Desktop or explicit save load selects a new cue.
        self.game.active = False
        if not self.game.session.episode_exited:
            self.game._sync_music()
        if self.audio:
            pygame.mixer.stop()
        self.game.menu_open = False
        if self.game.session.episode_exited:
            # Completed sessions cannot resume. The terminal automatic save
            # masks older progress without deleting the player's manual slot.
            if self.audio:
                pygame.mixer.music.stop()
            if checkpoint is not None:
                self.game = None
        self.history = []
        self.show('main', remember=False)
        self.refresh_saves()
        pygame.display.set_caption('Surviving High School')

    def browse(self, kind):
        self.browser_kind = kind
        self.show('browser')
        self.read_folder(self.folder)

    def read_folder(self, folder):
        folder = Path(folder).expanduser().resolve()
        extensions = ({'.apk', '.ipa'} if self.browser_kind == 'apk' else {'.apk'}
                      if self.browser_kind == 'music_apk' else {'.exp'} if self.browser_kind == 'episodes' else set())
        files = [p for p in folder.iterdir() if not p.name.startswith('.')
                 and (p.is_dir() or p.suffix.lower() in extensions
                      or (self.browser_kind == 'episodes' and p.name.lower() == 'shs_options.sav'))]
        # Existing hidden content libraries are useful in the library picker.
        if self.browser_kind == 'library':
            files.extend(p for p in folder.iterdir() if p.name.startswith('.')
                         and p.is_dir() and (p / 'library.json').is_file())
        self.files = sorted(files, key=lambda p: (not p.is_dir(), p.name.casefold()))
        self.folder, self.path_text, self.scroll = folder, str(folder), 0
        self.focus = None
        pygame.key.stop_text_input()

    def import_paths(self, paths):
        if self.busy:
            return
        paths = [Path(p).expanduser() for p in paths]
        if not self.library:
            ipas = [p for p in paths if p.suffix.lower() == '.ipa']
            apks = [p for p in paths if p.suffix.lower() == '.apk']
            if len(ipas) > 1 or len(apks) > 1 or not (ipas or apks):
                raise ContentError('Choose one APK or IPA. An IPA can also include one APK for missing music.')
            source = ipas[0] if ipas else apks[0]
            music_apk = apks[0] if ipas and apks else None
            episodes = [p for p in paths if p not in ipas + apks]
            self.job_kind = 'library'
            self.job = self.executor.submit(import_game, source, episodes, self.directory, music_apk=music_apk)
        elif any(p.suffix.lower() == '.apk' for p in paths):
            if len(paths) != 1:
                raise ContentError('Add one music APK at a time; add episode files separately.')
            self.job_kind = 'music'
            self.job = self.executor.submit(self.library.add_music_apk, paths[0])
        else:
            self.job_kind = 'episodes'
            self.job = self.executor.submit(self.library.add_episodes, paths)
        self.focus, self.pressed = None, None
        pygame.key.stop_text_input()

    def flush_drops(self):
        if self.dropped_files and not self.busy and not self.dropping:
            paths, self.dropped_files = self.dropped_files, []
            self._attempt(lambda: self.import_paths(paths))

    def command(self, command):
        kind = command[0]
        self.pressed = None
        if self.busy:
            return
        if kind == 'dismiss':
            self.message = ''
            return
        self._click_sound()
        def perform():
            if kind == 'back':
                self.back()
            elif kind == 'episodes':
                self.scope, self.query = command[1], ''
                self.episode_scroll = self.scroll = 0
                self.refresh_saves()
                self.show('episodes')
            elif kind == 'episode':
                self.selected = command[1]
                self.show('episode')
            elif kind in ('options', 'help', 'library', 'restart'):
                self.show(kind)
            elif kind == 'start':
                self.start(resume=command[1])
            elif kind == 'legacy':
                self.message = 'The original EA store is not part of this player. Add your own episode files through Options.'
            elif kind == 'toggle':
                key = command[1]
                setattr(self.state, key, not getattr(self.state, key))
                self.state.persist()
            elif kind == 'order':
                self.state.order = 'title' if self.state.order == 'episode' else 'episode'
                self.state.persist()
                self.scroll = 0
            elif kind == 'episode_group':
                key = command[1]
                self.expanded_groups.symmetric_difference_update({key})
                self._scroll(0)
            elif kind == 'episode_groups':
                keys = {section.key for section in self.episode_sections()}
                if keys <= self.expanded_groups:
                    self.expanded_groups.difference_update(keys)
                else:
                    self.expanded_groups.update(keys)
                self.scroll = 0
            elif kind == 'clear_search':
                self.query, self.scroll, self.focus = '', 0, None
                pygame.key.stop_text_input()
            elif kind == 'browse':
                self.browse(command[1])
            elif kind == 'up':
                self.read_folder(self.folder.parent)
            elif kind == 'file':
                if command[1].is_dir():
                    self.read_folder(command[1])
                else:
                    self.import_paths([command[1]])
            elif kind == 'folder':
                if self.browser_kind == 'library':
                    self.open_library(self.folder, remember=True)
                else:
                    self.import_paths([self.folder])
            elif kind in ('search', 'path'):
                self.focus = kind
                if kind == 'path':
                    self.path_text = ''
                pygame.key.start_text_input()
        self._attempt(perform)

    def tick(self, elapsed):
        if self.job and self.job.done():
            job, kind = self.job, self.job_kind
            self.job = self.job_kind = None
            try:
                result = job.result()
                if kind == 'library':
                    self.open_library(self.directory)
                elif kind == 'music':
                    # Retry the current cue on Resume if its earlier load failed.
                    # Keep the live story and all existing checkpoints intact.
                    if self.game and result and not self.game.music_loaded:
                        self.game.music_token = None
                    self.history = ['main']
                    self.show('library', remember=False)
                    self.message = (f'Added {result} missing music tracks.' if result
                                    else 'No missing music tracks to add.')
                else:
                    self.refresh_saves()
                    self.scope, self.query, self.history = 'all', '', ['main']
                    self.episode_scroll = self.scroll = 0
                    self.show('episodes', remember=False)
                    self.message = f'Added {result} episodes.' if result else 'Library updated. No new episodes were added.'
            except ERRORS as error:
                self.message = str(error)
        self.flush_drops()
        if not self.active or self.busy or self.message:
            return
        if self.screen == 'game':
            self.game.tick(elapsed)
            if self.game.session.episode_exited:
                self.return_to_menu()
        else:
            self.menu_age += elapsed
            self.transition_age = min(200, self.transition_age + elapsed)

    def render(self):
        if self.screen == 'game':
            if self.game.session.episode_exited:
                self.return_to_menu()
            else:
                self.game.render()
                return
        canvas = self.renderer.draw(self)
        if self.transition_from is not None and self.transition_age < 200 and not self.message and not self.busy:
            layer = canvas.copy()
            layer.set_alpha(round(255 * self.transition_age / 200))
            canvas = self.transition_from.copy()
            canvas.blit(layer, (0, 0))
        self.buttons = self.renderer.buttons if self.ready or self.message else []
        if self.buttons and self.focus == 'buttons':
            rect, _ = self.buttons[self.focus_index % len(self.buttons)]
            pygame.draw.rect(canvas, (255, 255, 255), rect.inflate(4, 4), 1, border_radius=4)
        width, height = self.window.get_size()
        factor = min(width / 320, height / 480)
        size = max(1, round(320 * factor)), max(1, round(480 * factor))
        self.viewport = pygame.Rect((width - size[0]) // 2, (height - size[1]) // 2, *size)
        self.window.fill((8, 12, 20))
        self.window.blit(pygame.transform.smoothscale(canvas, size), self.viewport)
        pygame.display.flip()

    def _scroll(self, delta):
        total, height = (len(self.files) * 35, 210) if self.screen == 'browser' else (self.episode_rows()[1], 252)
        self.scroll = max(0, min(max(0, total - height), self.scroll + delta))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWFOCUSGAINED):
            self.active = event.type == pygame.WINDOWFOCUSGAINED
            self.pressed = None
        if self.screen == 'game':
            return self.game.handle_event(event)
        if event.type == pygame.DROPBEGIN:
            self.dropping = True
        if event.type == pygame.DROPFILE:
            self.dropped_files.append(Path(event.file))
            return True
        if event.type == pygame.DROPCOMPLETE:
            self.dropping = False
            self.flush_drops()
        if self.busy:
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.back()
            return True
        if self.message:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.message = ''
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.message = ''
            return True
        if not self.ready:
            return True
        if event.type == pygame.TEXTINPUT and self.focus in ('search', 'path'):
            value = ''.join(c for c in event.text if c.isprintable())
            if self.focus == 'search':
                self.query = (self.query + value)[:100]
                self.scroll = 0
            else:
                self.path_text = (self.path_text + value)[:4096]
        elif event.type == pygame.KEYDOWN:
            if self.focus in ('search', 'path'):
                if event.key == pygame.K_BACKSPACE:
                    if self.focus == 'search':
                        self.query = self.query[:-1]
                        self.scroll = 0
                    else:
                        self.path_text = self.path_text[:-1]
                elif event.key == pygame.K_RETURN:
                    if self.focus == 'path':
                        self._attempt(lambda: self.read_folder(self.path_text))
                    else:
                        self.focus = None
                        pygame.key.stop_text_input()
            elif event.key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                if self.focus == 'buttons':
                    self.focus_index += -1 if event.key == pygame.K_UP else 1
                self.focus = 'buttons'
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.buttons:
                self.command(self.buttons[self.focus_index % len(self.buttons)][1])
            elif event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN) and self.screen in ('browser', 'episodes'):
                self._scroll(-210 if event.key == pygame.K_PAGEUP else 210)
        elif event.type == pygame.MOUSEWHEEL and self.screen in ('browser', 'episodes'):
            self.pressed = None
            self._scroll(-event.y * 35)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and event.button == 1:
            point = ((event.pos[0] - self.viewport.x) * 320 / self.viewport.width,
                     (event.pos[1] - self.viewport.y) * 480 / self.viewport.height)
            hit = next((command for rect, command in self.buttons if rect.collidepoint(point)), None)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.pressed = hit
            else:
                pressed, self.pressed = self.pressed, None
                if hit is not None and hit == pressed:
                    self.command(hit)
        return True

    def close(self):
        # Worker must finish its atomic publication before its ZIP is closed.
        self.executor.shutdown(wait=True)
        if self.game and self.screen == 'game':
            try:
                self.state.checkpoint(self.game.session)
            except ERRORS as error:
                logging.error('Automatic checkpoint failed: %s', error)
        if self.library:
            self.library.close()
        pygame.quit()

    def run(self):
        clock = pygame.time.Clock()
        running = True
        try:
            while running:
                elapsed = clock.tick(60)
                self.render()
                screen = self.screen
                for event in pygame.event.get():
                    running = self.handle_event(event)
                    # Do not deliver a queued click to a newly opened screen.
                    if not running or self.screen != screen:
                        break
                    if self.screen == 'game' and self.game.screen_token != self.game._screen_token():
                        break
                if running:
                    self.tick(elapsed)
        finally:
            self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Surviving High School — bring your own APK or IPA and episodes')
    parser.add_argument('--library', type=Path, help='Local content library (default: per-user application data)')
    parser.add_argument('--no-audio', action='store_true')
    parser.add_argument('--smoke-test', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.smoke_test:
        # A packaged-build check must never open or alter the player's library.
        with tempfile.TemporaryDirectory(prefix='shs-setup-test-') as temporary:
            app = Application(Path(temporary) / 'library', audio=False)
            try:
                if app.screen != 'setup' or app.library is not None:
                    raise RuntimeError('Expected first-launch setup without game content')
                app.render()
            finally:
                app.close()
        return
    Application(args.library, audio=not args.no_audio).run()


if __name__ == '__main__':
    main()
