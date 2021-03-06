import unittest
from stig.tui.keymap import (Key, KeyChain, KeyMap)
from urwid import Text

import logging
log = logging.getLogger(__name__)


class TestKey(unittest.TestCase):
    def test_compare_Key_with_Key(self):
        self.assertEqual(Key('alt-l'), Key('Alt-l'))
        self.assertEqual(Key('alt-l'), Key('meta-l'))
        self.assertEqual(Key('alt-l'), Key('Meta-l'))
        self.assertEqual(Key('alt-l'), Key('<alt-l>'))
        self.assertNotEqual(Key('alt-l'), Key('alt-L'))

        self.assertEqual(Key('ctrl-e'), Key('Ctrl-e'))
        self.assertEqual(Key('ctrl-e'), Key('<ctrl-e>'))
        self.assertEqual(Key('ctrl-e'), Key('CTRL-e'))
        self.assertEqual(Key('ctrl-e'), Key('ctrl-E'))

        self.assertEqual(Key('space'), Key(' '))
        self.assertEqual(Key('escape'), Key('esc'))
        self.assertEqual(Key('home'), Key('pos1'))
        self.assertEqual(Key('delete'), Key('del'))
        self.assertEqual(Key('enter'), Key('return'))
        self.assertEqual(Key('insert'), Key('ins'))

        self.assertEqual(Key('alt-insert'), Key('meta-ins'))
        self.assertEqual(Key('alt-del'), Key('meta-delete'))
        self.assertEqual(Key('shift-ctrl-enter'), Key('shift-Ctrl-RETURN'))

    def test_convert_shift_modifier(self):
        self.assertEqual(Key('shift-E'), Key('E'))
        self.assertEqual(Key('shift-e'), Key('E'))
        self.assertEqual(Key('shift-ö'), Key('Ö'))
        self.assertEqual(Key('shift-alt-ö'), Key('alt-Ö'))
        self.assertEqual(Key('ctrl-shift-alt-ö'), Key('ctrl-alt-Ö'))

    def test_invalid_modifier(self):
        with self.assertRaises(ValueError) as cm:
            Key('shit-e')
        self.assertIn('Invalid modifier', str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            Key('alt-')
        self.assertIn('Missing key', str(cm.exception))

    def test_invalid_key(self):
        with self.assertRaises(ValueError) as cm:
            Key('hello')
        self.assertIn('Unknown key', str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            Key('alt-hello')
        self.assertIn('Unknown key', str(cm.exception))


class TestKeyChain(unittest.TestCase):
    def test_advance(self):
        kc = KeyChain('a', 'b', 'c')
        for _ in range(10):
            self.assertEqual(kc.given, ())
            kc.advance()
            self.assertEqual(kc.given, ('a',))
            kc.advance()
            self.assertEqual(kc.given, ('a', 'b'))
            kc.advance()
            self.assertEqual(kc.given, ('a', 'b', 'c'))
            kc.advance()

    def test_reset(self):
        kc = KeyChain('a', 'b', 'c')
        for i in range(10):
            for _ in range(i): kc.advance()
            kc.reset()
            self.assertEqual(kc.given, ())

    def test_next_key(self):
        kc = KeyChain('a', 'b', 'c')
        for i in range(10):
            self.assertEqual(kc.next_key, 'a')
            kc.advance()
            self.assertEqual(kc.next_key, 'b')
            kc.advance()
            self.assertEqual(kc.next_key, 'c')
            kc.advance()
            self.assertEqual(kc.next_key, None)  # chain is complete
            kc.advance()  # same as reset() if complete

    def test_startswith(self):
        kc = KeyChain('a', 'b', 'c')
        self.assertEqual(kc.startswith(('a',)), True)
        self.assertEqual(kc.startswith(('a', 'b')), True)
        self.assertEqual(kc.startswith(('a', 'b', 'c')), True)
        self.assertEqual(kc.startswith(('a', 'b', 'c', 'x')), False)
        self.assertEqual(kc.startswith(('a', 'b', 'x')), False)
        self.assertEqual(kc.startswith(('a', 'x')), False)
        self.assertEqual(kc.startswith(('x')), False)
        self.assertEqual(kc.startswith(()), True)

    def test_is_complete(self):
        kc = KeyChain('a', 'b', 'c')
        for i in range(10):
            self.assertEqual(kc.is_complete, False)
            kc.advance()
            self.assertEqual(kc.is_complete, False)
            kc.advance()
            self.assertEqual(kc.is_complete, False)
            kc.advance()
            self.assertEqual(kc.is_complete, True)
            kc.advance()

    def test_feed_with_correct_chain(self):
        kc = KeyChain('a', 'b', 'c')
        self.assertEqual(kc.feed('a'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('b'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('c'), KeyChain.COMPLETED)

    def test_feed_with_wrong_chain(self):
        kc = KeyChain('a', 'b', 'c')
        self.assertEqual(kc.feed('x'), KeyChain.REFUSED)

        self.assertEqual(kc.feed('a'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('x'), KeyChain.ABORTED)

        self.assertEqual(kc.feed('a'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('b'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('x'), KeyChain.ABORTED)


class TestKeyMap(unittest.TestCase):
    def test_mkkey(self):
        km = KeyMap()
        self.assertEqual(km.mkkey(Key('x')), Key('x'))
        self.assertEqual(km.mkkey(KeyChain('1', '2', '3')),
                                  KeyChain('1', '2', '3'))

        self.assertEqual(km.mkkey('x'), Key('x'))
        self.assertEqual(km.mkkey('x y z'), KeyChain('x', 'y', 'z'))
        self.assertEqual(km.mkkey('x+y+z'), KeyChain('x', 'y', 'z'))
        self.assertEqual(km.mkkey('x +'), KeyChain('x', '+'))
        self.assertEqual(km.mkkey('+ x'), KeyChain('+', 'x'))
        self.assertEqual(km.mkkey('x y +'), KeyChain('x', 'y', '+'))
        self.assertEqual(km.mkkey('+ y z'), KeyChain('+', 'y', 'z'))
        self.assertEqual(km.mkkey('+ + +'), KeyChain('+', '+', '+'))

    def test_action_is_callback(self):
        km = KeyMap()
        km.bind(key='a',
                action=lambda widget: widget.set_text('foo'))
        widget = km.wrap(Text)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'foo')

    def test_widget_callback(self):
        def cb(action, widget):
            widget.set_text(action)

        km = KeyMap()
        km.bind(key='a', action='foo')
        widget = km.wrap(Text, callback=cb)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'foo')

    def test_default_callback(self):
        def cb(action, widget):
            widget.set_text(action)

        km = KeyMap(callback=cb)
        km.bind(key='a', action='foo')
        widget = km.wrap(Text)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'foo')

    def test_widget_callback_overrides_default_callback(self):
        def default_cb(action, widget):
            widget.set_text(action)

        def widget_cb(action, widget):
            widget.set_text(action.upper())

        km = KeyMap(callback=default_cb)
        km.bind(key='a', action='foo')
        widget = km.wrap(Text, callback=widget_cb)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'FOO')

    def test_key_translation(self):
        km = KeyMap()
        km.bind(key='a',
                action=lambda widget: widget.set_text('Key pressed: a'))
        km.bind(key='b', action=Key('a'))
        widget = km.wrap(Text)('Test Text')
        widget.keypress((80,), 'b')
        self.assertEqual(widget.text, 'Key pressed: a')


class TestKeyMap_with_key_chains(unittest.TestCase):
    def setUp(self):
        self.km = KeyMap(callback=self.handle_action)
        self.widget = self.km.wrap(Text)('Test Text')
        self.widgetA = self.km.wrap(Text, context='A')('Test Text A')
        self.widgetB = self.km.wrap(Text, context='B')('Test Text B')
        self._action_counter = 0

    def handle_action(self, action, widget):
        self._action_counter += 1
        widget.set_text('%s%d' % (str(action), self._action_counter))

    def status(self):
        return (self.widget.text, self.widgetA.text, self.widgetB.text)

    def test_correct_chain(self):
        self.km.bind('1 2 3', 'foo')
        self.widget.keypress((80,), '1')
        self.assertEqual(self.widget.text, 'Test Text')
        self.widget.keypress((80,), '2')
        self.assertEqual(self.widget.text, 'Test Text')
        self.widget.keypress((80,), '3')
        self.assertEqual(self.widget.text, 'foo1')

    def test_incorrect_chain_then_correct_chain(self):
        self.km.bind('1 2 3', 'foo')
        self.widget.keypress((80,), '1')
        self.assertEqual(self.widget.text, 'Test Text')
        self.widget.keypress((80,), '2')
        self.assertEqual(self.widget.text, 'Test Text')
        self.widget.keypress((80,), 'x')
        self.assertEqual(self.widget.text, 'Test Text')
        self.widget.keypress((80,), '3')
        self.assertEqual(self.widget.text, 'Test Text')
        for c in ('1', '2', '3'):
            self.widget.keypress((80,), c)
        self.assertEqual(self.widget.text, 'foo1')

    def test_abort_with_bound_key_does_nothing(self):
        self.km.bind('1 2 3', 'foo')
        self.km.bind('x', 'bar')
        for c in ('1', '2', 'x', '3'):
            self.widget.keypress((80,), c)
        self.assertEqual(self.widget.text, 'Test Text')
        self.widget.keypress((80,), 'x')
        self.assertEqual(self.widget.text, 'bar1')

    def test_competing_chains_in_default_context(self):
        self.km.bind('1 2 3', 'foo')
        self.km.bind('1 2 0', 'bar')
        for c in ('1', '2', '3'):
            self.widget.keypress((80,), c)
        self.assertEqual(self.widget.text, 'foo1')
        for c in ('1', '2', '0'):
            self.widget.keypress((80,), c)
        self.assertEqual(self.widget.text, 'bar2')

    def test_competing_chains_in_default_context_with_different_lengths(self):
        self.km.bind('1 2 3', 'foo')
        self.km.bind('1 2 3 4', 'bar')
        for c in ('1', '2', '3'):
            self.widget.keypress((80,), c)
        self.assertEqual(self.widget.text, 'foo1')
        for c in ('1', '2', '3'):
            self.widget.keypress((80,), c)
        self.assertEqual(self.widget.text, 'foo2')
        self.widget.keypress((80,), '4')
        self.assertEqual(self.widget.text, 'foo2')

    def test_correct_contexts(self):
        self.km.bind('1 2 3', 'foo', context='A')
        self.km.bind('a b c', 'bar', context='B')
        for c in ('1', '2', '3'):
            self.widgetA.keypress((80,), c)
        self.assertEqual(self.widgetA.text, 'foo1')
        for c in ('a', 'b', 'c'):
            self.widgetB.keypress((80,), c)
        self.assertEqual(self.widgetB.text, 'bar2')
        self.assertEqual(self.widgetA.text, 'foo1')

    def test_wrong_contexts(self):
        self.km.bind('1 2 3', 'foo', context='A')
        self.km.bind('a b c', 'bar', context='B')
        before = self.status()
        for c in ('a', 'b', 'c'):
            self.widgetA.keypress((80,), c)
        self.assertEqual(before, self.status())
        for c in ('1', '2', '3'):
            self.widgetB.keypress((80,), c)
        self.assertEqual(before, self.status())

    def test_starting_one_chain_prevents_other_chains(self):
        self.km.bind('1 2 3', 'foo', context='A')
        self.km.bind('a b c', 'bar', context='B')
        before = self.status()
        self.widgetA.keypress((80,), '1')
        # Even though the 'a b c' is sent to the correct widget, the 'a' is
        # used up to abort the previously started '1 2 3' chain.
        for c in ('a', 'b', 'c'):
            self.widgetB.keypress((80,), c)
        self.assertEqual(before, self.status())
