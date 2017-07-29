import astroid

from pylint.checkers import BaseChecker, utils
from pylint.interfaces import IAstroidChecker

import pylint_django.transforms
import transforms


class QuerysetAttributionChecker(BaseChecker):
    __implements__ = IAstroidChecker

    name = 'queryset-expr'
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
            try:
                for qs in node.value.infer():
                    if qs.is_subtype_of('django.db.models.query.QuerySet'):
                        self.add_message('queryset-expr-not-assigned', node=node)
                        return
            except astroid.InferenceError as e:
                return


CELERY_TASK_CALL_FUNCTIONS = {  # TODO: improve this
    'delay',
    'si',
    's',
}


class CeleryCallWithModelsChecker(BaseChecker):
    __implements__ = IAstroidChecker

    name = 'celery-call-with-models'
    priority = -1
    msgs = {
      'E9002': (
          'Celery task call with model instance as argument.',
          'celery-call-with-model-instance',
          'Celery tasks shouldn\'t be called with model instances '
          'as arguments. Pass the PK instead and fetch the instance '
          'inside the task to avoid race conditions.'
      ),
      'E9003': (
          'Celery task call with queryset as argument.',
          'celery-call-with-queryset',
          'Celery tasks shouldn\'t be called with queryset instances '
          'as arguments. Pass the necessary values to make the query '
          'inside the task to avoid race conditions.'
      ),
    }
    options = ()

    def __init__(self, linter=None):
        super().__init__(linter)
        self._found_celery_task_nodes = set()

    def visit_functiondef(self, node):
        # Find Celery tasks
        if node.decorators:
            names = {'task', 'shared_task'}
            for decorator in node.decorators.nodes:
                if isinstance(decorator, astroid.Attribute):
                    attr = decorator.attrname
                elif isinstance(decorator, astroid.Name):
                    attr = decorator.name
                else:
                    continue

                if attr in names:
                    inferred = utils.safe_infer(decorator)
                    if inferred.is_bound() and \
                            inferred.bound.is_subtype_of('celery.app.base.Celery'):
                        self._found_celery_task_nodes.add(node)
                        return
                    elif not inferred.is_bound() and \
                            inferred.qname() == 'celery.app.shared_task':
                        self._found_celery_task_nodes.add(node)
                        return

    def visit_call(self, node):
        if isinstance(node.func, astroid.Attribute):
            attr = node.func.attrname
        elif isinstance(node.func, astroid.Name):
            attr = node.func.name
        else:
            return

        if attr in CELERY_TASK_CALL_FUNCTIONS:
            function_def = utils.safe_infer(node.func.expr)
            if function_def in self._found_celery_task_nodes:
                args = node.args + [k.value for k in (node.keywords or [])]
                for arg in args:
                    obj = utils.safe_infer(arg)
                    if obj:
                        if obj.is_subtype_of('django.db.models.query.QuerySet'):
                            self.add_message('celery-call-with-queryset', node=node)
                        elif obj.is_subtype_of('django.db.models.base.Model'):
                            self.add_message('celery-call-with-model-instance', node=node)


def register(linter):
    linter.register_checker(QuerysetAttributionChecker(linter))
    linter.register_checker(CeleryCallWithModelsChecker(linter))
