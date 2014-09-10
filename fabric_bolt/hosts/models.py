import re

from django.db import models
from django.core.validators import URLValidator

def full_domain_validator(hostname):
    """
    Fully validates a domain name as compilant with the standard rules:
        - Composed of series of labels concatenated with dots, as are all domain names.
        - Each label must be between 1 and 63 characters long.
        - The entire hostname (including the delimiting dots) has a maximum of 255 characters.
        - Only characters 'a' through 'z' (in a case-insensitive manner), the digits '0' through '9'.
        - Labels can't start or end with a hyphen.
    """
    HOSTNAME_LABEL_PATTERN = re.compile("(?!-)[A-Z\d-]+(?<!-)$", re.IGNORECASE)
    if not hostname:
        return
    if len(hostname) > 255:
        raise ValidationError(_("The domain name cannot be composed of more than 255 characters."))
    if hostname[-1:] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present
    for label in hostname.split("."):
        if len(label) > 63:
            raise ValidationError(
                _("The label '%(label)s' is too long (maximum is 63 characters).") % {'label': label})
        if not HOSTNAME_LABEL_PATTERN.match(label):
            raise ValidationError(_("Unallowed characters in label '%(label)s'.") % {'label': label})


class Host(models.Model):
    """Defines a Host that deployments can be made to"""

    name = models.CharField(max_length=255, help_text='DNS name or IP address', validators=[full_domain_validator])

    alias = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text='Human readable value (optional)',
        validators=[full_domain_validator]
    )

    def __unicode__(self):
        return self.alias or self.name
