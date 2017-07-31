import textwrap

import astroid
from astroid.builder import AstroidBuilder


def build_fake_queryset_module(model_name='Model', manager_name='BaseManager'):
    return AstroidBuilder(astroid.MANAGER).string_build(textwrap.dedent('''
    import datetime

    from django.db.models.base import Model
    from django.db.models import sql
    from django.db.models.manager import BaseManager
    from django.db.models.query import BaseIterable, QuerySet as OriginalQuerySet, RawQuerySet

    class _QuerySetMethodsToManager:
        def iterator(self):
            return iter(BaseIterable())

        def aggregate(self, *args, **kwargs):
            return QuerySet()

        def count(self):
            return 0

        def get(self, *args, **kwargs):
            return {MODEL_NAME}()

        def create(self, **kwargs):
            return {MODEL_NAME}()

        def bulk_create(self, objs, batch_size=None):
            return list(objs)

        def get_or_create(self, defaults=None, **kwargs):
            return {MODEL_NAME}(), False

        def update_or_create(self, defaults=None, **kwargs):
            return {MODEL_NAME}(), False

        def earliest(self, field_name=None):
            return {MODEL_NAME}()

        def latest(self, field_name=None):
            return {MODEL_NAME}()

        def first(self):
            return {MODEL_NAME}()

        def last(self):
            return {MODEL_NAME}()

        def in_bulk(self, id_list=None):
            return {{{MODEL_NAME}()._get_pk_val(): {MODEL_NAME}()}}

        def update(self, **kwargs):
            return 0
        update.alters_data = True

        def exists(self):
            return False

        def raw(self, raw_query, params=None, translations=None, using=None):
            return RawQuerySet()

        def values(self, *fields, **expressions):
            return QuerySet()

        def values_list(self, *fields, flat=False):
            return QuerySet()

        def dates(self, field_name, kind, order='ASC'):
            return [datetime.date()]

        def datetimes(self, field_name, kind, order='ASC', tzinfo=None):
            return [datetime.datetime()]

        def none(self):
            return QuerySet()

        def all(self):
            return QuerySet()

        def filter(self, *args, **kwargs):
            return QuerySet()

        def exclude(self, *args, **kwargs):
            return QuerySet()

        def union(self, *other_qs, all=False):
            return QuerySet()

        def intersection(self, *other_qs):
            return QuerySet()

        def difference(self, *other_qs):
            return QuerySet()

        def select_for_update(self, nowait=False, skip_locked=False):
            return QuerySet()

        def select_related(self, *fields):
            return QuerySet()

        def prefetch_related(self, *lookups):
            return QuerySet()

        def annotate(self, *args, **kwargs):
            return QuerySet()

        def order_by(self, *field_names):
            return QuerySet()

        def distinct(self, *field_names):
            return QuerySet()

        def extra(self, select=None, where=None, params=None, tables=None,
                  order_by=None, select_params=None):
            return QuerySet()

        def reverse(self):
            return QuerySet()

        def defer(self, *fields):
            return QuerySet()

        def only(self, *fields):
            return QuerySet()

        def using(self, alias):
            return QuerySet()

        @property
        def ordered(self):
            return False

        @property
        def db(self):
            return self._db

    class QuerySet(OriginalQuerySet, _QuerySetMethodsToManager):
        def __init__(self, model=None, query=None, using=None, hints=None):
            self.model = {MODEL_NAME}
            self._db = using
            self._hints = {{}}
            self.query = sql.Query(self.model)
            self._result_cache = None
            self._sticky_filter = False
            self._for_write = False
            self._prefetch_related_lookups = ()
            self._prefetch_done = False
            self._known_related_objects = {{}}
            self._iterable_class = BaseIterable
            self._fields = None

        def __deepcopy__(self, memo):
            return QuerySet()

        def __getstate__(self):
            return self.__dict__.copy()

        def __setstate__(self, state):
            pass

        def __repr__(self):
            return ''

        def __len__(self):
            return 0

        def __iter__(self):
            return iter(self._result_cache)

        def __bool__(self):
            return bool(self._result_cache)

        def __getitem__(self, k):
            qs = QuerySet()
            return list(qs)[0]

        def __and__(self, other):
            return other

        def __or__(self, other):
            return other

        def as_manager(cls):
            return {MANAGER_NAME}()
        as_manager.queryset_only = True
        as_manager = classmethod(as_manager)

        def delete(self):
            return False, {{}}
        delete.alters_data = True
        delete.queryset_only = True
    '''.format(MODEL_NAME=model_name, MANAGER_NAME=manager_name)))


def transform_django_manager_instance_methods(node, context=None):
    model_cls = node.scope()
    try:
        manager_cls = next(node.func.infer(context=context))
        manager_instance = next(node.infer(context=context))
    except astroid.InferenceError:
        raise astroid.UseInferenceDefault()

    fake_queryset_module = build_fake_queryset_module(
        model_name=model_cls.name,
        manager_name=manager_cls.name)
    qs_methods_cls = fake_queryset_module['_QuerySetMethodsToManager']

    # fix scope for manager and model names
    fake_queryset_module.locals[model_cls.name] = [model_cls]
    fake_queryset_module.locals[manager_cls.name] = [manager_cls]

    # add missing queryset methods to manager instance
    for method in qs_methods_cls.methods():
        manager_instance.locals[method.name] = [method]

    return node


def is_django_manager_in_model_class(node):
    # is this of the form "objects = Manager" inside a class?
    if not isinstance(node.parent, astroid.Assign):
        return False
    model_cls = node.scope()
    if not isinstance(model_cls, astroid.ClassDef):
        return False
    # we'll not handle multiple assignment, probably no-one does this with managers
    if len(node.parent.targets) > 1:
        return False

    try:
        manager_cls = next(node.func.infer())
    except astroid.InferenceError:
        return False
    else:
        return (
            model_cls.is_subtype_of('django.db.models.base.Model') and
            manager_cls.is_subtype_of('django.db.models.manager.Manager'))


def transform_django_class_adding_default_manager(model_cls, context=None):
    fake_queryset_module = build_fake_queryset_module(
        model_name=model_cls.name,
        manager_name='BaseManager')
    manager_cls = astroid.MANAGER.ast_from_module_name('django.db.models.manager')['BaseManager']
    manager_instance = manager_cls.instantiate_class()
    qs_methods_cls = fake_queryset_module['_QuerySetMethodsToManager']

    # fix scope for model name
    fake_queryset_module.locals[model_cls.name] = [model_cls]

    # add missing queryset methods to manager instance
    for method in qs_methods_cls.methods():
        manager_instance.locals[method.name] = [method]

    # add default manager to class
    model_cls.locals['objects'] = [manager_instance]

    return model_cls


def is_model_class_without_manager(model_cls):
    if not isinstance(model_cls, astroid.ClassDef):
        return False
    return (
        model_cls.is_subtype_of('django.db.models.base.Model') and
        'objects' not in model_cls.locals)


def add_transforms(manager):
    manager.register_transform(
        astroid.Call,
        transform_django_manager_instance_methods,
        is_django_manager_in_model_class)
    manager.register_transform(
        astroid.ClassDef,
        transform_django_class_adding_default_manager,
        is_model_class_without_manager)
    astroid.register_module_extender(
        manager,
        'django.db.models.query',
        build_fake_queryset_module)


add_transforms(astroid.MANAGER)
