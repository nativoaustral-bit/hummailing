#!/home1/paulocis/MAILING/venv/bin/python
import sys, os

sys.path.insert(0, '/home1/paulocis/MAILING')

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from config.wsgi import application as _application

def application(environ, start_response):
    environ['SCRIPT_NAME'] = ''
    return _application(environ, start_response)

if __name__ == '__main__' or 'GATEWAY_INTERFACE' in os.environ:
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(application)
