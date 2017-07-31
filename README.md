# django_bug_finder

PYTHONPATH='.' pylint --load-plugins=django_bug_finder --disable=all --enable=queryset-expr,celery-call-with-models test_django.py
