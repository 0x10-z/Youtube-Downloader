from flask import Flask, render_template, request, jsonify, send_file
from pytube import YouTube
import os

app = Flask(__name__)

# Ruta principal que renderiza el HTML
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para procesar el enlace de YouTube
@app.route('/download', methods=['POST'])
def download_video():
    try:
        youtube_url = request.form['youtube_url']
        yt = YouTube(youtube_url)
        
        # Obtener la mejor resolución disponible
        stream = yt.streams.filter(progressive=True)
        video_title = yt.title
        print(youtube_url)
        # Descargar el video en el servidor
        download_path = stream.download(output_path='downloads/')
        return jsonify({'title': video_title, 'file_path': download_path})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 400

# Ruta para descargar el archivo después de procesar el enlace
@app.route('/download_file/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    # Asegúrate de que la carpeta 'downloads' exista
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True)
