import unittest

import sys
from mock import patch

from honeybadger import honeybadger
from honeybadger.config import Configuration
from honeybadger.contrib.flask import FlaskPlugin, FlaskHoneybadger

PY3_2 = sys.version_info[0:2] == (3, 2)


class FlaskPluginTestCase(unittest.TestCase):
    def setUp(self):
        if PY3_2:
            self.skipTest(
                'Flask requires Python3 > 3.2. More info at http://flask.pocoo.org/docs/0.12/python3/#requirements')
        import flask

        self.config = Configuration()

        self.app = flask.Flask(__name__)
        self.app.secret_key = 'safe'
        self.app.config.update({
            'HONEYBADGER_ENVIRONMENT': 'production_flask'
        })
        self.plugin = FlaskPlugin()

        @self.app.route('/test',  methods=['GET', 'POST', 'PUT'])
        def foo():
            return 'bar'

    def test_supports_in_request_context(self):
        with self.app.test_request_context():
            self.assertTrue(self.plugin.supports(self.config, {}))

    def test_supports_no_request_context(self):
        self.assertFalse(self.plugin.supports(self.config, {}))

    def test_get_request_with_headers(self):
        with self.app.test_request_context(path='/test',
                                           base_url='http://server:1234/path',
                                           query_string='a=1&a=2&foo=bar',
                                           headers={
                                               'X-Wizard-Color': 'grey'
                                           }):
            payload = self.plugin.generate_payload(self.config, {'k': 'value'})

            self.assertEqual(payload['url'], 'http://server:1234/path/test')
            self.assertEqual(payload['component'], 'honeybadger.tests.contrib.test_flask')
            self.assertEqual(payload['action'], 'foo')
            self.assertDictEqual(payload['params'], {'a': ['1', '2'], 'foo': ['bar']})
            self.assertDictEqual(payload['session'], {})
            self.assertDictEqual(payload['cgi_data'], {
                'Content-Length': '0',
                'Host': 'server:1234',
                'X-Wizard-Color': 'grey',
                'REQUEST_METHOD': 'GET'
            })
            self.assertDictEqual(payload['context'], {'k': 'value'})

    def test_get_request_with_session(self):
        with self.app.test_request_context(path='/test', base_url='http://server:1234/path') as ctx:
            ctx.session['answer'] = 42
            ctx.session['password'] = 'this is fine'

            payload = self.plugin.generate_payload(self.config, {'k': 'value'})

            self.assertEqual(payload['url'], 'http://server:1234/path/test')
            self.assertEqual(payload['component'], 'honeybadger.tests.contrib.test_flask')
            self.assertEqual(payload['action'], 'foo')
            self.assertDictEqual(payload['params'], {})
            self.assertDictEqual(payload['session'], {'answer': 42, 'password': '[FILTERED]'})
            self.assertDictEqual(payload['cgi_data'], {
                'Content-Length': '0',
                'Host': 'server:1234',
                'REQUEST_METHOD': 'GET'
            })
            self.assertDictEqual(payload['context'], {'k': 'value'})

    def test_post_request(self):
        with self.app.test_request_context(path='/test', base_url='http://server:1234/path', method='POST',
                                           data={'foo': 'bar', 'password': 'this is file'}):

            payload = self.plugin.generate_payload(self.config, {'k': 'value'})

            self.assertEqual(payload['url'], 'http://server:1234/path/test')
            self.assertEqual(payload['component'], 'honeybadger.tests.contrib.test_flask')
            self.assertEqual(payload['action'], 'foo')
            self.assertDictEqual(payload['params'], {'foo': ['bar'], 'password': '[FILTERED]'})
            self.assertDictEqual(payload['session'], {})
            self.assertDictEqual(payload['cgi_data'], {
                'Host': 'server:1234',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Content-Length': '29',
                'REQUEST_METHOD': 'POST'
            })
            self.assertDictEqual(payload['context'], {'k': 'value'})

    def test_put_request(self):
        with self.app.test_request_context(path='/test', base_url='http://server:1234/path', method='PUT',
                                           data={'foo': 'bar', 'password': 'this is file'}):

            payload = self.plugin.generate_payload(self.config, {'k': 'value'})

            self.assertEqual(payload['url'], 'http://server:1234/path/test')
            self.assertEqual(payload['component'], 'honeybadger.tests.contrib.test_flask')
            self.assertEqual(payload['action'], 'foo')
            self.assertDictEqual(payload['params'], {'foo': ['bar'], 'password': '[FILTERED]'})
            self.assertDictEqual(payload['session'], {})
            self.assertDictEqual(payload['cgi_data'], {
                'Host': 'server:1234',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Content-Length': '29',
                'REQUEST_METHOD': 'PUT'
            })
            self.assertDictEqual(payload['context'], {'k': 'value'})


