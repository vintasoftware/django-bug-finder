# pylint: disable=missing-docstring

from django.contrib.auth.models import User
from django.db import models

from celery import Celery, shared_task


app = Celery('celery-app')


def test():
    qs = User.objects.all()
    qs.filter(first_name='A')  # wrong

    manager = User.objects
    manager.select_related()  # wrong
    qs = qs.order_by('first_name')
    return qs.filter(first_name='C')


class PersonQuerySet(models.QuerySet):

    def authors(self):
        return self.filter(role='A')

    def admin_authors(self):
        self.filter(is_admin=True).authors()  # wrong

    def editors(self):
        self.filter(role='E')  # wrong


@app.task
def celery_task(model_instance):
    return model_instance.pk


@shared_task
def celery_shared_task(queryset):
    return queryset


user = User.objects.get(email='a@b.com')
user_qs = User.objects.filter(first_name='B')
celery_task.delay(user)  # wrong
celery_shared_task.si(user_qs=user_qs).delay()  # wrong
celery_task.apply_async((user,))  # wrong
celery_task.apply([], {'user': user})  # wrong
celery_task.apply_async(args=[user])  # wrong
celery_task.retry(kwargs={'user': user})  # wrong
