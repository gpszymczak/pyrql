# -*- coding: utf-8 -*-

import datetime

import pytest

from pyrql import parser as pm
from pyrql.unparser import unparser


parser = pm.parser

CMP_OPS = ['eq', 'lt', 'le', 'gt', 'ge', 'ne']


class TestTokens:

    @pytest.mark.parametrize('exre', [('%20', ' ')])
    def test_PCT_ENCODED(self, exre):
        expr, rep = exre
        pd = pm.PCT_ENCODED.parseString(expr)
        assert pd[0] == rep

    @pytest.mark.parametrize('exre', [('%20', ' '), ('a', 'a'), ('1', '1')])
    def test_NCHAR(self, exre):
        expr, rep = exre
        pd = pm.NCHAR.parseString(expr)
        assert pd[0] == rep

    @pytest.mark.parametrize('exre', [('a%20b', 'a b'), ('abc', 'abc'), ('123', '123')])
    def test_NAME(self, exre):
        expr, rep = exre
        pd = pm.NAME.parseString(expr)
        assert pd[0] == rep

    @pytest.mark.parametrize(
        'exre',
        [('string:3', '3'),
         ('number:3', 3),
         ('date:2017-01-01', datetime.date(2017, 1, 1)),
         ('datetime:2017-01-01T22:04:23', datetime.datetime(2017, 1, 1, 22, 4, 23)),
         ('boolean:true', True),
         ('boolean:false', False),
         ])
    def test_TYPED_VALUE(self, exre):
        expr, rep = exre

        pd = pm.TYPED_VALUE.parseString(expr)
        assert pd[0] == rep

    @pytest.mark.parametrize(
        'exre',
        [('123', '123'),
         ('number:123', 123),
         ('date:2017-01-01', datetime.date(2017, 1, 1)),
         ])
    def test_VALUE(self, exre):
        expr, rep = exre

        pd = pm.VALUE.parseString(expr)
        assert pd[0] == rep

    @pytest.mark.parametrize(
        'exre',
        [('(123,number:123,date:2017-01-01)', ('123', 123, datetime.date(2017, 1, 1))),
         ('(1,(2, 3, (4, 5)))', ('1', ('2', '3', ('4', '5')))),
         ])
    def test_ARRAY(self, exre):
        expr, rep = exre

        pd = pm.ARRAY.parseString(expr)
        assert pd[0] == rep

    @pytest.mark.parametrize(
        'pair',
        [('a()', []),
         ('a(1)', ['1']),
         ('a(x,(y,z))', ['x', ('y', 'z')]),
         ('a(number:1,string:2)', [1, '2']),
         ('a(date:2017-01-01)', [datetime.date(2017, 1, 1)])
         ])
    def test_CALL_OPERATOR(self, pair):
        expr, args = pair

        pd = pm.CALL_OPERATOR.parseString(expr)
        assert pd[0] == {'name': 'a', 'args': args}

    def test_nested_CALL_OPERATOR(self):
        expr = 'a(1,b(2),3)'

        pd = pm.CALL_OPERATOR.parseString(expr)
        assert pd[0] == {'name': 'a', 'args': ['1', {'name': 'b', 'args': ['2']}, '3']}

    @pytest.mark.parametrize(
        'pair',
        [('a=1', ['a', '1']), ('a=xyz', ['a', 'xyz']), ('a=string:1', ['a', '1']),
         ('a=date:2017-01-01', ['a', datetime.date(2017, 1, 1)])])
    def test_call_eq_expressions(self, pair):
        expr, args = pair

        pd = pm.COMPARISON.parseString(expr)
        assert pd[0] == {'name': 'eq', 'args': args}

    @pytest.mark.parametrize('op', CMP_OPS)
    @pytest.mark.parametrize(
        'pair',
        [('a=%s=1', ['a', '1']), ('a=%s=xyz', ['a', 'xyz']), ('a=%s=string:1', ['a', '1']),
         ('a=%s=date:2017-01-01', ['a', datetime.date(2017, 1, 1)])])
    def test_call_fiql_expression(self, op, pair):
        expr, args = pair

        pd = pm.COMPARISON.parseString(expr % op)
        assert pd[0] == {'name': op, 'args': args}

    @pytest.mark.parametrize(
        'pair',
        [('a()', []),
         ('a(1)', ['1']),
         ('a(x,(y,z))', ['x', ('y', 'z')]),
         ('a(number:1,string:2)', [1, '2']),
         ('a(date:2017-01-01)', [datetime.date(2017, 1, 1)])
         ])
    def test_OPERATOR_call(self, pair):
        expr, args = pair

        pd = pm.OPERATOR.parseString(expr)
        assert pd[0] == {'name': 'a', 'args': args}

    @pytest.mark.parametrize(
        'pair',
        [('a=1', ['a', '1']), ('a=xyz', ['a', 'xyz']), ('a=string:1', ['a', '1']),
         ('a=date:2017-01-01', ['a', datetime.date(2017, 1, 1)])])
    def test_OPERATOR_eq_expressions(self, pair):
        expr, args = pair

        pd = pm.OPERATOR.parseString(expr)
        assert pd[0] == {'name': 'eq', 'args': args}

    @pytest.mark.parametrize('op', CMP_OPS)
    @pytest.mark.parametrize(
        'pair',
        [('a=%s=1', ['a', '1']), ('a=%s=xyz', ['a', 'xyz']), ('a=%s=string:1', ['a', '1']),
         ('a=%s=date:2017-01-01', ['a', datetime.date(2017, 1, 1)])])
    def test_OPERATOR_fiql_expression(self, op, pair):
        expr, args = pair

        pd = pm.OPERATOR.parseString(expr % op)
        assert pd[0] == {'name': op, 'args': args}

    def test_AND(self):
        expr = 'a(1)&b(2)'

        pd = pm.AND.parseString(expr)
        assert pd[0] == {'name': 'and', 'args': [{'name': 'a', 'args': ['1']},
                                                 {'name': 'b', 'args': ['2']}]}

    def test_OR(self):
        expr = 'a(1)|b(2)'

        pd = pm.OR.parseString(expr)
        assert pd[0] == {'name': 'or', 'args': [{'name': 'a', 'args': ['1']},
                                                {'name': 'b', 'args': ['2']}]}


