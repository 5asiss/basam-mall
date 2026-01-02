from flask import Flask, send_from_directory
import os

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    # index.html 파일이 있는지 확인하고 보여줌
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    # Render 환경에서는 포트 번호를 환경변수에서 가져와야 함
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)