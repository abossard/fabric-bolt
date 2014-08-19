from django.contrib import admin

from fabric_bolt.roles import models


admin.site.register(models.Role)
