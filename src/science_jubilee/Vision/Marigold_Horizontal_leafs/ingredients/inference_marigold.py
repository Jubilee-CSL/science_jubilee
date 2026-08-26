import importlib
import os
import cv2
import numpy as np
from pathlib import Path
from sacred import Ingredient

inference_marigold = Ingredient("inference_marigold")


@inference_marigold.config
def config():
    image_path = "/images.latest.png"
    steps = 50
    output_path = "/output"


def _load_marigold_modules():
    try:
        torch = importlib.import_module("torch")
        diffusers = importlib.import_module("diffusers")
        depth_pipeline = getattr(diffusers, "MarigoldDepthPipeline")
        normals_pipeline = getattr(diffusers, "MarigoldNormalsPipeline")
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Marigold dependencies are not available. Install diffusers, transformers, accelerate and torch first."
        ) from exc

    return torch, depth_pipeline, normals_pipeline


def _build_pipeline(device: str):
    torch, _, _ = _load_marigold_modules()
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    return torch, device, dtype


def _to_numpy_array(prediction):
    if hasattr(prediction, "detach"):
        prediction = prediction.detach()
    if hasattr(prediction, "cpu"):
        prediction = prediction.cpu()
    if hasattr(prediction, "numpy"):
        prediction = prediction.numpy()
    return np.asarray(prediction, dtype=np.float32)


def infer_depth_and_normals(image_path: str, output_dir: str, steps: int = 30):
    image_path = str(image_path)
    output_dir = str(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    torch, device, _ = _build_pipeline(
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

    _, depth_pipeline, normals_pipeline = _load_marigold_modules()
    print("[+] Loading Marigold depth and normal models...")
    depth_pipe = depth_pipeline.from_pretrained(
        "prs-eth/marigold-depth-v1-1",
        variant="fp16",
        torch_dtype=torch.float16,
    )
    normal_pipe = normals_pipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1",
        variant="fp16",
        torch_dtype=torch.float16,
    )
    depth_pipe.to(device)
    normal_pipe.to(device)

    def run_model(pipe):
        try:
            return pipe(image_rgb, num_inference_steps=steps, match_input_res=True)
        except TypeError:
            return pipe(image_rgb, num_inference_steps=steps)

    with torch.inference_mode():
        print("[+] Running depth estimation...")
        depth_output = run_model(depth_pipe)
        print("[+] Running normal estimation...")
        normal_output = run_model(normal_pipe)

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
