"""
sketch_to_photo.py

Converts a hand-drawn/composite face sketch into a photo-realistic image,
so it can be fed into VeriFace's existing POST /search endpoint (which
expects a normal photo, not a sketch).

Model: Face-Sketch-SCG (Chen et al., CVIU 2023) — a semi-supervised
Cycle-GAN trained on CUFS/CUFSF sketch-photo pairs. Pretrained weights are
downloaded automatically on first run from the project's GitHub Releases
(no manual download or Google Drive step needed).
Source: https://github.com/chaofengc/Face-Sketch-SCG

Usage:
    python sketch_to_photo.py --input sketch.jpg --output converted.jpg
    python sketch_to_photo.py --input sketch.jpg --output converted.jpg --style cufsf

Requires: torch, torchvision, pillow  (see requirements-sketch.txt)
"""

import argparse
import os
import sys
from urllib.parse import urlparse

try:
    import torch
    import torchvision.transforms.functional as TF
    from torch.hub import download_url_to_file
    from PIL import Image, UnidentifiedImageError
except ImportError as e:
    sys.exit(
        f"Missing dependency: {e.name}\n"
        f"Install requirements first:  pip install -r requirements-sketch.txt --break-system-packages"
    )

from sketch_model.networks import ResnetGenerator, apply_norm

PRETRAINED_WEIGHT_URLS = {
    "cufs": "https://github.com/chaofengc/Face-Sketch-SCG/releases/download/v0.1/cufs_net_G_B.pth",
    "cufsf": "https://github.com/chaofengc/Face-Sketch-SCG/releases/download/v0.1/cufsf_net_G_B.pth",
}
MODEL_INPUT_SIZE = (256, 256)  # the model was trained at this resolution
WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pretrain_models")


def download_weights(style: str) -> str:
    """Downloads the pretrained sketch->photo weights for the given style
    (once) and returns the local checkpoint path."""
    if style not in PRETRAINED_WEIGHT_URLS:
        raise ValueError(f"Unknown style '{style}'. Choose from: {list(PRETRAINED_WEIGHT_URLS)}")

    url = PRETRAINED_WEIGHT_URLS[style]
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    filename = os.path.basename(urlparse(url).path)
    local_path = os.path.join(WEIGHTS_DIR, filename)

    if not os.path.exists(local_path):
        print(f"Downloading pretrained '{style}' weights (first run only)...")
        try:
            download_url_to_file(url, local_path, hash_prefix=None, progress=True)
        except Exception as e:
            raise RuntimeError(
                f"Could not download pretrained weights from {url}\n"
                f"Check your internet connection. Original error: {e}"
            ) from e

    return local_path


def load_model(style: str, device: torch.device) -> torch.nn.Module:
    """Loads the sketch(gray, 1-channel) -> photo(RGB, 3-channel) generator."""
    weight_path = download_weights(style)

    model = ResnetGenerator(1, 3, norm_type="gn", relu_type="silu").to(device)
    apply_norm(model)

    try:
        state_dict = torch.load(weight_path, map_location=device)
        model.load_state_dict(state_dict)
    except Exception as e:
        raise RuntimeError(
            f"Failed to load model weights from {weight_path}. "
            f"The downloaded file may be corrupted — try deleting it and re-running. "
            f"Original error: {e}"
        ) from e

    model.eval()
    return model


def load_sketch_as_tensor(input_path: str) -> tuple[torch.Tensor, tuple[int, int]]:
    """Loads the input sketch, converts to grayscale, resizes to the model's
    expected input size, and returns a (1, 1, H, W) tensor in [0, 255]
    plus the original (width, height) so we can resize the output back."""
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input sketch not found: {input_path}")

    try:
        img = Image.open(input_path)
        img.load()
    except UnidentifiedImageError as e:
        raise ValueError(
            f"'{input_path}' doesn't look like a valid image file. "
            f"Supported formats: JPG, PNG, BMP."
        ) from e

    original_size = img.size  # (width, height), used to resize output back
    if original_size[0] < 32 or original_size[1] < 32:
        raise ValueError(
            f"Input image is too small ({original_size[0]}x{original_size[1]}). "
            f"Use a sketch at least 32x32 pixels, ideally a clear face-sized image."
        )

    # Sketch model expects single-channel (grayscale) input regardless of
    # whether the source file is RGB, RGBA, or already grayscale.
    img = img.convert("L")
    img = img.resize(MODEL_INPUT_SIZE, Image.BICUBIC)

    tensor = TF.to_tensor(img).unsqueeze(0) * 255  # model expects [0, 255] range
    return tensor, original_size


def save_output_photo(output_tensor: torch.Tensor, output_path: str, original_size: tuple[int, int]) -> None:
    """Converts the model's raw RGB tensor output back into a saved image
    file, resized to match the original sketch's dimensions."""
    array = output_tensor.squeeze().detach().cpu().numpy().clip(0, 255)
    array = array.transpose(1, 2, 0).astype("uint8")  # (C,H,W) -> (H,W,C)

    img = Image.fromarray(array, mode="RGB")
    img = img.resize(original_size, Image.BICUBIC)

    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)
    img.save(output_path)


def convert_sketch_to_photo(input_path: str, output_path: str, style: str = "cufs") -> str:
    """Full pipeline: sketch file -> photo-realistic file. Returns the
    output path on success. Raises a clear exception on failure."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    sketch_tensor, original_size = load_sketch_as_tensor(input_path)
    model = load_model(style, device)

    with torch.no_grad():
        output_tensor = model(sketch_tensor.to(device))

    save_output_photo(output_tensor, output_path, original_size)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert a hand-drawn/composite face sketch into a photo-realistic image."
    )
    parser.add_argument("--input", required=True, help="Path to the input sketch image")
    parser.add_argument("--output", required=True, help="Path to save the converted photo-realistic image")
    parser.add_argument(
        "--style", default="cufs", choices=list(PRETRAINED_WEIGHT_URLS),
        help="Which pretrained style to use (default: cufs). "
             "'cufsf' can work better for sketches with shading/lighting variation.",
    )
    args = parser.parse_args()

    try:
        output_path = convert_sketch_to_photo(args.input, args.output, args.style)
    except (FileNotFoundError, ValueError) as e:
        # Problems with the input the user gave us — fail with a clear, specific message.
        print(f"Input error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        # Problems downloading/loading the model itself.
        print(f"Model error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Saved photo-realistic conversion to: {output_path}")


if __name__ == "__main__":
    main()
