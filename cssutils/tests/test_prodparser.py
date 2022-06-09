"""Testcases for cssutils.css.CSSCharsetRule"""

import sys
import re
import xml.dom
from . import basetest
from cssutils.prodparser import (
    Prod,
    Sequence,
    Choice,
    PreDef,
    ParseError,
    Exhausted,
    ProdParser,
)
import pytest


class TestProd(basetest.BaseTestCase):
    def test_init(self):
        "Prod.__init__(...)"
        p = Prod('min', lambda t, v: t == 1 and v == 2)

        assert str(p) == 'min'
        assert p.toStore is None
        assert p.optional is False

        p = Prod('optional', lambda t, v: True, optional=True)
        assert p.optional is True

    def test_initMatch(self):
        "Prod.__init__(...match=...)"
        p = Prod('min', lambda t, v: t == 1 and v == 2)
        assert p.match(1, 2) is True
        assert p.match(2, 2) is False
        assert p.match(1, 1) is False

    def test_initToSeq(self):
        "Prod.__init__(...toSeq=...)"
        # simply saves
        p = Prod('all', lambda t, tokens: True, toSeq=None)
        assert p.toSeq([1, 2], None) == (1, 2)  # simply saves
        assert p.toSeq(['s1', 's2'], None) == ('s1', 's2')  # simply saves

        # saves callback(val)
        p = Prod(
            'all', lambda t, v: True, toSeq=lambda t, tokens: (1 == t[0], 3 == t[1])
        )
        assert p.toSeq([1, 3], None) == (True, True)
        assert p.toSeq([2, 4], None) == (False, False)

    def test_initToStore(self):
        "Prod.__init__(...toStore=...)"
        p = Prod('all', lambda t, v: True, toStore='key')

        # save as key
        s = {}
        p.toStore(s, 1)
        assert s['key'] == 1

        # append to key
        s = {'key': []}
        p.toStore(s, 1)
        p.toStore(s, 2)
        assert s['key'] == [1, 2]

        # callback
        def doubleToStore(key):
            def toStore(store, item):
                store[key] = item * 2

            return toStore

        p = Prod('all', lambda t, v: True, toStore=doubleToStore('key'))
        s = {'key': []}
        p.toStore(s, 1)
        assert s['key'] == 2

    def test_matches(self):
        "Prod.matches(token)"
        p1 = Prod('p1', lambda t, v: t == 1 and v == 2)
        p2 = Prod('p2', lambda t, v: t == 1 and v == 2, optional=True)
        assert p1.matches([1, 2, 0, 0]) is True
        assert p2.matches([1, 2, 0, 0]) is True
        assert p1.matches([0, 0, 0, 0]) is False
        assert p2.matches([0, 0, 0, 0]) is False


