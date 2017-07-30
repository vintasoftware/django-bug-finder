# linters

PYTHONPATH='.' pylint --load-plugins=django_bug_linter --disable=all --enable=queryset-expr,celery-call-with-models test_django.py
