from flask import Flask, render_template, request, jsonify, Response, send_from_directory
import cv2
import threading
import time
import os
import logging
app = Flask(__name__)
import json
# Set up logging
logging.basicConfig(level=logging.DEBUG)
# RTSP URLs for the cameras
rtsp_urls = [
    'rtsp://admin:Phunggi@911@192.168.3.56:554/profile2/media.smp',
    'rtsp://admin:Phunggi@911@192.168.3.60:554/profile2/media.smp',
    'rtsp://admin:Phunggi@911@192.168.3.50:554/profile2/media.smp'
]

recording = False
threads = []
camera_frames = [None, None, None]
recording_type = "crowd"  # Default recording type
folder_name = ""  # Global variable to store the folder name

# Base directory to save the videos
base_video_dir = './videos'
os.makedirs(base_video_dir, exist_ok=True)

def record_camera(url, camera_id):
    global recording, camera_frames, recording_type, folder_name
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Error: Couldn't open camera {camera_id}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 20.0  # Default to 20.0 if camera doesn't provide FPS
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    timestamp = int(time.time())
    filename = f'{folder_name}_camera_{camera_id}.mp4'
    filepath = os.path.join(base_video_dir, folder_name, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
    if not out.isOpened():
        print(f"Error: Couldn't open VideoWriter for camera {camera_id}")
        cap.release()
        return

    while recording:
        ret, frame = cap.read()
        if not ret:
            print(f"Error: Couldn't read frame from camera {camera_id}")
            break
        camera_frames[camera_id-1] = frame
        if frame.shape[1] != width or frame.shape[0] != height:
            frame = cv2.resize(frame, (width, height))
        out.write(frame)

    cap.release()
    out.release()
    print(f"Recording stopped for camera {camera_id}")

def gen_frames(camera_id):
    while True:
        if camera_frames[camera_id-1] is not None:
            small_frame = cv2.resize(camera_frames[camera_id-1], (320, 240))
            ret, buffer = cv2.imencode('.jpg', small_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)

@app.route('/')
def index():
    video_files = []
    for root, dirs, files in os.walk(base_video_dir):
        for file in files:
            if file.endswith('.mp4'):
                rel_dir = os.path.relpath(root, base_video_dir)
                video_files.append(os.path.join(rel_dir, file))
    return render_template('index.html', video_files=video_files)

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(base_video_dir, filename)

@app.route('/video_feed/<int:camera_id>')
def video_feed(camera_id):
    return Response(gen_frames(camera_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global recording, threads, recording_type, folder_name
    if not recording:
        recording_type = request.json['recordingType']
        folder_name = request.json['filename']
        if not folder_name:
            return jsonify({"status": "Error: Filename is required"})
        
        recording = True
        for i, url in enumerate(rtsp_urls):
            thread = threading.Thread(target=record_camera, args=(url, i+1))
            thread.start()
            threads.append(thread)
        return jsonify({"status": f"Recording started - {recording_type}", "filename": folder_name})
    return jsonify({"status": "Already recording"})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global recording, threads
    if recording:
        recording = False
        for thread in threads:
            thread.join()
        threads = []
        return jsonify({"status": "Recording stopped"})
    return jsonify({"status": "Not recording"})

@app.route('/create_json', methods=['POST'])
def create_json():
    try:
        data = request.json
        logging.debug(f"Received data: {data}")

        folder_name = data.get('folderName')
        people = data.get('people')

        if not folder_name or not people:
            return jsonify({"error": "Missing folderName or people data"}), 400

        json_data = {
            "name": folder_name,
            "description": people
        }

        json_file_path = os.path.join(base_video_dir, folder_name, f"{folder_name}_info.json")
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

        logging.debug(f"Attempting to write JSON to: {json_file_path}")
        logging.debug(f"JSON data: {json_data}")

        with open(json_file_path, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)

        logging.info(f"JSON file created successfully at {json_file_path}")
        return jsonify({"status": "JSON file created successfully"})

    except json.JSONDecodeError as e:
        logging.error(f"JSON Decode Error: {str(e)}")
        return jsonify({"error": "Invalid JSON data"}), 400
    except IOError as e:
        logging.error(f"I/O Error: {str(e)}")
        return jsonify({"error": "Error writing JSON file"}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/get_json/<folder_name>')
def get_json(folder_name):
    json_file_path = os.path.join(base_video_dir, folder_name, f"{folder_name}_info.json")
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        return jsonify(data)
    else:
        return jsonify({"error": "JSON file not found"}), 404

# ... (rest of the previous code remains the same)

if __name__ == '__main__':
    app.run(debug=True)
if __name__ == '__main__':
    app.run(debug=True)