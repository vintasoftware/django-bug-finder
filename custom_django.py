import astroid

from pylint.checkers import BaseChecker, utils
from pylint.interfaces import IAstroidChecker

import pylint_django.transforms
import transforms


class QuerysetAttributionChecker(BaseChecker):
    __implements__ = IAstroidChecker

    name = 'queryset-attribution'
    priority = -1
    msgs = {
      'E9001': (
          'Queryset expression is not assigned.',
          'queryset-expr-not-assigned',
          'Operations over a queryset should be '
          'assigned to something or returned.'
      ),
    }
    options = ()

    def visit_expr(self, node):
        if isinstance(node.value, astroid.Call):
            if isinstance(node.value.func, astroid.Attribute):
                attr = node.value.func.attrname
            elif isinstance(node.value.func, astroid.Name):
                attr = node.value.func.name
            else:
                return

            if attr in transforms.QUERYSET_EXPRESSION_METHODS:
                qs = utils.safe_infer(node.value)
                if qs and qs.is_subtype_of('django.db.models.query.QuerySet'):
                    self.add_message('queryset-expr-not-assigned', node=node)


def register(linter):
    linter.register_checker(QuerysetAttributionChecker(linter))
