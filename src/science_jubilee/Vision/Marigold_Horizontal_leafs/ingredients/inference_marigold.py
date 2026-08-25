import os
import cv2
import numpy as np
from pathlib import Path
from sacred import Ingredient

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

from ..src.inference_marigold import infer_depth_and_normals

inference_marigold = Ingredient("inference_marigold")


@inference_marigold.config
def config():
    image_path="/images.latest.png"
    steps=50
    output_path="/output"



@inference_marigold.capture
def run_infer_depths_and_normals(
    image, output_dir: str, steps: int, image_name: str = "image.jpg"
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    image_path = output_path / Path(image_name).name
    cv2.imwrite(str(image_path), np.asarray(image))
    depth_output, normal_output = infer_depth_and_normals(
        str(image_path), str(output_path), steps
    )

    def to_numpy(prediction):
        if hasattr(prediction, "detach"):
            prediction = prediction.detach()
        if hasattr(prediction, "cpu"):
            prediction = prediction.cpu()
        if hasattr(prediction, "numpy"):
            prediction = prediction.numpy()
        return np.asarray(prediction, dtype=np.float32)

    return {
        "depth_output": depth_output,
        "normal_output": normal_output,
        "depth": to_numpy(depth_output.prediction[0]),
        "normals": to_numpy(normal_output.prediction[0]),
        "image": np.asarray(image),
    }
