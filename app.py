import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from pytube import YouTube
import subprocess
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)  # Enable WebSockets with SocketIO

downloads_folder_name = 'downloads'

# Utility function to delete all files in the downloads folder
def clear_downloads_folder():
    for filename in os.listdir(downloads_folder_name):
        file_path = os.path.join(downloads_folder_name, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f'Error deleting file {file_path}: {e}')

# Utility function to emit progress status and sleep to ensure real-time transmission
def emit_status(message, progress):
    emit('status', {'message': message, 'progress': progress})
    socketio.sleep(0)

# Utility function to handle video and audio combination
def combine_video_audio(video_path, audio_path, output_path):
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path, 
        '-c', 'copy', output_path, '-y'
    ]
    try:
        subprocess.run(command, check=True)
    except Exception as e:
        print(f'Error combining video and audio: {e}')
        return False
    return True

# Main route to render the form
@app.route('/')
def index():
    return render_template('index.html')


# Route to serve the downloaded files
@app.route('/downloads/<filename>')
def download_file(filename):
    try:
        return send_from_directory(downloads_folder_name, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

# Route to get available resolutions from a YouTube URL
@app.route('/get-resolutions', methods=['POST'])
def get_resolutions():
    youtube_url = request.json.get('youtube_url')

    if not youtube_url:
        return jsonify({'error': 'No YouTube URL provided'})

    try:
        yt = YouTube(youtube_url)
        video_title = yt.title
        
        # Get video and audio streams
        video_streams = yt.streams.filter(only_video=True, file_extension='mp4').order_by('resolution').desc()
        audio_streams = yt.streams.filter(only_audio=True, file_extension='mp4')

        # Combine video and audio streams in one list
        resolutions = [{
            'itag': stream.itag,
            'url': stream.url,
            'quality': stream.resolution if stream.resolution else 'Audio Only',
            'mime_type': stream.mime_type,
            'is_video': stream.includes_video_track,
            'is_audio': stream.includes_audio_track,
            'title': video_title
        } for stream in video_streams]

        # Add audio-only streams at the end
        resolutions += [{
            'itag': stream.itag,
            'url': stream.url,
            'quality': 'Audio Only',
            'mime_type': stream.mime_type,
            'is_video': False,
            'is_audio': True,
            'title': video_title
        } for stream in audio_streams]

        return jsonify({'resolutions': resolutions})

    except Exception as e:
        return jsonify({'error': str(e)})

# WebSocket event to handle video download
@socketio.on('download_video')
def handle_download_video(data):
    youtube_url = data.get('url')
    itag = data.get('itag')
    title = data.get('title')
    resolution = data.get('resolution')

    if not youtube_url or not itag or not title or not resolution:
        emit_status('Missing parameters', 0)
        return

    try:
        clear_downloads_folder()

        yt = YouTube(youtube_url)
        stream = yt.streams.get_by_itag(itag)

        sanitized_title = f"{title} ({resolution})".replace("/", "-")
        video_path = os.path.join('downloads', f"{sanitized_title}_video.mp4")
        audio_path = os.path.join('downloads', f"{sanitized_title}_audio.mp4")
        output_path = os.path.join('downloads', f"{sanitized_title}_combined.mp4")

        # Handling video with no audio (separate video and audio)
        if stream.includes_video_track and not stream.includes_audio_track:
            video_stream = stream
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()

            emit_status('Downloading video...', 30)
            video_stream.download(output_path='downloads', filename=f"{sanitized_title}_video.mp4")

            emit_status('Downloading audio...', 60)
            audio_stream.download(output_path='downloads', filename=f"{sanitized_title}_audio.mp4")

            emit_status('Combining video and audio...', 90)
            if combine_video_audio(video_path, audio_path, output_path):
                emit_status('Download completed!', 100)
                emit('download_complete', {'file': f"{sanitized_title}_combined.mp4"})
            else:
                emit('status', {'error': 'Error combining audio and video'})
        else:
            # Handling progressive stream with both video and audio
            emit_status('Downloading video with audio...', 50)
            stream.download(output_path='downloads', filename=sanitized_title)

            emit_status('Download completed!', 100)
            emit('download_complete', {'file': f"{sanitized_title}.mp4"})

    except Exception as e:
        emit('status', {'error': f"Error during the process: {str(e)}"})

if __name__ == '__main__':
    if not os.path.exists(downloads_folder_name):
        os.makedirs(downloads_folder_name)

    socketio.run(app, debug=True)