class TestSequence(basetest.BaseTestCase):
    def test_init(self):
        "Sequence.__init__()"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2)
        seq = Sequence(p1, p2)

        assert 1 == seq._min
        assert 1 == seq._max

    def test_initminmax(self):
        "Sequence.__init__(...minmax=...)"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2)

        s = Sequence(p1, p2, minmax=lambda: (2, 3))
        assert 2 == s._min
        assert 3 == s._max

        s = Sequence(p1, p2, minmax=lambda: (0, None))
        assert 0 == s._min

        try:
            # py2.6/3
            m = sys.maxsize
        except AttributeError:
            # py<1.6
            m = sys.maxsize
        assert m == s._max

    def test_optional(self):
        "Sequence.optional"
        p1 = Prod('p1', lambda t, v: t == 1)

        s = Sequence(p1, minmax=lambda: (1, 3))
        assert not s.optional
        s = Sequence(p1, minmax=lambda: (0, 3))
        assert s.optional
        s = Sequence(p1, minmax=lambda: (0, None))
        assert s.optional

    def test_reset(self):
        "Sequence.reset()"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2)
        seq = Sequence(p1, p2)
        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)
        assert p1 == seq.nextProd(t1)
        assert p2 == seq.nextProd(t2)
        with pytest.raises(Exhausted):
            seq.nextProd(t1)
        seq.reset()
        assert p1 == seq.nextProd(t1)

    def test_matches(self):
        "Sequence.matches()"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2, optional=True)

        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)
        t3 = (3, 0, 0, 0)

        s = Sequence(p1, p2)
        assert s.matches(t1)
        assert not s.matches(t2)

        s = Sequence(p2, p1)
        assert s.matches(t1)
        assert s.matches(t2)

        s = Sequence(Choice(p1, p2))
        assert s.matches(t1)
        assert s.matches(t2)
        assert not s.matches(t3)

    def test_nextProd(self):
        "Sequence.nextProd()"
        p1 = Prod('p1', lambda t, v: t == 1, optional=True)
        p2 = Prod('p2', lambda t, v: t == 2)
        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)

        tests = {
            # seq: list of list of (token, prod or error msg)
            (p1,): (
                [(t1, p1)],
                [(t2, 'Extra token')],  # as p1 optional
                [(t1, p1), (t1, 'Extra token')],
                [(t1, p1), (t2, 'Extra token')],
            ),
            (p2,): (
                [(t2, p2)],
                [(t2, p2), (t2, 'Extra token')],
                [(t2, p2), (t1, 'Extra token')],
                [(t1, 'Missing token for production p2')],
            ),
            (p1, p2): (
                [(t1, p1), (t2, p2)],
                [(t1, p1), (t1, 'Missing token for production p2')],
            ),
        }
        for seqitems, results in list(tests.items()):
            for result in results:
                seq = Sequence(*seqitems)
                for t, p in result:
                    if isinstance(p, str):
                        with pytest.raises(ParseError, match=p):
                            seq.nextProd(t)
                    else:
                        assert p == seq.nextProd(t)

        tests = {
            # seq: list of list of (token, prod or error msg)
            # as p1 optional!
            (p1, p1): (
                [(t1, p1)],
                [(t1, p1), (t1, p1)],
                [(t1, p1), (t1, p1)],
                [(t1, p1), (t1, p1), (t1, p1)],
                [(t1, p1), (t1, p1), (t1, p1), (t1, p1)],
                [(t1, p1), (t1, p1), (t1, p1), (t1, p1), (t1, 'Extra token')],
            ),
            (p1,): (
                [(t1, p1)],
                [(t2, 'Extra token')],
                [(t1, p1), (t1, p1)],
                [(t1, p1), (t2, 'Extra token')],
                [(t1, p1), (t1, p1), (t1, 'Extra token')],
                [(t1, p1), (t1, p1), (t2, 'Extra token')],
            ),
            # as p2 NOT optional
            (p2,): (
                [(t2, p2)],
                [(t1, 'Missing token for production p2')],
                [(t2, p2), (t2, p2)],
                [(t2, p2), (t1, 'No match for (1, 0, 0, 0) in Sequence(p2)')],
                [(t2, p2), (t2, p2), (t2, 'Extra token')],
                [(t2, p2), (t2, p2), (t1, 'Extra token')],
            ),
            (p1, p2): (
                [(t1, p1), (t1, 'Missing token for production p2')],
                [(t2, p2), (t2, p2)],
                [(t2, p2), (t1, p1), (t2, p2)],
                [(t1, p1), (t2, p2), (t2, p2)],
                [(t1, p1), (t2, p2), (t1, p1), (t2, p2)],
                [(t2, p2), (t2, p2), (t2, 'Extra token')],
                [(t2, p2), (t1, p1), (t2, p2), (t1, 'Extra token')],
                [(t2, p2), (t1, p1), (t2, p2), (t2, 'Extra token')],
                [(t1, p1), (t2, p2), (t2, p2), (t1, 'Extra token')],
                [(t1, p1), (t2, p2), (t2, p2), (t2, 'Extra token')],
                [(t1, p1), (t2, p2), (t1, p1), (t2, p2), (t1, 'Extra token')],
                [(t1, p1), (t2, p2), (t1, p1), (t2, p2), (t2, 'Extra token')],
            ),
        }
        for seqitems, results in list(tests.items()):
            for result in results:
                seq = Sequence(minmax=lambda: (1, 2), *seqitems)
                for t, p in result:
                    if isinstance(p, str):
                        with pytest.raises(ParseError, match=re.escape(p)):
                            seq.nextProd(t)
                    else:
                        assert p == seq.nextProd(t)