class TestParser:

    def test_simple_expr(self):
        expr = 'eq(a,1)'
        rep = {'name': 'eq', 'args': ['a', '1']}

        pd = parser.parse(expr)
        assert pd == rep

    @pytest.mark.parametrize('op', CMP_OPS)
    @pytest.mark.parametrize(
        'exre',
        [('%s(a,1)', ['a', '1']),
         ('%s(a,xyz)', ['a', 'xyz']),
         ('%s(a,string:1)', ['a', '1']),
         ('%s(a,date:2017-01-01)', ['a', datetime.date(2017, 1, 1)])])
    def test_op_calls(self, op, exre):
        expr, rep = exre

        pd = parser.parse(expr % op)

        assert pd == {'name': op, 'args': rep}

    def test_equality_operator(self):
        p1 = parser.parse('lero=0')
        p2 = parser.parse('eq(lero, 0)')
        assert p1 == p2

    def test_and_operator_pair(self):
        p1 = parser.parse('eq(a,0)&eq(b,1)')
        p2 = parser.parse('and(eq(a, 0), eq(b, 1))')

        p3 = {'name': 'and', 'args': [{'name': 'eq', 'args': ['a', '0']},
                                      {'name': 'eq', 'args': ['b', '1']}]}

        assert p1 == p2
        assert p1 == p3

    def test_and_operator_triple(self):
        p1 = parser.parse('eq(a,0)&eq(b,1)&eq(c,2)')
        p2 = parser.parse('and(eq(a, 0), eq(b, 1), eq(c, 2))')

        p3 = {'name': 'and', 'args': [{'name': 'eq', 'args': ['a', '0']},
                                      {'name': 'eq', 'args': ['b', '1']},
                                      {'name': 'eq', 'args': ['c', '2']}]}

        assert p1 == p2
        assert p1 == p3

    def test_or_operator(self):
        p1 = parser.parse('(f(1)|f(2))')
        p2 = parser.parse('or(f(1),f(2))')

        p3 = {'name': 'or', 'args': [{'name': 'f', 'args': ['1']},
                                     {'name': 'f', 'args': ['2']}]}

        assert p1 == p2
        assert p1 == p3

    @pytest.mark.parametrize('func', ['in', 'out', 'contains', 'excludes'])
    def test_member_functions(self, func):
        expr = '%s(name,(a,b))' % func
        parsed = {'name': func, 'args': ['name', ('a', 'b')]}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed) == expr

    @pytest.mark.parametrize('func', ['and', 'or'])
    def test_bool_functions(self, func):
        expr = '%s(a,b)' % func
        parsed = {'name': func, 'args': ['a', 'b']}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed, level=1) == expr

        expr = '%s(a,b,c)' % func
        parsed = {'name': func, 'args': ['a', 'b', 'c']}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed, level=1) == expr

    @pytest.mark.parametrize(
        'exre',
        [('sort(+lero)', [('+', 'lero')]),
         ('sort(+foo,-bar)', [('+', 'foo'), ('-', 'bar')]),
         ('sort(+(foo,bar),-lero)', [('+', ('foo', 'bar')), ('-', 'lero')]),
         ])
    def test_sort_function(self, exre):
        expr, args = exre

        pd = parser.parse(expr)

        assert pd == {'name': 'sort', 'args': args}

    @pytest.mark.parametrize('func', ['select', 'values'])
    def test_query_functions(self, func):
        expr = '%s(username,password,(address,city))' % func
        parsed = {'name': func, 'args': ['username', 'password', ('address', 'city')]}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed) == expr

    @pytest.mark.parametrize('func', ['sum', 'mean', 'max', 'min', 'count'])
    def test_aggregate_functions(self, func):
        expr = '%s((a,b,c))' % func
        parsed = {'name': func, 'args': [('a', 'b', 'c')]}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed) == expr

    @pytest.mark.parametrize('func', ['distinct', 'first', 'one'])
    def test_result_functions(self, func):
        expr = '%s()' % func
        parsed = {'name': func, 'args': []}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed) == expr

    def test_limit_function(self):
        expr = 'limit(10,0)'
        parsed = {'name': 'limit', 'args': ['10', '0']}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed) == expr

    def test_recurse_function(self):
        expr = 'recurse(lero)'
        parsed = {'name': 'recurse', 'args': ['lero']}

        assert parser.parse(expr) == parsed
        assert unparser.unparse(parsed) == expr

    @pytest.mark.parametrize('expr', ['foo=3&price=lt=10',
                                      'eq(foo,3)&lt(price,10)',
                                      'and(eq(foo,3),lt(price,10))',
                                      ])
    def test_equivalent_expressions(self, expr):
        parsed = parser.parse(expr)

        assert parsed == {'name': 'and', 'args': [{'name': 'eq', 'args': ['foo', '3']},
                                                  {'name': 'lt', 'args': ['price', '10']}]}

    def test_toplevel_and(self):
        parsed = parser.parse('eq(a, 1),eq(b, 2),eq(c, 3)')

        assert parsed == {'name': 'and', 'args': [{'name': 'eq', 'args': ['a', '1']},
                                                  {'name': 'eq', 'args': ['b', '2']},
                                                  {'name': 'eq', 'args': ['c', '3']},
                                                  ]}

    def test_parenthesis(self):
        parsed = parser.parse('(state=Florida|state=Alabama)&gender=female')

        assert parsed == {'name': 'and',
                          'args': [{'name': 'or',
                                    'args': [{'name': 'eq', 'args': ['state', 'Florida']},
                                             {'name': 'eq', 'args': ['state', 'Alabama']},
                                             ],
                                    },
                                   {'name': 'eq', 'args': ['gender', 'female']}]}


