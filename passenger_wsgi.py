#!/home1/paulocis/MAILING/venv/bin/python
import sys, os

sys.path.insert(0, '/home1/paulocis/MAILING')

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from config.wsgi import application as _application

def application(environ, start_response):
    environ['SCRIPT_NAME'] = ''
    if environ.get('HTTP_X_FORWARDED_PROTO') == 'https' or environ.get('HTTPS') in ('on', '1') or environ.get('HTTP_X_FORWARDED_SSL') == 'on':
        environ['wsgi.url_scheme'] = 'https'
    return _application(environ, start_response)

if __name__ == '__main__' or 'GATEWAY_INTERFACE' in os.environ:
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(application)
