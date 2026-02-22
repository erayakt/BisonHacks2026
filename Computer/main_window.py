from __future__ import annotations

import os
import threading
from typing import Optional

from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter

from controllers.app_controller import AppController
from ui.choices_panel import ChoicesPanel
from ui.image_canvas import ImageCanvas
from models.config import UiConfig

from dotenv import load_dotenv
load_dotenv()


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController, ui: UiConfig = UiConfig()):
        super().__init__()
        self.controller = controller

        # Used to suppress first highlight speech when entering choosing mode
        self._suppress_next_highlight_tts = False

        # --- TTS state ---
        self._tts_enabled = True
        self._tts_lock = threading.Lock()
        self._tts_generation = 0  # increment to cancel/override older speech
        self._eleven_client = None  # lazy init
        self._pygame_ready = False
        self._last_choosing_state: Optional[bool] = None  # avoid double MODE speech

        # Optional: configure voice/model via env
        self._eleven_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "xctasy8XvGp2cVO9HL9k")
        self._eleven_model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        self._eleven_output_format = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")

        # UI setup
        self.setWindowTitle(ui.window_title)
        self.resize(ui.window_width, ui.window_height)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = ImageCanvas()
        splitter.addWidget(self.canvas)

        self.choices_panel = ChoicesPanel(controller.state.choices)
        splitter.addWidget(self.choices_panel)

        splitter.setStretchFactor(0, ui.left_pane_weight)
        splitter.setStretchFactor(1, ui.right_pane_weight)
        splitter.setSizes([int(ui.window_width * 0.8), int(ui.window_width * 0.2)])

        self.choices_panel.setMinimumWidth(ui.right_min_width)
        self.choices_panel.setMaximumWidth(ui.right_max_width)

        self.setCentralWidget(splitter)

        # Wiring: image + overlays
        self.controller.image_changed.connect(self.canvas.set_image)
        self.controller.point_changed.connect(self.canvas.set_point)
        self.controller.grid_config_changed.connect(self.canvas.set_grid_config)

        # Wiring: choices
        self.controller.choices_updated.connect(self.choices_panel.set_choices)
        self.controller.highlighted_choice_changed.connect(self._on_highlight_changed)
        self.controller.chosen_choice_changed.connect(self._on_chosen_changed)

        # Mode: update UI + speak mode
        self.controller.choose_mode_changed.connect(self.choices_panel.set_choose_mode)
        self.controller.choose_mode_changed.connect(self._on_mode_changed)

        self.choices_panel.choice_clicked.connect(self.controller.on_choice_clicked)

        # Optional shortcuts
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.choices_panel.list.setFocus)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.canvas.setFocus)

        # CHOOSING/RUNNING controls
        QShortcut(QKeySequence("Space"), self, activated=self._on_space)
        QShortcut(QKeySequence("Up"), self, activated=lambda: self.controller.move_highlight(-1))
        QShortcut(QKeySequence("Down"), self, activated=lambda: self.controller.move_highlight(+1))

        # Demo shortcut
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._demo_move_point)

        # Optional: toggle TTS quickly
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._toggle_tts)

    # ------------------------
    # ElevenLabs + Windows audio (pygame) plumbing
    # ------------------------
    def _get_eleven_client(self):
        if self._eleven_client is not None:
            return self._eleven_client

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            self._tts_enabled = False
            print("[TTS] ELEVENLABS_API_KEY not set; disabling TTS.")
            return None

        try:
            from elevenlabs.client import ElevenLabs
            self._eleven_client = ElevenLabs(api_key=api_key)
            return self._eleven_client
        except Exception as e:
            self._tts_enabled = False
            print(f"[TTS] Failed to init ElevenLabs client; disabling TTS. Error: {e}")
            return None

    def _ensure_pygame_audio(self) -> bool:
        """
        Initialize pygame mixer once. Uses a conservative config for Windows reliability.
        """
        if self._pygame_ready:
            return True
        try:
            import pygame
            # Pre-init helps reduce latency and avoids some Windows mixer weirdness
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.init()
            self._pygame_ready = True
            return True
        except Exception as e:
            print(f"[TTS] Failed to init pygame audio. Error: {e}")
            self._tts_enabled = False
            return False

    def _stop_audio_locked(self) -> None:
        """
        Stop any currently playing audio immediately.
        Must be called while holding self._tts_lock.
        """
        if not self._pygame_ready:
            return
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass

    def speak(self, text: str) -> None:
        """
        Non-blocking TTS.
        - Hard-stops any currently playing audio before starting new.
        - Latest call wins (older threads self-cancel).
        """
        if not self._tts_enabled:
            return

        text = (text or "").strip()
        if not text:
            return

        # Cancel previous + stop audio right away
        with self._tts_lock:
            self._tts_generation += 1
            gen = self._tts_generation
            if self._pygame_ready:
                self._stop_audio_locked()

        def _worker():
            # Cancel early if something newer came in
            with self._tts_lock:
                if gen != self._tts_generation:
                    return

            client = self._get_eleven_client()
            if client is None:
                return

            if not self._ensure_pygame_audio():
                return

            try:
                audio = client.text_to_speech.convert(
                    text=text,
                    voice_id=self._eleven_voice_id,
                    model_id=self._eleven_model_id,
                    output_format=self._eleven_output_format,
                )

                # SDK may return bytes or an iterator of bytes
                if not isinstance(audio, (bytes, bytearray)):
                    audio = b"".join(audio)
                audio_bytes = bytes(audio)

                # Cancel again just before playback, and hard stop current audio
                with self._tts_lock:
                    if gen != self._tts_generation:
                        return
                    self._stop_audio_locked()

                # Play mp3 bytes via pygame.mixer.music using an in-memory file
                import io
                import pygame

                bio = io.BytesIO(audio_bytes)
                pygame.mixer.music.load(bio, namehint="speech.mp3")
                pygame.mixer.music.play()

            except Exception as e:
                print(f"[TTS] Error: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_tts(self) -> None:
        self._tts_enabled = not self._tts_enabled
        if not self._tts_enabled:
            with self._tts_lock:
                self._tts_generation += 1
                self._stop_audio_locked()
        self.statusBar().showMessage(f"TTS: {'ON' if self._tts_enabled else 'OFF'}")
        print(f"[TTS] {'ENABLED' if self._tts_enabled else 'DISABLED'}")

    # ------------------------
    # Your existing UI logic
    # ------------------------
    @Slot(bool)
    def _on_mode_changed(self, choosing: bool) -> None:
        # Avoid duplicate announcements if signal emits same value twice
        if self._last_choosing_state is not None and choosing == self._last_choosing_state:
            mode = "CHOOSING" if choosing else "RUNNING"
            self.statusBar().showMessage(f"Mode: {mode}")
            return
        self._last_choosing_state = choosing

        mode = "CHOOSING" if choosing else "RUNNING"
        print(f"[TTS] MODE: {mode}")
        self.statusBar().showMessage(f"Mode: {mode}")

        if choosing:
            # Suppress immediate highlight TTS triggered by entering choose mode
            self._suppress_next_highlight_tts = True

        # Speak mode change (no overlap due to hard-stop in speak())
        self.speak(f"Mode: {mode}")

    @Slot(int)
    def _on_highlight_changed(self, idx: int) -> None:
        self.choices_panel.set_highlighted_index(idx)

        if self._suppress_next_highlight_tts:
            self._suppress_next_highlight_tts = False
            return

        item = self.choices_panel.list.item(idx) if idx >= 0 else None
        if item is not None and self.controller.is_choosing():
            text = item.text()
            print(f"[TTS] {text}")
            self.speak(text)

    @Slot(int, str)
    def _on_chosen_changed(self, idx: int, text: str) -> None:
        self.choices_panel.set_chosen_index(idx)
        self.statusBar().showMessage(f"Chosen: {idx} — {text}")
        print(f"[TTS] CHOSEN: {text}")
        self.speak(f"Chosen. {text}")

    def _on_space(self) -> None:
        if not self.controller.is_choosing():
            self.controller.enter_choose_mode()
            self.choices_panel.list.setFocus()
            self.speak("Choosing mode.")
        else:
            self.controller.confirm_choice()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.controller.load_initial_image()
            self.choices_panel.list.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _demo_move_point(self) -> None:
        row = self.choices_panel.list.currentRow()
        offsets = [(80, 80), (220, 140), (340, 260), (420, 190)]
        x, y = offsets[row % len(offsets)] if row >= 0 else (60, 60)
        from PySide6.QtCore import QPointF
        self.controller.update_point(QPointF(x, y))