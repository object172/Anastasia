# -*- encoding: utf-8 -*-
import os

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

from settings import STATIC_PATH

__all__ = (
    'jsonb_property',
    'GeneratePdfMixin',
)


def jsonb_property(
        storage_name, property_name,
        default_value='', doc='',
):
    doc = doc or 'Property: {}'.format(property_name)

    def get_property(self):
        storage = getattr(self, storage_name) or {}
        return (
            storage.get(property_name) or
            (default_value() if callable(default_value) else default_value)
        )

    def set_property(self, value):
        storage = (getattr(self, storage_name) or {}).copy()
        storage[property_name] = value
        setattr(self, storage_name, storage)

    def del_property(self):
        storage = (getattr(self, storage_name) or {}).copy()
        if property_name in storage:
            del storage[property_name]
            setattr(self, storage_name, storage)

    return property(
        get_property,
        set_property,
        del_property,
        doc=doc
    )


class GeneratePdfMixin:

    ARIAL_TTF_PATH = os.path.join(STATIC_PATH, 'fonts', 'Arial.ttf')
    pdfmetrics.registerFont(TTFont("Arial", ARIAL_TTF_PATH))

    ARIAL_BOLD_TTF_PATH = os.path.join(STATIC_PATH, 'fonts', 'Arial-Bold.ttf')
    pdfmetrics.registerFont(TTFont("ArialBold", ARIAL_BOLD_TTF_PATH))

    MARGIN_LEFT_RIGHT = 38
    MARGIN_TOP_BOTTOM = 96

    LIST_WIDTH, LIST_HEIGHT = A4

    WRAPPED_WIDTH = LIST_WIDTH - 2 * MARGIN_LEFT_RIGHT
    WRAPPED_HALF_WIDTH = WRAPPED_WIDTH / 2.
    WRAPPED_HEIGHT = LIST_HEIGHT - 2 * MARGIN_TOP_BOTTOM

    @classmethod
    def draw_signature(
            cls, canvas,
            current_x, current_y, signature,
            max_height=50, max_width=100
    ):
        if signature is None:
            return current_x, current_y

        image_box = signature.getbbox()
        signature = signature.crop(image_box)

        width, height = signature.size

        ratio = min(1., 1. * max_height / height, 1. * max_width / width)

        draw_height = ratio * height
        draw_width = ratio * width

        canvas.drawImage(
            ImageReader(signature), current_x, current_y,
            height=draw_height, width=draw_width,
            mask='auto'
        )

        try:
            signature.close()
        except:
            pass

        return current_x + draw_width, current_y

    @classmethod
    def draw_horizontal_line(cls, canvas, start_x, current_y, end_x, line_width=1):
        canvas.line(start_x, current_y, end_x, current_y)
        return end_x, current_y - line_width

    @classmethod
    def draw_vertical_line(cls, canvas, start_x, current_y, end_y, line_width=1):
        canvas.line(start_x, current_y, start_x, end_y)
        return start_x + line_width, end_y

    @classmethod
    def draw_string(
            cls, canvas,
            current_x, current_y,
            text, font_name, font_size,
            max_x=None, new_line_offset_x=None,
            text_align='left'
    ):
        lineheiht = font_size + 3

        canvas.setFont(font_name, font_size)
        max_x = max_x or cls.WRAPPED_WIDTH
        if new_line_offset_x is None:
            new_line_offset_x = current_x

        lines_num = 0
        text_width = canvas.stringWidth(text, font_name, font_size)
        _current_x = current_x + text_width
        if _current_x > max_x:
            _text = ''
            for word in text.split():
                if _text:
                    __text = _text + ' ' + word
                else:
                    __text = word
                if not lines_num:
                    _current_x = current_x + canvas.stringWidth(
                        __text, font_name, font_size
                    )
                else:
                    _current_x = new_line_offset_x + canvas.stringWidth(
                        __text, font_name, font_size
                    )

                if _current_x > max_x:
                    if text_align == 'left':
                        if not lines_num:
                            canvas.drawString(
                                current_x, current_y - lineheiht * lines_num, _text
                            )
                        else:
                            canvas.drawString(
                                new_line_offset_x, current_y - lineheiht * lines_num, _text
                            )

                    elif text_align == 'right':
                        _text_width = canvas.stringWidth(_text, font_name, font_size)
                        canvas.drawString(
                            max_x - _text_width, current_y - lineheiht * lines_num, _text
                        )
                    elif text_align == 'center':
                        _text_width = canvas.stringWidth(_text, font_name, font_size)
                        if not lines_num:
                            canvas.drawString(
                                current_x + (max_x - current_x - _text_width) / 2., current_y - lineheiht * lines_num, _text
                            )
                        else:
                            canvas.drawString(
                                new_line_offset_x + (max_x - new_line_offset_x - _text_width) / 2., current_y - lineheiht * lines_num, _text
                            )

                    _text = word
                    lines_num += 1
                    continue
                else:
                    _text = __text

            if text_align == 'left':
                if not lines_num:
                    canvas.drawString(
                        current_x, current_y - lineheiht * lines_num, _text
                    )
                else:
                    canvas.drawString(
                        new_line_offset_x, current_y - lineheiht * lines_num, _text
                    )
            elif text_align == 'right':
                _text_width = canvas.stringWidth(_text, font_name, font_size)
                canvas.drawString(
                    max_x - _text_width, current_y - lineheiht * lines_num, _text
                )
                _current_x = max_x - _text_width
            elif text_align == 'center':
                _text_width = canvas.stringWidth(_text, font_name, font_size)
                if not lines_num:
                    canvas.drawString(
                        current_x + (max_x - current_x - _text_width) / 2., current_y - lineheiht * lines_num, _text
                    )
                    _current_x = max_x - (max_x - current_x - _text_width) / 2.
                else:
                    canvas.drawString(
                        new_line_offset_x + (max_x - new_line_offset_x - _text_width) / 2., current_y - lineheiht * lines_num, _text
                    )
                    _current_x = max_x - (max_x - new_line_offset_x - _text_width) / 2.

            lines_num += 1
        else:
            if text_align == 'left':
                canvas.drawString(current_x, current_y, text)
            elif text_align == 'right':
                canvas.drawString(max_x - text_width, current_y, text)
                _current_x = max_x - text_width
            elif text_align == 'center':
                canvas.drawString(
                    current_x + (max_x - current_x - text_width) / 2., current_y - lineheiht * lines_num, text
                )
                _current_x = max_x - (max_x - current_x - text_width) / 2.

            lines_num = 1
        return _current_x, current_y - lineheiht * lines_num
