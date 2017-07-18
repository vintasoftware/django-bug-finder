import astroid
from astroid import MANAGER, nodes, InferenceError, inference_tip, UseInferenceDefault
from pylint_django.compat import ClassDef, instantiate_class, Attribute
from pylint_django.transforms import foreignkey, fields
from pylint_django import utils

'''
assignname = node.parent.lookup('qs')[1][0]
assign = assignname.assign_type()
assign.value.func.expr.inferred()
assign.value.func.inferred()
assign.value.inferred()
'''

# Taken from: https://docs.djangoproject.com/en/1.11/ref/models/querysets/
QUERYSET_EXPRESSION_METHODS = {
    # Methods that return querysets
    'filter',
    'exclude',
    'annotate',
    'order_by',
    'reverse',
    'distinct',
    'values',
    'values_list',
    'dates',
    'datetimes',
    'none',
    'all',
    'union',
    'intersection',
    'difference',
    'select_related',
    'prefetch_related',
    'extra',
    'defer',
    'only',
    'using',
    'select_for_update',
    'raw',

    # Methods that does not return querysets
    # but make no sense to be isolated in a statement
    'get',
    'count',
    'in_bulk',
    'iterator',
    'latest',
    'earliest',
    'first',
    'last',
    'aggregate',
    'exists',
    'as_manager',
}


def is_manager(node):
    return node.is_subtype_of('django.db.models.manager.Manager')


def infer_manager_queryset_methods(klass, context=None):
    base_nodes = MANAGER.ast_from_module_name(
        'django.db.models.query').lookup('QuerySet')
    return iter([klass] + base_nodes[1])


def is_method_with_queryset_return(node):
    if isinstance(node.func, nodes.Attribute):
        attr = node.func.attrname
    elif isinstance(node.func, nodes.Name):
        attr = node.func.name
    else:
        return False

    if attr in QUERYSET_EXPRESSION_METHODS:
        try:
            method = next(node.func.infer())
        except InferenceError:
            return False
        else:
            return (
                isinstance(method, astroid.BoundMethod) and
                (
                    method.bound.is_subtype_of(
                        'django.db.models.manager.Manager') or
                    method.bound.is_subtype_of(
                        'django.db.models.query.QuerySet')
                )
            )


def infer_expression_queryset_methods(node, context=None):
    _, [qs_cls] = MANAGER.ast_from_module_name(
        'django.db.models.query').lookup('QuerySet')
    return iter([qs_cls.instantiate_class()])


def add_transforms(manager):
    manager.register_transform(
        nodes.ClassDef,
        inference_tip(infer_manager_queryset_methods),
        is_manager)
    manager.register_transform(
        nodes.Call,
        inference_tip(infer_expression_queryset_methods),
        is_method_with_queryset_return)


add_transforms(MANAGER)
