from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel

from app.services.asset_service import media_asset_path


class MediaFrame(QLabel):
    def __init__(
        self,
        *,
        kind: str,
        entity_id: str | None,
        subtype: str | None = None,
        width: int = 132,
        height: int = 160,
        placeholder_text: str = "NO IMAGE",
    ) -> None:
        super().__init__()
        self.kind = kind
        self.entity_id = entity_id
        self.subtype = subtype
        self.placeholder_text = placeholder_text
        self._source_pixmap: QPixmap | None = None
        self._source_path: str | None = None
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("MediaFrame")
        self.set_asset(kind=kind, entity_id=entity_id, subtype=subtype)

    def set_asset(self, *, kind: str, entity_id: str | None, subtype: str | None = None) -> None:
        self.kind = kind
        self.entity_id = entity_id
        self.subtype = subtype
        path = media_asset_path(kind, entity_id, subtype=subtype)
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._source_pixmap = pixmap
                self._source_path = path
                self.setToolTip(f"로컬 미디어 패치: {path}")
                self._render_pixmap()
                return
        self._source_pixmap = None
        self._source_path = None
        self.setToolTip(_placeholder_tooltip(kind))
        self._render_placeholder()

    def resizeEvent(self, event: object) -> None:
        if self._source_pixmap:
            self._render_pixmap()
        else:
            self._render_placeholder()
        super().resizeEvent(event)

    def _render_pixmap(self) -> None:
        if not self._source_pixmap:
            return
        canvas = QPixmap(max(1, self.width()), max(1, self.height()))
        canvas.fill(QColor("#111418"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scaled = self._source_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        _draw_border(painter, self.width(), self.height())
        painter.end()
        self.setPixmap(canvas)

    def _render_placeholder(self) -> None:
        canvas = QPixmap(max(1, self.width()), max(1, self.height()))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(canvas.rect(), QColor("#14191f"))
        _draw_placeholder_symbol(painter, self.width(), self.height(), self.placeholder_text)
        _draw_border(painter, self.width(), self.height())
        painter.end()
        self.setPixmap(canvas)


def people_media_frame(
    entity_id: str | None = None,
    person_type: str | None = None,
    *,
    width: int = 132,
    height: int = 160,
) -> MediaFrame:
    return MediaFrame(
        kind="people",
        entity_id=entity_id,
        subtype=person_type,
        width=width,
        height=height,
        placeholder_text="SILHOUETTE",
    )


def poster_media_frame(entity_id: str | None = None, *, width: int = 128, height: int = 184) -> MediaFrame:
    return MediaFrame(
        kind="posters",
        entity_id=entity_id,
        width=width,
        height=height,
        placeholder_text="POSTER",
    )


def organization_logo_frame(entity_id: str | None = None, *, width: int = 168, height: int = 104) -> MediaFrame:
    return MediaFrame(
        kind="organizations",
        entity_id=entity_id,
        width=width,
        height=height,
        placeholder_text="LOGO",
    )


def award_logo_frame(entity_id: str | None = None, *, width: int = 144, height: int = 112) -> MediaFrame:
    return MediaFrame(
        kind="awards",
        entity_id=entity_id,
        width=width,
        height=height,
        placeholder_text="AWARD",
    )


def _draw_border(painter: QPainter, width: int, height: int) -> None:
    painter.setPen(QPen(QColor("#303843"), 1))
    painter.drawRect(0, 0, width - 1, height - 1)


def _draw_placeholder_symbol(painter: QPainter, width: int, height: int, text: str) -> None:
    figure = QColor("#5b6571")
    label = QColor("#aeb7c2")
    painter.setBrush(figure)
    painter.setPen(Qt.PenStyle.NoPen)

    if text == "SILHOUETTE":
        head_size = min(width * 0.30, height * 0.25)
        painter.drawEllipse(QRectF((width - head_size) / 2, height * 0.18, head_size, head_size))
        painter.drawRoundedRect(
            QRectF(width * 0.22, height * 0.52, width * 0.56, height * 0.28),
            18,
            18,
        )
    elif text in {"LOGO", "AWARD"}:
        painter.drawRoundedRect(QRectF(width * 0.20, height * 0.28, width * 0.60, height * 0.34), 8, 8)
    else:
        painter.drawRoundedRect(QRectF(width * 0.22, height * 0.18, width * 0.56, height * 0.58), 5, 5)

    painter.setPen(label)
    font = QFont()
    font.setPointSize(8)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(0, height - 28, width, 20), Qt.AlignmentFlag.AlignCenter, text)


def _placeholder_tooltip(kind: str) -> str:
    if kind == "people":
        return "로컬 미디어 패치에 인물 이미지가 있으면 이 영역에 표시됩니다."
    if kind == "posters":
        return "로컬 미디어 패치에 포스터 이미지가 있으면 이 영역에 표시됩니다."
    if kind == "organizations":
        return "로컬 미디어 패치에 회사/극장 로고가 있으면 이 영역에 표시됩니다."
    if kind == "awards":
        return "로컬 미디어 패치에 시상식 로고가 있으면 이 영역에 표시됩니다."
    return "로컬 미디어 패치 이미지가 있으면 이 영역에 표시됩니다."