class FlaskHoneybadgerTestCase(unittest.TestCase):

    def setUp(self):
        if PY3_2:
            self.skipTest(
                'Flask requires Python3 > 3.2. More info at http://flask.pocoo.org/docs/0.12/python3/#requirements')

        import flask
        import werkzeug

        self.default_headers = {
           'Content-Length': '0',
           'Host': 'localhost',
           'User-Agent': 'werkzeug/%s' % werkzeug.__version__
        }
        self.app = flask.Flask(__name__)
        self.app.config.update({
            'environment': 'production_flask',
            'api_key': 'abcd'
        })

    def assert_called_with_exception_type(self, mock_hb, exc_type):
        self.assertEqual(1, mock_hb.notify.call_count)
        self.assertEqual(exc_type, type(mock_hb.notify.call_args[0][0]))

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_with_auto_report_exceptions(self, mock_hb):
        FlaskHoneybadger(self.app, report_exceptions=True)

        @self.app.route('/error')
        def error():
            return 1 / 0

        self.app.test_client().get('/error?a=1&b=2&b=3')

        self.assert_called_with_exception_type(mock_hb, ZeroDivisionError)

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_without_auto_report_exceptions(self, mock_hb):
        FlaskHoneybadger(self.app, report_exceptions=False)

        @self.app.route('/error')
        def error():
            return 1 / 0

        self.app.test_client().get('/error?a=1&b=2&b=3')

        mock_hb.notify.assert_not_called()

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_auto_report_exceptions_with_blueprint(self, mock_hb):
        from flask import Blueprint
        FlaskHoneybadger(self.app, report_exceptions=True)

        bp = Blueprint('blueprint', __name__)

        @bp.route('/error')
        def error():
            return 1 / 0

        self.app.register_blueprint(bp)

        self.app.test_client().get('/error?a=1&b=2&b=3')

        self.assert_called_with_exception_type(mock_hb, ZeroDivisionError)

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_auto_report_exceptions_with_view_class(self, mock_hb):
        from flask.views import MethodView

        FlaskHoneybadger(self.app, report_exceptions=True)

        class ErrorView(MethodView):
            def get(self):
                return 1 / 0
        self.app.add_url_rule('/error', view_func=ErrorView.as_view('error'))

        self.app.test_client().get('/error?a=1&b=2&b=3')

        self.assert_called_with_exception_type(mock_hb, ZeroDivisionError)

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_dont_reset_context_with_exception(self, mock_hb):
        from flask.views import MethodView

        FlaskHoneybadger(self.app, report_exceptions=True, reset_context_after_request=False)

        honeybadger.set_context(foo='bar')

        class ErrorView(MethodView):
            def get(self):
                return 1 / 0

        self.app.add_url_rule('/error', view_func=ErrorView.as_view('error'))

        self.app.test_client().get('/error?a=1&b=2&b=3')

        self.assert_called_with_exception_type(mock_hb, ZeroDivisionError)
        mock_hb.reset_context.assert_not_called()

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_dont_reset_context_when_not_reporting(self, mock_hb):
        from flask.views import MethodView

        FlaskHoneybadger(self.app, report_exceptions=False, reset_context_after_request=False)

        honeybadger.set_context(foo='bar')

        class ErrorView(MethodView):
            def get(self):
                return 1 / 0

        self.app.add_url_rule('/error', view_func=ErrorView.as_view('error'))

        self.app.test_client().get('/error?a=1&b=2&b=3')

        mock_hb.notify.assert_not_called()
        mock_hb.reset_context.assert_not_called()

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_reset_context_when_not_reporting(self, mock_hb):
        from flask.views import MethodView

        FlaskHoneybadger(self.app, report_exceptions=False, reset_context_after_request=True)

        honeybadger.set_context(foo='bar')

        class ErrorView(MethodView):
            def get(self):
                return 1 / 0

        self.app.add_url_rule('/error', view_func=ErrorView.as_view('error'))

        self.app.test_client().get('/error?a=1&b=2&b=3')

        mock_hb.notify.assert_not_called()
        self.assertEqual(1, mock_hb.reset_context.call_count)

    @patch('honeybadger.contrib.flask.honeybadger')
    def test_reset_context_when_reporting(self, mock_hb):
        from flask.views import MethodView

        FlaskHoneybadger(self.app, report_exceptions=True, reset_context_after_request=True)

        honeybadger.set_context(foo='bar')

        class ErrorView(MethodView):
            def get(self):
                return 1 / 0

        self.app.add_url_rule('/error', view_func=ErrorView.as_view('error'))

        self.app.test_client().get('/error?a=1&b=2&b=3')

        self.assert_called_with_exception_type(mock_hb, ZeroDivisionError)
        self.assertEqual(2, mock_hb.reset_context.call_count)
