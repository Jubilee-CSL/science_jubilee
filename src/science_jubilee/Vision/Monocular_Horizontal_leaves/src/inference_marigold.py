# Code for importing Marigold models from HugginFace and use it on our pipeline, the first time importing may take some time( around 2 min) then the models is instantly ready to use

import argparse
import importlib
import os
from pathlib import Path

import cv2
import numpy as np


def _load_marigold_modules():
    try:
        torch = importlib.import_module("torch")
        diffusers = importlib.import_module("diffusers")
        MarigoldDepthPipeline = getattr(diffusers, "MarigoldDepthPipeline")
        MarigoldNormalsPipeline = getattr(diffusers, "MarigoldNormalsPipeline")
    except Exception as exc:  # pragma: no cover - import is environment dependent
        raise RuntimeError(
            "Marigold dependencies are not available. Install diffusers, transformers, accelerate and torch first."
        ) from exc

    return torch, MarigoldDepthPipeline, MarigoldNormalsPipeline


def _build_pipeline(device: str):
    torch, _, _ = _load_marigold_modules()
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    dtype = torch.float16 if device == "cuda" else torch.float32
    return torch, device, dtype


def infer_depth_and_normals(image_path: str, output_dir: str, steps=30):
    image_path = str(image_path)
    output_dir = str(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    torch, device, dtype = _build_pipeline(
        "cuda"
        if importlib.util.find_spec("torch") is not None
        and importlib.import_module("torch").cuda.is_available()
        else "cpu"
    )
    print(f"[+] Using device: {device}")

    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Unable to read input image: {image_path}")

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    _, MarigoldDepthPipeline, MarigoldNormalsPipeline = _load_marigold_modules()

    print("[+] Loading Marigold depth and normal models...")
    depth_pipe = MarigoldDepthPipeline.from_pretrained(
        "prs-eth/marigold-depth-v1-1",
        variant="fp16",
        torch_dtype=torch.float16,
    )
    normal_pipe = MarigoldNormalsPipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1",
        variant="fp16",
        torch_dtype=torch.float16,
    )
    depth_pipe.to(device)
    normal_pipe.to(device)

    def _run_pipeline(pipe, image_rgb):
        try:
            return pipe(image_rgb, num_inference_steps=steps, match_input_res=True)
        except TypeError:
            return pipe(image_rgb, num_inference_steps=steps)

    with torch.inference_mode():
        print("[+] Running depth estimation...")
        depth_output = _run_pipeline(depth_pipe, image_rgb)
        print("[+] Running normal estimation...")
        normal_output = _run_pipeline(normal_pipe, image_rgb)

    def _to_numpy_array(prediction):
        if hasattr(prediction, "detach"):
            prediction = prediction.detach()
        if hasattr(prediction, "cpu"):
            prediction = prediction.cpu()
        if hasattr(prediction, "numpy"):
            prediction = prediction.numpy()
        return np.asarray(prediction, dtype=np.float32)

    depth_pred = _to_numpy_array(depth_output.prediction[0])
    normal_pred = _to_numpy_array(normal_output.prediction[0])

    base_name = Path(image_path).stem
    depth_path = os.path.join(output_dir, f"{base_name}_depth.npy")
    normals_path = os.path.join(output_dir, f"{base_name}_normals.npy")
    np.save(depth_path, depth_pred)
    np.save(normals_path, normal_pred)

    print(f"[+] Depth saved to: {depth_path}")
    print(f"[+] Normals saved to: {normals_path}")
    return depth_output, normal_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Marigold depth and normal inference on one image"
    )
    parser.add_argument("--image", required=True, help="Input image path")
    parser.add_argument(
        "--output", default="output", help="Directory to store depth and normal arrays"
    )
    args = parser.parse_args()

    infer_depth_and_normals(args.image, args.output)
