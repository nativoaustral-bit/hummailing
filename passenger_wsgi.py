#!/home1/paulocis/MAILING/venv/bin/python
import sys, os

sys.path.insert(0, '/home1/paulocis/MAILING')

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from config.wsgi import application as _application

def application(environ, start_response):
    environ['SCRIPT_NAME'] = ''
    if environ.get('HTTP_X_FORWARDED_PROTO') == 'https' or environ.get('HTTPS') in ('on', '1') or environ.get('HTTP_X_FORWARDED_SSL') == 'on':
        environ['wsgi.url_scheme'] = 'https'
    try:
        return _application(environ, start_response)
    except Exception as exc:
        import traceback, json
        tb = traceback.format_exc()
        try:
            for log_candidate in ['/home1/paulocis/private/hummailing_data/logs/crash.log', '/home1/paulocis/MAILING/logs/crash.log']:
                try:
                    with open(log_candidate, 'a') as f:
                        f.write(f"\n--- WSGI CRASH ---\n{tb}\n")
                    break
                except Exception:
                    continue
        except Exception:
            pass

        is_ajax = (
            environ.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or
            'application/json' in environ.get('HTTP_ACCEPT', '')
        )
        if is_ajax:
            body = json.dumps({'status': 'error', 'message': f"WSGI Error: {str(exc)}", 'traceback': tb}).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))])
            return [body]
        else:
            body = f"<h1>500 Internal Server Error</h1><pre>{tb}</pre>".encode('utf-8')
            start_response('500 Internal Server Error', [('Content-Type', 'text/html'), ('Content-Length', str(len(body)))])
            return [body]

if __name__ == '__main__' or 'GATEWAY_INTERFACE' in os.environ:
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(application)
