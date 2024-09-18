import warnings
import math
import html
import re

from typing import Union, Tuple, Dict, Optional, Any

import pygame

from pygame import MOUSEBUTTONDOWN, MOUSEBUTTONUP, BUTTON_LEFT, KEYDOWN
from pygame import KMOD_SHIFT, KMOD_META, KMOD_CTRL, KMOD_ALT, K_a, K_c
from pygame import K_LEFT, K_RIGHT, K_UP, K_DOWN, K_HOME, K_END
from pygame.event import Event

from pygame_gui.core import ObjectID
from pygame_gui.core.utility import clipboard_copy
from pygame_gui._constants import UI_TEXT_BOX_LINK_CLICKED, OldType, UITextEffectType
from pygame_gui._constants import TEXT_EFFECT_TYPING_APPEAR, TEXT_EFFECT_TILT
from pygame_gui._constants import TEXT_EFFECT_FADE_IN, TEXT_EFFECT_FADE_OUT, TEXT_EFFECT_BOUNCE
from pygame_gui._constants import TEXT_EFFECT_EXPAND_CONTRACT, TEXT_EFFECT_SHAKE

from pygame_gui.core.utility import translate
from pygame_gui.core.interfaces import IContainerLikeInterface, IUIManagerInterface
from pygame_gui.core.interfaces import IUITextOwnerInterface
from pygame_gui.core.ui_element import UIElement
from pygame_gui.core.drawable_shapes import RectDrawableShape, RoundedRectangleShape
from pygame_gui.core.utility import basic_blit

from pygame_gui.elements.ui_vertical_scroll_bar import UIVerticalScrollBar

from pygame_gui.core.text.html_parser import HTMLParser
from pygame_gui.core.text.text_box_layout import TextBoxLayout
from pygame_gui.core.text.text_line_chunk import TextLineChunkFTFont
from pygame_gui.core.text.text_effects import TextEffect, TypingAppearEffect, FadeInEffect, FadeOutEffect
from pygame_gui.core.text.text_effects import BounceEffect, TiltEffect, ExpandContractEffect, ShakeEffect
from pygame_gui.core.gui_type_hints import Coordinate, RectLike


