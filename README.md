# 360 Slicer

360 Slicer is a Python utility script designed to extract standard perspective images from equirectangular 360-degree videos or images. It processes a 360 video, a single image, or a directory of images, and generates 6 standard perspective views (Front, Right, Back, Left, Up, Down) for sampled frames, making it ideal for creating image datasets for photogrammetry, 3D Gaussian Splatting (3DGS), Colmap processing, or other computer vision tasks.

## Features

- **Equirectangular to Perspective Conversion:** Accurately projects spherical 360 video frames into flat, rectilinear perspective images.
- **Configurable Extraction:** Control which frames to process (e.g., 1 frame per second).
- **Customizable Views:** Generates 6 overlapping directional views (Front, Right, Back, Left, Up, Down).
- **Adjustable FOV and Resolution:** Choose your desired field of view and output image resolution. A FOV > 90° ensures robust overlap for feature matching tools like COLMAP.
- **Custom Naming:** Define custom prefixes for the generated image files.
- **Lossless Output Format:** Choose between standard `.jpg` or lossless `.png` output for the generated images to prevent compression artifacts during photogrammetry matching.

## Requirements

The script uses `numpy` for mathematical projection mapping and `opencv-python` (cv2) for image processing and file handling.

Install the required dependencies via pip:

```bash
pip install numpy opencv-python
```

(Optional but recommended: Run this within a Python virtual environment).

## Usage

Run the script from the command line:

```bash
python 360-slicer.py [options]
```

### Options

| Argument | Short | Default | Description |
| :--- | :---: | :--- | :--- |
| `--input`, `--video` | `-i` | `input.mp4` | Path to the input 360 equirectangular video, image file, or directory of images |
| `--output` | `-o` | `colmap_images` | Directory where the generated perspective images will be saved |
| `--skip` | `-s` | `30` | Process 1 frame every X frames (e.g., `30` = 1 frame per second for a 30fps video) |
| `--size` | | `1024` | Resolution (width and height) of the output square images |
| `--fov` | `-f` | `100` | Field of View in degrees  |
| `--prefix` | `-p` | `frame` | File prefix for the output image filenames |
| `--format` | | `jpg` | Output image format (`jpg` or `png`) |

### Example

Extract images from a video named `my_360_ride.mp4`, save them into a folder called `dataset`, process every 15th frame, set output resolution to 800x800, use a 110-degree FOV, and prefix files with `ride`:

```bash
python 360-slicer.py -i my_360_ride.mp4 -o dataset -s 15 --size 800 -f 110 -p ride --format png
```

This will produce images named like:
`dataset/ride_0000_view_0.png`, `dataset/ride_0000_view_1.png`, etc.

## How It Works

1. The script first calculates a meshgrid of pixel coordinates for the desired output square resolution.
2. It generates 3D vectors representing rays from the camera center through each pixel based on the defined Field of View (FOV).
3. Six standard rotation matrices (Yaw and Pitch) are applied to generate 6 independent viewing directions.
4. The rotated 3D vectors are converted into Equirectangular spherical coordinates (longitude and latitude).
5. These coordinates are mapped to pixel indices (UVs) of the equirectangular video frame.
6. For each processed frame in the video or image space, `cv2.remap` uses the computed maps to efficiently warp and extract the perspective projections.
