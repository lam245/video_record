import cv2
import threading
import time
from flask import Flask, Response, render_template_string, request, jsonify
import os

app = Flask(__name__)

# Global variables
camera_streams = {}
camera_prefix = "camera"
recording_status = False
video_writers = {}

def read_rtsp_streams(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def capture_and_record(stream_url, camera_id):
    global camera_streams, recording_status, video_writers
    cap = cv2.VideoCapture(stream_url)
    
    if not cap.isOpened():
        print(f"Error opening video stream for camera {camera_id}")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        camera_streams[camera_id] = frame

        if recording_status:
            if camera_id not in video_writers:
                output_filename = f"{camera_prefix}_{camera_id}_output.mp4"
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writers[camera_id] = cv2.VideoWriter(output_filename, fourcc, 20.0, (frame_width, frame_height))
            video_writers[camera_id].write(frame)
        elif camera_id in video_writers:
            video_writers[camera_id].release()
            del video_writers[camera_id]

    cap.release()
    if camera_id in video_writers:
        video_writers[camera_id].release()

def generate_frames(camera_id):
    while True:
        if camera_id in camera_streams:
            frame = camera_streams[camera_id]
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multi-Camera Recorder</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
        <script>
            function updatePrefix() {
                $.post('/update_prefix', { prefix: $('#prefix').val() }, function() {
                    location.reload();
                });
            }
            function toggleRecording() {
                $.post('/toggle_recording', function(response) {
                    $('#record_btn').text(response.status ? 'Stop Recording' : 'Start Recording');
                });
            }
            function saveVideos() {
                $.post('/save_videos', function(response) {
                    alert(response.message);
                });
            }
        </script>
    </head>
    <body>
        <h1>Multi-Camera Recorder</h1>
        <input type="text" id="prefix" placeholder="Enter camera prefix">
        <button onclick="updatePrefix()">Update Prefix</button>
        <button id="record_btn" onclick="toggleRecording()">
            {% if recording_status %}Stop Recording{% else %}Start Recording{% endif %}
        </button>
        <button onclick="saveVideos()">Save All Videos</button>
        {% for camera_id in camera_streams.keys() %}
        <h2>{{ camera_prefix }}_{{ camera_id }}</h2>
        <img src="{{ url_for('video_feed', camera_id=camera_id) }}" width="320" height="240"><br>
        {% endfor %}
    </body>
    </html>
    ''', camera_streams=camera_streams, camera_prefix=camera_prefix, recording_status=recording_status)

@app.route('/video_feed/<camera_id>')
def video_feed(camera_id):
    return Response(generate_frames(camera_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/update_prefix', methods=['POST'])
def update_prefix():
    global camera_prefix
    camera_prefix = request.form['prefix']
    return jsonify(success=True)

@app.route('/toggle_recording', methods=['POST'])
def toggle_recording():
    global recording_status, video_writers
    recording_status = not recording_status
    
    if not recording_status:
        for camera_id in video_writers:
            video_writers[camera_id].release()
        video_writers.clear()
    
    return jsonify(status=recording_status)

@app.route('/save_videos', methods=['POST'])
def save_videos():
    global video_writers
    if video_writers:
        for camera_id in video_writers:
            video_writers[camera_id].release()
        video_writers.clear()
        return jsonify(message="All videos saved successfully.")
    else:
        return jsonify(message="No active recordings to save.")

if __name__ == '__main__':
    rtsp_file = 'rtsp_streams.txt'
    streams = read_rtsp_streams(rtsp_file)

    for i, stream in enumerate(streams):
        threading.Thread(target=capture_and_record, args=(stream, str(i)), daemon=True).start()

    app.run(host='0.0.0.0', port=5000)



    camera_urls = [
    'rtsp://admin:Phunggi@911@192.168.3.56:554/profile2/media.smp',
'rtsp://admin:Phunggi@911@192.168.3.60:554/profile2/media.smp',
'rtsp://admin:Phunggi@911@192.168.3.50:554/profile2/media.smp'
    # Add more camera URLs as needed
]