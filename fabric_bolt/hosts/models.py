import re

from django.db import models
from django.core.validators import URLValidator, RegexValidator


class SchemelessURLValidator(URLValidator):
    regex = re.compile(
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)


class UnixUsernameValidator(RegexValidator):
    pass


class Host(models.Model):
    """Defines a Host that deployments can be made to"""
    username = models.CharField(max_length=255, blank=True, null=True, help_text='Optional username')
    name = models.CharField(max_length=255, help_text='DNS name or IP address', validators=[SchemelessURLValidator()])

    alias = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text='Human readable value (optional)',
        validators=[SchemelessURLValidator()]
    )

    user = models.CharField(max_length=255,
                            help_text="Username to connect to this system (or none, if you want ssh to decide)", blank=True, null=True, validators=[UnixUsernameValidator()])

    @property
    def port(self):
        if ":" in self.name:
            return self.name.rsplit(":", 1)[0]
        else:
            return 22

    @property
    def user_hostname(self):
        return self.name.lsplit(":", 1)[0]

    def __unicode__(self):
        return self.alias or self.name
