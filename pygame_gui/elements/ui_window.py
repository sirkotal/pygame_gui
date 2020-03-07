import pygame
from typing import Union, Tuple

from pygame_gui._constants import UI_WINDOW_CLOSE, UI_BUTTON_PRESSED

from pygame_gui.core.interfaces import IContainerInterface, IWindowInterface, IUIManagerInterface
from pygame_gui.core import UIElement, UIContainer
from pygame_gui.core.drawable_shapes import RectDrawableShape, RoundedRectangleShape

from pygame_gui.elements.ui_button import UIButton


class UIWindow(UIElement, IContainerInterface, IWindowInterface):
    """
    A base class for window GUI elements, any windows should inherit from this class.

    :param rect: A rectangle, representing size and position of the window (including title bar, shadow and borders).
    :param manager: The UIManager that manages this UIWindow.
    :param window_display_title: A string that will appear in the windows title bar if it has one.
    :param element_id: An element ID for this window, if one is not supplied it defaults to 'window'.
    :param object_id: An optional object ID for this window, useful for distinguishing different windows.
    :param resizable: Whether this window is resizable or not, defaults to False.
    """
    def __init__(self,
                 rect: pygame.Rect,
                 manager: IUIManagerInterface,
                 window_display_title: str = "",
                 element_id: Union[str, None] = None,
                 object_id: Union[str, None] = None,
                 resizable: bool = False):

        if element_id is None:
            element_id = 'window'

        new_element_ids, new_object_ids = self.create_valid_ids(container=None,
                                                                parent_element=None,
                                                                object_id=object_id,
                                                                element_id=element_id)

        self.window_display_title = window_display_title
        self._window_root_container = None
        self.resizable = resizable
        self.minimum_dimensions = (100, 100)
        self.edge_hovering = [False, False, False, False]

        super().__init__(rect, manager, container=None,
                         starting_height=1,
                         layer_thickness=1,
                         object_ids=new_object_ids,
                         element_ids=new_element_ids)

        self.set_image(self.ui_manager.get_universal_empty_surface())
        self.bring_to_front_on_focused = True

        self.is_blocking = False  # blocks all clicking events from interacting beyond this window

        self.resizing_mode_active = False
        self.start_resize_point = (0, 0)
        self.start_resize_rect = None

        self.grabbed_window = False
        self.starting_grab_difference = (0, 0)

        # Themed parameters
        self.shadow_width = None  # type: Union[None, int]
        self.border_width = None  # type: Union[None, int]
        self.background_colour = None
        self.border_colour = None
        self.shape_type = 'rectangle'
        self.shape_corner_radius = None
        self.enable_title_bar = True
        self.enable_close_button = True
        self.title_bar_height = 28
        self.title_bar_button_width = self.title_bar_height

        # UI elements
        self.window_element_container = None
        self.title_bar = None
        self.close_window_button = None

        self.rebuild_from_changed_theme_data()

        self._window_root_container = UIContainer(pygame.Rect(self.relative_rect.x + self.shadow_width,
                                                              self.relative_rect.y + self.shadow_width,
                                                              self.relative_rect.width - (2 * self.shadow_width),
                                                              self.relative_rect.height - (2 * self.shadow_width)),
                                                  manager=manager,
                                                  starting_height=1,
                                                  is_window_root_container=True,
                                                  container=None,
                                                  parent_element=self,
                                                  object_id="#window_root_container")

        self.title_bar = UIButton(relative_rect=pygame.Rect(0, 0,
                                                            (self._window_root_container.relative_rect.width -
                                                             self.title_bar_button_width),
                                                            self.title_bar_height),
                                  text=self.window_display_title,
                                  manager=self.ui_manager,
                                  container=self._window_root_container,
                                  parent_element=self,
                                  object_id='#title_bar',
                                  anchors={'top': 'top', 'bottom': 'top',
                                           'left': 'left', 'right': 'right'}
                                  )
        self.title_bar.set_hold_range((100, 100))

        self.close_window_button = UIButton(relative_rect=pygame.Rect((-self.title_bar_button_width, 0),
                                                                      (self.title_bar_button_width,
                                                                       self.title_bar_height)),
                                            text='╳',
                                            manager=self.ui_manager,
                                            container=self._window_root_container,
                                            parent_element=self,
                                            object_id='#close_button',
                                            anchors={'top': 'top', 'bottom': 'top',
                                                     'left': 'right', 'right': 'right'}
                                            )

        window_container_rect = pygame.Rect(self.border_width,
                                            self.title_bar_height,
                                            (self._window_root_container.relative_rect.width -
                                             (2 * self.border_width)),
                                            (self._window_root_container.relative_rect.height -
                                             self.title_bar_height - self.border_width))
        self.window_element_container = UIContainer(window_container_rect, manager,
                                                    starting_height=0,
                                                    container=self._window_root_container,
                                                    parent_element=self,
                                                    object_id="#window_element_container",
                                                    anchors={'top': 'top', 'bottom': 'bottom',
                                                             'left': 'left', 'right': 'right'}
                                                    )
        self.window_stack = self.ui_manager.get_window_stack()
        self.window_stack.add_new_window(self)

    def set_blocking(self, state: bool):
        """
        Sets whether this window being open should block clicks to the rest of the UI or not. Defaults to False.

        :param state: True if this window should block mouse clicks.
        """
        self.is_blocking = state

    def set_minimum_dimensions(self, dimensions: Union[pygame.math.Vector2, Tuple[int, int], Tuple[float, float]]):
        """
        If this window is resizable, then the dimensions we set here will be the minimum that users can change the
        window to. They are also used as the minimum size when 'set_dimensions' is called.

        TODO: check if current size is smaller than the minimum and, if so, re-size to the new minimum.

        :param dimensions: The new minimum dimension for the window.
        """
        self.minimum_dimensions = (min(self.ui_container.rect.width, int(dimensions[0])),
                                   min(self.ui_container.rect.height, int(dimensions[1])))

    def set_dimensions(self, dimensions: Union[pygame.math.Vector2, Tuple[int, int], Tuple[float, float]]):
        """
        Set the size of this window and then re-sizes and shifts the contents of the windows container to fit the new
        size.

        :param dimensions: The new dimensions to set.
        """
        # clamp to minimum dimensions and container size
        dimensions = (min(self.ui_container.rect.width, max(self.minimum_dimensions[0], int(dimensions[0]))),
                      min(self.ui_container.rect.height, max(self.minimum_dimensions[1], int(dimensions[1]))))

        # Don't use a basic gate on this set dimensions method because the container may be a different size to the
        # window
        super().set_dimensions(dimensions)

        if self._window_root_container is not None:
            new_container_dimensions = (self.relative_rect.width - (2 * self.shadow_width),
                                        self.relative_rect.height - (2 * self.shadow_width))
            if new_container_dimensions != self._window_root_container.relative_rect.size:
                self._window_root_container.set_dimensions(new_container_dimensions)
                self._window_root_container.set_relative_position((self.relative_rect.x + self.shadow_width,
                                                                   self.relative_rect.y + self.shadow_width))

    def set_relative_position(self, position: Union[pygame.math.Vector2, Tuple[int, int], Tuple[float, float]]):
        """
        Method to directly set the relative rect position of an element.

        :param position: The new position to set.
        """
        super().set_relative_position(position)

        if self._window_root_container is not None:
            self._window_root_container.set_relative_position((self.relative_rect.x + self.shadow_width,
                                                               self.relative_rect.y + self.shadow_width))

    def set_position(self, position: Union[pygame.math.Vector2, Tuple[int, int], Tuple[float, float]]):
        """
        Method to directly set the absolute screen rect position of an element.

        :param position: The new position to set.
        """
        super().set_position(position)

        if self._window_root_container is not None:
            self._window_root_container.set_relative_position((self.relative_rect.x + self.shadow_width,
                                                               self.relative_rect.y + self.shadow_width))

    def process_event(self, event: pygame.event.Event) -> bool:
        """
        Handles resizing & closing windows. Gives UI Windows access to pygame events. Derived windows should super()
        call this class if they implement their own process_event method.

        :param event: The event to process.

        :return bool: Return True if this element should consume this event and not pass it to the rest of the UI.
        """
        consumed_event = False

        if self.is_blocking and event.type == pygame.MOUSEBUTTONDOWN:
            consumed_event = True

        if self is not None and event.type == pygame.MOUSEBUTTONDOWN and event.button in [1, 3]:
            scaled_mouse_pos = (int(event.pos[0] * self.ui_manager.mouse_pos_scale_factor[0]),
                                int(event.pos[1] * self.ui_manager.mouse_pos_scale_factor[1]))

            if event.button == 1 and (self.edge_hovering[0] or self.edge_hovering[1] or
                                      self.edge_hovering[2] or self.edge_hovering[3]):
                self.resizing_mode_active = True
                self.start_resize_point = scaled_mouse_pos
                self.start_resize_rect = self.rect.copy()
                consumed_event = True
            elif self.hover_point(scaled_mouse_pos[0], scaled_mouse_pos[1]):
                consumed_event = True

        if self is not None and event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.resizing_mode_active:
            self.resizing_mode_active = False

        if (event.type == pygame.USEREVENT and event.user_type == UI_BUTTON_PRESSED
                and event.ui_element == self.close_window_button):
            self.kill()

        return consumed_event

    def check_clicked_inside_or_blocking(self, event: pygame.event.Event) -> bool:
        """
        A quick event check outside of the normal event processing so that this window is brought to the front of the
        window stack if we click on any of the elements contained within it.

        :param event: The event to check.

        :return bool: returns True if the event represents a click inside this window or the window is blocking.
        """
        consumed_event = False
        if self.is_blocking and event.type == pygame.MOUSEBUTTONDOWN:
            consumed_event = True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            scaled_mouse_pos = (int(event.pos[0] * self.ui_manager.mouse_pos_scale_factor[0]),
                                int(event.pos[1] * self.ui_manager.mouse_pos_scale_factor[1]))
            if self.hover_point(scaled_mouse_pos[0], scaled_mouse_pos[1]) or (self.edge_hovering[0] or
                                                                              self.edge_hovering[1] or
                                                                              self.edge_hovering[2] or
                                                                              self.edge_hovering[3]):
                if self.bring_to_front_on_focused:
                    self.window_stack.move_window_to_front(self)
                consumed_event = True

        return consumed_event

    def update(self, time_delta: float):
        """
        A method called every update cycle of our application. Designed to be overridden by derived classes
        but also has a little functionality to make sure the window's layer 'thickness' is accurate and to handle
        window resizing.

        :param time_delta: time passed in seconds between one call to this method and the next.
        """
        super().update(time_delta)
        if self._window_root_container.layer_thickness != self.layer_thickness:
            self.layer_thickness = self._window_root_container.layer_thickness

        if self.title_bar.held:
            mouse_x, mouse_y = self.ui_manager.get_mouse_position()
            if not self.grabbed_window:
                self.window_stack.move_window_to_front(self)
                self.grabbed_window = True
                self.starting_grab_difference = (mouse_x - self.rect.x,
                                                 mouse_y - self.rect.y)

            current_grab_difference = (mouse_x - self.rect.x,
                                       mouse_y - self.rect.y)

            adjustment_required = (current_grab_difference[0] - self.starting_grab_difference[0],
                                   current_grab_difference[1] - self.starting_grab_difference[1])

            self.set_relative_position((self.relative_rect.x + adjustment_required[0],
                                        self.relative_rect.y + adjustment_required[1]))
        else:
            self.grabbed_window = False

        if self.resizing_mode_active:

            x_pos = self.rect.left
            y_pos = self.rect.top

            x_dimension = self.rect.width
            y_dimension = self.rect.height

            mouse_x, mouse_y = self.ui_manager.get_mouse_position()
            x_diff = mouse_x - self.start_resize_point[0]
            y_diff = mouse_y - self.start_resize_point[1]

            if self.rect.height >= self.minimum_dimensions[1]:
                y_pos = self.start_resize_rect.y
                y_dimension = self.start_resize_rect.height
                if self.edge_hovering[1]:
                    y_dimension = self.start_resize_rect.height - y_diff
                    y_pos = self.start_resize_rect.y + y_diff
                elif self.edge_hovering[3]:
                    y_dimension = self.start_resize_rect.height + y_diff

                if y_dimension < self.minimum_dimensions[1]:
                    if y_diff > 0:
                        y_pos = self.rect.bottom - self.minimum_dimensions[1]
                    else:
                        y_pos = self.rect.top

            if self.rect.width >= self.minimum_dimensions[0]:
                x_pos = self.start_resize_rect.x
                x_dimension = self.start_resize_rect.width
                if self.edge_hovering[0]:
                    x_dimension = self.start_resize_rect.width - x_diff
                    x_pos = self.start_resize_rect.x + x_diff
                elif self.edge_hovering[2]:
                    x_dimension = self.start_resize_rect.width + x_diff

                if x_dimension < self.minimum_dimensions[0]:
                    if x_diff > 0:
                        x_pos = self.rect.right - self.minimum_dimensions[0]
                    else:
                        x_pos = self.rect.left

            x_dimension = max(self.minimum_dimensions[0], min(self.ui_container.rect.width, x_dimension))
            y_dimension = max(self.minimum_dimensions[1], min(self.ui_container.rect.height, y_dimension))

            self.set_position((x_pos, y_pos))
            self.set_dimensions((x_dimension, y_dimension))

    def get_container(self) -> UIContainer:
        """
        Returns the container that should contain all the UI elements in this window.

        :return UIContainer: The window's container.
        """
        return self.window_element_container

    # noinspection PyUnusedLocal
    def check_hover(self, time_delta: float, hovered_higher_element: bool) -> bool:
        """
        For the window the only hovering we care about is the edges if this is a resizable window.

        :param time_delta: time passed in seconds between one call to this method and the next.
        :param hovered_higher_element: Have we already hovered an element/window above this one.
        """
        hovered = False
        if not self.resizing_mode_active:
            self.edge_hovering = [False, False, False, False]
        if (self.alive() and self.can_hover() and self.resizable and
                not hovered_higher_element and not self.resizing_mode_active and not self.title_bar.held):
            mouse_x, mouse_y = self.ui_manager.get_mouse_position()
            mouse_pos = pygame.math.Vector2(mouse_x, mouse_y)

            # Build a temporary rect just a little bit larger than our container rect.
            resize_rect = pygame.Rect(self._window_root_container.rect.left - 4,
                                      self._window_root_container.rect.top - 4,
                                      self._window_root_container.rect.width + 8,
                                      self._window_root_container.rect.height + 8)
            if resize_rect.collidepoint(mouse_x, mouse_y):
                if resize_rect.right > mouse_x > resize_rect.right - 6:
                    self.edge_hovering[2] = True
                    hovered = True

                if resize_rect.left + 6 > mouse_x > resize_rect.left:
                    self.edge_hovering[0] = True
                    hovered = True

                if resize_rect.bottom > mouse_y > resize_rect.bottom - 6:
                    self.edge_hovering[3] = True
                    hovered = True

                if resize_rect.top + 6 > mouse_y > resize_rect.top:
                    self.edge_hovering[1] = True
                    hovered = True
        elif self.resizing_mode_active:
            hovered = True

        if self.is_blocking:
            hovered = True

        if hovered:
            hovered_higher_element = True
            self.hovered = True
        else:
            self.hovered = False

        return hovered_higher_element

    def get_top_layer(self) -> int:
        """
        Returns the 'highest' layer used by this window so that we can correctly place other windows on top of it.

        :return int: The top layer for this window as a number (greater numbers are higher layers).
        """
        return self._layer + self.layer_thickness

    def change_layer(self, new_layer: int):
        """
        Move this window, and it's contents, to a new layer in the UI.

        :param new_layer: The layer to move to.
        """
        if new_layer != self._layer:
            super().change_layer(new_layer)
            if self._window_root_container is not None:
                self._window_root_container.change_layer(new_layer)

    def kill(self):
        """
        Overrides the basic kill() method of a pygame sprite so that we also kill all the UI elements in this window,
        and remove if from the window stack.
        """
        window_close_event = pygame.event.Event(pygame.USEREVENT,
                                                {'user_type': UI_WINDOW_CLOSE,
                                                 'ui_element': self,
                                                 'ui_object_id': self.most_specific_combined_id})
        pygame.event.post(window_close_event)

        self.window_stack.remove_window(self)
        self._window_root_container.kill()
        super().kill()

    def rebuild(self):
        """
        Rebuilds the message window when the theme has changed.

        """
        theming_parameters = {'normal_bg': self.background_colour,
                              'normal_border': self.border_colour,
                              'border_width': self.border_width,
                              'shadow_width': self.shadow_width,
                              'shape_corner_radius': self.shape_corner_radius}

        if self.shape_type == 'rectangle':
            self.drawable_shape = RectDrawableShape(self.rect, theming_parameters,
                                                    ['normal'], self.ui_manager)
        elif self.shape_type == 'rounded_rectangle':
            self.drawable_shape = RoundedRectangleShape(self.rect, theming_parameters,
                                                        ['normal'], self.ui_manager)

        self.set_image(self.drawable_shape.get_surface('normal'))

        self.set_dimensions(self.relative_rect.size)

        if self.window_element_container is not None:
            element_container_width = self._window_root_container.relative_rect.width - (2 * self.border_width)
            element_container_height = self._window_root_container.relative_rect.height - self.title_bar_height
            self.window_element_container.set_dimensions((element_container_width, element_container_height))
            self.window_element_container.set_relative_position((self.border_width, self.title_bar_height))

            if self.enable_title_bar:
                if self.title_bar is not None:
                    self.title_bar.set_dimensions((self._window_root_container.relative_rect.width -
                                                   self.title_bar_button_width,
                                                   self.title_bar_height))
                else:
                    title_bar_width = self._window_root_container.relative_rect.width - self.title_bar_button_width
                    self.title_bar = UIButton(relative_rect=pygame.Rect(0, 0,
                                                                        title_bar_width,
                                                                        self.title_bar_height),
                                              text=self.window_display_title,
                                              manager=self.ui_manager,
                                              container=self._window_root_container,
                                              parent_element=self,
                                              object_id='#title_bar',
                                              anchors={'top': 'top', 'bottom': 'top',
                                                       'left': 'left', 'right': 'right'}
                                              )
                    self.title_bar.set_hold_range((100, 100))

                if self.enable_close_button:
                    if self.close_window_button is not None:
                        self.close_window_button.set_dimensions((self.title_bar_button_width,  self.title_bar_height))
                        self.close_window_button.set_relative_position((-self.title_bar_button_width, 0))
                    else:
                        self.close_window_button = UIButton(relative_rect=pygame.Rect((-self.title_bar_button_width, 0),
                                                                                      (self.title_bar_button_width,
                                                                                       self.title_bar_height)),
                                                            text='╳',
                                                            manager=self.ui_manager,
                                                            container=self._window_root_container,
                                                            parent_element=self,
                                                            object_id='#close_button',
                                                            anchors={'top': 'top', 'bottom': 'top',
                                                                     'left': 'right', 'right': 'right'}
                                                            )

                else:
                    if self.close_window_button is not None:
                        self.close_window_button.kill()
            else:
                if self.title_bar is not None:
                    self.title_bar.kill()
                if self.close_window_button is not None:
                    self.close_window_button.kill()

    def rebuild_from_changed_theme_data(self):
        """
        Called by the UIManager to check the theming data and rebuild whatever needs rebuilding for this element when
        the theme data has changed.
        """
        has_any_changed = False

        shape_type = 'rectangle'
        shape_type_string = self.ui_theme.get_misc_data(self.object_ids, self.element_ids, 'shape')
        if shape_type_string is not None and shape_type_string in ['rectangle', 'rounded_rectangle']:
            shape_type = shape_type_string
        if shape_type != self.shape_type:
            self.shape_type = shape_type
            has_any_changed = True

        corner_radius = 2
        shape_corner_radius_string = self.ui_theme.get_misc_data(self.object_ids,
                                                                 self.element_ids, 'shape_corner_radius')
        if shape_corner_radius_string is not None:
            try:
                corner_radius = int(shape_corner_radius_string)
            except ValueError:
                corner_radius = 2
        if corner_radius != self.shape_corner_radius:
            self.shape_corner_radius = corner_radius
            has_any_changed = True

        border_width = 1
        border_width_string = self.ui_theme.get_misc_data(self.object_ids, self.element_ids, 'border_width')
        if border_width_string is not None:
            try:
                border_width = int(border_width_string)
            except ValueError:
                border_width = 1

        if border_width != self.border_width:
            self.border_width = border_width
            has_any_changed = True

        shadow_width = 2
        shadow_width_string = self.ui_theme.get_misc_data(self.object_ids, self.element_ids, 'shadow_width')
        if shadow_width_string is not None:
            try:
                shadow_width = int(shadow_width_string)
            except ValueError:
                shadow_width = 2
        if shadow_width != self.shadow_width:
            self.shadow_width = shadow_width
            has_any_changed = True

        background_colour = self.ui_theme.get_colour_or_gradient(self.object_ids, self.element_ids, 'dark_bg')
        if background_colour != self.background_colour:
            self.background_colour = background_colour
            has_any_changed = True

        border_colour = self.ui_theme.get_colour_or_gradient(self.object_ids, self.element_ids, 'normal_border')
        if border_colour != self.border_colour:
            self.border_colour = border_colour
            has_any_changed = True

        enable_title_bar_param = self.ui_theme.get_misc_data(self.object_ids, self.element_ids, 'enable_title_bar')
        if enable_title_bar_param is not None:
            try:
                enable_title_bar = bool(int(enable_title_bar_param))
            except ValueError:
                enable_title_bar = True
            if enable_title_bar != self.enable_title_bar:
                self.enable_title_bar = enable_title_bar
                has_any_changed = True

        if self.enable_title_bar:

            enable_close_button_param = self.ui_theme.get_misc_data(self.object_ids, self.element_ids,
                                                                    'enable_close_button')
            if enable_close_button_param is not None:
                try:
                    enable_close_button = bool(int(enable_close_button_param))
                except ValueError:
                    enable_close_button = True
                if enable_close_button != self.enable_close_button:
                    self.enable_close_button = enable_close_button
                    has_any_changed = True

            title_bar_height_string = self.ui_theme.get_misc_data(self.object_ids, self.element_ids, 'title_bar_height')
            if title_bar_height_string is not None:
                try:
                    title_bar_height = int(title_bar_height_string)
                except ValueError:
                    title_bar_height = 28
                if title_bar_height != self.title_bar_height:
                    self.title_bar_height = title_bar_height
                    self.title_bar_button_width = title_bar_height
                    has_any_changed = True

        if has_any_changed:
            self.rebuild()
