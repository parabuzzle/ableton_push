#Embedded file name: /Users/versonator/Jenkins/live/Projects/AppLive/Resources/MIDI Remote Scripts/Push/MessageBoxComponent.py
from functools import partial
from _Framework.Dependency import dependency
from _Framework.CompoundComponent import CompoundComponent
from _Framework.DisplayDataSource import DisplayDataSource
from _Framework.SubjectSlot import subject_slot
from _Framework.Util import forward_property, const, nop
from _Framework import Task
from _Framework.ControlElement import ControlElement
from _Framework.Layer import Layer
from BackgroundComponent import BackgroundComponent
from consts import MessageBoxText, DISPLAY_LENGTH
import consts
from _Framework.CompoundElement import CompoundElement

class Messenger(object):
    """
    Externally provided interface for those components that provide
    global Push feedback.
    """
    expect_dialog = dependency(expect_dialog=const(nop))
    show_notification = dependency(show_notification=const(nop))


class MessageBoxComponent(BackgroundComponent):
    """
    Component showing a temporary message in the display
    """
    __subject_events__ = ('cancel',)
    _cancel_button_index = 7
    num_lines = 4

    def __init__(self, *a, **k):
        super(MessageBoxComponent, self).__init__(*a, **k)
        self._current_text = None
        self._can_cancel = False
        self._top_row_buttons = None
        self.data_sources = map(DisplayDataSource, ('',) * self.num_lines)
        self._notification_display = None

    @property
    def can_cancel(self):
        return self._can_cancel

    def _set_display_line(self, n, display_line):
        if display_line:
            display_line.set_data_sources((self.data_sources[n],))

    def set_display_line1(self, display_line):
        self._set_display_line(0, display_line)

    def set_display_line2(self, display_line):
        self._set_display_line(1, display_line)

    def set_display_line3(self, display_line):
        self._set_display_line(2, display_line)

    def set_display_line4(self, display_line):
        self._set_display_line(3, display_line)

    def set_top_buttons(self, buttons):
        self._top_row_buttons = buttons
        if buttons:
            buttons.reset()
        self.set_cancel_button(buttons[self._cancel_button_index] if buttons else None)

    def set_cancel_button(self, button):
        self._on_cancel_button_value.subject = button
        self._update_cancel_button()

    def _update_cancel_button(self):
        if self.is_enabled():
            button = self._on_cancel_button_value.subject
            if self._top_row_buttons:
                self._top_row_buttons.reset()
            if self._can_cancel and button:
                button.set_light('MessageBox.Cancel')

    def _update_display(self):
        if self._current_text != None:
            lines = self._current_text.split('\n')
            for source_line, line in map(None, self.data_sources, lines):
                if source_line:
                    source_line.set_display_string(line or '')

            if self._can_cancel:
                self.data_sources[-1].set_display_string('[  Ok  ]'.rjust(DISPLAY_LENGTH - 1))

    @subject_slot('value')
    def _on_cancel_button_value(self, value):
        if self.is_enabled() and self._can_cancel and value:
            self.notify_cancel()

    def _get_text(self):
        return self._current_text

    def _set_text(self, text):
        self._current_text = text
        self._update_display()

    text = property(_get_text, _set_text)

    def _get_can_cancel(self):
        return self._can_cancel

    def _set_can_cancel(self, can_cancel):
        self._can_cancel = can_cancel
        self._update_cancel_button()
        self._update_display()

    can_cancel = property(_get_can_cancel, _set_can_cancel)

    def update(self):
        self._update_cancel_button()
        self._update_display()


class _CallbackControl(CompoundElement):

    def __init__(self, token = None, callback = None, *a, **k):
        super(_CallbackControl, self).__init__(*a, **k)
        self._callback = callback
        self.register_control_element(token)

    def on_nested_control_element_grabbed(self, control):
        self._callback()

    def on_nested_control_element_released(self, control):
        pass


class _TokenControlElement(ControlElement):

    def reset(self):
        pass


