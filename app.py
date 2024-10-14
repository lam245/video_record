from flask import Flask, render_template, request, jsonify, Response
import cv2
import threading
import time
import os
import logging
import json
from queue import Queue

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
current_filename = 'car_park_config.txt'
view_configs = {
    'lobby': 'lobby_config.txt',
    'car_park': 'car_park_config.txt'
}

def read_camera_config(filename='car_park_config.txt'):
    with open(filename, 'r') as f:
        num_cameras = int(f.readline().strip())
        rtsp_urls = [line.strip() for line in f.readlines()]
    return num_cameras, rtsp_urls

num_cameras, rtsp_urls = read_camera_config()

recording = False
recording_type = "crowd"
base_video_dir = './videos'
os.makedirs(base_video_dir, exist_ok=True)

camera_captures = []
frame_queues = []
camera_locks = []
stop_threads = []

def initialize_cameras():
    global camera_captures, frame_queues, camera_locks, stop_threads
    camera_captures = []
    frame_queues = []
    camera_locks = []
    stop_threads = []
    for url in rtsp_urls:
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            logging.error(f"Error: Couldn't open camera {url}")
            cap = None
        camera_captures.append(cap)
        frame_queues.append(Queue(maxsize=30))
        camera_locks.append(threading.Lock())
        stop_threads.append(threading.Event())

def update_camera_frames(camera_id):
    global camera_captures, frame_queues, camera_locks, stop_threads
    while not stop_threads[camera_id].is_set():
        with camera_locks[camera_id]:
            if camera_id < len(camera_captures) and camera_captures[camera_id] is not None and camera_captures[camera_id].isOpened():
                ret, frame = camera_captures[camera_id].read()
                if ret:
                    if frame_queues[camera_id].full():
                        try:
                            frame_queues[camera_id].get_nowait()
                        except Queue.Empty:
                            pass
                    frame_queues[camera_id].put(frame)
        # time.sleep(0.005)  # Short sleep to prevent busy-waiting
def record_camera(camera_id):
    global recording, frame_queues, recording_type, folder_name, view, section
    cap = camera_captures[camera_id]
    if cap is None or not cap.isOpened():
        logging.error(f"Error: Camera {camera_id} is not available")
        return
    
    fps = 20
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    filename = f'camera_{camera_id+1}.mp4'
    filepath = os.path.join(base_video_dir, folder_name, view, section, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
    if not out.isOpened():
        logging.error(f"Error: Couldn't open VideoWriter for camera {camera_id}")
        return

    while recording:
        if not frame_queues[camera_id].empty():
            frame = frame_queues[camera_id].get()
            # Get the current time
            current_time = time.time()

            # Format the time in a readable way
            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))

            # Put the formatted time on the image
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frame, formatted_time, (50, 150), font, 2, (0, 255, 0), 2, cv2.LINE_AA)
            out.write(frame)
        else:
            time.sleep(0.005)  # Short sleep to prevent busy-waiting

    out.release()
    # cap.release()
    logging.info(f"Recording stopped for camera {camera_id}")
def gen_frames(camera_id):
    while True:
        if camera_id < len(frame_queues) and not frame_queues[camera_id].empty():
            frame = frame_queues[camera_id].get()
            small_frame = cv2.resize(frame, (320, 240))
            ret, buffer = cv2.imencode('.jpg', small_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            time.sleep(0.005)  # Short sleep to prevent busy-waiting

@app.route('/')
def index():
    video_files = []
    for root, dirs, files in os.walk(base_video_dir):
        for file in files:
            if file.endswith('.avi'):
                rel_dir = os.path.relpath(root, base_video_dir)
                video_files.append(os.path.join(rel_dir, file))
    return render_template('index.html', video_files=video_files, num_cameras=num_cameras)
@app.route('/start_recording', methods=['POST'])
def start_recording():
    global recording, recording_type, folder_name, view, section
    if not recording:
        recording_type = request.json['recordingType']
        folder_name = request.json['filename']
        view = request.json['view']
        section = request.json['section']
        if not folder_name:
            return jsonify({"status": "Error: Filename is required"})
        
        recording = True
        for i in range(num_cameras):
            threading.Thread(target=record_camera, args=(i,), daemon=True).start()
        return jsonify({"status": f"Recording started - {recording_type}", "filename": f"{folder_name}/{view}/{section}"})
    return jsonify({"status": "Already recording"})
@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global recording
    if recording:
        recording = False
        return jsonify({"status": "Recording stopped"})
    return jsonify({"status": "Not recording"})
@app.route('/video_feed/<int:camera_id>')
def video_feed(camera_id):
    return Response(gen_frames(camera_id-1),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/change_scene', methods=['POST'])
def change_scene():
    global current_filename, num_cameras, rtsp_urls, camera_captures, frame_queues, camera_locks, stop_threads
    view_name = request.json.get('view')
    
    if view_name in view_configs:
        new_filename = view_configs[view_name]
        if os.path.exists(new_filename):
            current_filename = new_filename
            try:
                # Stop all current camera threads
                for stop_event in stop_threads:
                    stop_event.set()
                time.sleep(0.1)  # Give threads time to stop

                # Close all current camera captures
                for cap in camera_captures:
                    if cap is not None:
                        cap.release()

                # Read new configuration
                num_cameras, rtsp_urls = read_camera_config(current_filename)
                
                # Reinitialize cameras
                initialize_cameras()

                # Start new camera threads
                for i in range(num_cameras):
                    threading.Thread(target=update_camera_frames, args=(i,), daemon=True).start()

                return jsonify({
                    'status': 'success',
                    'message': f'Scene changed to {view_name}',
                    'num_cameras': num_cameras,
                    'rtsp_urls': rtsp_urls
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Error reading config file: {str(e)}'
                }), 400
        else:
            return jsonify({
                'status': 'error',
                'message': f'Config file for {view_name} does not exist'
            }), 400
    else:
        return jsonify({
            'status': 'error',
            'message': 'Invalid view selected'
        }), 400

@app.route('/get_current_config')
def get_current_config():
    try:
        num_cameras, rtsp_urls = read_camera_config(current_filename)
        return jsonify({
            'status': 'success',
            'filename': current_filename,
            'num_cameras': num_cameras,
            'rtsp_urls': rtsp_urls
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error reading config file: {str(e)}'
        }), 400

if __name__ == '__main__':
    initialize_cameras()
    for i in range(num_cameras):
        threading.Thread(target=update_camera_frames, args=(i,), daemon=True).start()
    app.run(debug=True, threaded=True)