class UITextBox(UIElement, IUITextOwnerInterface):
    """
    A Text Box element lets us display word-wrapped, formatted text. If the text to display is
    longer than the height of the box given then the element will automatically create a vertical
    scroll bar so that all the text can be seen.

    Formatting the text is done via a subset of HTML tags. Currently supported tags are:

    - <b></b> or <strong></strong> - to encase bold styled text.
    - <i></i>, <em></em> or <var></var> - to encase italic styled text.
    - <u></u> - to encase underlined text.
    - <a href='id'></a> - to encase 'link' text that can be clicked on to generate events with the
                          id given in href.
    - <body bgcolor='#FFFFFF'></body> - to change the background colour of encased text.
    - <br> or <p></p> - to start a new line.
    - <font face='verdana' color='#000000' size=3.5></font> - To set the font, colour and size of
                                                              encased text.
    - <hr> a horizontal rule.
    - <effect id='custom_id'></effect> - to encase text to that will have an effect applied. The custom id
                                         supplied is used when setting an effect on this text box.
    - <shadow size=1 offset=1,1 color=#808080></shadow> - puts a shadow behind the text encased. Can also be used to
                                                          make a glow effect.
    - <img src="data/images/test_images/london.jpg" float=right> Inserts an image into the text with options on how to
                                                                 float the text around the image. Float options are
                                                                 left, right or none.

    More may be added in the future if needed or frequently requested.

    NOTE: if dimensions of the initial containing rect are set to -1 the text box will match the
    final dimension to whatever the text rendering produces. This lets us make dynamically sized
    text boxes depending on their contents.

    :param html_text: The HTML formatted text to display in this text box.
    :param relative_rect: The 'visible area' rectangle, positioned relative to its container.
    :param manager: The UIManager that manages this element. If not provided or set to None,
                    it will try to use the first UIManager that was created by your application.
    :param wrap_to_height: False by default, if set to True the box will increase in height to
                           match the text within.
    :param starting_height: Sets the height, above its container, to start placing the text
                            box at.
    :param container: The container that this element is within. If not provided or set to None
                      will be the root window's container.
    :param parent_element: The element this element 'belongs to' in the theming hierarchy.
    :param object_id: A custom defined ID for fine-tuning of theming.
    :param anchors: A dictionary describing what this element's relative_rect is relative to.
    :param visible: Whether the element is visible by default. Warning - container visibility
                    may override this.
    :param pre_parsing_enabled: When enabled will replace all newline characters with html <br> tags.
    :param text_kwargs: A dictionary of variable arguments to pass to the translated text
                        useful when you have multiple translations that need variables inserted
                        in the middle.
    :param allow_split_dashes: Sets whether long words that don't fit on a single line will be split with a dash
                               or just split without a dash (more compact).
    :param plain_text_display_only: No markup based styling & formatting will be done on the input text.
    :param should_html_unescape_input_text: When enabled turns plain text encoded html back into html for this text box.
                                            e.g. &lt; will become '<'
    :param placeholder_text: If the text line is empty, and not focused, this placeholder text will be shown instead.

    """

    def __init__(self,
                 html_text: str,
                 relative_rect: RectLike,
                 manager: Optional[IUIManagerInterface] = None,
                 wrap_to_height: bool = False,
                 starting_height: int = 1,
                 container: Optional[IContainerLikeInterface] = None,
                 parent_element: Optional[UIElement] = None,
                 object_id: Optional[Union[ObjectID, str]] = None,
                 anchors: Optional[Dict[str, Union[str, UIElement]]] = None,
                 visible: int = 1,
                 *,
                 pre_parsing_enabled: bool = True,
                 text_kwargs: Optional[Dict[str, str]] = None,
                 allow_split_dashes: bool = True,
                 plain_text_display_only: bool = False,
                 should_html_unescape_input_text: bool = False,
                 placeholder_text: Optional[str] = None):
        # Need to move some declarations early as they are indirectly referenced via the ui element
        # constructor
        self.scroll_bar = None
        relative_rect[3] = -1 if wrap_to_height else relative_rect[3]
        super().__init__(relative_rect, manager, container,
                         starting_height=starting_height,
                         layer_thickness=2,
                         anchors=anchors,
                         visible=visible,
                         parent_element=parent_element,
                         object_id=object_id,
                         element_id=['text_box'])
        self.should_html_unescape_input_text = should_html_unescape_input_text
        self.html_text = ""
        self._plain_text = ""
        if self.should_html_unescape_input_text:
            self.html_text = html.unescape(html_text)
        else:
            self.html_text = html_text

        self.placeholder_text = placeholder_text

        self.appended_text = ""
        self.text_kwargs = {}
        if text_kwargs is not None:
            self.text_kwargs = text_kwargs
        self.font_dict = self.ui_theme.get_font_dictionary()
        self.allow_split_dashes = allow_split_dashes
        self.plain_text_display_only = plain_text_display_only

        self._pre_parsing_enabled = pre_parsing_enabled

        self.link_hover_chunks = []  # container for any link chunks we have

        self.active_text_effect = None  # type: Optional[TextEffect]
        self.active_text_chunk_effects = []

        self.scroll_bar_width = 20

        self.border_width = None
        self.shadow_width = None
        self.padding = (5, 5)
        self.background_colour = None
        self.border_colour = None
        self.line_spacing = 1.25
        self.text_cursor_colour = pygame.Color("white")
        self.selected_bg_colour = pygame.Color(128, 128, 200, 255)
        self.selected_text_colour = pygame.Color(255, 255, 255, 255)

        self.link_normal_colour = None
        self.link_hover_colour = None
        self.link_selected_colour = None
        self.link_normal_underline = False
        self.link_hover_underline = True
        self.link_style = None

        self.rounded_corner_width_offsets = [0, 0]
        self.rounded_corner_height_offsets = [0, 0]
        self.text_box_layout = None  # type: Optional[TextBoxLayout]
        self.text_wrap_rect = None  # type: Optional[pygame.Rect]
        self.background_surf = None

        self.shape = 'rectangle'

        self.text_horiz_alignment = 'default'
        self.text_vert_alignment = 'default'
        self.text_horiz_alignment_padding = 0
        self.text_vert_alignment_padding = 0

        self.should_trigger_full_rebuild = True
        self.time_until_full_rebuild_after_changing_size = 0.2
        self.full_rebuild_countdown = self.time_until_full_rebuild_after_changing_size

        self.parser = None  # type: Optional[HTMLParser]

        self.double_click_timer = self.ui_manager.get_double_click_time() + 1.0

        self.edit_position = 0
        self._select_range = [0, 0]
        self.selection_in_progress = False
        self.cursor_has_moved_recently = False

        self.vertical_cursor_movement = False
        self.last_horiz_cursor_index = 0

        self.copy_text_enabled = True
        self.paste_text_enabled = False

        self.rebuild_from_changed_theme_data()

    @property
    def select_range(self):
        """
        The selected range for this text. A tuple containing the start
        and end indexes of the current selection.

        Made into a property to keep it synchronised with the underlying drawable shape's
        representation.
        """
        return self._select_range

    @select_range.setter
    def select_range(self, value):
        self._select_range = value
        start_select = min(self._select_range[0], self._select_range[1])
        end_select = max(self._select_range[0], self._select_range[1])

        self.text_box_layout.set_text_selection(start_select, end_select)
        self.redraw_from_text_block()

    def kill(self):
        """
        Overrides the standard sprite kill method to also kill any scroll bars belonging to this
        text box.
        """
        if self.scroll_bar is not None:
            self.scroll_bar.kill()
        super().kill()

    def rebuild(self):
        """
        Rebuild whatever needs building.

        """
        if self.scroll_bar is not None:
            self.scroll_bar.kill()
            self.scroll_bar = None

        # The text_wrap_area is the part of the text box that we try to keep the text inside
        # of so that none  of it overlaps. Essentially we start with the containing box,
        # subtract the border, then subtract the padding, then if necessary subtract the width
        # of the scroll bar
        tl_offset = round(self.shape_corner_radius[0] - (math.sin(math.pi / 4) * self.shape_corner_radius[0]))
        tr_offset = round(self.shape_corner_radius[1] - (math.sin(math.pi / 4) * self.shape_corner_radius[1]))
        bl_offset = round(self.shape_corner_radius[2] - (math.sin(math.pi / 4) * self.shape_corner_radius[2]))
        br_offset = round(self.shape_corner_radius[3] - (math.sin(math.pi / 4) * self.shape_corner_radius[3]))
        self.rounded_corner_width_offsets = [max(tl_offset, bl_offset), max(tr_offset, br_offset)]
        self.rounded_corner_height_offsets = [max(tl_offset, tr_offset), max(bl_offset, br_offset)]
        total_corner_width_offsets = self.rounded_corner_width_offsets[0] + self.rounded_corner_width_offsets[1]
        total_corner_height_offsets = self.rounded_corner_height_offsets[0] + self.rounded_corner_height_offsets[1]
        self.text_wrap_rect = pygame.Rect((self.rect[0] +
                                           self.padding[0] +
                                           self.border_width +
                                           self.shadow_width +
                                           self.rounded_corner_width_offsets[0]),
                                          (self.rect[1] +
                                           self.padding[1] +
                                           self.border_width +
                                           self.shadow_width +
                                           self.rounded_corner_height_offsets[0]),
                                          max(1, (self.rect[2] -
                                                  (self.padding[0] * 2) -
                                                  (self.border_width * 2) -
                                                  (self.shadow_width * 2) -
                                                  total_corner_width_offsets)),
                                          max(1, (self.rect[3] -
                                                  (self.padding[1] * 2) -
                                                  (self.border_width * 2) -
                                                  (self.shadow_width * 2) -
                                                  total_corner_height_offsets)))
        if self.dynamic_height:
            self.text_wrap_rect.height = -1
        if self.dynamic_width:
            self.text_wrap_rect.width = -1

        drawable_area_size = (self.text_wrap_rect[2], self.text_wrap_rect[3])

        # This gives us the height of the text at the 'width' of the text_wrap_area
        self.parse_html_into_style_data()
        if self.text_box_layout is not None:
            if self.dynamic_height or self.dynamic_width:
                final_text_area_size = self.text_box_layout.layout_rect.size
                new_dimensions = ((final_text_area_size[0] + (self.padding[0] * 2) +
                                   (self.border_width * 2) + (self.shadow_width * 2) +
                                   total_corner_width_offsets),
                                  (final_text_area_size[1] + (self.padding[1] * 2) +
                                   (self.border_width * 2) + (self.shadow_width * 2) +
                                   total_corner_height_offsets))
                self.set_dimensions(new_dimensions)

                # need to regen this because it was dynamically generated
                drawable_area_size = (max(1, (self.rect[2] -
                                              (self.padding[0] * 2) -
                                              (self.border_width * 2) -
                                              (self.shadow_width * 2) -
                                              total_corner_width_offsets)),
                                      max(1, (self.rect[3] -
                                              (self.padding[1] * 2) -
                                              (self.border_width * 2) -
                                              (self.shadow_width * 2) -
                                              total_corner_height_offsets)))

            elif self.text_box_layout.layout_rect.height > self.text_wrap_rect[3]:
                # We need a scrollbar because our text is longer than the space we
                # have to display it. This also means we need to parse the text again.
                text_rect_width = (self.rect[2] -
                                   (self.padding[0] * 2) -
                                   (self.border_width * 2) -
                                   (self.shadow_width * 2) -
                                   total_corner_width_offsets - self.scroll_bar_width)
                self.text_wrap_rect = pygame.Rect((self.rect[0] + self.padding[0] +
                                                   self.border_width + self.shadow_width +
                                                   self.rounded_corner_width_offsets[0]),
                                                  (self.rect[1] + self.padding[1] +
                                                   self.border_width +
                                                   self.shadow_width +
                                                   self.rounded_corner_height_offsets[0]),
                                                  max(1, text_rect_width),
                                                  max(1, (self.rect[3] -
                                                          (self.padding[1] * 2) -
                                                          (self.border_width * 2) -
                                                          (self.shadow_width * 2) -
                                                          total_corner_height_offsets)))
                self.parse_html_into_style_data()
                percentage_visible = (self.text_wrap_rect[3] /
                                      self.text_box_layout.layout_rect.height)
                scroll_bar_position = (self.relative_rect.right - self.border_width -
                                       self.shadow_width - self.scroll_bar_width,
                                       self.relative_rect.top + self.border_width +
                                       self.shadow_width)

                scroll_bar_rect = pygame.Rect(scroll_bar_position,
                                              (self.scroll_bar_width,
                                               self.rect.height -
                                               (2 * self.border_width) -
                                               (2 * self.shadow_width)))
                self.scroll_bar = UIVerticalScrollBar(scroll_bar_rect,
                                                      percentage_visible,
                                                      self.ui_manager,
                                                      self.ui_container,
                                                      parent_element=self,
                                                      visible=self.visible,
                                                      anchors=self.anchors)
                self.join_focus_sets(self.scroll_bar)
            else:
                # we don't need a scroll bar, make sure our text box is aligned to the top
                new_dimensions = (self.rect[2], self.rect[3])
                self.set_dimensions(new_dimensions)

        theming_parameters = {'normal_bg': self.background_colour,
                              'normal_border': self.border_colour,
                              'border_width': self.border_width,
                              'shadow_width': self.shadow_width,
                              'shape_corner_radius': self.shape_corner_radius,
                              'text_cursor_colour': self.text_cursor_colour}

        if self.shape == 'rectangle':
            self.drawable_shape = RectDrawableShape(self.rect, theming_parameters,
                                                    ['normal'], self.ui_manager)
        elif self.shape == 'rounded_rectangle':
            self.drawable_shape = RoundedRectangleShape(self.rect, theming_parameters,
                                                        ['normal'], self.ui_manager)

        self.background_surf = self.drawable_shape.get_fresh_surface()

        if self.scroll_bar is not None:
            height_adjustment = int(self.scroll_bar.start_percentage *
                                    self.text_box_layout.layout_rect.height)
        else:
            height_adjustment = 0

        if self.rect.width <= 0 or self.rect.height <= 0:
            return

        drawable_area = pygame.Rect((0, height_adjustment),
                                    drawable_area_size)
        new_image = pygame.surface.Surface(self.rect.size, flags=pygame.SRCALPHA, depth=32)
        new_image.fill(pygame.Color(0, 0, 0, 0))
        basic_blit(new_image, self.background_surf, (0, 0))

        basic_blit(new_image, self.text_box_layout.finalised_surface,
                   (self.padding[0] + self.border_width +
                    self.shadow_width + self.rounded_corner_width_offsets[0],
                    self.padding[1] + self.border_width +
                    self.shadow_width + self.rounded_corner_height_offsets[0]),
                   drawable_area)

        self._set_image(new_image)
        self.link_hover_chunks = []
        self.text_box_layout.add_chunks_to_hover_group(self.link_hover_chunks)

        self.should_trigger_full_rebuild = False
        self.full_rebuild_countdown = self.time_until_full_rebuild_after_changing_size

    def get_text_layout_top_left(self):
        return (self.rect.left + self.padding[0] + self.border_width +
                self.shadow_width + self.rounded_corner_width_offsets[0],
                self.rect.top + self.padding[1] + self.border_width +
                self.shadow_width + self.rounded_corner_height_offsets[0]
                )

    def _align_all_text_rows(self):
        """
        Aligns the text drawing position correctly according to our theming options.

        """
        # Horizontal alignment
        if self.text_horiz_alignment != 'default':
            if self.text_horiz_alignment == 'center':
                self.text_box_layout.horiz_center_all_rows()
            elif self.text_horiz_alignment == 'left':
                self.text_box_layout.align_left_all_rows(self.text_horiz_alignment_padding)
            else:
                self.text_box_layout.align_right_all_rows(self.text_horiz_alignment_padding)
        elif self.text_horiz_alignment == 'default':
            locale = self.ui_manager.get_locale()
            if locale in ['ar', 'he']:
                self.text_box_layout.align_right_all_rows(self.text_horiz_alignment_padding)
            else:
                self.text_box_layout.align_left_all_rows(self.text_horiz_alignment_padding)

        # Vertical alignment
        if self.text_vert_alignment != 'default':
            if self.text_vert_alignment == 'center':
                self.text_box_layout.vert_center_all_rows()
            elif self.text_vert_alignment == 'top':
                self.text_box_layout.vert_align_top_all_rows(self.text_vert_alignment_padding)
            else:
                self.text_box_layout.vert_align_bottom_all_rows(self.text_vert_alignment_padding)

    def update(self, time_delta: float):
        """
        Called once every update loop of the UI Manager. Used to react to scroll bar movement
        (if there is one), update the text effect (if there is one) and check if we are hovering
        over any text links (if there are any).

        :param time_delta: The time in seconds between calls to update. Useful for timing things.

        """
        super().update(time_delta)
        if not self.alive():
            return

        if self.double_click_timer < self.ui_manager.get_double_click_time():
            self.double_click_timer += time_delta

        if self.selection_in_progress:
            scaled_mouse_pos = self.ui_manager.get_mouse_position()
            text_layout_space_pos = self._calculate_text_space_pos(scaled_mouse_pos)
            select_end_pos = self.text_box_layout.find_cursor_position_from_click_pos(text_layout_space_pos)
            new_range = [self.select_range[0], select_end_pos]
            if new_range[0] != self.select_range[0] or new_range[1] != self.select_range[1]:
                self.select_range = [new_range[0], new_range[1]]

                self.edit_position = self.select_range[1]
                self.cursor_has_moved_recently = True

        if self.cursor_has_moved_recently:
            self.cursor_has_moved_recently = False

            self.text_box_layout.set_cursor_position(self.edit_position)
            if not self.vertical_cursor_movement:
                if self.text_box_layout.cursor_text_row is not None:
                    self.last_horiz_cursor_index = self.text_box_layout.cursor_text_row.get_cursor_index()
            self.vertical_cursor_movement = False
            self._handle_cursor_visibility()
            if self.scroll_bar is not None:
                cursor_y_pos_top, cursor_y_pos_bottom = self.text_box_layout.get_cursor_y_pos()
                current_height_adjustment = int(self.scroll_bar.start_percentage *
                                                self.text_box_layout.layout_rect.height)
                visible_bottom = current_height_adjustment + self.text_box_layout.view_rect.height
                # handle cursor moving above current scroll position
                if cursor_y_pos_top < current_height_adjustment:
                    new_start_percentage = cursor_y_pos_top / self.text_box_layout.layout_rect.height
                    self.scroll_bar.set_scroll_from_start_percentage(new_start_percentage)
                # handle cursor moving below visible area
                if cursor_y_pos_bottom > visible_bottom:
                    new_top = cursor_y_pos_bottom - self.text_box_layout.view_rect.height
                    new_start_percentage = new_top / self.text_box_layout.layout_rect.height
                    self.scroll_bar.set_scroll_from_start_percentage(new_start_percentage)

            self.redraw_from_text_block()

        if self.scroll_bar is not None and self.scroll_bar.check_has_moved_recently():
            height_adjustment = int(self.scroll_bar.start_percentage *
                                    self.text_box_layout.layout_rect.height)

            total_corner_width_offsets = self.rounded_corner_width_offsets[0] + self.rounded_corner_width_offsets[1]
            total_corner_height_offsets = self.rounded_corner_height_offsets[0] + self.rounded_corner_height_offsets[1]

            drawable_area_size = (max(1, (self.rect[2] -
                                          (self.padding[0] * 2) -
                                          (self.border_width * 2) -
                                          (self.shadow_width * 2) -
                                          total_corner_width_offsets)),
                                  max(1, (self.rect[3] -
                                          (self.padding[1] * 2) -
                                          (self.border_width * 2) -
                                          (self.shadow_width * 2) -
                                          total_corner_height_offsets)))
            drawable_area = pygame.Rect((0, height_adjustment),
                                        drawable_area_size)

            if self.rect.width <= 0 or self.rect.height <= 0:
                return

            new_image = pygame.surface.Surface(self.rect.size, flags=pygame.SRCALPHA, depth=32)
            new_image.fill(pygame.Color(0, 0, 0, 0))
            basic_blit(new_image, self.background_surf, (0, 0))
            basic_blit(new_image, self.text_box_layout.finalised_surface,
                       (self.padding[0] + self.border_width +
                        self.shadow_width +
                        self.rounded_corner_width_offsets[0],
                        self.padding[1] + self.border_width +
                        self.shadow_width +
                        self.rounded_corner_height_offsets[0]),
                       drawable_area)
            self._set_image(new_image)

        any_hyper_link_hovered = False
        if len(self.link_hover_chunks) > 0:
            mouse_x, mouse_y = self.ui_manager.get_mouse_position()
            should_redraw_from_layout = False
            if self.scroll_bar is not None:
                height_adjustment = (self.scroll_bar.start_percentage *
                                     self.text_box_layout.layout_rect.height)
            else:
                height_adjustment = 0
            base_x = int(self.rect[0] + self.padding[0] + self.border_width +
                         self.shadow_width + self.rounded_corner_width_offsets[0])
            base_y = int(self.rect[1] + self.padding[1] + self.border_width +
                         self.shadow_width + self.rounded_corner_height_offsets[0] - height_adjustment)

            for chunk in self.link_hover_chunks:
                hovered_currently = False

                hover_rect = pygame.Rect((base_x + chunk.x,
                                          base_y + chunk.y),
                                         chunk.size)
                if hover_rect.collidepoint(mouse_x, mouse_y) and self.rect.collidepoint(mouse_x,
                                                                                        mouse_y):
                    hovered_currently = True
                    any_hyper_link_hovered = True
                if chunk.is_hovered and not hovered_currently:
                    chunk.on_unhovered()
                    should_redraw_from_layout = True
                elif hovered_currently and not chunk.is_hovered:
                    chunk.on_hovered()
                    should_redraw_from_layout = True

            if should_redraw_from_layout:
                self.redraw_from_text_block()

        scaled_mouse_pos = self.ui_manager.get_mouse_position()
        if self.hovered:
            if (self.scroll_bar is None or
                    (self.scroll_bar is not None and
                     not self.scroll_bar.hover_point(scaled_mouse_pos[0], scaled_mouse_pos[1]))):

                if not (any_hyper_link_hovered and not self.selection_in_progress):
                    self.ui_manager.set_text_hovered(True)

        self.update_text_effect(time_delta)

        if self.should_trigger_full_rebuild and self.full_rebuild_countdown <= 0.0:
            self.rebuild()

        if self.full_rebuild_countdown > 0.0:
            self.full_rebuild_countdown -= time_delta

    def _handle_cursor_visibility(self):
        # do nothing in text box - this is for the text entry box
        pass

    def on_fresh_drawable_shape_ready(self):
        """
        Called by an element's drawable shape when it has a new image surface ready for use,
        normally after a rebuilding/redrawing of some kind.
        """
        self.background_surf = self.drawable_shape.get_fresh_surface()
        self.redraw_from_text_block()

    def set_relative_position(self, position: Coordinate):
        """
        Sets the relative screen position of this text box, updating its subordinate scroll bar at
        the same time.

        :param position: The relative screen position to set.

        """
        super().set_relative_position(position)

        if self.scroll_bar is not None:
            scroll_bar_position = (self.relative_rect.right - self.border_width -
                                   self.shadow_width - self.scroll_bar_width,
                                   self.relative_rect.top + self.border_width +
                                   self.shadow_width)
            self.scroll_bar.set_relative_position(scroll_bar_position)

    def set_position(self, position: Coordinate):
        """
        Sets the absolute screen position of this text box, updating its subordinate scroll bar
        at the same time.

        :param position: The absolute screen position to set.

        """
        super().set_position(position)

        if self.scroll_bar is not None:
            scroll_bar_position = (self.relative_rect.right - self.border_width -
                                   self.shadow_width - self.scroll_bar_width,
                                   self.relative_rect.top + self.border_width +
                                   self.shadow_width)
            self.scroll_bar.set_relative_position(scroll_bar_position)

    def set_dimensions(self, dimensions: Coordinate, clamp_to_container: bool = False):
        """
        Method to directly set the dimensions of a text box.

        :param dimensions: The new dimensions to set.
        :param clamp_to_container: Whether we should clamp the dimensions to the
                                   dimensions of the container or not.

        """
        self.relative_rect.width = int(dimensions[0])
        self.relative_rect.height = int(dimensions[1])
        self.rect.size = self.relative_rect.size

        if dimensions[0] >= 0 and dimensions[1] >= 0:
            if self.relative_right_margin is not None:
                self.relative_right_margin = self.ui_container.get_container().get_rect().right - self.rect.right

            if self.relative_bottom_margin is not None:
                self.relative_bottom_margin = self.ui_container.get_container().get_rect().bottom - self.rect.bottom

            self._update_container_clip()

            # Quick and dirty temporary scaling to cut down on number of
            # full rebuilds triggered when rapid scaling
            if self.image is not None:
                if (self.full_rebuild_countdown > 0.0 and
                        (self.relative_rect.width > 0 and
                         self.relative_rect.height > 0)):
                    new_image = pygame.surface.Surface(self.relative_rect.size,
                                                       flags=pygame.SRCALPHA,
                                                       depth=32)
                    new_image.fill(pygame.Color('#00000000'))
                    basic_blit(new_image, self.image, (0, 0))
                    self._set_image(new_image)

                    if self.scroll_bar is not None:
                        self.scroll_bar.set_dimensions((self.scroll_bar.relative_rect.width,
                                                        self.relative_rect.height -
                                                        (2 * self.border_width) -
                                                        (2 * self.shadow_width)))
                        scroll_bar_position = (self.relative_rect.right - self.border_width -
                                               self.shadow_width - self.scroll_bar_width,
                                               self.relative_rect.top + self.border_width +
                                               self.shadow_width)
                        self.scroll_bar.set_relative_position(scroll_bar_position)

                self.should_trigger_full_rebuild = True
                self.full_rebuild_countdown = self.time_until_full_rebuild_after_changing_size

    def parse_html_into_style_data(self):
        """
        Parses HTML styled string text into a format more useful for styling rendered text.
        """
        if len(self.html_text) == 0 and self.placeholder_text is not None and not self.is_focused:
            feed_input = self.placeholder_text
        else:
            feed_input = self.html_text
        if self.plain_text_display_only:
            feed_input = html.escape(feed_input)  # might have to add true to second param here for quotes
        feed_input = self._pre_parse_text(translate(feed_input, **self.text_kwargs) + self.appended_text)
        self.parser.feed(feed_input)

        default_font = self.ui_theme.get_font_dictionary().find_font(
            font_name=self.parser.default_style['font_name'],
            font_size=self.parser.default_style['font_size'],
            bold=self.parser.default_style['bold'],
            italic=self.parser.default_style['italic'],
            antialiased=self.parser.default_style['antialiased'],
            script=self.parser.default_style['script'],
            direction=self.parser.default_style['direction'])
        default_font_data = {"font": default_font,
                             "font_colour": self.parser.default_style['font_colour'],
                             "bg_colour": self.parser.default_style['bg_colour']
                             }
        self.text_box_layout = TextBoxLayout(self.parser.layout_rect_queue,
                                             pygame.Rect((0, 0), (self.text_wrap_rect[2],
                                                                  self.text_wrap_rect[3])),
                                             pygame.Rect((0, 0), (self.text_wrap_rect[2],
                                                                  self.text_wrap_rect[3])),
                                             line_spacing=self.line_spacing,
                                             default_font_data=default_font_data,
                                             allow_split_dashes=self.allow_split_dashes,
                                             text_direction=self.parser.default_style['direction'],
                                             editable=True)
        self.text_box_layout.set_cursor_colour(self.text_cursor_colour)
        self.text_box_layout.selection_colour = self.selected_bg_colour
        self.text_box_layout.selection_text_colour = self.selected_text_colour
        self.parser.empty_layout_queue()
        if self.dynamic_height:
            self.text_box_layout.view_rect.height = self.text_box_layout.layout_rect.height

        self._align_all_text_rows()
        self.text_box_layout.finalise_to_new()

    def redraw_from_text_block(self):
        """
        Redraws the final parts of the text box element that don't include redrawing the actual
        text. Useful if we've just moved the position of the text (say, with a scroll bar)
        without actually changing the text itself.
        """
        if self.rect.width <= 0 or self.rect.height <= 0:
            return
        if (self.scroll_bar is None and not self.dynamic_height and
                (self.text_box_layout.layout_rect.height > self.text_wrap_rect[3])):
            self.rebuild()
            return
        else:
            if self.scroll_bar is not None:
                height_adjustment = int(self.scroll_bar.start_percentage *
                                        self.text_box_layout.layout_rect.height)
                percentage_visible = (self.text_wrap_rect[3] /
                                      self.text_box_layout.layout_rect.height)
                if percentage_visible >= 1.0:
                    self.rebuild()
                    return
                else:
                    self.scroll_bar.set_visible_percentage(percentage_visible)
            else:
                height_adjustment = 0
            total_corner_width_offsets = self.rounded_corner_width_offsets[0] + self.rounded_corner_width_offsets[1]
            total_corner_height_offsets = self.rounded_corner_height_offsets[0] + self.rounded_corner_height_offsets[1]
            drawable_area_size = (max(1, (self.rect[2] -
                                          (self.padding[0] * 2) -
                                          (self.border_width * 2) -
                                          (self.shadow_width * 2) -
                                          total_corner_width_offsets)),
                                  max(1, (self.rect[3] -
                                          (self.padding[1] * 2) -
                                          (self.border_width * 2) -
                                          (self.shadow_width * 2) -
                                          total_corner_height_offsets)))
            drawable_area = pygame.Rect((0, height_adjustment),
                                        drawable_area_size)
            new_image = pygame.surface.Surface(self.rect.size, flags=pygame.SRCALPHA, depth=32)
            new_image.fill(pygame.Color(0, 0, 0, 0))
            basic_blit(new_image, self.background_surf, (0, 0))
            basic_blit(new_image, self.text_box_layout.finalised_surface,
                       (self.padding[0] + self.border_width +
                        self.shadow_width + self.rounded_corner_width_offsets[0],
                        self.padding[1] + self.border_width +
                        self.shadow_width + self.rounded_corner_height_offsets[0]),
                       drawable_area)
            self._set_image(new_image)

    def redraw_from_chunks(self):
        """
        Redraws from slightly earlier in the process than 'redraw_from_text_block'. Useful if we
        have redrawn individual chunks already (say, to change their style slightly after being
        hovered) and now want to update the text block with those changes without doing a
        full redraw.

        This won't work very well if redrawing a chunk changed its dimensions.
        """
        self.text_box_layout.finalise_to_new()
        self.redraw_from_text_block()

    def full_redraw(self):
        """
        Trigger a full redraw of the entire text box. Useful if we have messed with the text
        chunks in a more fundamental fashion and need to reposition them (say, if some of them
        have gotten wider after being made bold).

        NOTE: This doesn't reparse the text of our box. If you need to do that, just create a
        new text box.

        """
        self.text_box_layout.reprocess_layout_queue(pygame.Rect((0, 0),
                                                                (self.text_wrap_rect[2],
                                                                 self.text_wrap_rect[3])))
        self.text_box_layout.finalise_to_new()
        self.redraw_from_text_block()
        self.link_hover_chunks = []
        self.text_box_layout.add_chunks_to_hover_group(self.link_hover_chunks)

    def _process_mouse_button_event(self, event: Event) -> bool:
        """
        Process a mouse button event.

        :param event: Event to process.

        :return: True if we consumed the mouse event.

        """
        consumed_event = False
        should_redraw_from_layout = False
        if event.type == MOUSEBUTTONDOWN and event.button == BUTTON_LEFT:
            scaled_mouse_pos = self.ui_manager.calculate_scaled_mouse_position(event.pos)
            if self.hover_point(scaled_mouse_pos[0], scaled_mouse_pos[1]):
                if self.is_enabled:
                    consumed_event = True
                    should_redraw_from_layout = self._handle_hyper_link_mouse_button_down(scaled_mouse_pos)
                    if not should_redraw_from_layout:
                        text_layout_space_pos = self._calculate_text_space_pos(scaled_mouse_pos)
                        self.text_box_layout.set_cursor_from_click_pos(text_layout_space_pos)
                        self.edit_position = self.text_box_layout.get_cursor_index()
                        self.redraw_from_text_block()

                        double_clicking = False
                        if self.double_click_timer < self.ui_manager.get_double_click_time():
                            if self._calculate_double_click_word_selection():
                                double_clicking = True
                                self.cursor_has_moved_recently = True

                        if not double_clicking:
                            self.select_range = [self.edit_position, self.edit_position]
                            self.cursor_has_moved_recently = True
                            self.selection_in_progress = True
                            self.double_click_timer = 0.0

        if (event.type == MOUSEBUTTONUP and
                event.button == BUTTON_LEFT):
            scaled_mouse_pos = self.ui_manager.calculate_scaled_mouse_position(event.pos)

            if self.hover_point(scaled_mouse_pos[0], scaled_mouse_pos[1]):
                if self.is_enabled:
                    consumed_event = True
                    should_redraw_from_layout = self._handle_hyper_link_mouse_button_up(scaled_mouse_pos)
                    if not should_redraw_from_layout and self.selection_in_progress:
                        text_layout_space_pos = self._calculate_text_space_pos(scaled_mouse_pos)
                        self.text_box_layout.set_cursor_from_click_pos(text_layout_space_pos)
                        new_edit_pos = self.text_box_layout.get_cursor_index()
                        if new_edit_pos != self.edit_position:
                            self.edit_position = new_edit_pos
                            self.cursor_has_moved_recently = True
                            self.select_range = [self.select_range[0], self.edit_position]
                            self.redraw_from_text_block()

            self.selection_in_progress = False

        if should_redraw_from_layout:
            self.redraw_from_text_block()

        return consumed_event

    def process_event(self, event: Event) -> bool:
        consumed_event = False
        if self._process_mouse_button_event(event):
            consumed_event = True
        if self.is_enabled and self.is_focused and event.type == KEYDOWN:
            if self._process_keyboard_shortcut_event(event):
                consumed_event = True
            elif self._process_edit_pos_move_key(event):
                consumed_event = True
        return consumed_event

    def _process_keyboard_shortcut_event(self, event: Event) -> bool:
        """
        Check if event is one of the CTRL key keyboard shortcuts.

        :param event: event to process.

        :return: True if event consumed.

        """
        consumed_event = False
        if self._process_select_all_event(event):
            consumed_event = True
        elif self._process_copy_event(event):
            consumed_event = True
        return consumed_event

    def _process_select_all_event(self, event: Event) -> bool:
        """
        Process a select all shortcut event. (CTRL+ A)

        :param event: The event to process.

        :return: True if the event is consumed.

        """
        consumed_event = False
        if (event.key == K_a and
                (event.mod & KMOD_CTRL or event.mod & KMOD_META) and
                not (event.mod & KMOD_ALT)):  # hopefully enable diacritic letters
            self._do_select_all()
            consumed_event = True
        return consumed_event

    def _do_select_all(self):
        if self.text_box_layout is not None:
            self.select_range = [0, len(self.text_box_layout.plain_text)]
            self.edit_position = len(self.text_box_layout.plain_text)
            self.cursor_has_moved_recently = True

    def _process_copy_event(self, event: Event) -> bool:
        """
        Process a copy shortcut event. (CTRL+ C)

        :param event: The event to process.

        :return: True if the event is consumed.

        """
        consumed_event = False
        if (event.key == K_c and
                (event.mod & KMOD_CTRL or event.mod & KMOD_META) and
                not (event.mod & KMOD_ALT)):
            self._do_copy()
            consumed_event = True
        return consumed_event

    def _do_copy(self):
        if self.text_box_layout is not None and abs(self.select_range[0] - self.select_range[1]) > 0:
            low_end = min(self.select_range[0], self.select_range[1])
            high_end = max(self.select_range[0], self.select_range[1])
            if self.ui_manager.copy_text_enabled and self.copy_text_enabled:
                clipboard_copy(self.text_box_layout.plain_text[low_end:high_end])

    def _calculate_double_click_word_selection(self):
        """
        If we double-clicked on a word in the text, select that word.

        """
        if self.edit_position != self.select_range[0] or self.text_box_layout is None:
            return False
        index = min(self.edit_position, len(self.text_box_layout.plain_text) - 1)
        if index >= 0:
            char = self.text_box_layout.plain_text[index]
            # Check we clicked in the same place on our second click.
            pattern = re.compile(r"[\w']+")

            while index >= 0 and not pattern.match(char):
                index -= 1
                if index >= 0:
                    char = self.text_box_layout.plain_text[index]
                else:
                    break
            while index >= 0 and pattern.match(char):
                index -= 1
                if index >= 0:
                    char = self.text_box_layout.plain_text[index]
                else:
                    break
            start_select_index = index + 1
            index += 1
            if index < len(self.text_box_layout.plain_text):
                char = self.text_box_layout.plain_text[index]
                while index < len(self.text_box_layout.plain_text) and pattern.match(char):
                    index += 1
                    if index < len(self.text_box_layout.plain_text):
                        char = self.text_box_layout.plain_text[index]
            end_select_index = index
            self.select_range = [start_select_index, end_select_index]
            self.edit_position = end_select_index
            self.selection_in_progress = False
            return True
        else:
            return False

    def _calculate_text_space_pos(self, scaled_mouse_pos):
        height_adjustment = 0
        if self.scroll_bar is not None:
            height_adjustment = (self.scroll_bar.start_percentage * self.text_box_layout.layout_rect.height)

        text_layout_top_left = self.get_text_layout_top_left()
        text_layout_space_pos = (scaled_mouse_pos[0] - text_layout_top_left[0],
                                 scaled_mouse_pos[1] - text_layout_top_left[1] + height_adjustment)
        return text_layout_space_pos

    def _calculate_hyperlinks_offsets(self):
        height_adjustment = 0
        if self.scroll_bar is not None:
            height_adjustment = (self.scroll_bar.start_percentage * self.text_box_layout.layout_rect.height)

        text_layout_top_left = self.get_text_layout_top_left()
        base_x = int(text_layout_top_left[0])
        base_y = int(text_layout_top_left[1] - height_adjustment)

        return base_x, base_y

    def _handle_hyper_link_mouse_button_down(self, scaled_mouse_pos: Tuple[int, int]) -> bool:
        should_redraw_from_layout = False
        base_x, base_y = self._calculate_hyperlinks_offsets()
        for chunk in self.link_hover_chunks:

            hover_rect = pygame.Rect((base_x + chunk.x,
                                      base_y + chunk.y),
                                     chunk.size)
            if hover_rect.collidepoint(scaled_mouse_pos[0], scaled_mouse_pos[1]):
                if not chunk.is_active:
                    chunk.set_active()
                    should_redraw_from_layout = True
        return should_redraw_from_layout

    def _handle_hyper_link_mouse_button_up(self, scaled_mouse_pos: Tuple[int, int]) -> bool:
        should_redraw_from_layout = False
        base_x, base_y = self._calculate_hyperlinks_offsets()

        for chunk in self.link_hover_chunks:

            hover_rect = pygame.Rect((base_x + chunk.x,
                                      base_y + chunk.y),
                                     chunk.size)
            if (hover_rect.collidepoint(scaled_mouse_pos[0], scaled_mouse_pos[1]) and
                    self.rect.collidepoint(scaled_mouse_pos[0], scaled_mouse_pos[1])):

                if chunk.is_active:
                    # old event - to be removed in 0.8.0
                    event_data = {'user_type': OldType(UI_TEXT_BOX_LINK_CLICKED),
                                  'link_target': chunk.href,
                                  'ui_element': self,
                                  'ui_object_id': self.most_specific_combined_id}
                    pygame.event.post(pygame.event.Event(pygame.USEREVENT, event_data))

                    # new event
                    event_data = {'link_target': chunk.href,
                                  'ui_element': self,
                                  'ui_object_id': self.most_specific_combined_id}
                    pygame.event.post(pygame.event.Event(UI_TEXT_BOX_LINK_CLICKED, event_data))

            if chunk.is_active:
                chunk.set_inactive()
                should_redraw_from_layout = True
        return should_redraw_from_layout

    def rebuild_from_changed_theme_data(self):
        """
        Called by the UIManager to check the theming data and rebuild whatever needs rebuilding
        for this element when the theme data has changed.
        """
        super().rebuild_from_changed_theme_data()
        has_any_changed = False

        # misc parameters
        if self._check_misc_theme_data_changed(attribute_name='shape',
                                               default_value='rectangle',
                                               casting_func=str,
                                               allowed_values=['rectangle',
                                                               'rounded_rectangle']):
            has_any_changed = True

        if self._check_shape_theming_changed(defaults={'border_width': 1,
                                                       'shadow_width': 2,
                                                       'shape_corner_radius': [2, 2, 2, 2]}):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='padding',
                                               default_value=(5, 5),
                                               casting_func=self.tuple_extract):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='line_spacing', default_value=1.25, casting_func=float):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='tool_tip_delay',
                                               default_value=1.0,
                                               casting_func=float):
            has_any_changed = True

        # colour parameters
        background_colour = self.ui_theme.get_colour_or_gradient('dark_bg',
                                                                 self.combined_element_ids)
        if background_colour != self.background_colour:
            self.background_colour = background_colour
            has_any_changed = True

        border_colour = self.ui_theme.get_colour_or_gradient('normal_border',
                                                             self.combined_element_ids)
        if border_colour != self.border_colour:
            self.border_colour = border_colour
            has_any_changed = True

        text_cursor_colour = self.ui_theme.get_colour_or_gradient('text_cursor',
                                                                  self.combined_element_ids)
        if text_cursor_colour != self.text_cursor_colour:
            self.text_cursor_colour = text_cursor_colour
            has_any_changed = True

        selected_bg_colour = self.ui_theme.get_colour_or_gradient('selected_bg',
                                                                  self.combined_element_ids)
        if selected_bg_colour != self.selected_bg_colour:
            self.selected_bg_colour = selected_bg_colour
            has_any_changed = True

        selected_text_colour = self.ui_theme.get_colour_or_gradient('selected_text',
                                                                    self.combined_element_ids)
        if selected_text_colour != self.selected_text_colour:
            self.selected_text_colour = selected_text_colour
            has_any_changed = True

        if self._check_text_alignment_theming():
            has_any_changed = True

        if self._check_link_style_changed():
            has_any_changed = True

        if has_any_changed:
            self._reparse_and_rebuild()

    def _reparse_and_rebuild(self):
        self.parser = HTMLParser(self.ui_theme, self.combined_element_ids,
                                 self.link_style, line_spacing=self.line_spacing,
                                 text_direction=self.font_dict.get_default_font().get_direction())
        self.rebuild()

    def _check_text_alignment_theming(self) -> bool:
        """
        Checks for any changes in the theming data related to text alignment.

        :return: True if changes found.

        """
        has_any_changed = False

        if self._check_misc_theme_data_changed(attribute_name='text_horiz_alignment',
                                               default_value='default',
                                               casting_func=str):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='text_horiz_alignment_padding',
                                               default_value=0,
                                               casting_func=int):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='text_vert_alignment',
                                               default_value='top',
                                               casting_func=str):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='text_vert_alignment_padding',
                                               default_value=0,
                                               casting_func=int):
            has_any_changed = True

        return has_any_changed

    def _check_link_style_changed(self) -> bool:
        """
        Checks for any changes in hyperlink related styling in the theme data.

        :return: True if changes detected.

        """
        has_any_changed = False

        def parse_to_bool(str_data: str):
            return bool(int(str_data))

        if self._check_misc_theme_data_changed(attribute_name='link_normal_underline',
                                               default_value=True,
                                               casting_func=parse_to_bool):
            has_any_changed = True

        if self._check_misc_theme_data_changed(attribute_name='link_hover_underline',
                                               default_value=True,
                                               casting_func=parse_to_bool):
            has_any_changed = True

        link_normal_colour = self.ui_theme.get_colour_or_gradient('link_text',
                                                                  self.combined_element_ids)
        if link_normal_colour != self.link_normal_colour:
            self.link_normal_colour = link_normal_colour
        link_hover_colour = self.ui_theme.get_colour_or_gradient('link_hover',
                                                                 self.combined_element_ids)
        if link_hover_colour != self.link_hover_colour:
            self.link_hover_colour = link_hover_colour
        link_selected_colour = self.ui_theme.get_colour_or_gradient('link_selected',
                                                                    self.combined_element_ids)
        if link_selected_colour != self.link_selected_colour:
            self.link_selected_colour = link_selected_colour
        link_style = {'link_text': self.link_normal_colour,
                      'link_hover': self.link_hover_colour,
                      'link_selected': self.link_selected_colour,
                      'link_normal_underline': self.link_normal_underline,
                      'link_hover_underline': self.link_hover_underline}
        if link_style != self.link_style:
            self.link_style = link_style
            has_any_changed = True
        return has_any_changed

    def disable(self):
        """
        Disable the text box. Basically just disables the scroll bar if one exists.
        """
        if self.is_enabled:
            self.is_enabled = False
            if self.scroll_bar:
                self.scroll_bar.disable()

    def enable(self):
        """
        Enable the text box. Re-enables the scroll bar if one exists.
        """
        if not self.is_enabled:
            self.is_enabled = True
            if self.scroll_bar:
                self.scroll_bar.enable()

    def show(self):
        """
        In addition to the base UIElement.show() - call show() of scroll_bar if it exists.
        """
        super().show()

        if self.scroll_bar is not None:
            self.scroll_bar.show()

    def hide(self):
        """
        In addition to the base UIElement.hide() - call hide() of scroll_bar if it exists.
        """
        super().hide()

        if self.scroll_bar is not None:
            self.scroll_bar.hide()

    def append_html_text(self, new_html_str: str):
        """
        Adds a string, that is parsed for any HTML tags that pygame_gui supports, onto the bottom
        of the text box's current contents.

        This is useful for making things like logs.

        :param new_html_str: The, potentially HTML tag, containing string of text to append.
        """
        if self.should_html_unescape_input_text:
            feed_input = html.unescape(new_html_str)
        else:
            feed_input = new_html_str
        self.appended_text += feed_input
        if self.plain_text_display_only:
            # if we are supporting only plain text rendering then we turn html input into text at this point
            feed_input = html.escape(feed_input)  # might have to add true to second param here for quotes
        # this converts plain text special characters to html just for the parser
        feed_input = self._pre_parse_text(feed_input)

        self.parser.feed(feed_input)
        self.text_box_layout.append_layout_rects(self.parser.layout_rect_queue)
        self.parser.empty_layout_queue()

        if (self.scroll_bar is None and
                (self.text_box_layout.layout_rect.height > self.text_wrap_rect[3])):
            self.rebuild()
        else:
            if self.scroll_bar is not None:
                # set the scroll bar to the bottom
                percentage_visible = (self.text_wrap_rect[3] /
                                      self.text_box_layout.layout_rect.height)
                self.scroll_bar.start_percentage = 1.0 - percentage_visible
                self.scroll_bar.scroll_position = (self.scroll_bar.start_percentage *
                                                   self.scroll_bar.scrollable_height)
            self.redraw_from_text_block()
            self.link_hover_chunks = []
            self.text_box_layout.add_chunks_to_hover_group(self.link_hover_chunks)

    def on_locale_changed(self):
        self._reparse_and_rebuild()

    # -------------------------------------------------
    # The Text owner interface
    # -------------------------------------------------
    def set_text_alpha(self, alpha: int, sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            self.text_box_layout.set_alpha(alpha)
        else:
            sub_chunk.set_alpha(alpha)

    def set_text_offset_pos(self, offset: Tuple[int, int],
                            sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            pass
        else:
            sub_chunk.set_offset_pos(offset)

    def set_text_rotation(self, rotation: int,
                          sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            pass
        else:
            sub_chunk.set_rotation(rotation)

    def set_text_scale(self, scale: float, sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            pass
        else:
            sub_chunk.set_scale(scale)

    def clear_text_surface(self,
                           sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            self.text_box_layout.clear_final_surface()
        else:
            sub_chunk.clear()

    def get_text_letter_count(self,
                              sub_chunk: Optional[TextLineChunkFTFont] = None) -> int:
        if sub_chunk is None:
            return self.text_box_layout.letter_count
        else:
            return sub_chunk.letter_count

    def update_text_end_position(self, end_pos: int,
                                 sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            self.text_box_layout.update_text_with_new_text_end_pos(end_pos)
        else:
            sub_chunk.letter_end = end_pos
            sub_chunk.redraw()

    def set_active_effect(self, effect_type: Optional[UITextEffectType] = None,
                          params: Optional[Dict[str, Any]] = None,
                          effect_tag: Optional[str] = None):
        if effect_tag is not None:
            redrew_all_chunks = False
            if self.active_text_effect is not None:
                # don't allow mixing of full text box effects and chunk effects
                self.clear_all_active_effects()
                self.active_text_effect = None
                redrew_all_chunks = True
            # we have a tag so only want to apply our effect to tagged chunks
            # first see if we have any tagged chunks in the layout
            for row in self.text_box_layout.layout_rows:
                for chunk in row.items:
                    if isinstance(chunk, TextLineChunkFTFont):
                        if chunk.effect_id == effect_tag:
                            # need to clear off any old effects on this chunk too if we didn't
                            # already redraw everything
                            if not redrew_all_chunks:
                                self.clear_all_active_effects(chunk)
                            effect = None
                            if effect_type == TEXT_EFFECT_TYPING_APPEAR:
                                effect = TypingAppearEffect(self, params, chunk)
                            elif effect_type == TEXT_EFFECT_FADE_IN:
                                effect = FadeInEffect(self, params, chunk)
                            elif effect_type == TEXT_EFFECT_FADE_OUT:
                                effect = FadeOutEffect(self, params, chunk)
                            elif effect_type == TEXT_EFFECT_BOUNCE:
                                effect = BounceEffect(self, params, chunk)
                            elif effect_type == TEXT_EFFECT_TILT:
                                effect = TiltEffect(self, params, chunk)
                            elif effect_type == TEXT_EFFECT_EXPAND_CONTRACT:
                                effect = ExpandContractEffect(self, params, chunk)
                            elif effect_type == TEXT_EFFECT_SHAKE:
                                effect = ShakeEffect(self, params, chunk)
                            else:
                                warnings.warn('Unsupported effect name: ' + str(
                                    effect_type) + ' for text chunk')
                            if effect is not None:
                                chunk.grab_pre_effect_surface()
                                self.active_text_chunk_effects.append({'chunk': chunk,
                                                                       'effect': effect})
                                effect.text_changed = True
                                self.update_text_effect(0.0)
        else:
            if self.active_text_effect is not None or len(self.active_text_chunk_effects) != 0:
                self.clear_all_active_effects()
            if effect_type is None:
                self.active_text_effect = None
            elif isinstance(effect_type, UITextEffectType):
                if effect_type == TEXT_EFFECT_TYPING_APPEAR:
                    self.active_text_effect = TypingAppearEffect(self, params)
                elif effect_type == TEXT_EFFECT_FADE_IN:
                    self.active_text_effect = FadeInEffect(self, params)
                elif effect_type == TEXT_EFFECT_FADE_OUT:
                    self.active_text_effect = FadeOutEffect(self, params)
                else:
                    warnings.warn('Unsupported effect name: '
                                  + str(effect_type) + ' for whole text box')
            else:
                warnings.warn('Unsupported effect name: '
                              + str(effect_type) + ' for whole text box')

            if self.active_text_effect is not None:
                self.active_text_effect.text_changed = True
                self.update_text_effect(0.0)

    def stop_finished_effect(self, sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            self.active_text_effect = None
        else:
            self.active_text_chunk_effects = [effect_chunk for effect_chunk in
                                              self.active_text_chunk_effects
                                              if effect_chunk['chunk'] != sub_chunk]

    def clear_all_active_effects(self, sub_chunk: Optional[TextLineChunkFTFont] = None):
        if sub_chunk is None:
            self.active_text_effect = None
            self.text_box_layout.clear_effects()
            for effect_chunk in self.active_text_chunk_effects:
                effect_chunk['chunk'].clear_effects()
            self.active_text_chunk_effects = []
            self.text_box_layout.finalise_to_new()
        else:
            self.active_text_chunk_effects = [effect_chunk for effect_chunk in
                                              self.active_text_chunk_effects
                                              if effect_chunk['chunk'] != sub_chunk]
            sub_chunk.clear_effects()

            effect_chunks = []
            for affected_chunk in self.active_text_chunk_effects:
                effect_chunks.append(affected_chunk['chunk'])
            self.text_box_layout.redraw_other_chunks(effect_chunks)

            sub_chunk.redraw()

    def update_text_effect(self, time_delta: float):
        if self.active_text_effect is not None:
            self.active_text_effect.update(time_delta)
            # update can set effect to None
            if (self.active_text_effect is not None and
                    self.active_text_effect.has_text_changed()):
                self.active_text_effect.apply_effect()
                self.redraw_from_text_block()

        if len(self.active_text_chunk_effects) > 0:
            any_text_changed = False
            for affected_chunk in self.active_text_chunk_effects:
                affected_chunk['effect'].update(time_delta)
                if (affected_chunk['effect'] is not None and
                        affected_chunk['effect'].has_text_changed()):
                    any_text_changed = True
            if any_text_changed:
                effect_chunks = []
                for affected_chunk in self.active_text_chunk_effects:
                    chunk = affected_chunk['chunk']
                    chunk.clear(chunk.transform_effect_rect)
                    effect_chunks.append(chunk)

                self.text_box_layout.redraw_other_chunks(effect_chunks)

                for affected_chunk in self.active_text_chunk_effects:
                    affected_chunk['effect'].apply_effect()
                self.redraw_from_text_block()

    def get_object_id(self) -> str:
        return self.most_specific_combined_id

    def set_text(self, html_text: str, *, text_kwargs: Optional[Dict[str, str]] = None):
        if self.should_html_unescape_input_text:
            self.html_text = html.unescape(html_text)
        else:
            self.html_text = html_text
        if text_kwargs is not None:
            self.text_kwargs = text_kwargs
        else:
            self.text_kwargs = {}
        self.appended_text = ""  # clear appended text as it feels odd to set the text and still have appended text
        self._reparse_and_rebuild()

    def clear(self):
        self.set_text("")

    def _pre_parse_text(self, input_text: str):
        """
        Some optional automatic pre-parsing/clean-up on input text before parsing it onto the html parser.

        :param input_text: the text to pre parse

        :return: a string with the cleaned up text.
        """
        pre_parsed_text = input_text
        if self._pre_parsing_enabled:
            # replace \n with <br>
            pre_parsed_text = pre_parsed_text.replace('\n', '<br>')

        return pre_parsed_text

    def unfocus(self):
        """
        Called when this element is no longer the current focus.
        """
        super().unfocus()
        if self.placeholder_text is not None:
            self.should_trigger_full_rebuild = True
            self.full_rebuild_countdown = 0.0

    def focus(self):
        """
        Called when we 'select focus' on this element.
        """
        super().focus()
        self.cursor_has_moved_recently = True
        if self.placeholder_text is not None:
            self.should_trigger_full_rebuild = True
            self.full_rebuild_countdown = 0.0

    def _process_edit_pos_move_key(self, event: Event) -> bool:
        """
        Process an action key that is moving the cursor edit position.

        :param event: The event to process.

        :return: True if event is consumed.

        """
        consumed_event = False
        # 4 left/right cases:
        # 1. jump left or right one character (LEFT or RIGHT on their own)
        # 2. jump to end/start of word (CTRL + LEFT or RIGHT)
        # 3. jump to end/start of line (HOME or END)
        # 4. jump to end/start of document (CTRL + HOME or END)
        # plus 1 up or down a line/text row case (UP & DOWN arrows, CTRL makes no difference here in notepad,
        # but in IDE it scrolls if possible)
        # All cases can have selection attached with shift held

        if event.key == K_LEFT:
            if event.mod & KMOD_CTRL or event.mod & KMOD_META:
                self._jump_edit_pos_to_start_of_word(should_select=(event.mod & KMOD_SHIFT))
            else:
                self._jump_edit_pos_one_character_left(should_select=(event.mod & KMOD_SHIFT))
            consumed_event = True
        elif event.key == K_RIGHT:
            if event.mod & KMOD_CTRL or event.mod & KMOD_META:
                self._jump_edit_pos_to_end_of_word(should_select=(event.mod & KMOD_SHIFT))
            else:
                self._jump_edit_pos_one_character_right(should_select=(event.mod & KMOD_SHIFT))
            consumed_event = True
        elif event.key == K_UP:
            self._jump_edit_pos_one_row_up(should_select=(event.mod & KMOD_SHIFT))
            consumed_event = True
        elif event.key == K_DOWN:
            self._jump_edit_pos_one_row_down(should_select=(event.mod & KMOD_SHIFT))
            consumed_event = True
        elif event.key == K_HOME:
            if event.mod & KMOD_CTRL or event.mod & KMOD_META:
                self._jump_edit_pos_to_start_of_all_text(should_select=(event.mod & KMOD_SHIFT))
            else:
                self._jump_edit_pos_to_start_of_line(should_select=(event.mod & KMOD_SHIFT))
            consumed_event = True
        elif event.key == K_END:
            if event.mod & KMOD_CTRL or event.mod & KMOD_META:
                self._jump_edit_pos_to_end_of_all_text(should_select=(event.mod & KMOD_SHIFT))
            else:
                self._jump_edit_pos_to_end_of_line(should_select=(event.mod & KMOD_SHIFT))
            consumed_event = True
        return consumed_event

    def _jump_edit_pos_one_character_right(self, should_select=False):
        if self.text_box_layout is not None:
            if should_select:
                if abs(self.select_range[0] - self.select_range[1]) > 0:
                    if self.edit_position == self.select_range[1]:
                        # try to extend to the right
                        self.select_range = [self.select_range[0],
                                             min(len(self.text_box_layout.plain_text), self.edit_position + 1)]
                    elif self.edit_position == self.select_range[0]:
                        # reduce to the right
                        self.select_range = [min(len(self.text_box_layout.plain_text), self.edit_position + 1),
                                             self.select_range[1]]
                else:
                    self.select_range = [self.edit_position, min(len(self.text_box_layout.plain_text),
                                                                 self.edit_position + 1)]
                if self.edit_position < len(self.text_box_layout.plain_text):
                    self.edit_position += 1
                    self.cursor_has_moved_recently = True
            else:
                if abs(self.select_range[0] - self.select_range[1]) > 0:
                    self.edit_position = max(self.select_range[0], self.select_range[1])
                    self.select_range = [0, 0]
                    self.cursor_has_moved_recently = True
                elif self.edit_position < len(self.text_box_layout.plain_text):
                    self.edit_position += 1
                    self.cursor_has_moved_recently = True

    def _jump_edit_pos_one_character_left(self, should_select=False):
        if should_select:
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                # existing selection, so edit_position should correspond to one
                # end of it
                if self.edit_position == self.select_range[0]:
                    # try to extend to the left
                    self.select_range = [max(0, self.edit_position - 1),
                                         self.select_range[1]]
                elif self.edit_position == self.select_range[1]:
                    # reduce to the left
                    self.select_range = [self.select_range[0],
                                         max(0, self.edit_position - 1)]
            else:
                self.select_range = [max(0, self.edit_position - 1),
                                     self.edit_position]
            if self.edit_position > 0:
                self.edit_position -= 1
                self.cursor_has_moved_recently = True
        else:
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                self.edit_position = min(self.select_range[0], self.select_range[1])
                self.select_range = [0, 0]
                self.cursor_has_moved_recently = True
            elif self.edit_position > 0:
                self.edit_position -= 1
                self.cursor_has_moved_recently = True

    def _jump_edit_pos_one_row_down(self, should_select=False):
        if self.text_box_layout is not None:
            if should_select:
                new_pos = self.text_box_layout.get_cursor_pos_move_down_one_row(self.last_horiz_cursor_index)
                if abs(self.select_range[0] - self.select_range[1]) > 0:
                    if self.edit_position == self.select_range[1]:
                        # try to extend to the right
                        self.select_range = [self.select_range[0],
                                             min(len(self.text_box_layout.plain_text), new_pos)]
                    elif self.edit_position == self.select_range[0]:
                        # reduce to the right
                        self.select_range = [min(len(self.text_box_layout.plain_text), new_pos),
                                             self.select_range[1]]
                else:
                    self.select_range = [self.edit_position, min(len(self.text_box_layout.plain_text),
                                                                 new_pos)]
                if self.edit_position < len(self.text_box_layout.plain_text):
                    self.edit_position = new_pos
                    self.cursor_has_moved_recently = True
            else:
                if abs(self.select_range[0] - self.select_range[1]) > 0:
                    self.edit_position = self.text_box_layout.get_cursor_pos_move_down_one_row(self.last_horiz_cursor_index)
                    self.select_range = [0, 0]
                    self.cursor_has_moved_recently = True
                else:
                    self.edit_position = self.text_box_layout.get_cursor_pos_move_down_one_row(self.last_horiz_cursor_index)
                    self.cursor_has_moved_recently = True
                self.vertical_cursor_movement = True

    def _jump_edit_pos_one_row_up(self, should_select=False):
        if should_select:
            new_pos = self.text_box_layout.get_cursor_pos_move_up_one_row(self.last_horiz_cursor_index)
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                # existing selection, so edit_position should correspond to one
                # end of it
                if self.edit_position == self.select_range[0]:
                    # try to extend to the left
                    self.select_range = [max(0, new_pos),
                                         self.select_range[1]]
                elif self.edit_position == self.select_range[1]:
                    # reduce to the left
                    self.select_range = [self.select_range[0],
                                         max(0, new_pos)]
            else:
                self.select_range = [max(0, new_pos),
                                     self.edit_position]
            if self.edit_position > 0:
                self.edit_position = new_pos
                self.cursor_has_moved_recently = True
        else:
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                self.edit_position = self.text_box_layout.get_cursor_pos_move_up_one_row(self.last_horiz_cursor_index)
                self.select_range = [0, 0]
                self.cursor_has_moved_recently = True
            else:
                self.edit_position = self.text_box_layout.get_cursor_pos_move_up_one_row(self.last_horiz_cursor_index)
                self.cursor_has_moved_recently = True
            self.vertical_cursor_movement = True

    def _jump_edit_pos_to_start_of_word(self, should_select=False):
        if self.text_box_layout is not None:
            try:
                text_to_search = self.text_box_layout.plain_text[max(0, self.edit_position - 1)::-1]
                match_result = re.search(r'\b\w+\b', text_to_search)
                if match_result is not None:
                    next_pos = max(self.edit_position - match_result.regs[-1][1], 0)
                else:
                    next_pos = self.edit_position
            except ValueError:
                next_pos = 0
            # include case when shift held down to select everything to start
            # of current line.
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                if should_select:
                    if self.edit_position == self.select_range[1]:
                        # undo selection to right, create to left
                        self.select_range = [next_pos, self.select_range[0]]
                    else:
                        # extend left
                        self.select_range = [next_pos, self.select_range[1]]
                else:
                    next_pos = self.select_range[0]
                    self.select_range = [0, 0]
            else:
                if should_select:
                    self.select_range = [next_pos, self.edit_position]
                else:
                    self.select_range = [0, 0]
            self.edit_position = next_pos
            self.cursor_has_moved_recently = True

    def _jump_edit_pos_to_end_of_word(self, should_select=False):
        if self.text_box_layout is not None:
            try:
                match_result = re.search(r'\b\w+\b', self.text_box_layout.plain_text[self.edit_position:])
                if match_result is not None:
                    next_pos = min(self.edit_position + match_result.regs[0][1], len(self.text_box_layout.plain_text))
                else:
                    next_pos = self.edit_position
            except ValueError:
                next_pos = len(self.text_box_layout.plain_text)
            # include case when shift held down to select everything to end
            # of current line.
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                if should_select:
                    if self.edit_position == self.select_range[0]:
                        # undo selection to left, create to right
                        self.select_range = [self.select_range[1], next_pos]
                    else:
                        # extend right
                        self.select_range = [self.select_range[0], next_pos]
                else:
                    self.select_range = [0, 0]
            else:
                if should_select:
                    self.select_range = [self.edit_position, next_pos]
                else:
                    self.select_range = [0, 0]
            self.edit_position = next_pos
            self.cursor_has_moved_recently = True

    def _jump_edit_pos_to_start_of_line(self, should_select=False):
        try:
            next_pos = self.text_box_layout.set_cursor_to_start_of_current_row()
        except ValueError:
            next_pos = 0
        # include case when shift held down to select everything to start
        # of current line.
        if abs(self.select_range[0] - self.select_range[1]) > 0:
            if should_select:
                if self.edit_position == self.select_range[1]:
                    # undo selection to right, create to left
                    self.select_range = [next_pos, self.select_range[0]]
                else:
                    # extend left
                    self.select_range = [next_pos, self.select_range[1]]
            else:
                self.select_range = [0, 0]
        else:
            if should_select:
                self.select_range = [next_pos, self.edit_position]
            else:
                self.select_range = [0, 0]
        self.edit_position = next_pos
        self.cursor_has_moved_recently = True

    def _jump_edit_pos_to_end_of_line(self, should_select=False):
        if self.text_box_layout is not None:
            try:
                next_pos = self.text_box_layout.set_cursor_to_end_of_current_row()
            except ValueError:
                next_pos = len(self.text_box_layout.plain_text)
            # include case when shift held down to select everything to end
            # of current line.
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                if should_select:
                    if self.edit_position == self.select_range[0]:
                        # undo selection to left, create to right
                        self.select_range = [self.select_range[1], next_pos]
                    else:
                        # extend right
                        self.select_range = [self.select_range[0], next_pos]
                else:
                    self.select_range = [0, 0]
            else:
                if should_select:
                    self.select_range = [self.edit_position, next_pos]
                else:
                    self.select_range = [0, 0]
            self.edit_position = next_pos
            self.cursor_has_moved_recently = True

    def _jump_edit_pos_to_start_of_all_text(self, should_select=False):
        if should_select:
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                if self.edit_position == self.select_range[0]:
                    self.select_range = [0, self.select_range[1]]
                else:
                    self.select_range = [0, self.select_range[0]]
            else:
                self.select_range = [0, self.edit_position]
        else:
            if abs(self.select_range[0] - self.select_range[1]) > 0:
                self.select_range = [0, 0]
        self.edit_position = 0
        self.cursor_has_moved_recently = True

    def _jump_edit_pos_to_end_of_all_text(self, should_select=False):
        if self.text_box_layout is not None:
            end_of_all_pos = len(self.text_box_layout.plain_text)
            if should_select:
                if abs(self.select_range[0] - self.select_range[1]) > 0:
                    if self.edit_position == self.select_range[0]:
                        self.select_range = [self.select_range[1], end_of_all_pos]
                    else:
                        self.select_range = [self.select_range[0], end_of_all_pos]
                else:
                    self.select_range = [self.edit_position, end_of_all_pos]
            else:
                if abs(self.select_range[0] - self.select_range[1]) > 0:
                    self.select_range = [0, 0]
            self.edit_position = end_of_all_pos
            self.cursor_has_moved_recently = True
