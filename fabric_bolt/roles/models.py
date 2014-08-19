from django.db import models

# Create your models here.

class Role(models.Model):
    """ Defines a role """

    name = models.CharField(
        max_length=255,
        help_text='Name of the role to use in fabric',
        primary_key=True)
