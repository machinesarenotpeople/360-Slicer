import cv2
import numpy as np
import os
import sys
import argparse
import glob

def get_perspective_map(img_w, img_h, fov, yaw, pitch, eq_w, eq_h):
    """
    Generates the X and Y mapping arrays for cv2.remap to convert 
    equirectangular to perspective.
    """
    # 1. Create a meshgrid of pixel coordinates
    x, y = np.meshgrid(np.linspace(-1, 1, img_w), np.linspace(-1, 1, img_h))
    
    # 2. Calculate focal length based on FOV
    # We assume the camera is at (0,0,0) looking down Z
    f = 0.5 / np.tan(np.deg2rad(fov) / 2)
    
    # 3. Convert image plane (x,y) to 3D vectors (x, y, f)
    # Note: In standard CV coords, Y is down. 
    z = np.ones_like(x) * f
    vectors = np.stack([x, -y, z], axis=-1) # (H, W, 3)
    
    # Normalize vectors
    norm = np.linalg.norm(vectors, axis=-1, keepdims=True)
    vectors = vectors / norm
    
    # 4. Apply Rotation (Yaw and Pitch)
    # Rotation matrices
    # Pitch (Rotate around X axis)
    rx = np.array([
        [1, 0, 0],
        [0, np.cos(np.deg2rad(pitch)), -np.sin(np.deg2rad(pitch))],
        [0, np.sin(np.deg2rad(pitch)), np.cos(np.deg2rad(pitch))]
    ])
    
    # Yaw (Rotate around Y axis)
    ry = np.array([
        [np.cos(np.deg2rad(yaw)), 0, np.sin(np.deg2rad(yaw))],
        [0, 1, 0],
        [-np.sin(np.deg2rad(yaw)), 0, np.cos(np.deg2rad(yaw))]
    ])
    
    # Apply rotations: Global_Vec = Ry * Rx * Local_Vec
    # We transpose for matrix multiplication with the last axis of vectors
    # Reshape vectors to (N, 3) for matmul, then reshape back
    H, W, _ = vectors.shape
    vectors_flat = vectors.reshape(-1, 3)
    
    # Rotate
    rotated_vectors = vectors_flat @ rx.T @ ry.T
    
    # 5. Convert 3D vectors to Spherical (Equirectangular) coordinates
    # x', y', z' -> theta, phi
    vx = rotated_vectors[:, 0]
    vy = rotated_vectors[:, 1]
    vz = rotated_vectors[:, 2]
    
    # Longitude (theta) ranges [-pi, pi]
    theta = np.arctan2(vx, vz) 
    
    # Latitude (phi) ranges [-pi/2, pi/2]
    phi = np.arcsin(vy)
    
    # 6. Map spherical coords to image pixels (UV)
    # Equirectangular image is 2:1 ratio covering 360x180 deg
    u = (theta + np.pi) / (2 * np.pi)
    v = (phi + np.pi / 2) / np.pi
    
    map_x = (u * (eq_w - 1)).astype(np.float32)
    map_y = (v * (eq_h - 1)).astype(np.float32)
    
    return map_x.reshape(H, W), map_y.reshape(H, W)

# --- Configuration ---
parser = argparse.ArgumentParser(description="Extract perspective images from 360 equirectangular video or images.")
parser.add_argument("-i", "--input", "--video", dest="input", type=str, default="input.mp4", help="Input video file, image file, or directory of images")
parser.add_argument("-o", "--output", type=str, default="colmap_images", help="Output directory for images")
parser.add_argument("-s", "--skip", type=int, default=30, help="Process 1 frame every X frames (30 = 1 sec if 30fps)")
parser.add_argument("--size", type=int, default=1024, help="Resolution of output square images (1024x1024)")
parser.add_argument("-f", "--fov", type=int, default=100, help="Field of View")
parser.add_argument("-p", "--prefix", type=str, default="frame", help="Prefix for the output image filenames")

args = parser.parse_args()

INPUT_PATH = args.input
OUTPUT_DIR = args.output
FRAME_SKIP = args.skip
OUTPUT_SIZE = args.size
FOV = args.fov
PREFIX = args.prefix

# Define the 6 standard views (Yaw, Pitch)
VIEWS = [
    (0, 0),    # Front
    (90, 0),   # Right
    (180, 0),  # Back
    (-90, 0),  # Left
    (0, 90),   # Up
    (0, -90)   # Down
]

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Determine input type
if os.path.isdir(INPUT_PATH):
    # Directory of images
    image_files = []
    for ext in ('*.jpg', '*.jpeg', '*.png', '*.bmp'):
        image_files.extend(glob.glob(os.path.join(INPUT_PATH, ext)))
        image_files.extend(glob.glob(os.path.join(INPUT_PATH, ext.upper())))
    image_files.sort()
    if not image_files:
        print(f"Error: No images found in directory {INPUT_PATH}")
        sys.exit()
    
    first_frame = cv2.imread(image_files[0])
    if first_frame is None:
        print(f"Error: Could not read image {image_files[0]}")
        sys.exit()
    eq_h, eq_w = first_frame.shape[:2]
    total_frames = len(image_files)
    
    def frame_generator():
        for f in image_files:
            yield cv2.imread(f)
            
elif os.path.isfile(INPUT_PATH):
    ext = os.path.splitext(INPUT_PATH)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.bmp'):
        # Single image
        frame = cv2.imread(INPUT_PATH)
        if frame is None:
            print(f"Error: Could not read image {INPUT_PATH}")
            sys.exit()
        eq_h, eq_w = frame.shape[:2]
        total_frames = 1
        
        def frame_generator():
            yield frame
    else:
        # Video
        cap = cv2.VideoCapture(INPUT_PATH)
        if not cap.isOpened():
            print(f"Error: Could not open video {INPUT_PATH}")
            sys.exit()
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        eq_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        eq_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        def frame_generator():
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                yield frame
            cap.release()
else:
    print(f"Error: Input {INPUT_PATH} not found.")
    sys.exit()

print(f"Processing {INPUT_PATH}...")
print(f"Resolution: {eq_w}x{eq_h}")
if total_frames > 1:
    print(f"Extracting frames every {FRAME_SKIP} frames.")

frame_idx = 0
processed_count = 0

# Pre-calculate maps (Optimization: Calculate maps once, reuse for all frames)
# This assumes the camera output size doesn't change, which is true for video.
# Since eq_w and eq_h are needed for the map, we calculate them after opening the video.
maps = []
print("Pre-calculating projection maps...")
for yaw, pitch in VIEWS:
    mx, my = get_perspective_map(OUTPUT_SIZE, OUTPUT_SIZE, FOV, yaw, pitch, eq_w, eq_h)
    maps.append((mx, my, yaw, pitch))

frames = frame_generator()
for frame in frames:
    if frame is None:
        continue

    # Note: total_frames == 1 is for single image
    if total_frames == 1 or frame_idx % FRAME_SKIP == 0:
        if total_frames > 1:
            print(f"Processing frame {frame_idx}/{total_frames}...")
        else:
            print(f"Processing image...")
        
        for i, (map_x, map_y, yaw, pitch) in enumerate(maps):
            # Remap uses interpolation to create the perspective view
            perspective_img = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR)
            
            # Save file: {PREFIX}_{frame_idx:04d}_view_{i}.jpg
            filename = f"{PREFIX}_{frame_idx:04d}_view_{i}.jpg"
            cv2.imwrite(os.path.join(OUTPUT_DIR, filename), perspective_img)
            
        processed_count += 1

    frame_idx += 1

print(f"Done! Extracted {processed_count * 6} images to '{OUTPUT_DIR}'.")