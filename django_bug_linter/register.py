from django_bug_linter.checkers import CeleryCallWithModelsChecker, QuerysetAttributionChecker


def register(linter):
    linter.register_checker(QuerysetAttributionChecker(linter))
    linter.register_checker(CeleryCallWithModelsChecker(linter))
