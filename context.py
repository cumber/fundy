
class SimpleRecord(object):
    def __init__(self, graph):
        self.graph = graph

    def get_assoc(self):
        assert False

    def get_prec(self):
        assert False

    def get_fixity(self):
        assert False

    def __repr__(self):
        """
        NOT_RPYTHON:
        """
        return repr(self.graph)


class OperatorRecord(SimpleRecord):
    def __init__(self, graph, assoc, prec, fixity):
        self.graph = graph
        self.assoc = assoc
        self.prec = prec
        self.fixity = fixity

    def get_assoc(self):
        return self.assoc

    def get_prec(self):
        return self.prec

    def get_fixity(self):
        return self.fixity

    def __repr__(self):
        """
        NOT_RPYTHON:
        """
        return '<%r, %r, %r> %r' % (self.assoc, self.prec, self.fixity,
                                    self.graph)


class Context(object):
    def __init__(self):
        self.graphs = {}

    def copy(self):
        other = Context()
        other.graphs = self.graphs.copy()
        return other

    def bind(self, name, graph):
        self.graphs[name] = SimpleRecord(graph)

    def bind_operator(self, name, graph, assoc, prec, fixity):
        # TODO: support overloaded names
        self.graphs[name] = OperatorRecord(graph, assoc, prec, fixity)

    def lookup(self, name):
        return self.graphs[name].graph

    def is_operator(self, name):
        return isinstance(self.graphs[name], OperatorRecord)

    def get_assoc(self, name):
        return self.graphs[name].get_assoc()

    def get_prec(self, name):
        return self.graphs[name].get_prec()

    def get_fixity(self, name):
        return self.graphs[name].get_fixity()

    def items(self):
        """
        NOT_RPYTHON:
        """
        for name in self.graphs:
            yield name, self.lookup(name)

    def update(self, other):
        self.graphs.update(other.graphs)

    def __repr__(self):
        """
        NOT_RPYTHON:
        """
        names = sorted(self.graphs.keys())
        lines = ['%s -> %r' % (name, self.graphs[name])
                 for name in sorted(self.graphs.keys())]
        return '\n'.join(lines)
