import astroid
from astroid import MANAGER, nodes, InferenceError, inference_tip, UseInferenceDefault
from pylint_django.compat import ClassDef, instantiate_class, Attribute
from pylint_django.transforms import foreignkey, fields
from pylint_django import utils
from astroid import MANAGER, register_module_extender
from astroid.builder import AstroidBuilder
import textwrap


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
}


def build_fake_queryset_module(model_name, manager_name):
    return AstroidBuilder(MANAGER).string_build(textwrap.dedent('''
    import datetime
    from django.db.models.query import *

    class QuerySetMethodsToManager:
        def iterator(self):
            return iter(BaseIterable())

        def aggregate(self, *args, **kwargs):
            return FakeQuerySet()

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
            return FakeQuerySet()

        def values_list(self, *fields, flat=False):
            return FakeQuerySet()

        def dates(self, field_name, kind, order='ASC'):
            return [datetime.date()]

        def datetimes(self, field_name, kind, order='ASC', tzinfo=None):
            return [datetime.datetime()]

        def none(self):
            return FakeQuerySet()

        def all(self):
            return FakeQuerySet()

        def filter(self, *args, **kwargs):
            return FakeQuerySet()

        def exclude(self, *args, **kwargs):
            return FakeQuerySet()

        def union(self, *other_qs, all=False):
            return FakeQuerySet()

        def intersection(self, *other_qs):
            return FakeQuerySet()

        def difference(self, *other_qs):
            return FakeQuerySet()

        def select_for_update(self, nowait=False, skip_locked=False):
            return FakeQuerySet()

        def select_related(self, *fields):
            return FakeQuerySet()

        def prefetch_related(self, *lookups):
            return FakeQuerySet()

        def annotate(self, *args, **kwargs):
            return FakeQuerySet()

        def order_by(self, *field_names):
            return FakeQuerySet()

        def distinct(self, *field_names):
            return FakeQuerySet()

        def extra(self, select=None, where=None, params=None, tables=None,
                  order_by=None, select_params=None):
            return FakeQuerySet()

        def reverse(self):
            return FakeQuerySet()

        def defer(self, *fields):
            return FakeQuerySet()

        def only(self, *fields):
            return FakeQuerySet()

        def using(self, alias):
            return FakeQuerySet()

        @property
        def ordered(self):
            return False

        @property
        def db(self):
            return self._db
    queryset_manager_methods = QuerySetMethodsToManager()

    class FakeQuerySet(QuerySetMethodsToManager, QuerySet):
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
            return FakeQuerySet()

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
            qs = FakeQuerySet()
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


def fix_django_manager_instance_methods(node, context=None):
    model_cls = node.parent
    manager_instance = next(node.value.infer())

    _, [base_manager_cls] = MANAGER.ast_from_module_name(
        'django.db.models.manager').lookup('BaseManager')
    fake_queryset_module = build_fake_queryset_module(
        model_name=model_cls.name,
        manager_name=manager_instance.name)
    base_qs_cls = fake_queryset_module['QuerySetMethodsToManager']

    # fix scope for manager and model names
    fake_queryset_module.locals[model_cls.name] = [model_cls]
    fake_queryset_module.locals[manager_instance._proxied.name] = [manager_instance._proxied]

    for base_cls in [base_manager_cls, base_qs_cls]:
        for method in base_cls.methods():
            manager_instance.locals[method.name] = [method]

    return node


def is_django_manager_in_model_class(node):
    # is this of the form objects = Manager inside a class
    if not isinstance(node.parent, ClassDef):
        return False
    if not isinstance(node.value, nodes.Call):
        return False

    try:
        model_cls = next(node.parent.infer())
        manager_cls = next(node.value.func.infer())
    except InferenceError:
        return False
    else:
        return (
            isinstance(manager_cls, ClassDef) and
            model_cls.is_subtype_of('django.db.models.base.Model') and
            manager_cls.is_subtype_of('django.db.models.manager.Manager'))


def add_transforms(manager):
    manager.register_transform(
        nodes.Assign,
        fix_django_manager_instance_methods,
        is_django_manager_in_model_class)


add_transforms(MANAGER)
