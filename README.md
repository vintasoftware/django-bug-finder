# linters

PYTHONPATH='/Users/fjsj/workspace/linters/:/Users/fjsj/workspace/linters/venv/lib/python3.6/site-packages/' pylint --load-plugins=pylint_django,custom_django --disable=all --enable=queryset-expr,celery-call-with-models test_django.py
