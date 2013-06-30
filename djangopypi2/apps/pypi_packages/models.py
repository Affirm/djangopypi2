import os
from logging import getLogger

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.utils.translation import ugettext_lazy as _
from django.utils import simplejson as json
from django.utils.datastructures import MultiValueDict
from django.contrib.auth.models import User
from django.dispatch import receiver

from ..pypi_metadata.models import DistributionType
from ..pypi_metadata.models import PythonVersion
from ..pypi_metadata.models import PlatformName

log = getLogger(__name__)

class ConfigurationManager(models.Manager):
    def latest(self):
        try:
            return super(ConfigurationManager, self).latest()
        except Configuration.DoesNotExist:
            configuration = Configuration()
            configuration.save()
            return configuration

class Configuration(models.Model):
    '''Stores the configuration of this site. As a rule, the most
    recent configuration is always used, and past configurations
    are kept for reference and for rollback.
    '''
    objects = ConfigurationManager()

    timestamp = models.DateTimeField(auto_now_add=True)
    allow_version_overwrite = models.BooleanField(default=False)
    upload_directory = models.CharField(max_length=256, default='dists',
        help_text='Direcory relative to MEDIA_ROOT in which user uploads are kept')

    class Meta:
        ordering = ('-timestamp', )
        verbose_name = _(u'Configuration')
        verbose_name_plural = _(u'Configurations')
        get_latest_by = 'timestamp'

class PackageInfoField(models.Field):
    description = u'Python Package Information Field'
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs['editable'] = False
        super(PackageInfoField,self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, basestring):
            if value:
                return MultiValueDict(json.loads(value))
            else:
                return MultiValueDict()
        if isinstance(value, dict):
            return MultiValueDict(value)
        if isinstance(value,MultiValueDict):
            return value
        raise ValueError('Unexpected value encountered when converting data to python')

    def get_prep_value(self, value):
        if isinstance(value,MultiValueDict):
            return json.dumps(dict(value.iterlists()))
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, basestring) or value is None:
            return value

        raise ValueError('Unexpected value encountered when preparing for database')

    def get_internal_type(self):
        return 'TextField'

class Package(models.Model):
    name = models.CharField(max_length=255, unique=True, primary_key=True,
                            editable=False)
    auto_hide = models.BooleanField(default=True, blank=False)
    allow_comments = models.BooleanField(default=True, blank=False)
    owners = models.ManyToManyField(User, blank=True,
                                    related_name="packages_owned")
    maintainers = models.ManyToManyField(User, blank=True,
                                         related_name="packages_maintained")

    class Meta:
        verbose_name = _(u"package")
        verbose_name_plural = _(u"packages")
        get_latest_by = "releases__latest"
        ordering = ['name',]

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('djangopypi2-package', (), {'package_name': self.name})

    @property
    def latest(self):
        try:
            return self.releases.latest()
        except Release.DoesNotExist:
            return None

    def get_release(self, version):
        """Return the release object for version, or None"""
        try:
            return self.releases.get(version=version)
        except Release.DoesNotExist:
            return None

class Release(models.Model):
    package = models.ForeignKey(Package, related_name="releases", editable=False)
    version = models.CharField(max_length=128, editable=False)
    metadata_version = models.CharField(max_length=64, default='1.0')
    package_info = PackageInfoField(blank=False)
    hidden = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = _(u"release")
        verbose_name_plural = _(u"releases")
        unique_together = ("package", "version")
        get_latest_by = 'created'
        ordering = ['-created']

    def __unicode__(self):
        return self.release_name

    @property
    def release_name(self):
        return u"%s-%s" % (self.package.name, self.version)

    @property
    def summary(self):
        return self.package_info.get('summary', u'')

    @property
    def description(self):
        return self.package_info.get('description', u'')

    @property
    def classifiers(self):
        return self.package_info.getlist('classifier')

    @models.permalink
    def get_absolute_url(self):
        return ('djangopypi2-release', (), {'package_name': self.package.name,
                                            'version': self.version})

def distribution_upload_path(instance, filename):
    configuration = Configuration.objects.latest()
    return os.path.join(str(configuration.upload_directory), os.path.basename(filename))

class Distribution(models.Model):
    release = models.ForeignKey(Release, related_name="distributions",
                                editable=False)
    content = models.FileField(upload_to=distribution_upload_path)
    md5_digest = models.CharField(max_length=32, blank=True, editable=False)
    filetype = models.ForeignKey(DistributionType, related_name='distributions')
    pyversion = models.ForeignKey(PythonVersion, related_name='distributions', null=True,
                                  help_text='Python version, or None for any version of Python')
    platform = models.ForeignKey(PlatformName, related_name='distributions', null=True,
                                 help_text='Platform name or None if platform agnostic')
    comment = models.CharField(max_length=255, blank=True)
    signature = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    uploader = models.ForeignKey(User, related_name='distributions_uploaded',
                                 editable=False, blank=True, null=True)

    @property
    def filename(self):
        return os.path.basename(self.content.name)

    @property
    def display_filetype(self):
        return self.filetype.name

    @property
    def path(self):
        return self.content.name

    def get_absolute_url(self):
        return "%s#md5=%s" % (self.content.url, self.md5_digest)

    class Meta:
        verbose_name = _(u"distribution")
        verbose_name_plural = _(u"distributions")
        unique_together = ("release", "filetype", "pyversion", "platform")

    def __unicode__(self):
        return self.filename


@receiver(post_delete, sender=Distribution)
def handle_media_delete(instance, **kwargs):
    path = os.path.join(settings.MEDIA_ROOT, instance.path)
    log.info("Deleting file {}".format(path))
    os.remove(path)

class Review(models.Model):
    release = models.ForeignKey(Release, related_name="reviews")
    rating = models.PositiveSmallIntegerField(blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name = _(u'release review')
        verbose_name_plural = _(u'release reviews')

try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^djangopypi2\.apps\.pypi_frontend\.models\.PackageInfoField"])
except ImportError:
    pass
