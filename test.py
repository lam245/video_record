import cv2

def display_rtsp_stream(rtsp_url):
    # Create a VideoCapture object
    cap = cv2.VideoCapture(rtsp_url)

    while True:
        # Read a frame from the video stream
        ret, frame = cap.read()

        # If frame is read correctly ret is True
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            break

        # Display the frame
        cv2.imshow('RTSP Stream', frame)

        # Press 'q' to quit
        if cv2.waitKey(1) == ord('q'):
            break

    # Release the VideoCapture object and close windows
    cap.release()
    cv2.destroyAllWindows()

# Replace this with your RTSP stream URL
rtsp_url = "rtsp://admin:Phunggi@911@192.168.3.27:554/profile2/media.smp"

display_rtsp_stream(rtsp_url)