import subprocess
import tempfile
from codemirror import CodeMirrorField
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import pre_save
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from fabric_bolt.fabfiles.utils import validate_filename
import os


class Fabfile(models.Model):
    """Defines a period of time that deployments can be made in"""
    name = models.CharField(max_length=255, validators=[validate_filename])
    file = models.FileField(upload_to='.fabfiles', editable=False)
    content = CodeMirrorField()
    fabfile_requirements = models.TextField(null=True, blank=True,
                                            help_text='Pip requirements to install for fabfile. ')

    def clean(self):
        try:
            # p = subprocess.Popen(
            #     ['python', '-m py_compile'],
            #     stdin=subprocess.PIPE,
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.PIPE,
            #
            # )
            tmpfile = tempfile.NamedTemporaryFile(delete=False)
            tmpfile.write(self.content)
            tmpfile.close()
            out = subprocess.check_output(
                #['python', '-m py_compile', self.file.file.name],
                'python -m py_compile "{}"'.format(tmpfile.name),
                stderr=subprocess.STDOUT,
                shell=True
            )
            os.remove(tmpfile.name)
            # stdout, stderr = p.communicate("print 'a'")
            # if stderr or stdout:
            #     raise ValidationError("hihi")
        except subprocess.CalledProcessError as e:
            raise ValidationError(mark_safe('%s is not valid python code because:<br/>\n%s' % (self.file.file.name, '<br/>'.join(e.output.split('\n')))))


def save_fabfile(sender, **kwargs):
    instance = kwargs['instance']
    instance.file.save("%s.py" % slugify(instance.name), ContentFile(instance.content), save=False)


pre_save.connect(save_fabfile, sender=Fabfile)
