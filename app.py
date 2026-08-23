import os
import sys
import cv2
import numpy as np
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QLabel, QPushButton, QSlider, QCheckBox,
    QDoubleSpinBox, QSpinBox, QFileDialog, QGroupBox, QProgressBar, QComboBox,
    QMessageBox, QLineEdit, QScrollArea, QTabWidget, QStyleOptionSlider, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QIcon, QPainter, QPen, QColor

from ser_parser import SERParser
from converter_worker import ConverterWorker
from image_utils import apply_hsl_colorization, apply_logo_overlay

class BookmarkSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.start_bookmark = None  # 0-indexed frame
        self.end_bookmark = None    # 0-indexed frame

    def set_bookmarks(self, start_idx: Optional[int], end_idx: Optional[int]):
        self.start_bookmark = start_idx
        self.end_bookmark = end_idx
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.minimum() >= self.maximum():
            return

        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderGroove, self
        )

        total_range = float(self.maximum() - self.minimum())
        if total_range <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = groove_rect.width()
        y_top = groove_rect.top() - 3
        h = groove_rect.height() + 6

        # Draw Start Crop Bookmark Line (Green)
        if self.start_bookmark is not None and self.minimum() <= self.start_bookmark <= self.maximum():
            ratio = (self.start_bookmark - self.minimum()) / total_range
            x = groove_rect.left() + int(ratio * w)
            painter.setPen(QPen(QColor("#2ea44f"), 3))
            painter.drawLine(x, y_top, x, y_top + h)

        # Draw End Crop Bookmark Line (Red)
        if self.end_bookmark is not None and self.minimum() <= self.end_bookmark <= self.maximum():
            ratio = (self.end_bookmark - self.minimum()) / total_range
            x = groove_rect.left() + int(ratio * w)
            painter.setPen(QPen(QColor("#dc2626"), 3))
            painter.drawLine(x, y_top, x, y_top + h)

