from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook-server")

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        logger.info(f"📩 Received POST request to {self.path}")
        logger.info(f"Headers: {self.headers}")
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            print("\n----- WEBHOOK PAYLOAD -----")
            print(json.dumps(data, indent=2))
            print("---------------------------\n")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "received"}).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error parsing JSON: {e}")
            self.send_response(400)
            self.end_headers()

def run(server_class=HTTPServer, handler_class=WebhookHandler, port=9999):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logger.info(f"🚀 Webhook server started on port {port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logger.info("Server stopped.")

if __name__ == '__main__':
    run()
