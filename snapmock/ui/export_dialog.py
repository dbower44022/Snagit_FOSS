"""ExportDialog — format, options, region, output path, preview (General UI PRD 11.2).

The Library's multi-select variant (Library PRD 7.2) swaps the output path for
an output directory, adds Apply to All, and offers the SnapMock Project copy.
Accepting the dialog stores the options as the last-used settings for the
format and the directory as the last-used directory for the format (PRD 15.4).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from snapmock.io.exporter import (
    DPI_CHOICES,
    PNG_COLOR_DEPTHS,
    ExportFormat,
    ExportRegion,
    ExportSettings,
    PdfPageSize,
    estimate_export_size,
    format_byte_size,
    render_export_image,
    resolve_region,
)
from snapmock.ui.unmet_requirements import check_requirements

if TYPE_CHECKING:
    from snapmock.config.settings import AppSettings
    from snapmock.core.scene import SnapScene

PREVIEW_SIZE = 240
PREVIEW_DELAY_MS = 150

REGION_LABELS: dict[ExportRegion, str] = {
    ExportRegion.CANVAS: "Entire Canvas",
    ExportRegion.SELECTION: "Selection Only",
    ExportRegion.VISIBLE: "Visible Area Only",
}


class DpiSelector(QWidget):
    """DPI dropdown (72, 150, 300, Custom) with a spinbox that appears for Custom."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        for dpi in DPI_CHOICES:
            self._combo.addItem(str(dpi), dpi)
        self._combo.addItem("Custom", 0)
        self._spin = QSpinBox()
        self._spin.setRange(1, 2400)
        self._spin.setSuffix(" dpi")
        self._spin.hide()
        layout.addWidget(self._combo)
        layout.addWidget(self._spin)
        layout.addStretch(1)
        self._combo.currentIndexChanged.connect(self._on_combo)
        self._spin.valueChanged.connect(self.changed)

    def value(self) -> int:
        chosen = self._combo.currentData()
        return int(self._spin.value()) if not chosen else int(chosen)

    def set_value(self, dpi: int) -> None:
        index = self._combo.findData(dpi)
        if index < 0:
            index = self._combo.count() - 1
            self._spin.setValue(dpi)
        self._combo.setCurrentIndex(index)
        self._spin.setVisible(index == self._combo.count() - 1)

    def is_custom(self) -> bool:
        return self._combo.currentIndex() == self._combo.count() - 1

    def _on_combo(self, index: int) -> None:
        custom = index == self._combo.count() - 1
        self._spin.setVisible(custom)
        if custom and self._spin.value() in DPI_CHOICES:
            self._spin.setValue(self._spin.value())
        self.changed.emit()


