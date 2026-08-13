import logging
import math
import random

import cv2
import numpy as np
from sacred import Ingredient

logger = logging.getLogger(__name__)

rrt = Ingredient("rrt")


@rrt.config
def config():
    step_size = 20
    max_iter = 3000
    goal_sample_rate = 0.1


def check_collision(obstacle_mask, pt1, pt2):
    """
    Vérifie les collisions pour une machine se déplaçant en 'L' :
    D'abord sur l'axe X (jusqu'à x2), puis sur l'axe Y (jusqu'à y2).
    """
    x1, y1 = pt1
    x2, y2 = pt2

    # 1. Déplacement en X : On fixe Y = y1, on avance X de x1 vers x2
    x_min, x_max = min(x1, x2), max(x1, x2)
    # L'indexation numpy est [y, x]. On check tous les X entre x_min et x_max inclus
    if np.any(obstacle_mask[y1, x_min : x_max + 1] > 0):
        return True

    # 2. Déplacement en Y : On fixe X = x2 (car on vient d'y arriver), on avance Y de y1 vers y2
    y_min, y_max = min(y1, y2), max(y1, y2)
    if np.any(obstacle_mask[y_min : y_max + 1, x2] > 0):
        return True

    return False


@rrt.capture
def rrt_path_planning(
    start_2d,
    goal_2d,
    obstacle_mask,
    roi_mask,
    marge,
    step_size,
    max_iter,
    goal_sample_rate,
):
    kernel_size = int(2 * marge + 1)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    # On dilate les obstacles (le blanc bave sur le noir)
    obstacle_mask = cv2.dilate(
        obstacle_mask, kernel
    )  # on ajoute un bord de 2mm à tout les duckweed pour pas qu'elles soient aspirées par l'effet capillaire
    h, w = obstacle_mask.shape
    nodes = [{"pos": start_2d, "parent": -1}]

    for _ in range(max_iter):
        if random.random() < goal_sample_rate:
            sample = goal_2d
        else:
            while True:
                rx = random.randint(0, w - 1)
                ry = random.randint(0, h - 1)
                if roi_mask[ry, rx] > 0:
                    sample = (rx, ry)
                    break

        nearest_idx = 0
        min_dist = float("inf")
        for i, n in enumerate(nodes):
            dist = np.hypot(n["pos"][0] - sample[0], n["pos"][1] - sample[1])
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        nearest_node = nodes[nearest_idx]

        theta = math.atan2(
            sample[1] - nearest_node["pos"][1], sample[0] - nearest_node["pos"][0]
        )
        new_x = int(nearest_node["pos"][0] + step_size * math.cos(theta))
        new_y = int(nearest_node["pos"][1] + step_size * math.sin(theta))

        new_x = max(0, min(w - 1, new_x))
        new_y = max(0, min(h - 1, new_y))
        new_pos = (new_x, new_y)

        if not check_collision(obstacle_mask, nearest_node["pos"], new_pos):
            nodes.append({"pos": new_pos, "parent": nearest_idx})

            # Pour la validation finale du goal, on vérifie bien que c'est atteignable
            if np.hypot(new_pos[0] - goal_2d[0], new_pos[1] - goal_2d[1]) <= step_size:
                if not check_collision(obstacle_mask, new_pos, goal_2d):
                    nodes.append({"pos": goal_2d, "parent": len(nodes) - 1})

                    path = []
                    curr = len(nodes) - 1
                    while curr != -1:
                        path.append(nodes[curr]["pos"])
                        curr = nodes[curr]["parent"]
                    return path[::-1]

    logger.warning("RRT n'a pas trouvé de chemin dans la limite d'itérations.")
    return None


def smooth_path(path_2d, obstacle_mask):
    if not path_2d or len(path_2d) <= 2:
        return path_2d

    smoothed_path = [path_2d[0]]
    curr_idx = 0

    while curr_idx < len(path_2d) - 1:
        furthest_valid_idx = curr_idx + 1
        for i in range(len(path_2d) - 1, curr_idx, -1):
            # Le check_collision va valider si on peut relier 2 checkpoints éloignés
            # avec la cinématique X puis Y
            if not check_collision(obstacle_mask, path_2d[curr_idx], path_2d[i]):
                furthest_valid_idx = i
                break
        smoothed_path.append(path_2d[furthest_valid_idx])
        curr_idx = furthest_valid_idx

    return smoothed_path
