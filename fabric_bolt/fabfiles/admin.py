from django.contrib import admin
from fabric_bolt.fabfiles.models import Fabfile


#
#class FabfileAdmin(admin.ModelAdmin):
#    form = FabfileForm

admin.site.register(Fabfile)