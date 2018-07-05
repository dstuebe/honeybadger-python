from __future__ import absolute_import
import re

from six import iteritems

from honeybadger import honeybadger
from honeybadger.plugins import Plugin, default_plugin_manager
from honeybadger.utils import filter_dict

try:
    # Support for Django 1.10...
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    # ...while maintaining support for Django <= 1.9.
    class MiddlewareMixin(object):
        def __init__(self, get_response=None):
            pass

try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local


_thread_locals = local()

REQUEST_LOCAL_KEY = '__django_current_request'


def current_request():
    """
    Return current request for this thread.
    :return: current request for this thread.
    """
    return getattr(_thread_locals, REQUEST_LOCAL_KEY, None)


def set_request(request):
    """
    Set request for current thread.
    :param request: current request.
    """
    setattr(_thread_locals, REQUEST_LOCAL_KEY, request)


def clear_request():
    """
    Clears request for this thread.
    """
    if hasattr(_thread_locals, REQUEST_LOCAL_KEY):
        setattr(_thread_locals, REQUEST_LOCAL_KEY, None)


class DjangoPlugin(Plugin):
    """
    Plugin for generating payload from Django requests.
    """
    def __init__(self):
        super(DjangoPlugin, self).__init__('Django')

    def supports(self, config, context):
        """
        Check whether this is a django request or not.
        :param config: honeybadger configuration.
        :param context: current honeybadger configuration.
        :return: True if this is a django request, False else.
        """
        request = current_request()
        return request is not None and re.match(r'^django\.', request.__module__)

    def generate_payload(self, config, context):
        """
        Generate payload by checking Django request object.
        :param context: current context.
        :param config: honeybadger configuration.
        :return: a dict with the generated payload.
        """
        request = current_request()

        payload = {
            'url': request.build_absolute_uri(),
            'component': request.resolver_match.app_name,
            'action': request.resolver_match.func.__name__,
            'params': {},
            'session': {},
            'cgi_data': dict(request.META),
            'context': context
        }

        if hasattr(request, 'session'):
            payload['session'] = filter_dict(dict(request.session), config.params_filters)

        payload['params'] = filter_dict(dict(getattr(request, request.method)), config.params_filters)

        return payload


class DjangoHoneybadgerMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        super(DjangoHoneybadgerMiddleware, self).__init__(get_response=get_response)
        from django.conf import settings
        if getattr(settings, 'DEBUG'):
            honeybadger.configure(environment='development')
        config_kwargs = dict([(k.lower(), v) for (k, v) in iteritems(getattr(settings, 'HONEYBADGER', {}))])
        honeybadger.configure(**config_kwargs)
        honeybadger.config.set_12factor_config()  # environment should override Django settings
        default_plugin_manager.register(DjangoPlugin())

    def process_request(self, request):
        set_request(request)
        honeybadger.begin_request(request)
        return None

    def process_exception(self, request, exception):
        honeybadger.notify(exception)
        clear_request()
        return None

    def process_response(self, request, response):
        honeybadger.reset_context()
        clear_request()
        return response