class NotificationComponent(CompoundComponent):
    """
    Displays notifications to the user for a given amount of time.
    
    To adjust the way notifications are shown in special cases, assign a generated
    control using use_single_line or use_full_display to a layer. If the layer is on
    top, it will set the preferred view.
    This will show the notification on line 1 if my_component is enabled and
    the priority premise of the layer is met:
    
        my_component.layer = Layer(
            _notification = notification_component.use_single_line(1))
    """

    def __init__(self, notification_time = 2.5, blinking_time = 0.3, display_lines = [], *a, **k):
        super(NotificationComponent, self).__init__(*a, **k)
        self._display_lines = display_lines
        self._token_control = _TokenControlElement()
        self._message_box = self.register_component(MessageBoxComponent())
        self._message_box.set_enabled(False)
        self._notification_timeout_task = self._tasks.add(Task.sequence(Task.wait(notification_time), Task.run(self.hide_notification))).kill()
        self._blink_text_task = self._tasks.add(Task.loop(Task.sequence(Task.run(lambda : self._message_box.__setattr__('text', self._original_text)), Task.wait(blinking_time), Task.run(lambda : self._message_box.__setattr__('text', self._blink_text)), Task.wait(blinking_time)))).kill()
        self._original_text = None
        self._blink_text = None

    message_box_layer = forward_property('_message_box')('layer')

    def show_notification(self, text, blink_text = None):
        """
        Triggers a notification with the given text.
        """
        if blink_text is not None:
            self._original_text = text
            self._blink_text = blink_text
            self._blink_text_task.restart()
        self._message_box.text = text
        self._message_box.set_enabled(True)
        self._notification_timeout_task.restart()

    def hide_notification(self):
        """
        Hides the current notification, if any existing.
        """
        self._blink_text_task.kill()
        self._message_box.set_enabled(False)

    def use_single_line(self, line_index):
        """
        Returns a control, that will change the notification to a single line view,
        if it is grabbed.
        """
        return _CallbackControl(self._token_control, partial(self._set_single_line, line_index))

    def use_full_display(self, message_line_index = 2):
        """
        Returns a control, that will change the notification to use the whole display,
        if it is grabbed.
        """
        return _CallbackControl(self._token_control, partial(self._set_full_display, message_line_index=message_line_index))

    def _set_single_line(self, line_index):
        raise line_index >= 0 and line_index < len(self._display_lines) or AssertionError
        layer = Layer(**{'display_line1': self._display_lines[line_index]})
        layer.priority = consts.MESSAGE_BOX_PRIORITY
        self._message_box.layer = layer

    def _set_full_display(self, message_line_index = 2):
        layer = Layer(**dict([ ('display_line1' if i == message_line_index else 'bg%d' % i, line) for i, line in enumerate(self._display_lines) ]))
        layer.priority = consts.MESSAGE_BOX_PRIORITY
        self._message_box.layer = layer

    def update(self):
        pass


class DialogComponent(CompoundComponent):
    """
    Handles representing modal dialogs from the application.  The
    script can also request dialogs.
    """

    def __init__(self, *a, **k):
        super(DialogComponent, self).__init__(*a, **k)
        self._message_box = self.register_component(MessageBoxComponent())
        self._message_box.set_enabled(False)
        self._next_message = None
        self._on_open_dialog_count.subject = self.application()
        self._on_message_cancel.subject = self._message_box

    message_box_layer = forward_property('_message_box')('layer')

    def expect_dialog(self, message):
        """
        Expects a dialog from Live to appear soon.  The dialog will be
        shown on the controller with the given message regardless of
        wether a dialog actually appears.  This dialog can be
        cancelled.
        """
        self._next_message = message
        self._update_dialog()

    @subject_slot('open_dialog_count')
    def _on_open_dialog_count(self):
        self._update_dialog(open_dialog_changed=True)
        self._next_message = None

    @subject_slot('cancel')
    def _on_message_cancel(self):
        self._next_message = None
        try:
            self.application().press_current_dialog_button(0)
        except RuntimeError:
            pass

        self._update_dialog()

    def _update_dialog(self, open_dialog_changed = False):
        message = self._next_message or MessageBoxText.LIVE_DIALOG
        can_cancel = self._next_message != None
        self._message_box.text = message
        self._message_box.can_cancel = can_cancel
        self._message_box.set_enabled(self.application().open_dialog_count > 0 or not open_dialog_changed and self._next_message)

    def update(self):
        pass