class TestChoice(basetest.BaseTestCase):
    def test_init(self):
        "Choice.__init__()"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2)
        t0 = (0, 0, 0, 0)
        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)

        ch = Choice(p1, p2)
        with pytest.raises(
            ParseError, match=re.escape('No match for (0, 0, 0, 0) in Choice(p1, p2)')
        ):
            ch.nextProd(t0)
        assert p1 == ch.nextProd(t1)
        with pytest.raises(Exhausted, match='Extra token'):
            ch.nextProd(t1)

        ch = Choice(p1, p2)
        assert p2 == ch.nextProd(t2)
        with pytest.raises(Exhausted, match='Extra token'):
            ch.nextProd(t2)

        ch = Choice(p2, p1)
        with pytest.raises(
            ParseError, match=re.escape('No match for (0, 0, 0, 0) in Choice(p2, p1)')
        ):
            ch.nextProd(t0)
        assert p1 == ch.nextProd(t1)
        with pytest.raises(Exhausted, match='Extra token'):
            ch.nextProd(t1)

        ch = Choice(p2, p1)
        assert p2 == ch.nextProd(t2)
        with pytest.raises(Exhausted, match='Extra token'):
            ch.nextProd(t2)

    def test_matches(self):
        "Choice.matches()"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2, optional=True)

        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)
        t3 = (3, 0, 0, 0)

        c = Choice(p1, p2)
        assert c.matches(t1)
        assert c.matches(t2)
        assert not c.matches(t3)

        c = Choice(Sequence(p1), Sequence(p2))
        assert c.matches(t1)
        assert c.matches(t2)
        assert not c.matches(t3)

    def test_nested(self):
        "Choice with nested Sequence"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2)
        s1 = Sequence(p1, p1)
        s2 = Sequence(p2, p2)
        t0 = (0, 0, 0, 0)
        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)

        ch = Choice(s1, s2)
        expected = (
            'No match for (0, 0, 0, 0) in Choice(Sequence(p1, p1), Sequence(p2, p2))'
        )
        with pytest.raises(ParseError, match=re.escape(expected)):
            ch.nextProd(t0)
        assert s1 == ch.nextProd(t1)
        with pytest.raises(Exhausted, match='Extra token'):
            ch.nextProd(t1)

        ch = Choice(s1, s2)
        assert s2 == ch.nextProd(t2)
        with pytest.raises(Exhausted, match='Extra token'):
            ch.nextProd(t1)

    def test_reset(self):
        "Choice.reset()"
        p1 = Prod('p1', lambda t, v: t == 1)
        p2 = Prod('p2', lambda t, v: t == 2)
        t1 = (1, 0, 0, 0)
        t2 = (2, 0, 0, 0)

        ch = Choice(p1, p2)
        assert p1 == ch.nextProd(t1)
        with pytest.raises(Exhausted):
            ch.nextProd(t1)
        ch.reset()
        assert p2 == ch.nextProd(t2)


class TestProdParser(basetest.BaseTestCase):
    def setup(self):
        pass

    def test_parse_keepS(self):
        "ProdParser.parse(keepS)"
        p = ProdParser()

        # text, name, productions, store=None
        def prods():
            return Sequence(PreDef.char(';', ';'), PreDef.char(':', ':'))

        w, seq, store, unused = p.parse('; :', 'test', prods(), keepS=True)
        assert w
        assert 3 == len(seq)

        w, seq, store, unused = p.parse('; :', 'test', prods(), keepS=False)
        assert w
        assert 2 == len(seq)

    def test_combi(self):
        "ProdParser.parse() 2"
        p1 = Prod('p1', lambda t, v: v == '1')
        p2 = Prod('p2', lambda t, v: v == '2')
        p3 = Prod('p3', lambda t, v: v == '3')

        tests = {
            '1 2': True,
            '1 2 1 2': True,
            '3': True,
            # '': 'No match in Choice(Sequence(p1, p2), p3)',
            '1': 'Missing token for production p2',
            '1 2 1': 'Missing token for production p2',
            '1 2 1 2 x': "No match: ('IDENT', 'x', 1, 9)",
            '1 2 1 2 1': "No match: ('NUMBER', '1', 1, 9)",
            '3 x': "No match: ('IDENT', 'x', 1, 3)",
            '3 3': "No match: ('NUMBER', '3', 1, 3)",
        }
        for text, exp in list(tests.items()):
            prods = Choice(Sequence(p1, p2, minmax=lambda: (1, 2)), p3)
            if exp is True:
                wellformed, seq, store, unused = ProdParser().parse(text, 'T', prods)
                assert wellformed == exp
            else:
                with pytest.raises(xml.dom.SyntaxErr, match=re.escape(f'T: {exp}')):
                    ProdParser().parse(
                        text,
                        'T',
                        prods,
                    )

        tests = {
            '1 3': True,
            '1 1 3': True,
            '2 3': True,
            '1': 'Missing token for production p3',
            '1 1': 'Missing token for production p3',
            '1 3 3': "No match: ('NUMBER', '3', 1, 5)",
            '1 1 3 3': "No match: ('NUMBER', '3', 1, 7)",
            '2 3 3': "No match: ('NUMBER', '3', 1, 5)",
            '2': 'Missing token for production p3',
            '3': "Missing token for production Choice(Sequence(p1), p2): "
            "('NUMBER', '3', 1, 1)",
        }
        for text, exp in list(tests.items()):
            prods = Sequence(Choice(Sequence(p1, minmax=lambda: (1, 2)), p2), p3)
            if exp is True:
                wellformed, seq, store, unused = ProdParser().parse(text, 'T', prods)
                assert wellformed == exp
            else:
                with pytest.raises(xml.dom.SyntaxErr, match=re.escape(f'T: {exp}')):
                    ProdParser().parse(
                        text,
                        'T',
                        prods,
                    )
