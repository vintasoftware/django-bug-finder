import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker

from django_bug_linter import transforms  # noqa: F401  # pylint: disable=unused-import


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

    CELERY_TASK_DECORATOR_NAMES = {
        'task',
        'shared_task',
    }
    # From: http://docs.celeryproject.org/en/latest/reference/celery.app.task.html
    CELERY_TASK_DIRECT_CALLS = {
        'delay',
        'si',
        's',
        'signature',
    }
    CELERY_TASK_ARGS_CALLS = {
        'apply',
        'apply_async',
        'retry',
    }

    def __init__(self, linter=None):
        super().__init__(linter)
        self._task_function_def_nodes = set()

    def visit_functiondef(self, node):
        # Find Celery tasks and store them on self._task_function_def_nodes
        if node.decorators:
            for decorator in node.decorators.nodes:
                if isinstance(decorator, astroid.Attribute):
                    attr = decorator.attrname
                elif isinstance(decorator, astroid.Name):
                    attr = decorator.name
                else:
                    continue

                if attr in self.CELERY_TASK_DECORATOR_NAMES:
                    try:
                        for inferred in decorator.infer():
                            if inferred.is_bound() and \
                                    inferred.bound.is_subtype_of('celery.app.base.Celery'):
                                self._task_function_def_nodes.add(node)
                                return
                            elif not inferred.is_bound() and \
                                    inferred.qname() == 'celery.app.shared_task':
                                self._task_function_def_nodes.add(node)
                                return
                    except astroid.InferenceError:
                        return

    def _add_message_if_model_arg(self, node, args, kwargs):
        for arg in (args + kwargs):
            try:
                for obj in arg.infer():
                    if obj.is_subtype_of('django.db.models.query.QuerySet'):
                        self.add_message('celery-call-with-queryset', node=node)
                        return
                    elif obj.is_subtype_of('django.db.models.base.Model'):
                        self.add_message('celery-call-with-model-instance', node=node)
                        return
            except astroid.InferenceError:
                return

    def _visit_celery_task_direct_call(self, node):
        args = node.args
        kwargs = [key.value for key in (node.keywords or [])]

        for arg in (args + kwargs):
            self._add_message_if_model_arg(node, args, kwargs)

    def _visit_celery_task_args_call(self, node):
        # node.args[0] and node.args[1] are task args and kwargs respectively
        args = []
        kwargs = []
        if len(node.args) >= 1:
            # Only try to infer if it's a list or a tuple, because that's what Celery expects
            if node.args[0].pytype() in {'builtins.list', 'builtins.tuple'}:
                args = node.args[0].itered()
        if len(node.args) >= 2:
            # Only try to infer if it's a dict, because that's what Celery expects
            if node.args[1].pytype() == 'builtins.dict':
                kwargs = [v for __, v in node.args[1].itered()]
        if not args:
            for key in (node.keywords or []):
                if key.arg == 'args' and \
                        key.value.pytype() in {'builtins.list', 'builtins.tuple'}:
                    args = key.value.itered()
                    break
        if not kwargs:
            for key in (node.keywords or []):
                if key.arg == 'kwargs' and \
                        key.value.pytype() == 'builtins.dict':
                    kwargs = [v for __, v in key.value.itered()]
                    break

        for arg in (args + kwargs):
            self._add_message_if_model_arg(node, args, kwargs)

    def visit_call(self, node):
        if isinstance(node.func, astroid.Attribute):
            attr = node.func.attrname
        elif isinstance(node.func, astroid.Name):
            attr = node.func.name
        else:
            return

        if attr in self.CELERY_TASK_DIRECT_CALLS or attr in self.CELERY_TASK_ARGS_CALLS:
            try:
                for function_def in node.func.expr.infer():
                    if function_def in self._task_function_def_nodes:
                        if attr in self.CELERY_TASK_DIRECT_CALLS:
                            self._visit_celery_task_direct_call(node)
                        elif attr in self.CELERY_TASK_ARGS_CALLS:
                            self._visit_celery_task_args_call(node)
            except astroid.InferenceError:
                return
