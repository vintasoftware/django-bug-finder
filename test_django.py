# pylint: disable=missing-docstring

from django.contrib.auth.models import User
from django.db import models


def test():
    qs = User.objects.all()
    qs.filter(first_name='A')  # wrong

    manager = User.objects
    manager.select_related()  # wrong
    qs = qs.order_by('first_name')
    return qs.filter(first_name='C')


class PersonQuerySet(models.QuerySet):

    def authors(self):
        self.filter(role='A')  # wrong

    def editors(self):
        return self.filter(role='E')
