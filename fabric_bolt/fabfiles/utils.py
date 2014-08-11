import subprocess
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
import re

RE_VALID_FILENAME = "^[\w,\s-]+$"


def validate_filename(value):
    if not re.match(RE_VALID_FILENAME, value):
        raise ValidationError('%s is not matching what it should: %s' % (value, RE_VALID_FILENAME))
