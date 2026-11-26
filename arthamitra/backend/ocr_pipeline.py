"""Raw bytes remain local. Remote vision must NOT receive unredacted images.

OCRProvider supports a replacement local OCR implementation (including a local
TrOCR service) without adding model downloads to this repository.
"""
import io
from dataclasses import dataclass
from typing import Protocol
from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError


class DocumentError(ValueError):
    pass


class OCRProvider(Protocol):
    def recognize(self, image: Image.Image) -> str: ...


@dataclass
class OCRResult:
    text: str
    warnings: list[str]


def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.width * image.height > 20_000_000:
        raise DocumentError('Image exceeds 20 megapixels; crop or resize it.')
    image = ImageOps.autocontrast(ImageOps.grayscale(image))
    # Small-angle deskew using horizontal projection variance, bounded work.
    preview = image.copy()
    preview.thumbnail((600, 600))
    best_angle, best_score = 0, -1.0
    for angle in (-4, -2, 0, 2, 4):
        rotated = preview.rotate(angle, fillcolor=255)
        rows = [ImageStat.Stat(rotated.crop((0, y, rotated.width, y + 1))).mean[0] for y in range(rotated.height)]
        mean = sum(rows) / len(rows)
        score = sum((r - mean) ** 2 for r in rows)
        if score > best_score:
            best_angle, best_score = angle, score
    return image.rotate(best_angle, expand=True, fillcolor=255)


class TesseractOCR:
    def __init__(self, languages: str = 'kan+eng'):
        self.languages = languages

    def recognize(self, image: Image.Image) -> str:
        try:
            import pytesseract
            return pytesseract.image_to_string(image, lang=self.languages, timeout=10)
        except Exception:
            raise DocumentError('Local OCR unavailable. Install Tesseract with kan+eng language data, or upload UTF-8 text.') from None


class OCRPipeline:
    def __init__(self, provider: OCRProvider | None = None):
        self.provider = provider or TesseractOCR()

    def process(self, content: bytes, suffix: str) -> OCRResult:
        warnings = []
        if suffix == '.txt':
            try:
                text = content.decode('utf-8-sig')
            except UnicodeError:
                raise DocumentError('Text files must use UTF-8.') from None
        elif suffix == '.pdf':
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content), strict=True)
                if reader.is_encrypted or len(reader.pages) > 10:
                    raise DocumentError('Use an unencrypted PDF of at most 10 pages.')
                pages = [page.extract_text() or '' for page in reader.pages]
                if any(len(page.strip()) < 20 for page in pages):
                    raise DocumentError('PDF contains scanned or unreadable pages. Upload clear page photos for local OCR.')
                text = '\n'.join(pages)
                warnings.append('PDF layout may affect extraction; compare the fields with the original.')
            except DocumentError:
                raise
            except Exception:
                raise DocumentError('PDF could not be read. Use a text PDF or a clear photo.') from None
        elif suffix in ('.png', '.jpg', '.jpeg', '.webp'):
            try:
                with Image.open(io.BytesIO(content)) as image:
                    text = self.provider.recognize(preprocess_image(image))
                warnings.append('OCR may misread digits or omit text. Verify every extracted amount.')
            except DocumentError:
                raise
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise DocumentError('Image could not be safely decoded.') from None
        else:
            raise DocumentError('Supported formats: TXT, text PDF, PNG, JPG and WEBP.')
        if len(text) > 60_000:
            raise DocumentError('Too much text; upload a shorter document.')
        if len(text.strip()) < 10:
            raise DocumentError('Not enough readable text. Please take a clearer photo.')
        return OCRResult(text, warnings)
