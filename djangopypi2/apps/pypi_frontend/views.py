from django.http import Http404
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.views.generic.list import ListView
from ..pypi_ui.shortcuts import render_to_response
from ..pypi_packages.models import Package
from ..pypi_packages.models import Release
from .models import MirrorSite
from . import xmlrpc_views
from . import distutils_request
import shutil

@csrf_exempt
def index(request):
    """ Root view of the package index, handle incoming actions from distutils
    or redirect to a more user friendly view """
    if xmlrpc_views.is_xmlrpc_request(request):
        return xmlrpc_views.handle_xmlrpc_request(request)

    if distutils_request.is_distutils_request(request):
        return distutils_request.handle_distutils_request(request)

    return HttpResponseRedirect(reverse('djangopypi2-packages-index'))

class SimpleIndex(ListView):
    model = Package
    template_name = 'pypi_frontend/package_list_simple.html'
    context_object_name = 'packages'

import os.path
from contextlib import contextmanager
from django.core.files.base import File
from django.contrib.auth.models import User
from django.utils.datastructures import MultiValueDict
from ..pypi_metadata.models import Classifier, DistributionType
from setuptools.package_index import PackageIndex
import pkginfo

@contextmanager
def tempdir():
    """Simple context that provides a temporary directory that is deleted
    when the context is exited."""
    import tempfile
    d = tempfile.mkdtemp(".tmp", "djangopypi.")
    yield d
    shutil.rmtree(d)

def _save_package(path, ownerid):
    meta = _get_meta(path)

    try:
        # can't use get_or_create as that demands there be an owner
        package = Package.objects.get(name=meta.name)
        isnewpackage = False
    except Package.DoesNotExist:
        package = Package(name=meta.name)
        isnewpackage = True

    release = package.get_release(meta.version)
    if not isnewpackage and release and release.version == meta.version:
        print "%s-%s already added" % (meta.name, meta.version)
        return

    # algorithm as follows: If owner is given, try to grab user with that
    # username from db. If doesn't exist, bail. If no owner set look at
    # mail address from metadata and try to get that user. If it exists
    # use it. If not, bail.
    owner = None

    if ownerid:
        try:
            if "@" in ownerid:
                owner = User.objects.get(email=ownerid)
            else:
                owner = User.objects.get(username=ownerid)
        except User.DoesNotExist:
            pass
    else:
        try:
            owner = User.objects.get(email=meta.author_email)
        except User.DoesNotExist:
            pass

    if not owner:
        print "No owner defined. Use --owner to force one"
        return

    # at this point we have metadata and an owner, can safely add it.
    package.save()

    package.owners.add(owner)
    package.maintainers.add(owner)

    release = Release()

    for classifier in meta.classifiers:
        release.classifiers.append(
                Classifier.objects.get_or_create(name=classifier)[0])

    release.version = meta.version
    release.package = package
    release.metadata_version = meta.metadata_version
    package_info = MultiValueDict()
    package_info.update(meta.__dict__)
    release.package_info = package_info
    release.save()

    file = File(open(path, "rb"))
    if isinstance(meta, pkginfo.SDist):
        dist = 'sdist'
    elif meta.filename.endswith('.rmp') or meta.filename.endswith('.srmp'):
        dist = 'bdist_rpm'
    elif meta.filename.endswith('.exe'):
        dist = 'bdist_wininst'
    elif meta.filename.endswith('.egg'):
        dist = 'bdist_egg'
    elif meta.filename.endswith('.dmg'):
        dist = 'bdist_dmg'
    else:
        dist = 'bdist_dumb'
    release.distributions.create(content=file, uploader=owner, filetype=DistributionType(dist))
    print "%s-%s added" % (meta.name, meta.version)

def _get_meta(path):
    data = pkginfo.get_metadata(path)
    if data:
        return data
    else:
        print "Couldn't get metadata from %s. Not added to chishop" % os.path.basename(path)
        return None
    pass

def _cache_add_package(label):
    pypi = PackageIndex()
    with tempdir() as tmp:
        path = pypi.download(label, tmp)
        if path:
            _save_package(path, "pypi")

def _cache_if_not_found(proxy_folder):
    def decorator(func):
        def internal(request, package_name, version=None):
            try:
                return func(request, package_name, version)
            except Http404:
                if version:
                    label = "%s==%s" % (package_name, version)
                else:
                    label = package_name
                try:
                    print _cache_add_package(label)
                except:
                    print "Pooped crap"
                    import traceback
                    traceback.print_exc()
                else:
                    for mirror_site in MirrorSite.objects.filter(enabled=True):
                        url = '/'.join([mirror_site.url.rstrip('/'), proxy_folder, package_name])
                        mirror_site.logs.create(action='Redirect to ' + url)
                        return HttpResponseRedirect(url)
            raise Http404(u'%s is not a registered package' % (package_name,))
        return internal
    return decorator

def _mirror_if_not_found(proxy_folder):
    def decorator(func):
        def internal(request, package_name):
            try:
                return func(request, package_name)
            except Http404:
                for mirror_site in MirrorSite.objects.filter(enabled=True):
                    url = '/'.join([mirror_site.url.rstrip('/'), proxy_folder, package_name])
                    mirror_site.logs.create(action='Redirect to ' + url)
                    return HttpResponseRedirect(url)
            raise Http404(u'%s is not a registered package' % (package_name,))
        return internal
    return decorator

def simple_details_version(request, package_name, version):
    return simple_details(request, package_name, version)

@_cache_if_not_found('simple')
def simple_details(request, package_name, version=None):
    try:
        package = Package.objects.get(name__iexact=package_name)
    except Package.DoesNotExist:
        package = get_object_or_404(Package, name__iexact=package_name.replace('_', '-'))
    if version and not package.get_release(version):
        raise Http404
    # If the package we found is not exactly the same as the name the user typed, redirect
    # to the proper url:
    if package.name != package_name:
        return HttpResponseRedirect(reverse('djangopypi2-simple-package-info', kwargs=dict(package_name=package.name)))
    return render_to_response('pypi_frontend/package_detail_simple.html',
                              context_instance=RequestContext(request, dict(package=package)),
                              mimetype='text/html')

@_mirror_if_not_found('pypi')
def package_details(request, package_name):
    package = get_object_or_404(Package, name=package_name)
    return HttpResponseRedirect(package.get_absolute_url())

@_mirror_if_not_found('pypi')
def package_doap(request, package_name):
    package = get_object_or_404(Package, name=package_name)
    return render_to_response('pypi_frontend/package_doap.xml',
                              context_instance=RequestContext(request, dict(package=package)),
                              mimetype='text/xml')

def release_doap(request, package_name, version):
    release = get_object_or_404(Release, package__name=package_name, version=version)
    return render_to_response('pypi_frontend/release_doap.xml',
                              context_instance=RequestContext(request, dict(release=release)),
                              mimetype='text/xml')