class TestRFCExamples:

    def test_abstract_example(self):
        expr = 'category=dates&sort(+price)'
        rep = {'name': 'and', 'args': [{'name': 'eq', 'args': ['category', 'dates']},
                                       {'name': 'sort', 'args': [('+', 'price')]}]}

        pd = parser.parse(expr)
        assert pd == rep

    def test_arrays_example(self):
        expr = 'in(category,(toy,food))'
        rep = {'name': 'in', 'args': ['category', ('toy', 'food')]}

        pd = parser.parse(expr)
        assert pd == rep

    def test_nested_operators_example(self):
        expr = 'or(eq(category,toy),eq(category,food))'
        rep = {'name': 'or', 'args': [{'name': 'eq', 'args': ['category', 'toy']},
                                      {'name': 'eq', 'args': ['category', 'food']}]}

        pd = parser.parse(expr)
        assert pd == rep

    @pytest.mark.parametrize(
        'exre',
        [('sort(+foo)', [('+', 'foo')]),
         ('sort(+price,-rating)', [('+', 'price'), ('-', 'rating')]),
         ])
    def test_sort_examples(self, exre):
        expr, args = exre

        pd = parser.parse(expr)
        assert pd == {'name': 'sort', 'args': args}

    def test_aggregate_example(self):
        expr = 'aggregate(departmentId,sum(sales))'
        rep = {'name': 'aggregate', 'args': ['departmentId', {'name': 'sum', 'args': ['sales']}]}

        pd = parser.parse(expr)
        assert pd == rep

    def test_comparison_example(self):
        expr = 'foo=3&(bar=text|bar=string)'
        rep = {'name': 'and', 'args': [{'name': 'eq', 'args': ['foo', '3']},
                                       {'name': 'or', 'args': [
                                           {'name': 'eq', 'args': ['bar', 'text']},
                                           {'name': 'eq', 'args': ['bar', 'string']},
                                           ]}]}

        pd = parser.parse(expr)
        assert pd == rep

    def test_typed_value_example(self):
        expr = 'foo=number:4'
        rep = {'name': 'eq', 'args': ['foo', 4]}

        pd = parser.parse(expr)
        assert pd == rep
