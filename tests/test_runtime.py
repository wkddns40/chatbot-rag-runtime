"""Run inside Compose: docker compose exec -T app python -m unittest discover -s tests -v"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from app import main


class ModelHandler(BaseHTTPRequestHandler):
    received = None
    fail = False

    def log_message(self, *args):
        pass

    def do_POST(self):
        ModelHandler.received = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        for text in ['검증된 ', '스트리밍 응답 [1]']:
            self.wfile.write(('data: ' + json.dumps({'choices': [{'delta': {'content': text}}]}) + '\n\n').encode())
        if not ModelHandler.fail:
            self.wfile.write(b'data: [DONE]\n\n')


class RuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        cls.client.__enter__()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ModelHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.client.__exit__(None, None, None)

    def setUp(self):
        main.LLM = ''
        ModelHandler.fail = False
        self.headers = {'Authorization': 'Bearer ' + os.environ['ADMIN_TOKEN']}
        self.reader = {'Authorization': 'Bearer ' + os.environ['READER_TOKEN']}
        self.key = self.client.post('/api/conversations', headers=self.headers).json()['id']

    def chat(self, question, mode='rag', headers=None, key=None):
        response = self.client.post('/api/chat', headers=headers or self.headers,
                                    json={'conversation_id': key or self.key, 'question': question, 'mode': mode})
        self.assertEqual(response.status_code, 200)
        return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]

    def document(self, body, acl='public'):
        result = self.client.post('/api/documents', headers=self.headers,
                                  data={'acl': acl}, files={'file': ('sample.md', body.encode(), 'text/markdown')})
        self.assertEqual(result.status_code, 200)
        return result.json()['id']

    def test_auth_and_ownership(self):
        self.assertEqual(self.client.get('/api/conversations').status_code, 401)
        self.assertEqual(self.client.get(f'/api/conversations/{self.key}', headers=self.reader).status_code, 404)
        self.assertEqual(self.client.get('/api/documents', headers=self.reader).status_code, 403)
        self.assertEqual(self.client.post('/api/chat', headers=self.headers,
            json={'conversation_id':self.key,'question':'test','role':'admin'}).status_code, 422)

    def test_approval_and_acl(self):
        marker = 'violet-' + uuid4().hex
        doc = self.document(marker, 'admin')
        pending = self.chat(marker)
        self.assertNotIn(doc, json.dumps(pending))
        self.assertEqual(self.client.post(f'/api/documents/{doc}/approve', headers=self.reader).status_code, 403)
        self.assertEqual(self.client.post(f'/api/documents/{doc}/approve', headers=self.headers).status_code, 200)
        approved = self.chat(marker)
        self.assertIn(doc, json.dumps(approved))
        key = self.client.post('/api/conversations', headers=self.reader).json()['id']
        self.assertNotIn(doc, json.dumps(self.chat(marker, headers=self.reader, key=key)))

    def test_public_sources_and_persistence(self):
        marker = 'approved-' + uuid4().hex
        doc = self.document(marker)
        self.client.post(f'/api/documents/{doc}/approve', headers=self.headers)
        key = self.client.post('/api/conversations', headers=self.reader).json()['id']
        events = self.chat(marker, headers=self.reader, key=key)
        self.assertEqual(events[-1]['type'], 'done')
        self.assertIn(doc, json.dumps(events))
        saved = self.client.get(f'/api/conversations/{key}', headers=self.reader).json()
        self.assertEqual(len(saved), 2)
        self.assertTrue(saved[-1]['sources'])

    def test_attachment_is_not_global_rag(self):
        marker = 'attachment-' + uuid4().hex
        response = self.client.post(f'/api/conversations/{self.key}/attachments', headers=self.headers,
                                    files={'file': ('attachment.txt', marker.encode(), 'text/plain')})
        self.assertEqual(response.status_code, 200)
        events = self.chat(marker, mode='attachment')
        self.assertIn(marker, json.dumps(events))
        other = self.client.post('/api/conversations', headers=self.headers).json()['id']
        self.assertNotIn(marker, json.dumps(self.chat(marker, mode='attachment', key=other)))
        self.assertNotIn(marker, json.dumps(self.chat(marker, mode='rag', key=other)))

    def test_upload_validation(self):
        for name, data, status in [('file.exe', b'bad',422), ('file.pdf',b'bad',422),
                                   ('empty.txt',b'',422), ('large.txt',b'a'*2_000_001,413)]:
            response = self.client.post('/api/documents',headers=self.headers,files={'file':(name,data)})
            self.assertEqual(response.status_code,status)

    def test_real_sse_transport_and_fail_closed(self):
        main.LLM = f'http://127.0.0.1:{self.server.server_port}/v1'
        events = self.chat('hello', mode='chat')
        self.assertEqual(events[-1]['type'],'done')
        self.assertEqual(''.join(e.get('text','') for e in events),'검증된 스트리밍 응답 [1]')
        self.assertEqual(ModelHandler.received['model'],main.MODEL)
        self.assertTrue(ModelHandler.received['stream'])
        ModelHandler.fail = True
        events = self.chat('interrupted',mode='chat')
        self.assertEqual(events[-1]['type'],'error')
        saved = self.client.get(f'/api/conversations/{self.key}',headers=self.headers).json()
        self.assertEqual(len(saved),2)

    def test_feedback_and_ui(self):
        self.assertEqual(self.client.post('/api/feedback',headers=self.headers,
                          json={'conversation_id':self.key,'rating':1}).status_code,200)
        page = self.client.get('/')
        self.assertEqual(page.status_code,200)
        self.assertIn("frame-ancestors 'none'",page.headers['Content-Security-Policy'])


if __name__ == '__main__':
    unittest.main()