class DropFrame(QFrame):
    file_dropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop-frame")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.ser'):
                    event.acceptProposedAction()
                    self.setStyleSheet("border: 2px dashed #4fd1c5; background-color: #1e2837;")
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.ser'):
                self.file_dropped.emit(file_path)
                event.acceptProposedAction()
                return

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AstroSER to MP4 Converter")
        self.resize(1150, 920)
        self.setMinimumSize(980, 780)
        
        self.current_ser_path = None
        self.parser = None
        self.worker = None
        self.original_fps = 30.0
        self.current_preview_frame = None

        self.init_ui()
        self.apply_stylesheet()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(10)

        # 1. Header Title
        title_label = QLabel("AstroSER to MP4 Converter")
        title_label.setObjectName("app-title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 2. Compact Drag & Drop Area
        self.drop_frame = DropFrame()
        drop_layout = QHBoxLayout(self.drop_frame)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.setSpacing(10)
        drop_layout.setContentsMargins(15, 5, 15, 5)
        
        self.lbl_drop_icon = QLabel("📁")
        self.lbl_drop_icon.setObjectName("drop-icon")
        drop_layout.addWidget(self.lbl_drop_icon)

        self.lbl_drop_text = QLabel("Trascina qui il file .SER o fai clic per sfogliare")
        self.lbl_drop_text.setObjectName("drop-text")
        drop_layout.addWidget(self.lbl_drop_text)

        self.drop_frame.file_dropped.connect(self.load_ser_file)
        self.drop_frame.clicked.connect(self.browse_ser_file)
        main_layout.addWidget(self.drop_frame)

        # 3. Main Content Panel (Left Tabs | Right Preview)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        main_layout.addLayout(content_layout, stretch=1)

        # Left Column - QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(460)

        # --- TAB 1: 📷 Immagine & Colore ---
        tab_img = QWidget()
        tab_img_layout = QVBoxLayout(tab_img)
        tab_img_layout.setContentsMargins(10, 10, 10, 10)
        tab_img_layout.setSpacing(10)

        # Metadati Group
        self.grp_meta = QGroupBox("Metadati File SER")
        meta_grid = QGridLayout(self.grp_meta)
        meta_grid.setSpacing(6)
        meta_grid.setContentsMargins(12, 18, 12, 12)
        
        self.lbl_meta_file = QLabel("File: -")
        self.lbl_meta_dim = QLabel("Risoluzione: -")
        self.lbl_meta_frames = QLabel("Fotogrammi: -")
        self.lbl_meta_depth = QLabel("Bit Depth: -")
        self.lbl_meta_color = QLabel("Formato Colore: -")
        self.lbl_meta_observer = QLabel("Osservatore: -")
        self.lbl_meta_instrument = QLabel("Strumento: -")
        self.lbl_meta_telescope = QLabel("Telescopio: -")
        self.lbl_meta_date = QLabel("Data (UTC): -")

        meta_grid.addWidget(self.lbl_meta_file, 0, 0, 1, 2)
        meta_grid.addWidget(self.lbl_meta_dim, 1, 0)
        meta_grid.addWidget(self.lbl_meta_frames, 1, 1)
        meta_grid.addWidget(self.lbl_meta_depth, 2, 0)
        meta_grid.addWidget(self.lbl_meta_color, 2, 1)
        meta_grid.addWidget(self.lbl_meta_observer, 3, 0, 1, 2)
        meta_grid.addWidget(self.lbl_meta_instrument, 4, 0, 1, 2)
        meta_grid.addWidget(self.lbl_meta_telescope, 5, 0, 1, 2)
        meta_grid.addWidget(self.lbl_meta_date, 6, 0, 1, 2)
        tab_img_layout.addWidget(self.grp_meta)

        # Bayer & Color Group
        self.grp_bayer = QGroupBox("Correzione Colore & Pattern Bayer")
        bayer_layout = QVBoxLayout(self.grp_bayer)
        bayer_layout.setSpacing(8)
        bayer_layout.setContentsMargins(12, 18, 12, 12)

        pattern_hbox = QHBoxLayout()
        lbl_pat = QLabel("Pattern Bayer / Modalità:")
        lbl_pat.setMinimumWidth(160)
        pattern_hbox.addWidget(lbl_pat)
        
        self.cmb_pattern = QComboBox()
        self.cmb_pattern.addItems([
            "Auto (dall'Header)",
            "Disattivato (Già a Colori / RGB)",
            "Bayer RGGB",
            "Bayer BGGR",
            "Bayer GRBG",
            "Bayer GBRG",
            "Monocromatico",
            "RGB Intercalato",
            "RGB Planare"
        ])
        self.cmb_pattern.currentIndexChanged.connect(self.on_pattern_changed)
        pattern_hbox.addWidget(self.cmb_pattern, stretch=1)
        bayer_layout.addLayout(pattern_hbox)

        algo_hbox = QHBoxLayout()
        lbl_alg = QLabel("Algoritmo Debayer:")
        lbl_alg.setMinimumWidth(160)
        algo_hbox.addWidget(lbl_alg)

        self.cmb_algo = QComboBox()
        self.cmb_algo.addItems([
            "Edge-Aware (Alta Qualità, No Righe)",
            "VNG (Astronomia)",
            "Bilineare Standard"
        ])
        self.cmb_algo.currentIndexChanged.connect(self.refresh_preview)
        algo_hbox.addWidget(self.cmb_algo, stretch=1)
        bayer_layout.addLayout(algo_hbox)

        self.chk_awb = QCheckBox("Auto Bilanciamento Bianco (AWB)")
        self.chk_awb.setChecked(True)
        self.chk_awb.stateChanged.connect(self.refresh_preview)
        bayer_layout.addWidget(self.chk_awb)

        tab_img_layout.addWidget(self.grp_bayer)

        # Enhancements Group
        self.grp_enh = QGroupBox("Luminosità & Stiramento Gamma")
        enh_layout = QVBoxLayout(self.grp_enh)
        enh_layout.setSpacing(8)
        enh_layout.setContentsMargins(12, 18, 12, 12)

        self.chk_stretch = QCheckBox("Auto-Stretch (Ottimizzazione Contrasto)")
        self.chk_stretch.setChecked(True)
        self.chk_stretch.stateChanged.connect(self.refresh_preview)
        enh_layout.addWidget(self.chk_stretch)

        self.lbl_gamma = QLabel("Stiramento Gamma Oggetto (1.00x):")
        enh_layout.addWidget(self.lbl_gamma)
        
        self.sld_gamma = QSlider(Qt.Orientation.Horizontal)
        self.sld_gamma.setRange(10, 500)
        self.sld_gamma.setValue(100)
        self.sld_gamma.valueChanged.connect(self.on_gamma_changed)
        enh_layout.addWidget(self.sld_gamma)

        self.lbl_brightness = QLabel("Luminosità Lineare (0):")
        enh_layout.addWidget(self.lbl_brightness)
        
        self.sld_brightness = QSlider(Qt.Orientation.Horizontal)
        self.sld_brightness.setRange(-100, 100)
        self.sld_brightness.setValue(0)
        self.sld_brightness.valueChanged.connect(self.on_brightness_changed)
        enh_layout.addWidget(self.sld_brightness)

        tab_img_layout.addWidget(self.grp_enh)
        tab_img_layout.addStretch(1)
        self.tabs.addTab(tab_img, "📷 Immagine & Colore")

        # --- TAB 2: ⏱️ Velocità & Taglio ---
        tab_speed = QWidget()
        tab_speed_layout = QVBoxLayout(tab_speed)
        tab_speed_layout.setContentsMargins(10, 10, 10, 10)
        tab_speed_layout.setSpacing(10)

        # Speed Regulation Group
        self.grp_speed = QGroupBox("Regolazione Velocità Video")
        speed_layout = QVBoxLayout(self.grp_speed)
        speed_layout.setSpacing(10)
        speed_layout.setContentsMargins(12, 18, 12, 12)

        fps_hbox = QHBoxLayout()
        lbl_fps = QLabel("FPS Video Output:")
        lbl_fps.setMinimumWidth(160)
        fps_hbox.addWidget(lbl_fps)

        self.num_fps = QDoubleSpinBox()
        self.num_fps.setRange(0.1, 240.0)
        self.num_fps.setValue(30.0)
        self.num_fps.setSingleStep(1.0)
        self.num_fps.setDecimals(2)
        self.num_fps.valueChanged.connect(self.update_multiplier_from_fps)
        fps_hbox.addWidget(self.num_fps, stretch=1)
        speed_layout.addLayout(fps_hbox)

        mult_hbox = QHBoxLayout()
        lbl_mult = QLabel("Moltiplicatore Velocità:")
        lbl_mult.setMinimumWidth(160)
        mult_hbox.addWidget(lbl_mult)

        self.cmb_mult = QComboBox()
        self.cmb_mult.addItems([
            "Personalizzato",
            "0.1x (Molto Lento)",
            "0.25x (1/4 Velocità)",
            "0.33x (1/3 Velocità)",
            "0.5x (1/2 Velocità)",
            "0.75x",
            "1.0x (Normale)",
            "1.5x",
            "2.0x (2x Accelerato)",
            "3.0x (3x)",
            "5.0x (5x)",
            "10.0x (10x)"
        ])
        self.cmb_mult.setCurrentIndex(6) # 1.0x
        self.cmb_mult.currentIndexChanged.connect(self.update_fps_from_multiplier)
        mult_hbox.addWidget(self.cmb_mult, stretch=1)
        speed_layout.addLayout(mult_hbox)

        tab_speed_layout.addWidget(self.grp_speed)

        # Trim / Crop Range Group
        self.grp_trim = QGroupBox("Taglio Fotogrammi (Trim Range)")
        trim_layout = QVBoxLayout(self.grp_trim)
        trim_layout.setSpacing(10)
        trim_layout.setContentsMargins(12, 18, 12, 12)

        start_hbox = QHBoxLayout()
        start_hbox.addWidget(QLabel("Da Fotogramma:"))
        self.num_start_frame = QSpinBox()
        self.num_start_frame.setRange(1, 999999)
        self.num_start_frame.setValue(1)
        self.num_start_frame.editingFinished.connect(self.on_start_frame_changed)
        self.num_start_frame.valueChanged.connect(self.on_start_frame_changed)
        start_hbox.addWidget(self.num_start_frame, stretch=1)

        self.btn_set_start_frame = QPushButton("Da Anteprima")
        self.btn_set_start_frame.clicked.connect(self.set_start_from_preview)
        start_hbox.addWidget(self.btn_set_start_frame)
        trim_layout.addLayout(start_hbox)

        end_hbox = QHBoxLayout()
        end_hbox.addWidget(QLabel("A Fotogramma:"))
        self.num_end_frame = QSpinBox()
        self.num_end_frame.setRange(1, 999999)
        self.num_end_frame.setValue(1)
        self.num_end_frame.editingFinished.connect(self.on_end_frame_changed)
        self.num_end_frame.valueChanged.connect(self.on_end_frame_changed)
        end_hbox.addWidget(self.num_end_frame, stretch=1)

        self.btn_set_end_frame = QPushButton("Da Anteprima")
        self.btn_set_end_frame.clicked.connect(self.set_end_from_preview)
        end_hbox.addWidget(self.btn_set_end_frame)
        trim_layout.addLayout(end_hbox)

        self.lbl_trim_info = QLabel("Fotogrammi selezionati: 0 / 0")
        self.lbl_trim_info.setObjectName("status-label")
        trim_layout.addWidget(self.lbl_trim_info)

        tab_speed_layout.addWidget(self.grp_trim)
        tab_speed_layout.addStretch(1)
        self.tabs.addTab(tab_speed, "⏱️ Velocità & Taglio")

        # --- TAB 3: 🎨 Colorizzazione HSL ---
        tab_hsl = QWidget()
        tab_hsl_layout = QVBoxLayout(tab_hsl)
        tab_hsl_layout.setContentsMargins(10, 10, 10, 10)
        tab_hsl_layout.setSpacing(10)

        self.grp_hsl = QGroupBox("Colorizzazione Solare & Tonalità (HSL)")
        hsl_layout = QVBoxLayout(self.grp_hsl)
        hsl_layout.setSpacing(10)
        hsl_layout.setContentsMargins(12, 18, 12, 12)

        self.chk_hsl_enable = QCheckBox("Abilita Colorizzazione (Colorize)")
        self.chk_hsl_enable.stateChanged.connect(self.refresh_preview)
        hsl_layout.addWidget(self.chk_hsl_enable)

        preset_hbox = QHBoxLayout()
        preset_hbox.addWidget(QLabel("Preset Colore:"))
        self.cmb_hsl_preset = QComboBox()
        self.cmb_hsl_preset.addItems([
            "Rosso Solare H-alpha (656nm - Rubino)",
            "Arancione Solare (Prominenze / Luce Solare)",
            "Giallo Solare (Continuum / Luce Bianca)",
            "Oro Solare",
            "Calcio-K / CaK (393nm - Violetto)",
            "Blu (Deep Sky)",
            "Inferno (Falso Colore)",
            "Plasma (Falso Colore)",
            "Personalizzato"
        ])
        self.cmb_hsl_preset.currentIndexChanged.connect(self.on_hsl_preset_changed)
        preset_hbox.addWidget(self.cmb_hsl_preset, stretch=1)
        hsl_layout.addLayout(preset_hbox)

        self.lbl_hsl_hue = QLabel("Tonalità / Hue (355°):")
        hsl_layout.addWidget(self.lbl_hsl_hue)
        self.sld_hsl_hue = QSlider(Qt.Orientation.Horizontal)
        self.sld_hsl_hue.setRange(0, 360)
        self.sld_hsl_hue.setValue(355)
        self.sld_hsl_hue.valueChanged.connect(self.on_hsl_slider_changed)
        hsl_layout.addWidget(self.sld_hsl_hue)

        self.lbl_hsl_sat = QLabel("Saturazione (100%):")
        hsl_layout.addWidget(self.lbl_hsl_sat)
        self.sld_hsl_sat = QSlider(Qt.Orientation.Horizontal)
        self.sld_hsl_sat.setRange(0, 300)
        self.sld_hsl_sat.setValue(100)
        self.sld_hsl_sat.valueChanged.connect(self.on_hsl_slider_changed)
        hsl_layout.addWidget(self.sld_hsl_sat)

        self.lbl_hsl_lum = QLabel("Luminosità (0):")
        hsl_layout.addWidget(self.lbl_hsl_lum)
        self.sld_hsl_lum = QSlider(Qt.Orientation.Horizontal)
        self.sld_hsl_lum.setRange(-100, 100)
        self.sld_hsl_lum.setValue(0)
        self.sld_hsl_lum.valueChanged.connect(self.on_hsl_slider_changed)
        hsl_layout.addWidget(self.sld_hsl_lum)

        tab_hsl_layout.addWidget(self.grp_hsl)
        tab_hsl_layout.addStretch(1)
        self.tabs.addTab(tab_hsl, "🎨 Colorizzazione HSL")

        # --- TAB 4: 🎵 Logo, Titoli & Audio ---
        tab_extras = QWidget()
        tab_extras_scroll = QScrollArea()
        tab_extras_scroll.setWidgetResizable(True)
        tab_extras_scroll_content = QWidget()
        tab_extras_layout = QVBoxLayout(tab_extras_scroll_content)
        tab_extras_layout.setContentsMargins(10, 10, 10, 10)
        tab_extras_layout.setSpacing(10)

        # Logo Watermark Group
        self.grp_logo = QGroupBox("Sovrapposizione Logo / Filigrana PNG")
        logo_layout = QVBoxLayout(self.grp_logo)
        logo_layout.setSpacing(8)
        logo_layout.setContentsMargins(12, 18, 12, 12)

        self.chk_logo_enable = QCheckBox("Sovrapponi Logo / Filigrana")
        self.chk_logo_enable.stateChanged.connect(self.refresh_preview)
        logo_layout.addWidget(self.chk_logo_enable)

        logo_file_hbox = QHBoxLayout()
        self.txt_logo_path = QLineEdit()
        self.txt_logo_path.setPlaceholderText("Seleziona immagine PNG con trasparenza...")
        self.txt_logo_path.textChanged.connect(self.refresh_preview)
        logo_file_hbox.addWidget(self.txt_logo_path, stretch=1)
        
        self.btn_browse_logo = QPushButton("Sfoglia...")
        self.btn_browse_logo.clicked.connect(self.browse_logo_file)
        logo_file_hbox.addWidget(self.btn_browse_logo)
        logo_layout.addLayout(logo_file_hbox)

        pos_hbox = QHBoxLayout()
        pos_hbox.addWidget(QLabel("Posizione Logo:"))
        self.cmb_logo_pos = QComboBox()
        self.cmb_logo_pos.addItems([
            "In Basso a Destra",
            "In Basso a Sinistra",
            "In Alto a Destra",
            "In Alto a Sinistra",
            "Centro"
        ])
        self.cmb_logo_pos.currentIndexChanged.connect(self.refresh_preview)
        pos_hbox.addWidget(self.cmb_logo_pos, stretch=1)
        logo_layout.addLayout(pos_hbox)

        self.lbl_logo_scale = QLabel("Dimensione Logo (15%):")
        logo_layout.addWidget(self.lbl_logo_scale)
        self.sld_logo_scale = QSlider(Qt.Orientation.Horizontal)
        self.sld_logo_scale.setRange(5, 50)
        self.sld_logo_scale.setValue(15)
        self.sld_logo_scale.valueChanged.connect(self.on_logo_slider_changed)
        logo_layout.addWidget(self.sld_logo_scale)

        self.lbl_logo_opacity = QLabel("Opacità Logo (100%):")
        logo_layout.addWidget(self.lbl_logo_opacity)
        self.sld_logo_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sld_logo_opacity.setRange(10, 100)
        self.sld_logo_opacity.setValue(100)
        self.sld_logo_opacity.valueChanged.connect(self.on_logo_slider_changed)
        logo_layout.addWidget(self.sld_logo_opacity)

        tab_extras_layout.addWidget(self.grp_logo)

        # Intro / Outro Title Cards Group
        self.grp_titles = QGroupBox("Schede Titolo Iniziale ed Finale (Intro / Outro)")
        titles_layout = QVBoxLayout(self.grp_titles)
        titles_layout.setSpacing(8)
        titles_layout.setContentsMargins(12, 18, 12, 12)

        dur_hbox = QHBoxLayout()
        dur_hbox.addWidget(QLabel("Durata Titoli Inizio/Fine:"))
        self.num_title_duration = QDoubleSpinBox()
        self.num_title_duration.setRange(0.5, 10.0)
        self.num_title_duration.setValue(2.0)
        self.num_title_duration.setSingleStep(0.5)
        self.num_title_duration.setSuffix(" sec")
        dur_hbox.addWidget(self.num_title_duration, stretch=1)
        titles_layout.addLayout(dur_hbox)

        # Intro
        self.chk_intro_enable = QCheckBox("Titolo Iniziale (Intro)")
        titles_layout.addWidget(self.chk_intro_enable)

        intro_hbox = QHBoxLayout()
        self.txt_intro_path = QLineEdit()
        self.txt_intro_path.setPlaceholderText("Seleziona immagine/FITS per l'Intro...")
        intro_hbox.addWidget(self.txt_intro_path, stretch=1)
        self.btn_browse_intro = QPushButton("Sfoglia...")
        self.btn_browse_intro.clicked.connect(self.browse_intro_file)
        intro_hbox.addWidget(self.btn_browse_intro)
        titles_layout.addLayout(intro_hbox)

        # Outro
        self.chk_outro_enable = QCheckBox("Titolo Finale (Outro)")
        titles_layout.addWidget(self.chk_outro_enable)

        outro_hbox = QHBoxLayout()
        self.txt_outro_path = QLineEdit()
        self.txt_outro_path.setPlaceholderText("Seleziona immagine/FITS per l'Outro...")
        outro_hbox.addWidget(self.txt_outro_path, stretch=1)
        self.btn_browse_outro = QPushButton("Sfoglia...")
        self.btn_browse_outro.clicked.connect(self.browse_outro_file)
        outro_hbox.addWidget(self.btn_browse_outro)
        titles_layout.addLayout(outro_hbox)

        tab_extras_layout.addWidget(self.grp_titles)

        # Audio Soundtrack Group
        self.grp_audio = QGroupBox("Colonna Sonora Audio (Video MP4)")
        audio_layout = QVBoxLayout(self.grp_audio)
        audio_layout.setSpacing(8)
        audio_layout.setContentsMargins(12, 18, 12, 12)

        self.chk_audio_enable = QCheckBox("Includi Colonna Sonora Audio nel Video MP4")
        audio_layout.addWidget(self.chk_audio_enable)

        audio_preset_hbox = QHBoxLayout()
        audio_preset_hbox.addWidget(QLabel("Brano Audio:"))
        self.cmb_audio_preset = QComboBox()
        self.cmb_audio_preset.addItems([
            "Interstellar - Hans Zimmer Style (30s)",
            "Beethoven - Moonlight Sonata (30s)",
            "Beethoven - 5th Symphony (30s)",
            "Beethoven - Moonlight Sonata (Completo)",
            "Beethoven - 5th Symphony (Completo)",
            "Personalizzato (Sfoglia file audio...)"
        ])
        self.cmb_audio_preset.currentIndexChanged.connect(self.on_audio_preset_changed)
        audio_preset_hbox.addWidget(self.cmb_audio_preset, stretch=1)
        audio_layout.addLayout(audio_preset_hbox)

        audio_file_hbox = QHBoxLayout()
        self.txt_audio_path = QLineEdit()
        self.txt_audio_path.setPlaceholderText("Seleziona file audio WAV / MP3 / OGG...")
        audio_file_hbox.addWidget(self.txt_audio_path, stretch=1)
        self.btn_browse_audio = QPushButton("Sfoglia...")
        self.btn_browse_audio.clicked.connect(self.browse_audio_file)
        audio_file_hbox.addWidget(self.btn_browse_audio)
        audio_layout.addLayout(audio_file_hbox)

        self.chk_audio_loop = QCheckBox("Ripeti audio in loop se il video è più lungo")
        self.chk_audio_loop.setChecked(True)
        audio_layout.addWidget(self.chk_audio_loop)

        tab_extras_layout.addWidget(self.grp_audio)
        tab_extras_layout.addStretch(1)

        tab_extras_scroll.setWidget(tab_extras_scroll_content)
        
        tab_extras_main_layout = QVBoxLayout(tab_extras)
        tab_extras_main_layout.setContentsMargins(0, 0, 0, 0)
        tab_extras_main_layout.addWidget(tab_extras_scroll)

        self.tabs.addTab(tab_extras, "🎵 Logo, Titoli & Audio")

        # Initialize default audio track path
        self.on_audio_preset_changed(0)

        content_layout.addWidget(self.tabs, stretch=1)

        # Right Column - Preview Area
        self.grp_preview = QGroupBox("Anteprima Fotogramma")
        preview_layout = QVBoxLayout(self.grp_preview)
        preview_layout.setSpacing(10)
        preview_layout.setContentsMargins(12, 18, 12, 12)

        self.lbl_preview_img = QLabel("Carica un file .SER per visualizzare l'anteprima")
        self.lbl_preview_img.setObjectName("preview-img-label")
        self.lbl_preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_img.setMinimumSize(400, 320)
        preview_layout.addWidget(self.lbl_preview_img, stretch=1)

        slider_hbox = QHBoxLayout()
        self.lbl_frame_idx = QLabel("Frame: 0 / 0")
        self.lbl_frame_idx.setMinimumWidth(110)
        
        # Use custom BookmarkSlider to paint crop start/end bookmarks
        self.sld_preview = BookmarkSlider(Qt.Orientation.Horizontal)
        self.sld_preview.setEnabled(False)
        self.sld_preview.valueChanged.connect(self.on_preview_slider_changed)
        
        slider_hbox.addWidget(self.lbl_frame_idx)
        slider_hbox.addWidget(self.sld_preview, stretch=1)
        preview_layout.addLayout(slider_hbox)

        # Bookmark legend
        self.lbl_legend = QLabel("🟢 Inizio Crop   🔴 Fine Crop")
        self.lbl_legend.setObjectName("timestamp-label")
        self.lbl_legend.setAlignment(Qt.AlignmentFlag.AlignRight)
        preview_layout.addWidget(self.lbl_legend)
        
        self.lbl_frame_time = QLabel("Timestamp: -")
        self.lbl_frame_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_frame_time.setObjectName("timestamp-label")
        preview_layout.addWidget(self.lbl_frame_time)

        content_layout.addWidget(self.grp_preview, stretch=1)

        # 4. Output Path Selector & Convert Button
        self.grp_output = QGroupBox("Output Video / Esportazione")
        output_layout = QVBoxLayout(self.grp_output)
        output_layout.setSpacing(8)
        output_layout.setContentsMargins(12, 18, 12, 12)

        format_hbox = QHBoxLayout()
        format_hbox.addWidget(QLabel("Formato Output:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(["Video MP4 (.mp4)", "Animazione GIF (.gif)"])
        self.cmb_format.currentIndexChanged.connect(self.on_format_changed)
        format_hbox.addWidget(self.cmb_format, stretch=1)
        output_layout.addLayout(format_hbox)

        out_hbox = QHBoxLayout()
        out_hbox.addWidget(QLabel("Salva come:"))
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setPlaceholderText("Seleziona il percorso per il file di output...")
        out_hbox.addWidget(self.txt_output_path, stretch=1)
        
        self.btn_browse_out = QPushButton("Sfoglia...")
        self.btn_browse_out.clicked.connect(self.browse_output_path)
        out_hbox.addWidget(self.btn_browse_out)
        output_layout.addLayout(out_hbox)

        self.quality_widget = QWidget()
        quality_hbox = QHBoxLayout(self.quality_widget)
        quality_hbox.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_quality = QLabel("Qualità video MP4 (98%):")
        self.lbl_quality.setMinimumWidth(180)
        quality_hbox.addWidget(self.lbl_quality)
        
        self.sld_quality = QSlider(Qt.Orientation.Horizontal)
        self.sld_quality.setRange(50, 100)
        self.sld_quality.setValue(98)
        self.sld_quality.valueChanged.connect(self.on_quality_slider_changed)
        quality_hbox.addWidget(self.sld_quality, stretch=1)
        output_layout.addWidget(self.quality_widget)

        self.btn_convert = QPushButton("Converti / Esporta")
        self.btn_convert.setObjectName("btn-convert")
        self.btn_convert.clicked.connect(self.toggle_conversion)
        output_layout.addWidget(self.btn_convert)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Pronto")
        self.lbl_status.setObjectName("status-label")
        output_layout.addWidget(self.lbl_status)

        main_layout.addWidget(self.grp_output)

    def apply_stylesheet(self):
        style = """
            QMainWindow {
                background-color: #0d1117;
            }
            #app-title {
                color: #58a6ff;
                font-size: 20px;
                font-weight: bold;
                padding-bottom: 3px;
                border-bottom: 1px solid #21262d;
            }
            QGroupBox {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                font-weight: bold;
                color: #58a6ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                left: 10px;
                top: 2px;
                background-color: #21262d;
                border-radius: 4px;
            }
            QLabel {
                color: #c9d1d9;
                font-size: 13px;
                min-height: 20px;
            }
            #timestamp-label {
                color: #8b949e;
                font-size: 11px;
            }
            #status-label {
                color: #8b949e;
                font-style: italic;
            }
            #drop-frame {
                border: 2px dashed #30363d;
                border-radius: 8px;
                background-color: #161b22;
            }
            #drop-frame:hover {
                border: 2px dashed #58a6ff;
                background-color: #1c212a;
            }
            #drop-icon {
                font-size: 20px;
            }
            #drop-text {
                font-size: 13px;
                font-weight: bold;
                color: #8b949e;
            }
            #preview-img-label {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #8b949e;
            }
            QPushButton {
                background-color: #21262d;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px 12px;
                font-weight: bold;
                min-height: 26px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
            QPushButton#btn-convert {
                background-color: #238636;
                color: white;
                border: 1px solid #2ea44f;
                font-size: 15px;
                min-height: 36px;
            }
            QPushButton#btn-convert:hover {
                background-color: #2ea44f;
            }
            QPushButton#btn-convert:disabled {
                background-color: #21262d;
                border-color: #30363d;
                color: #8b949e;
            }
            QProgressBar {
                border: 1px solid #30363d;
                border-radius: 6px;
                text-align: center;
                background-color: #0d1117;
                color: white;
                height: 20px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 5px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #30363d;
                height: 6px;
                background: #0d1117;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #58a6ff;
                border: 1px solid #30363d;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #1f6feb;
            }
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
                padding: 4px 8px;
                min-height: 24px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1f242c;
                border: 1px solid #30363d;
                color: #c9d1d9;
                selection-background-color: #2d3748;
                selection-color: #58a6ff;
                padding: 4px;
            }
            QCheckBox {
                color: #c9d1d9;
                min-height: 22px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #30363d;
                border-radius: 4px;
                background: #0d1117;
            }
            QCheckBox::indicator:checked {
                background: #238636;
                border-color: #2ea44f;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 8px;
                background-color: #161b22;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 12px;
                color: #8b949e;
                font-weight: bold;
                font-size: 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #161b22;
                color: #58a6ff;
                border-bottom: 2px solid #58a6ff;
            }
            QTabBar::tab:hover {
                color: #c9d1d9;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
        """
        self.setStyleSheet(style)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_preview_frame is not None:
            self.display_preview(self.current_preview_frame)

    def browse_ser_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona File SER", "", "Astro SER Files (*.ser)"
        )
        if file_path:
            self.load_ser_file(file_path)

    def load_ser_file(self, file_path: str):
        try:
            self.lbl_status.setText("Caricamento del file in corso...")
            if self.parser:
                self.parser.close()
            
            self.parser = SERParser(file_path)
            self.current_ser_path = file_path
            header = self.parser.header

            filename = os.path.basename(file_path)
            self.lbl_drop_text.setText(f"File caricato: {filename} (Fai clic o trascina un altro file per cambiarlo)")
            self.lbl_drop_icon.setText("⭐")

            self.original_fps = self.parser.get_average_fps()
            self.num_fps.setValue(self.original_fps)
            self.cmb_mult.setCurrentIndex(6) # 1.0x

            is_already_debayered = header.color_id >= 100 or self.parser._channels == 3
            if is_already_debayered:
                if header.color_id == 100:
                    color_str = "RGB Colore (Già Debayerizzato)"
                elif header.color_id == 101:
                    color_str = "BGR Colore (Già Debayerizzato)"
                else:
                    color_str = "RGB Colore (3 Canali - Già Debayerizzato)"
            else:
                color_names = {
                    0: "Monocromatico",
                    1: "Bayer RGGB",
                    2: "Bayer GRBG",
                    3: "Bayer GBRG",
                    4: "Bayer BGGR",
                    8: "Bayer CYYM",
                    9: "Bayer YCMY",
                    16: "Bayer YMCY",
                    17: "Bayer MYYC"
                }
                color_str = color_names.get(header.color_id, f"Sconosciuto ({header.color_id})")

            if is_already_debayered:
                self.chk_awb.blockSignals(True)
                self.chk_awb.setChecked(False)
                self.chk_awb.blockSignals(False)
            else:
                self.chk_awb.blockSignals(True)
                self.chk_awb.setChecked(True)
                self.chk_awb.blockSignals(False)

            duration_sec = header.frame_count / self.original_fps if self.original_fps > 0 else 0
            dur_min = int(duration_sec // 60)
            dur_sec = duration_sec % 60

            self.lbl_meta_file.setText(f"File: {filename}")
            self.lbl_meta_dim.setText(f"Risoluzione: {header.image_width} x {header.image_height}")
            self.lbl_meta_frames.setText(f"Fotogrammi: {header.frame_count} (~{dur_min}m {dur_sec:.1f}s)")
            self.lbl_meta_depth.setText(f"Bit Depth: {header.pixel_depth} bit")
            self.lbl_meta_color.setText(f"Formato Colore: {color_str}")
            self.lbl_meta_observer.setText(f"Osservatore: {header.observer or '-'}")
            self.lbl_meta_instrument.setText(f"Strumento: {header.instrument or '-'}")
            self.lbl_meta_telescope.setText(f"Telescopio: {header.telescope or '-'}")
            
            date_str = header.datetime_utc.strftime("%d/%m/%Y %H:%M:%S UTC") if header.datetime_utc else "-"
            self.lbl_meta_date.setText(f"Data di Inizio: {date_str}")

            # Configure Trim controls range
            self.num_start_frame.blockSignals(True)
            self.num_end_frame.blockSignals(True)
            self.num_start_frame.setRange(1, header.frame_count)
            self.num_start_frame.setValue(1)
            self.num_end_frame.setRange(1, header.frame_count)
            self.num_end_frame.setValue(header.frame_count)
            self.num_start_frame.blockSignals(False)
            self.num_end_frame.blockSignals(False)

            self.update_bookmarks()
            self.update_trim_info()
            self.update_output_path_extension()

            self.sld_preview.setEnabled(True)
            self.sld_preview.setRange(0, header.frame_count - 1)
            self.sld_preview.setValue(0)
            self.lbl_frame_idx.setText(f"Frame: 1 / {header.frame_count}")

            self.update_debayer_algo_state()
            self.on_preview_slider_changed(0)
            self.lbl_status.setText("File SER caricato con successo.")

        except Exception as e:
            QMessageBox.critical(self, "Errore Caricamento", f"Impossibile aprire il file SER:\n{str(e)}")
            self.lbl_status.setText("Errore durante il caricamento.")

    def get_current_bayer_mode(self) -> str:
        idx = self.cmb_pattern.currentIndex()
        modes = ["AUTO", "DISABLED", "RGGB", "BGGR", "GRBG", "GBRG", "MONO", "RGB", "RGB_PLANAR"]
        return modes[idx] if idx < len(modes) else "AUTO"

    def get_current_debayer_algo(self) -> str:
        idx = self.cmb_algo.currentIndex()
        algos = ["EA", "VNG", "BILINEAR"]
        return algos[idx] if idx < len(algos) else "EA"

    def update_debayer_algo_state(self):
        mode = self.get_current_bayer_mode()
        is_already_debayered = self.parser and (self.parser.header.color_id >= 100 or self.parser._channels == 3)
        if mode in ["DISABLED", "MONO", "RGB", "RGB_PLANAR"] or (mode == "AUTO" and is_already_debayered):
            self.cmb_algo.setEnabled(False)
        else:
            self.cmb_algo.setEnabled(True)

    def on_pattern_changed(self):
        self.update_debayer_algo_state()
        self.refresh_preview()

    def on_preview_slider_changed(self, val: int):
        if not self.parser:
            return

        self.lbl_frame_idx.setText(f"Frame: {val + 1} / {self.parser.header.frame_count}")
        
        try:
            auto_stretch = self.chk_stretch.isChecked()
            auto_wb = self.chk_awb.isChecked()
            brightness = self.sld_brightness.value()
            gamma = self.sld_gamma.value() / 100.0
            color_mode = self.get_current_bayer_mode()
            debayer_algo = self.get_current_debayer_algo()

            frame_bgr = self.parser.get_frame(
                frame_idx=val,
                auto_stretch=auto_stretch,
                auto_wb=auto_wb,
                brightness=brightness,
                gamma=gamma,
                color_mode_override=color_mode,
                debayer_algorithm=debayer_algo
            )

            # Apply HSL Colorization in Live Preview
            if self.chk_hsl_enable.isChecked():
                frame_bgr = apply_hsl_colorization(
                    frame_bgr,
                    enabled=True,
                    preset=self.cmb_hsl_preset.currentText(),
                    hue=self.sld_hsl_hue.value(),
                    saturation=self.sld_hsl_sat.value(),
                    luminance=self.sld_hsl_lum.value()
                )

            # Apply Logo Overlay in Live Preview
            if self.chk_logo_enable.isChecked() and self.txt_logo_path.text().strip():
                frame_bgr = apply_logo_overlay(
                    frame_bgr,
                    logo_path=self.txt_logo_path.text().strip(),
                    position=self.cmb_logo_pos.currentText(),
                    scale_pct=self.sld_logo_scale.value(),
                    opacity_pct=self.sld_logo_opacity.value()
                )

            self.current_preview_frame = frame_bgr
            self.display_preview(frame_bgr)

            ts = self.parser.get_frame_timestamp(val)
            if ts:
                self.lbl_frame_time.setText(f"Timestamp: {ts.strftime('%H:%M:%S.%f')[:-3]} UTC")
            else:
                self.lbl_frame_time.setText("Timestamp: Non disponibile")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.lbl_status.setText(f"Errore anteprima: {str(e)}")

    def refresh_preview(self):
        if self.parser:
            self.on_preview_slider_changed(self.sld_preview.value())

    def on_gamma_changed(self, val: int):
        gamma_val = val / 100.0
        self.lbl_gamma.setText(f"Stiramento Gamma Oggetto ({gamma_val:.2f}x):")
        self.refresh_preview()

    def on_brightness_changed(self, val: int):
        self.lbl_brightness.setText(f"Luminosità Lineare ({val}):")
        self.refresh_preview()

    def on_hsl_preset_changed(self, idx: int):
        preset_name = self.cmb_hsl_preset.currentText()
        is_colormap = preset_name in ["Inferno (Falso Colore)", "Plasma (Falso Colore)"]
        
        self.sld_hsl_hue.setEnabled(not is_colormap)
        self.sld_hsl_sat.setEnabled(not is_colormap)
        self.sld_hsl_lum.setEnabled(not is_colormap)

        preset_defaults = {
            "Rosso Solare H-alpha (656nm - Rubino)": (355, 100, 0),
            "Arancione Solare (Prominenze / Luce Solare)": (20, 100, 0),
            "Giallo Solare (Continuum / Luce Bianca)": (38, 90, 0),
            "Oro Solare": (32, 85, 0),
            "Calcio-K / CaK (393nm - Violetto)": (270, 100, 0),
            "Blu (Deep Sky)": (210, 90, 0),
        }
        if preset_name in preset_defaults:
            h, s, v = preset_defaults[preset_name]
            self.sld_hsl_hue.blockSignals(True)
            self.sld_hsl_sat.blockSignals(True)
            self.sld_hsl_lum.blockSignals(True)
            self.sld_hsl_hue.setValue(h)
            self.sld_hsl_sat.setValue(s)
            self.sld_hsl_lum.setValue(v)
            self.lbl_hsl_hue.setText(f"Tonalità / Hue ({h}°):")
            self.lbl_hsl_sat.setText(f"Saturazione ({s}%):")
            self.lbl_hsl_lum.setText(f"Luminosità ({v}):")
            self.sld_hsl_hue.blockSignals(False)
            self.sld_hsl_sat.blockSignals(False)
            self.sld_hsl_lum.blockSignals(False)

        self.refresh_preview()

    def on_hsl_slider_changed(self, val: int):
        self.lbl_hsl_hue.setText(f"Tonalità / Hue ({self.sld_hsl_hue.value()}°):")
        self.lbl_hsl_sat.setText(f"Saturazione ({self.sld_hsl_sat.value()}%):")
        self.lbl_hsl_lum.setText(f"Luminosità ({self.sld_hsl_lum.value()}):")
        self.refresh_preview()

    def on_logo_slider_changed(self, val: int):
        self.lbl_logo_scale.setText(f"Dimensione Logo ({self.sld_logo_scale.value()}%):")
        self.lbl_logo_opacity.setText(f"Opacità Logo ({self.sld_logo_opacity.value()}%):")
        self.refresh_preview()

    def update_fps_from_multiplier(self, idx: int):
        if not self.parser:
            return
        
        multipliers = [1.0, 0.1, 0.25, 0.33333, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
        if idx == 0:
            return
        
        factor = multipliers[idx]
        new_fps = round(self.original_fps * factor, 2)
        self.num_fps.blockSignals(True)
        self.num_fps.setValue(new_fps)
        self.num_fps.blockSignals(False)
        self.update_trim_info()

    def update_multiplier_from_fps(self, fps_val: float):
        if not self.parser:
            return
        self.cmb_mult.blockSignals(True)
        self.cmb_mult.setCurrentIndex(0)
        self.cmb_mult.blockSignals(False)
        self.update_trim_info()

    def on_start_frame_changed(self):
        if not self.parser:
            return
        start_f = self.num_start_frame.value()
        self.sld_preview.blockSignals(True)
        self.sld_preview.setValue(start_f - 1)
        self.sld_preview.blockSignals(False)
        self.update_bookmarks()
        self.update_trim_info()
        self.on_preview_slider_changed(start_f - 1)

    def on_end_frame_changed(self):
        if not self.parser:
            return
        end_f = self.num_end_frame.value()
        self.sld_preview.blockSignals(True)
        self.sld_preview.setValue(end_f - 1)
        self.sld_preview.blockSignals(False)
        self.update_bookmarks()
        self.update_trim_info()
        self.on_preview_slider_changed(end_f - 1)

    def set_start_from_preview(self):
        if self.parser:
            curr = self.sld_preview.value() + 1
            self.num_start_frame.setValue(curr)
            self.on_start_frame_changed()

    def set_end_from_preview(self):
        if self.parser:
            curr = self.sld_preview.value() + 1
            self.num_end_frame.setValue(curr)
            self.on_end_frame_changed()

    def update_bookmarks(self):
        if self.parser:
            s = self.num_start_frame.value() - 1
            e = self.num_end_frame.value() - 1
            self.sld_preview.set_bookmarks(s, e)

    def update_trim_info(self):
        if not self.parser:
            self.lbl_trim_info.setText("Fotogrammi selezionati: 0 / 0")
            return

        start_f = self.num_start_frame.value()
        end_f = self.num_end_frame.value()
        
        if start_f > end_f:
            self.lbl_trim_info.setText("Attenzione: Fotogramma Inizio maggiore di Fine!")
            return

        total_sel = end_f - start_f + 1
        fps = self.num_fps.value()
        dur_sec = total_sel / fps if fps > 0 else 0
        dur_min = int(dur_sec // 60)
        dur_rem_sec = dur_sec % 60

        self.lbl_trim_info.setText(
            f"Fotogrammi selezionati: {start_f} - {end_f} ({total_sel} fotogrammi ~{dur_min}m {dur_rem_sec:.1f}s)"
        )

    def browse_logo_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona Immagine Logo PNG", "", "Immagini PNG (*.png);;Tutti i File (*.*)"
        )
        if file_path:
            self.txt_logo_path.setText(file_path)
            self.chk_logo_enable.setChecked(True)
            self.refresh_preview()

    def browse_intro_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona Titolo Iniziale (Intro)", "",
            "Immagini e FITS (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.fit *.fits);;Tutti i File (*.*)"
        )
        if file_path:
            self.txt_intro_path.setText(file_path)
            self.chk_intro_enable.setChecked(True)

    def browse_outro_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona Titolo Finale (Outro)", "",
            "Immagini e FITS (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.fit *.fits);;Tutti i File (*.*)"
        )
        if file_path:
            self.txt_outro_path.setText(file_path)
            self.chk_outro_enable.setChecked(True)

    def on_audio_preset_changed(self, idx: int):
        soundtrack_dir = os.path.join(os.path.dirname(__file__), "colonne_sonore")
        preset_files = {
            0: "Interstellar_Hans_Zimmer_Style_30s.wav",
            1: "Beethoven_Moonlight_Sonata_30s.wav",
            2: "Beethoven_5th_Symphony_30s.wav",
            3: "Beethoven_Moonlight_Sonata.ogg",
            4: "Beethoven_5th_Symphony.ogg"
        }
        if idx in preset_files:
            file_path = os.path.join(soundtrack_dir, preset_files[idx])
            if os.path.exists(file_path):
                self.txt_audio_path.setText(file_path)
                self.chk_audio_enable.setChecked(True)
            else:
                self.txt_audio_path.setText("")

    def browse_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona File Colonna Sonora Audio", "",
            "File Audio (*.wav *.mp3 *.ogg *.aac *.m4a *.flac);;Tutti i File (*.*)"
        )
        if file_path:
            self.cmb_audio_preset.blockSignals(True)
            self.cmb_audio_preset.setCurrentIndex(5) # Personalizzato
            self.cmb_audio_preset.blockSignals(False)
            self.txt_audio_path.setText(file_path)
            self.chk_audio_enable.setChecked(True)

    def on_quality_slider_changed(self, val: int):
        self.lbl_quality.setText(f"Qualità video MP4 ({val}%):")

    def on_format_changed(self, idx: int):
        self.update_output_path_extension()
        self.quality_widget.setVisible(idx == 0)

    def update_output_path_extension(self):
        current_text = self.txt_output_path.text().strip()
        ext = ".gif" if self.cmb_format.currentIndex() == 1 else ".mp4"
        
        if current_text:
            base, _ = os.path.splitext(current_text)
            self.txt_output_path.setText(base + ext)
        elif self.current_ser_path:
            base = os.path.splitext(self.current_ser_path)[0]
            self.txt_output_path.setText(base + ext)

    def display_preview(self, frame_bgr):
        h, w, c = frame_bgr.shape
        bytes_per_line = c * w
        
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb = np.ascontiguousarray(frame_rgb)
        
        q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        scaled_pixmap = pixmap.scaled(
            self.lbl_preview_img.width() - 4,
            self.lbl_preview_img.height() - 4,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_preview_img.setPixmap(scaled_pixmap)

    def browse_output_path(self):
        if not self.current_ser_path:
            initial_dir = ""
        else:
            initial_dir = os.path.dirname(self.current_ser_path)

        is_gif = self.cmb_format.currentIndex() == 1
        filter_str = "Animazione GIF (*.gif)" if is_gif else "Video MP4 (*.mp4)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salva File di Output", initial_dir, filter_str
        )
        if file_path:
            self.txt_output_path.setText(file_path)

    def toggle_conversion(self):
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Annullamento in corso...")
            self.btn_convert.setEnabled(False)
            self.worker.cancel()
            return

        if not self.current_ser_path:
            QMessageBox.warning(self, "Nessun File", "Seleziona prima un file .SER di input.")
            return

        out_path = self.txt_output_path.text().strip()
        if not out_path:
            QMessageBox.warning(self, "Percorso Output vuoto", "Seleziona un percorso di destinazione per il file di output.")
            return

        start_f = self.num_start_frame.value()
        end_f = self.num_end_frame.value()
        if start_f > end_f:
            QMessageBox.warning(self, "Intervallo Fotogrammi Errato", "Il fotogramma iniziale non può essere maggiore di quello finale.")
            return

        fps = self.num_fps.value()
        auto_stretch = self.chk_stretch.isChecked()
        auto_wb = self.chk_awb.isChecked()
        brightness = self.sld_brightness.value()
        gamma = self.sld_gamma.value() / 100.0
        color_mode = self.get_current_bayer_mode()
        debayer_algo = self.get_current_debayer_algo()
        quality = self.sld_quality.value()

        self.btn_convert.setText("Annulla Esportazione")
        self.btn_convert.setStyleSheet("background-color: #b91c1c; border-color: #dc2626;")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.set_controls_enabled(False)
        self.cmb_format.setEnabled(False)

        self.worker = ConverterWorker(
            ser_path=self.current_ser_path,
            mp4_path=out_path,
            output_fps=fps,
            auto_stretch=auto_stretch,
            auto_wb=auto_wb,
            brightness=brightness,
            gamma=gamma,
            color_mode_override=color_mode,
            debayer_algorithm=debayer_algo,
            quality=quality,
            start_frame=start_f,
            end_frame=end_f,
            hsl_enabled=self.chk_hsl_enable.isChecked(),
            hsl_preset=self.cmb_hsl_preset.currentText(),
            hsl_hue=self.sld_hsl_hue.value(),
            hsl_saturation=self.sld_hsl_sat.value(),
            hsl_luminance=self.sld_hsl_lum.value(),
            logo_enabled=self.chk_logo_enable.isChecked(),
            logo_path=self.txt_logo_path.text().strip(),
            logo_position=self.cmb_logo_pos.currentText(),
            logo_scale=self.sld_logo_scale.value(),
            logo_opacity=self.sld_logo_opacity.value(),
            intro_enabled=self.chk_intro_enable.isChecked(),
            intro_path=self.txt_intro_path.text().strip(),
            intro_duration=self.num_title_duration.value(),
            outro_enabled=self.chk_outro_enable.isChecked(),
            outro_path=self.txt_outro_path.text().strip(),
            outro_duration=self.num_title_duration.value(),
            audio_enabled=self.chk_audio_enable.isChecked(),
            audio_path=self.txt_audio_path.text().strip(),
            audio_loop=self.chk_audio_loop.isChecked()
        )
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.status_changed.connect(self.lbl_status.setText)
        self.worker.conversion_finished.connect(self.on_conversion_finished)
        self.worker.start()

    def set_controls_enabled(self, enabled: bool):
        self.drop_frame.setEnabled(enabled)
        self.tabs.setEnabled(enabled)
        self.sld_preview.setEnabled(enabled and self.parser is not None)
        self.txt_output_path.setEnabled(enabled)
        self.btn_browse_out.setEnabled(enabled)
        self.sld_quality.setEnabled(enabled)

    def on_conversion_finished(self, success: bool, msg: str):
        self.btn_convert.setText("Converti / Esporta")
        self.btn_convert.setStyleSheet("")
        self.btn_convert.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.set_controls_enabled(True)
        self.cmb_format.setEnabled(True)
        
        self.lbl_status.setText(msg)

        if success:
            QMessageBox.information(self, "Esportazione Completata", msg)
        else:
            if "annullata" in msg.lower():
                QMessageBox.warning(self, "Annullato", msg)
            else:
                QMessageBox.critical(self, "Errore", msg)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        if self.parser:
            self.parser.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
