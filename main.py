from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib
from urllib.parse import urlparse, unquote_plus
import mimetypes
from pathlib import Path
import json
import socket
import logging
from multiprocessing import Process
from dotenv import dotenv_values
from datetime import datetime

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

config = dotenv_values(".env_mongo")

# MongoDB Docker container is running on localhost with the default port
MONGO_HOST = "mongodb"
MONGO_PORT = 27017
MONGO_DB = "CS_final_project"

URI_DB = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"
#URI_DB = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"
BASE_DIR = Path(__file__).parent

CHUNK_SIZE = 1024
HTTP_PORT = 3000
SOCKET_PORT = 5000
HTTP_HOST = "0.0.0.0"
SOCKET_HOST = "127.0.0.1"

class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        elif pr_url.path == '/message':
            self.send_html_file('message.html')
        else:
            if Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file('error.html', 404)

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        data = self.rfile.read(size)

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(data, (SOCKET_HOST, SOCKET_PORT))
            client_socket.close()
        except socket.error:
            logging.error("Failed to send data")

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", 'text/plain')

        self.end_headers()
        with open(f'.{self.path}', 'rb') as file:
            self.wfile.write(file.read())

def run_http_server():
    httpd = HTTPServer((HTTP_HOST, HTTP_PORT), HttpHandler)  # noqa
    try:
        logging.info(f"Server started: http://{HTTP_HOST}:{HTTP_PORT}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(e)
    finally:
        logging.info("Server stopped")
        httpd.server_close()

def save_to_db(data):
    client = MongoClient(URI_DB)
    db = client.CS_final_project
    try:
        data = unquote_plus(data)
        parse_data = dict([i.split("=") for i in data.split("&")])
        parse_data['date'] = datetime.now()  # Add current date and time
        print(parse_data)
        db.messages.insert_one(parse_data)
    except Exception as e:
        logging.error(e)
    finally:
        client.close()

def run_socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((SOCKET_HOST, SOCKET_PORT))
    logging.info(f"Server started: socket://{SOCKET_HOST}:{SOCKET_PORT}")
    try:
        while True:
            data, addr = s.recvfrom(CHUNK_SIZE)
            logging.info(f"Received from {addr}: {data.decode()}")
            save_to_db(data.decode())
    except Exception as e:
        logging.error(e)
    finally:
        logging.info("Server socket stopped")
        s.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(processName)s - %(message)s")
    http_process = Process(target=run_http_server, name="HTTP_Server")
    socket_process = Process(target=run_socket_server, name="SOCKET_Server")
    http_process.start()
    socket_process.start()
    http_process.join()
    socket_process.join()

