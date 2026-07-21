import os
import sys
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QLabel, QPushButton, QSlider, QCheckBox,
    QDoubleSpinBox, QFileDialog, QGroupBox, QProgressBar, QComboBox,
    QMessageBox, QLineEdit, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QIcon

from ser_parser import SERParser
from converter_worker import ConverterWorker

class DropFrame(QFrame):
    file_dropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop-frame")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(90)

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
        self.resize(1100, 850)
        self.setMinimumSize(950, 720)
        
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
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # 1. Header Title
        title_label = QLabel("AstroSER to MP4 Converter")
        title_label.setObjectName("app-title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 2. Drag & Drop Area
        self.drop_frame = DropFrame()
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.setSpacing(6)
        drop_layout.setContentsMargins(10, 10, 10, 10)
        
        self.lbl_drop_icon = QLabel("📁")
        self.lbl_drop_icon.setObjectName("drop-icon")
        self.lbl_drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.lbl_drop_icon)

        self.lbl_drop_text = QLabel("Trascina qui il file .SER o fai clic per sfogliare")
        self.lbl_drop_text.setObjectName("drop-text")
        self.lbl_drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.lbl_drop_text)

        self.drop_frame.file_dropped.connect(self.load_ser_file)
        self.drop_frame.clicked.connect(self.browse_ser_file)
        main_layout.addWidget(self.drop_frame)

        # 3. Content Panel
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        main_layout.addLayout(content_layout, stretch=1)

        # Left Column - Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumWidth(450)

        left_widget = QWidget()
        left_col = QVBoxLayout(left_widget)
        left_col.setContentsMargins(0, 0, 10, 0)
        left_col.setSpacing(12)

        # 3a. Metadata Group
        self.grp_meta = QGroupBox("Metadati File SER")
        meta_grid = QGridLayout(self.grp_meta)
        meta_grid.setSpacing(6)
        meta_grid.setContentsMargins(12, 20, 12, 12)
        
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
        left_col.addWidget(self.grp_meta)

        # 3b. Debayer & Color Group
        self.grp_bayer = QGroupBox("Correzione Colore & Pattern Bayer")
        bayer_layout = QVBoxLayout(self.grp_bayer)
        bayer_layout.setSpacing(10)
        bayer_layout.setContentsMargins(12, 20, 12, 12)

        pattern_hbox = QHBoxLayout()
        lbl_pat = QLabel("Pattern Bayer / Modalità:")
        lbl_pat.setMinimumWidth(160)
        pattern_hbox.addWidget(lbl_pat)
        
        self.cmb_pattern = QComboBox()
        self.cmb_pattern.addItems([
            "Auto (dall'Header)",
            "Bayer RGGB",
            "Bayer BGGR",
            "Bayer GRBG",
            "Bayer GBRG",
            "Monocromatico",
            "RGB Intercalato",
            "RGB Planare"
        ])
        self.cmb_pattern.currentIndexChanged.connect(self.refresh_preview)
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

        left_col.addWidget(self.grp_bayer)

        # 3c. Speed Settings Group
        self.grp_speed = QGroupBox("Regolazione Velocità")
        speed_layout = QVBoxLayout(self.grp_speed)
        speed_layout.setSpacing(10)
        speed_layout.setContentsMargins(12, 20, 12, 12)

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
        self.cmb_mult.addItems(["Personalizzato", "0.25x (Rallentato)", "0.5x", "1.0x (Normale)", "1.5x", "2.0x (Accelerato)", "5.0x", "10.0x"])
        self.cmb_mult.setCurrentIndex(3)
        self.cmb_mult.currentIndexChanged.connect(self.update_fps_from_multiplier)
        mult_hbox.addWidget(self.cmb_mult, stretch=1)
        speed_layout.addLayout(mult_hbox)
        
        left_col.addWidget(self.grp_speed)

        # 3d. Enhancements Group
        self.grp_enh = QGroupBox("Luminosità & Stiramento Gamma")
        enh_layout = QVBoxLayout(self.grp_enh)
        enh_layout.setSpacing(10)
        enh_layout.setContentsMargins(12, 20, 12, 12)

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

        left_col.addWidget(self.grp_enh)
        left_col.addStretch(1)

        scroll_area.setWidget(left_widget)
        content_layout.addWidget(scroll_area, stretch=1)

        # Right Column - Preview Area
        self.grp_preview = QGroupBox("Anteprima Fotogramma")
        preview_layout = QVBoxLayout(self.grp_preview)
        preview_layout.setSpacing(10)
        preview_layout.setContentsMargins(12, 20, 12, 12)

        self.lbl_preview_img = QLabel("Carica un file .SER per visualizzare l'anteprima")
        self.lbl_preview_img.setObjectName("preview-img-label")
        self.lbl_preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_img.setMinimumSize(400, 320)
        preview_layout.addWidget(self.lbl_preview_img, stretch=1)

        slider_hbox = QHBoxLayout()
        self.lbl_frame_idx = QLabel("Frame: 0 / 0")
        self.lbl_frame_idx.setMinimumWidth(110)
        self.sld_preview = QSlider(Qt.Orientation.Horizontal)
        self.sld_preview.setEnabled(False)
        self.sld_preview.valueChanged.connect(self.on_preview_slider_changed)
        
        slider_hbox.addWidget(self.lbl_frame_idx)
        slider_hbox.addWidget(self.sld_preview, stretch=1)
        preview_layout.addLayout(slider_hbox)
        
        self.lbl_frame_time = QLabel("Timestamp: -")
        self.lbl_frame_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_frame_time.setObjectName("timestamp-label")
        preview_layout.addWidget(self.lbl_frame_time)

        content_layout.addWidget(self.grp_preview, stretch=1)

        # 4. Output Path Selector & Convert Button
        self.grp_output = QGroupBox("Output Video / Esportazione")
        output_layout = QVBoxLayout(self.grp_output)
        output_layout.setSpacing(10)
        output_layout.setContentsMargins(12, 20, 12, 12)

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
                font-size: 22px;
                font-weight: bold;
                padding-bottom: 5px;
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
                border-radius: 12px;
                background-color: #161b22;
            }
            #drop-frame:hover {
                border: 2px dashed #58a6ff;
                background-color: #1c212a;
            }
            #drop-icon {
                font-size: 32px;
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
                padding: 6px 14px;
                font-weight: bold;
                min-height: 28px;
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
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
                padding: 4px 8px;
                min-height: 26px;
            }
            QComboBox::drop-down {
                border: none;
            }
            /* Explicit dark style for the dropdown popup list to prevent white-out bugs */
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
            QScrollArea {
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
            self.lbl_drop_text.setText(f"File caricato: {filename}\n(Fai clic o trascina un altro file per cambiarlo)")
            self.lbl_drop_icon.setText("⭐")

            self.original_fps = self.parser.get_average_fps()
            self.num_fps.setValue(self.original_fps)
            self.cmb_mult.setCurrentIndex(3)

            color_names = {
                0: "Monocromatico",
                1: "Bayer RGGB",
                2: "Bayer GRBG",
                3: "Bayer GBRG",
                4: "Bayer BGGR",
                8: "Bayer CYYM",
                9: "Bayer YCMY",
                16: "Bayer YMCY",
                17: "Bayer MYYC",
                100: "RGB Colore",
                101: "BGR Colore"
            }
            color_str = color_names.get(header.color_id, f"Sconosciuto ({header.color_id})")
            
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

            self.update_output_path_extension()

            self.sld_preview.setEnabled(True)
            self.sld_preview.setRange(0, header.frame_count - 1)
            self.sld_preview.setValue(0)
            self.lbl_frame_idx.setText(f"Frame: 1 / {header.frame_count}")

            self.on_preview_slider_changed(0)
            self.lbl_status.setText("File SER caricato con successo.")

        except Exception as e:
            QMessageBox.critical(self, "Errore Caricamento", f"Impossibile aprire il file SER:\n{str(e)}")
            self.lbl_status.setText("Errore durante il caricamento.")

    def get_current_bayer_mode(self) -> str:
        idx = self.cmb_pattern.currentIndex()
        modes = ["AUTO", "RGGB", "BGGR", "GRBG", "GBRG", "MONO", "RGB", "RGB_PLANAR"]
        return modes[idx] if idx < len(modes) else "AUTO"

    def get_current_debayer_algo(self) -> str:
        idx = self.cmb_algo.currentIndex()
        algos = ["EA", "VNG", "BILINEAR"]
        return algos[idx] if idx < len(algos) else "EA"

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

    def update_fps_from_multiplier(self, idx: int):
        if not self.parser:
            return
        
        multipliers = [1.0, 0.25, 0.5, 1.0, 1.5, 2.0, 5.0, 10.0]
        if idx == 0:
            return
        
        factor = multipliers[idx]
        new_fps = self.original_fps * factor
        self.num_fps.blockSignals(True)
        self.num_fps.setValue(new_fps)
        self.num_fps.blockSignals(False)

    def update_multiplier_from_fps(self, fps_val: float):
        if not self.parser:
            return
        self.cmb_mult.blockSignals(True)
        self.cmb_mult.setCurrentIndex(0)
        self.cmb_mult.blockSignals(False)

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
            quality=quality
        )
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.status_changed.connect(self.lbl_status.setText)
        self.worker.conversion_finished.connect(self.on_conversion_finished)
        self.worker.start()

    def set_controls_enabled(self, enabled: bool):
        self.drop_frame.setEnabled(enabled)
        self.grp_speed.setEnabled(enabled)
        self.grp_enh.setEnabled(enabled)
        self.grp_bayer.setEnabled(enabled)
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