class ExportDialog(QDialog):
    """File > Export, and the Library panel's Export... for one or many files."""

    def __init__(
        self,
        scene: SnapScene,
        app_settings: AppSettings,
        parent: QWidget | None = None,
        *,
        document_name: str = "Untitled",
        document_directory: Path | None = None,
        selection: QRectF | None = None,
        visible: QRectF | None = None,
        library_files: list[Path] | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene = scene
        self._app_settings = app_settings
        self._document_name = document_name
        self._document_directory = document_directory
        self._selection = selection if selection is not None and not selection.isEmpty() else None
        self._visible = visible
        self._library_files = list(library_files or [])
        self._library_mode = bool(self._library_files)
        self._multi = len(self._library_files) > 1
        self._path_is_auto = True
        self._per_format: dict[ExportFormat, ExportSettings] = {}
        self._loading = False

        self.setWindowTitle("Export")
        self.setModal(True)
        self._build()
        self._load_remembered()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._on_format_changed()

    # ----- construction ---------------------------------------------------

    def formats(self) -> list[ExportFormat]:
        base = [ExportFormat.PNG, ExportFormat.JPEG, ExportFormat.SVG, ExportFormat.PDF]
        return base + [ExportFormat.SMK] if self._library_mode else base

    def _build(self) -> None:
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        right = QVBoxLayout()
        root.addLayout(left, 1)
        root.addLayout(right, 0)

        # Format
        format_box = QGroupBox("Format")
        format_row = QHBoxLayout(format_box)
        self._format_group = QButtonGroup(self)
        self._format_buttons: dict[ExportFormat, QRadioButton] = {}
        for fmt in self.formats():
            button = QRadioButton(fmt.label)
            button.setObjectName(f"format_{fmt.value}")
            self._format_buttons[fmt] = button
            self._format_group.addButton(button)
            format_row.addWidget(button)
        format_row.addStretch(1)
        self._format_group.buttonClicked.connect(lambda _b: self._on_format_changed())
        left.addWidget(format_box)

        # Per-format options
        self._options = QStackedWidget()
        self._pages: dict[ExportFormat, QWidget] = {}
        self._pages[ExportFormat.PNG] = self._build_png_page()
        self._pages[ExportFormat.JPEG] = self._build_jpeg_page()
        self._pages[ExportFormat.SVG] = self._build_svg_page()
        self._pages[ExportFormat.PDF] = self._build_pdf_page()
        if self._library_mode:
            self._pages[ExportFormat.SMK] = self._build_smk_page()
        for fmt in self.formats():
            self._options.addWidget(self._pages[fmt])
        options_box = QGroupBox("Options")
        options_layout = QVBoxLayout(options_box)
        options_layout.addWidget(self._options)
        left.addWidget(options_box)

        # Region
        self._region_box = QGroupBox("Export region")
        region_row = QHBoxLayout(self._region_box)
        self._region_group = QButtonGroup(self)
        self._region_buttons: dict[ExportRegion, QRadioButton] = {}
        for region, label in REGION_LABELS.items():
            button = QRadioButton(label)
            button.setObjectName(f"region_{region.value}")
            self._region_buttons[region] = button
            self._region_group.addButton(button)
            region_row.addWidget(button)
        self._region_buttons[ExportRegion.CANVAS].setChecked(True)
        self._region_group.buttonClicked.connect(lambda _b: self._schedule_preview())
        left.addWidget(self._region_box)
        # Files that are not open in a tab have no selection and no visible area.
        self._region_box.setVisible(not self._library_mode)

        # Output
        output_box = QGroupBox("Output directory" if self._multi else "Output path")
        output_layout = QVBoxLayout(output_box)
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setObjectName("output_path")
        self._path_edit.textEdited.connect(self._on_path_edited)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse)
        output_layout.addLayout(path_row)
        self._apply_all = QCheckBox("Apply to All")
        self._apply_all.setToolTip("Use these settings for every selected file")
        self._apply_all.setChecked(True)
        self._apply_all.setVisible(self._multi)
        output_layout.addWidget(self._apply_all)
        if self._multi:
            files_label = QLabel(f"{len(self._library_files)} files, named by their display names")
            output_layout.addWidget(files_label)
        left.addWidget(output_box)
        left.addStretch(1)

        # Preview and size estimate
        preview_box = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_box)
        self._preview = QLabel()
        self._preview.setObjectName("preview")
        self._preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFrameShape(QFrame.Shape.StyledPanel)
        self._size_label = QLabel("Estimating size…")
        self._size_label.setObjectName("size_estimate")
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview)
        preview_layout.addWidget(self._size_label)
        right.addWidget(preview_box)
        right.addStretch(1)

        buttons = QDialogButtonBox()
        self._export_button = buttons.addButton("Export", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)

    def _build_png_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._png_dpi = DpiSelector()
        self._png_dpi.changed.connect(self._on_option_changed)
        self._png_transparency = QCheckBox("Transparency")
        self._png_transparency.setObjectName("png_transparency")
        self._png_transparency.toggled.connect(self._on_option_changed)
        self._png_depth = QComboBox()
        self._png_depth.setObjectName("png_depth")
        for depth in PNG_COLOR_DEPTHS:
            self._png_depth.addItem(f"{depth}-bit", depth)
        self._png_depth.currentIndexChanged.connect(self._on_option_changed)
        form.addRow("DPI:", self._png_dpi)
        form.addRow("", self._png_transparency)
        form.addRow("Color depth:", self._png_depth)
        return page

    def _build_jpeg_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        quality_row = QHBoxLayout()
        self._jpeg_quality = QSlider(Qt.Orientation.Horizontal)
        self._jpeg_quality.setObjectName("jpeg_quality")
        self._jpeg_quality.setRange(1, 100)
        self._jpeg_quality_spin = QSpinBox()
        self._jpeg_quality_spin.setRange(1, 100)
        self._jpeg_quality.valueChanged.connect(self._jpeg_quality_spin.setValue)
        self._jpeg_quality_spin.valueChanged.connect(self._jpeg_quality.setValue)
        self._jpeg_quality.valueChanged.connect(self._on_option_changed)
        quality_row.addWidget(self._jpeg_quality, 1)
        quality_row.addWidget(self._jpeg_quality_spin)
        self._jpeg_dpi = DpiSelector()
        self._jpeg_dpi.changed.connect(self._on_option_changed)
        form.addRow("Quality:", quality_row)
        form.addRow("DPI:", self._jpeg_dpi)
        return page

    def _build_svg_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._svg_embed = QCheckBox("Embed raster images")
        self._svg_embed.setObjectName("svg_embed")
        self._svg_embed.toggled.connect(self._on_option_changed)
        self._svg_viewbox = QLabel()
        self._svg_viewbox.setObjectName("svg_viewbox")
        form.addRow("", self._svg_embed)
        form.addRow("Viewbox:", self._svg_viewbox)
        return page

    def _build_pdf_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._pdf_dpi = DpiSelector()
        self._pdf_dpi.changed.connect(self._on_option_changed)
        self._pdf_page_size = QComboBox()
        self._pdf_page_size.setObjectName("pdf_page_size")
        for size in PdfPageSize:
            self._pdf_page_size.addItem(size.label, size.value)
        self._pdf_page_size.currentIndexChanged.connect(self._on_option_changed)
        self._pdf_orientation = QLabel()
        self._pdf_orientation.setObjectName("pdf_orientation")
        form.addRow("DPI:", self._pdf_dpi)
        form.addRow("Page size:", self._pdf_page_size)
        form.addRow("Orientation:", self._pdf_orientation)
        return page

    def _build_smk_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("Copies the project file to the chosen location, keeping it fully editable.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    # ----- remembered settings -------------------------------------------

    def _load_remembered(self) -> None:
        for fmt in self.formats():
            stored = self._app_settings.export_settings(fmt.value)
            base = ExportSettings.from_dict(stored) if stored else ExportSettings()
            self._per_format[fmt] = base.with_format(fmt)
        last = self._app_settings.export_last_format()
        try:
            initial = ExportFormat(last)
        except ValueError:
            initial = ExportFormat.PNG
        if initial not in self._format_buttons:
            initial = ExportFormat.PNG
        self._format_buttons[initial].setChecked(True)
        remembered_region = self._per_format[initial].region
        if remembered_region in self._region_buttons:
            self._region_buttons[remembered_region].setChecked(True)
        self._path_edit.setText(str(self._default_path(initial)))

    def _default_directory(self, fmt: ExportFormat) -> Path:
        remembered = self._app_settings.export_last_directory(fmt.value)
        if remembered is not None:
            return remembered
        if self._document_directory is not None:
            return self._document_directory
        return Path.home()

    def _default_path(self, fmt: ExportFormat) -> Path:
        directory = self._default_directory(fmt)
        if self._multi:
            return directory
        return directory / f"{self._document_name}{fmt.suffix}"

    def _apply_settings_to_page(self, settings: ExportSettings) -> None:
        self._loading = True
        try:
            self._png_dpi.set_value(settings.dpi if settings.format is ExportFormat.PNG else 72)
            self._png_transparency.setChecked(settings.png_transparency)
            self._png_depth.setCurrentIndex(
                max(0, self._png_depth.findData(settings.png_color_depth))
            )
            self._jpeg_quality.setValue(settings.jpeg_quality)
            self._jpeg_dpi.set_value(settings.dpi if settings.format is ExportFormat.JPEG else 72)
            self._svg_embed.setChecked(settings.svg_embed_raster)
            self._pdf_dpi.set_value(settings.dpi if settings.format is ExportFormat.PDF else 72)
            index = self._pdf_page_size.findData(settings.pdf_page_size.value)
            self._pdf_page_size.setCurrentIndex(max(0, index))
        finally:
            self._loading = False

    # ----- state -----------------------------------------------------------

    def current_format(self) -> ExportFormat:
        for fmt, button in self._format_buttons.items():
            if button.isChecked():
                return fmt
        return ExportFormat.PNG

    def current_region(self) -> ExportRegion:
        if self._library_mode:
            return ExportRegion.CANVAS
        for region, button in self._region_buttons.items():
            if button.isChecked():
                return region
        return ExportRegion.CANVAS

    def settings(self) -> ExportSettings:
        """The options as the dialog shows them right now."""
        fmt = self.current_format()
        if fmt is ExportFormat.PNG:
            dpi = self._png_dpi.value()
        elif fmt is ExportFormat.JPEG:
            dpi = self._jpeg_dpi.value()
        elif fmt is ExportFormat.PDF:
            dpi = self._pdf_dpi.value()
        else:
            dpi = 72
        page_value = self._pdf_page_size.currentData()
        return ExportSettings(
            format=fmt,
            region=self.current_region(),
            dpi=dpi,
            png_transparency=self._png_transparency.isChecked(),
            png_color_depth=int(self._png_depth.currentData() or 8),
            jpeg_quality=int(self._jpeg_quality.value()),
            svg_embed_raster=self._svg_embed.isChecked(),
            pdf_page_size=PdfPageSize(str(page_value)) if page_value else PdfPageSize.CANVAS,
        )

    def region_rect(self) -> QRectF:
        return resolve_region(
            self._scene, self.current_region(), selection=self._selection, visible=self._visible
        )

    def output_path(self) -> Path:
        return Path(self._path_edit.text().strip()).expanduser()

    def output_directory(self) -> Path:
        path = self.output_path()
        return path if self._multi else path.parent

    def apply_to_all(self) -> bool:
        return not self._multi or self._apply_all.isChecked()

    def set_output_directory(self, directory: Path) -> None:
        """Pre-fill the directory (the per-file dialogs of an Apply to All = off batch)."""
        if self._multi:
            self._path_edit.setText(str(directory))
        else:
            self._path_edit.setText(str(directory / self.output_path().name))
        self._path_is_auto = False

    # ----- reactions -------------------------------------------------------

    def _on_format_changed(self) -> None:
        fmt = self.current_format()
        self._options.setCurrentWidget(self._pages[fmt])
        self._apply_settings_to_page(self._per_format[fmt])
        if self._path_is_auto:
            self._path_edit.setText(str(self._default_path(fmt)))
        elif not self._multi:
            current = self.output_path()
            if current.name:
                self._path_edit.setText(str(current.with_suffix(fmt.suffix)))
        self._update_derived_labels()
        self._schedule_preview()

    def _on_option_changed(self, *_args: object) -> None:
        if self._loading:
            return
        fmt = self.current_format()
        self._per_format[fmt] = self.settings()
        self._update_derived_labels()
        self._schedule_preview()

    def _on_path_edited(self, _text: str) -> None:
        self._path_is_auto = False

    def _update_derived_labels(self) -> None:
        rect = self.region_rect()
        self._svg_viewbox.setText(f"0 0 {rect.width():g} {rect.height():g}")
        landscape = rect.width() > rect.height()
        self._pdf_orientation.setText("Landscape (auto)" if landscape else "Portrait (auto)")

    def _browse(self) -> None:
        fmt = self.current_format()
        start = str(self.output_path()) if self._path_edit.text().strip() else str(Path.home())
        if self._multi:
            chosen = QFileDialog.getExistingDirectory(self, "Export To Directory", start)
        else:
            chosen, _filter = QFileDialog.getSaveFileName(self, "Export", start, fmt.file_filter)
            if chosen and not Path(chosen).suffix:
                chosen = str(Path(chosen).with_suffix(fmt.suffix))
        if chosen:
            self._path_edit.setText(chosen)
            self._path_is_auto = False

    # ----- preview ---------------------------------------------------------

    def _schedule_preview(self) -> None:
        self._preview_timer.start()

    def _refresh_preview(self) -> None:
        settings = self.settings()
        rect = self.region_rect()
        source_file = self._library_files[0] if self._library_files else None
        preview_settings = settings.with_format(
            ExportFormat.JPEG if settings.format is ExportFormat.JPEG else ExportFormat.PNG
        )
        scale = min(1.0, PREVIEW_SIZE / max(1.0, rect.width(), rect.height()))
        preview_settings.dpi = max(1, round(72 * scale))
        image = render_export_image(self._scene, preview_settings, rect)
        self._preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                PREVIEW_SIZE,
                PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        try:
            size = estimate_export_size(self._scene, settings, rect, source_file=source_file)
        except (OSError, ValueError):
            self._size_label.setText("Size unavailable")
            return
        pixels = ""
        if settings.format in (ExportFormat.PNG, ExportFormat.JPEG):
            width = round(rect.width() * settings.scale)
            height = round(rect.height() * settings.scale)
            pixels = f" · {width} × {height} px"
        self._size_label.setText(f"≈ {format_byte_size(size)}{pixels}")

    def preview_pixmap(self) -> QPixmap | None:
        return self._preview.pixmap()

    def size_estimate_text(self) -> str:
        return self._size_label.text()

    # ----- accept ----------------------------------------------------------

    def accept(self) -> None:
        self._preview_timer.stop()
        settings = self.settings()
        path = self.output_path()
        requirements = [(bool(self._path_edit.text().strip()), "an output path")]
        if self._multi:
            requirements = [(bool(self._path_edit.text().strip()), "an output directory")]
        if settings.region is ExportRegion.SELECTION:
            requirements.append((self._selection is not None, "a selection on the canvas"))
        if settings.region is ExportRegion.VISIBLE:
            requirements.append((self._visible is not None, "a visible canvas area"))
        if not check_requirements(self, "Export", requirements):
            return
        directory = path if self._multi else path.parent
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            check_requirements(self, "Export", [(False, f"a writable directory ({exc.strerror})")])
            return
        fmt = settings.format
        self._app_settings.set_export_settings(fmt.value, settings.to_dict())
        self._app_settings.set_export_last_directory(fmt.value, directory)
        self._app_settings.set_export_last_format(fmt.value)
        super().accept()

    def reject(self) -> None:
        self._preview_timer.stop()
        super().reject()
