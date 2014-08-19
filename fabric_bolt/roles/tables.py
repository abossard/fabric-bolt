import django_tables2 as tables

from fabric_bolt.roles import models
from fabric_bolt.core.mixins.tables import ActionsColumn, PaginateTable


class RoleTable(PaginateTable):
    actions = ActionsColumn([
        {'title': '<i class="glyphicon glyphicon-file"></i>', 'url': 'roles_role_detail', 'args': [tables.A('pk')],
         'attrs':{'data-toggle': 'tooltip', 'title': 'View Role', 'data-delay': '{ "show": 300, "hide": 0 }'}},
        {'title': '<i class="glyphicon glyphicon-pencil"></i>', 'url': 'roles_role_update', 'args': [tables.A('pk')],
         'attrs':{'data-toggle': 'tooltip', 'title': 'Edit Role', 'data-delay': '{ "show": 300, "hide": 0 }'}},
        {'title': '<i class="glyphicon glyphicon-trash"></i>', 'url': 'roles_role_delete', 'args': [tables.A('pk')],
         'attrs':{'data-toggle': 'tooltip', 'title': 'Delete Role', 'data-delay': '{ "show": 300, "hide": 0 }'}},
    ], delimiter='&#160;&#160;&#160;')

    class Meta:
        model = models.Role
        attrs = {"class": "table table-striped"}
