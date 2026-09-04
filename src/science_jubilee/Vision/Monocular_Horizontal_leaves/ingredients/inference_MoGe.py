import importlib
import os
import cv2
import numpy as np
from pathlib import Path
from sacred import Ingredient

inference_MoGe = Ingredient("inference_MoGe")

@inference_MoGe.config
def config():
    image_path = "/images.latest.png"
    output_path = "/output"
    resolution_level = 9
    refinement_steps = 5
    model_version = 3

def _load_MoGe_modules(model_version: int = 3):
    try:
        import torch
        
        if model_version == 3:
            from moge.model.v3 import MoGeModel 
            device = torch.device("cuda")
            model = MoGeModel.from_pretrained("Ruicheng/moge-3-vitl").to(device)
        # Load the model
        if model_version == 2:
            from moge.model.v2 import MoGeModel
            device = torch.device("cuda")
            model = MoGeModel.from_pretrained("Ruicheng/moge-2-vitl-normal").to(device)
        model.eval() 
        
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "MoGe dependencies are not available. Install https://github.com/microsoft/MoGe dependencies."
        ) from exc

    return torch, model, device

def infer_depth_and_normals(image_path: str, output_dir: str, resolution_level: int = 9,refinement_steps: int = 5, model_version: int = 3):
    image_path = str(image_path)
    output_dir = str(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    torch, model, device = _load_MoGe_modules(model_version=model_version)
    
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Unable to read input image: {image_path}")
        
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    
    image_tensor = torch.tensor(image_rgb / 255.0, dtype=torch.float32, device=device).permute(2, 0, 1)   
    
    with torch.no_grad():
        if model_version == 3:
            output = model.infer(image_tensor, resolution_level=resolution_level,refine_steps=refinement_steps)
        elif model_version == 2:
            output = model.infer(image_tensor, resolution_level=resolution_level)
        
    return output

def to_numpy(tensor):
    """Convert the Pytorch tensor into Numpy array"""
    if isinstance(tensor, np.ndarray):
        return tensor
    return tensor.detach().cpu().numpy()

@inference_MoGe.capture
def run_infer_depths_and_normals(
    image, output_dir: str, image_name: str = "image.jpg", resolution_level: int = 9, refinement_steps: int = 5, model_version: int = 3
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    image_path = output_path / Path(image_name).name
    
    cv2.imwrite(str(image_path), np.asarray(image))
    
    predict = infer_depth_and_normals(
        str(image_path), str(output_path), resolution_level=resolution_level,refinement_steps=refinement_steps, model_version=model_version
    )

    return {
        "depth_output": predict["depth"], 
        "normal_output": predict["normal"],
        "depth": to_numpy(predict["depth"]), 
        "normals": to_numpy(predict["normal"]),
        "3d_points": to_numpy(predict["points"]), 
        "image": np.asarray(image),
    }