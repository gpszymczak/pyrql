# -*- coding: utf-8 -*-

import datetime
import operator
from collections import OrderedDict
from copy import deepcopy
from urllib.parse import unquote

from .exceptions import RQLQueryError
from .parser import Parser


class Node:
    def __init__(self, *args):
        self.args = args

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.args)


class Key(Node):
    def __init__(self, *args):
        self.args = []
        for token in args:
            self.args.extend(token.split("."))

    def __call__(self, row):
        value = row
        for key in self.args:
            value = value[key]

        return value

    @property
    def key(self):
        return '.'.join(self.args)


class RowNode(Node):
    pass


class DataNode(Node):
    pass


class Filter(RowNode):
    def __call__(self, row):
        opname, key, value = self.args

        if not isinstance(key, Key):
            if isinstance(key, str):
                key = Key(key)
            else:
                key = Key(*key)

        op = getattr(operator, opname)
        return op(key(row), value)


class And(RowNode):
    def __call__(self, row):
        return all([f(row) for f in self.args if f is not None])


class Or(RowNode):
    def __call__(self, row):
        return any([f(row) for f in self.args if f is not None])


class In(RowNode):
    def __call__(self, row):
        attr, value = self.args
        return operator.contains(value, attr(row))


class NotIn(RowNode):
    def __call__(self, row):
        attr, value = self.args
        return operator.not_(operator.contains(value, attr(row)))


class Contains(RowNode):
    def __call__(self, row):
        attr, value = self.args
        return operator.contains(attr(row), value)


class Excludes(RowNode):
    def __call__(self, row):
        attr, value = self.args
        return operator.not_(operator.contains(attr(row), value))


class AggregateNode(DataNode):
    @property
    def label(self):
        return self.args[0].key


class Min(AggregateNode):
    def __call__(self, data):
        (attr,) = self.args
        return min([attr(row) for row in data])


class Max(AggregateNode):
    @property
    def label(self):
        return self.args[0].key

    def __call__(self, data):
        (attr,) = self.args
        return max([attr(row) for row in data])


class Sum(AggregateNode):
    def __call__(self, data):
        (attr,) = self.args
        return sum([attr(row) for row in data])


class Mean(AggregateNode):
    def __call__(self, data):
        (attr,) = self.args
        return sum([attr(row) for row in data]) / len(data)


class Select(DataNode):
    def __call__(self, data):
        return [{k.key: k(row) for k in self.args} for row in data]


class Values(DataNode):
    def __call__(self, data):
        (attr,) = self.args
        return [attr(row) for row in data]


class Aggregate(DataNode):
    def __call__(self, data):
        group_by, attrs = self.args

        groups = OrderedDict()
        for row in data:
            try:
                groups[group_by(row)].append(row)
            except KeyError:
                groups[group_by(row)] = [row]

        out = []
        for group_key, rows in groups.items():
            outrow = {attr.label: attr(rows) for attr in attrs}

            outrow[group_by.key] = group_key

            out.append(outrow)

        return out


class Limit(DataNode):
    def __call__(self, data):
        limit, offset = self.args

        if offset:
            data = data[offset:]

        if limit:
            data = data[:limit]

        return data


class Count(DataNode):
    label = "count"

    def __call__(self, data):
        return len(data)


class Distinct(DataNode):
    def __call__(self, data):
        new_data = []

        for row in data:
            if row not in new_data:
                new_data.append(row)
        return new_data


class Sort(DataNode):
    def __call__(self, data):
        # sort least significant first
        for prefix, attr in reversed(self.args):
            data.sort(key=operator.itemgetter(attr), reverse=prefix == "-")

        return data


class One(DataNode):
    def __call__(self, data):
        if len(data) > 1:
            raise ValueError("Multiple results found for 'one'")

        if len(data) == 0:
            raise ValueError("No results found for 'one'")

        return data


class Query:

    _rql_max_limit = None
    _rql_default_limit = None

    def __init__(self, data):
        self.data = deepcopy(data)

    def query(self, expr):
        if not expr:
            self.rql_parsed = None
            self.rql_expr = ""

        else:
            self.rql_expr = expr = unquote(expr)
            self.rql_parsed = Parser().parse(expr)

        self._rql_filter_clause = None
        self._rql_sort_clause = None
        self._rql_limit_clause = None
        self._rql_results_clause = None
        self._rql_distinct_clause = None

        return self

    def all(self):
        data = self.data

        # set default limit
        if self._rql_default_limit:
            self._rql_limit_clause = Limit(self._rql_default_limit)

        self._rql_walk(self.rql_parsed)

        # filter the data
        if self._rql_filter_clause is not None:
            data = [row for row in data if self._rql_filter_clause(row)]

        # generate results
        if self._rql_results_clause:
            data = self._rql_results_clause(data)

        # order the data
        if self._rql_sort_clause is not None:
            data = self._rql_sort_clause(data)

        # apply distinct clause
        if self._rql_distinct_clause:
            data = self._rql_distinct_clause(data)

        # apply any limit and offset
        if self._rql_limit_clause:
            data = self._rql_limit_clause(data)

        return data

    def _rql_walk(self, node):
        if node:
            self._rql_filter_clause = self._rql_apply(node)

    def _rql_apply(self, node):
        if isinstance(node, dict):
            name = node["name"]
            args = node["args"]

            if name in {"eq", "ne", "lt", "le", "gt", "ge"}:
                return self._rql_cmp(name, args)

            try:
                method = getattr(self, "_rql_" + name)
            except AttributeError:
                raise RQLQueryError("Invalid query function: %s" % name)

            return method(args)

        elif isinstance(node, list):
            raise NotImplementedError

        elif isinstance(node, tuple):
            raise NotImplementedError

        return node

    def _rql_cmp(self, name, args):
        attr, value = args

        attr = self._rql_attr(attr)
        value = self._rql_value(value, attr)

        return Filter(name, attr, value)

    def _rql_value(self, value, attr=None):
        if isinstance(value, dict):
            value = self._rql_apply(value)

        return value

    def _rql_attr(self, attr):
        if isinstance(attr, str):
            return Key(attr)
        else:
            return Key(*attr)

    def _rql_and(self, args):
        args = [self._rql_apply(a) for a in args]

        return And(*args)

    def _rql_or(self, args):
        args = [self._rql_apply(a) for a in args]

        return Or(*args)

    def _rql_in(self, args):
        attr, value = args

        attr = self._rql_attr(attr)
        value = self._rql_value(value, attr)

        return In(attr, value)

    def _rql_out(self, args):
        attr, value = args

        attr = self._rql_attr(attr)
        value = self._rql_value(value, attr)

        return NotIn(attr, value)

    def _rql_limit(self, args):
        args = [self._rql_value(v) for v in args]

        limit = min(args[0], self._rql_max_limit or float("inf"))

        try:
            offset = args[1]
        except IndexError:
            offset = 0

        self._rql_limit_clause = Limit(limit, offset)

    def _rql_sort(self, args):
        args = [("+", v) if isinstance(v, str) else v for v in args]

        args = [(attr, prefix) for (attr, prefix) in args]
        self._rql_sort_clause = Sort(*args)

    def _rql_contains(self, args):
        attr, value = args
        attr = self._rql_attr(attr)
        value = self._rql_value(value, attr)

        return Contains(attr, value)

    def _rql_excludes(self, args):
        attr, value = args
        attr = self._rql_attr(attr)
        value = self._rql_value(value, attr)

        return Excludes(attr, value)

    def _rql_select(self, args):
        attrs = [self._rql_attr(attr) for attr in args]
        self._rql_results_clause = Select(*attrs)

    def _rql_values(self, args):
        (attr,) = args
        attr = self._rql_attr(attr)
        self._rql_results_clause = Values(attr)

    def _rql_distinct(self, args):
        self._rql_distinct_clause = Distinct()

    def _rql_count(self, args):
        self._rql_results_clause = Count()

    def _rql_min(self, args):
        self._rql_results_clause = Min(self._rql_attr(args))

    def _rql_max(self, args):
        self._rql_results_clause = Max(self._rql_attr(args))

    def _rql_sum(self, args):
        self._rql_results_clause = Sum(self._rql_attr(args))

    def _rql_mean(self, args):
        self._rql_results_clause = Mean(self._rql_attr(args))

    def _rql_first(self, args):
        self._rql_limit_clause = Limit(1, 0)

    def _rql_one(self, args):
        self._rql_results_clause = One()

    def _rql_time(self, args):
        return datetime.time(*args)

    def _rql_date(self, args):
        return datetime.date(*args)

    def _rql_dt(self, args):
        return datetime.datetime(*args)

    def _rql_aggregate(self, args):
        funcs = {"sum": Sum, "min": Min, "max": Max, "mean": Mean, "count": Count}

        group_by = self._rql_attr(args[0])
        fields = args[1:]

        aggrs = []

        for f in fields:
            agg_func = funcs[f["name"]]
            agg_attr = self._rql_attr(*f["args"]) if f["args"] else None

            aggrs.append(agg_func(agg_attr))

        self._rql_results_clause = Aggregate(group_by, aggrs)
