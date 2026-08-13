import cv2
import numpy as np
from sacred import Ingredient

insertion_point = Ingredient("insertion_point")


@insertion_point.config
def config():
    max_offset_px = 50


@insertion_point.capture
def get_insertion_point(obstacle_mask, duckweed_goal, marge):
    """Find insertion point maximizing distance to obstacles, excluding a disk around goal."""
    mask_for_insertion = obstacle_mask.copy()
    center = (int(duckweed_goal[0]), int(duckweed_goal[1]))
    radius = int(marge)

    cv2.circle(mask_for_insertion, center, radius, 255, -1)
    free_space = cv2.bitwise_not(mask_for_insertion)
    dist_transform = cv2.distanceTransform(free_space, cv2.DIST_L2, 5)
    _, _, _, max_loc = cv2.minMaxLoc(dist_transform)

    return max_loc, mask_for_insertion


@insertion_point.capture
def get_insertion_point_2(obstacle_mask, duckweed_goal, marge, max_offset_px):
    """Find insertion point with both min and max radial constraints from goal."""
    mask_for_insertion = obstacle_mask.copy()
    center = (int(duckweed_goal[0]), int(duckweed_goal[1]))
    radius = int(marge)

    cv2.circle(mask_for_insertion, center, radius, 255, -1)

    max_dist_mask = np.zeros(mask_for_insertion.shape[:2], dtype=np.uint8)
    cv2.circle(max_dist_mask, center, radius + int(max_offset_px), 255, -1)
    max_dist_mask = cv2.bitwise_not(max_dist_mask)
    mask_for_insertion = cv2.bitwise_or(mask_for_insertion, max_dist_mask)

    free_space = cv2.bitwise_not(mask_for_insertion)
    dist_transform = cv2.distanceTransform(free_space, cv2.DIST_L2, 5)
    _, _, _, max_loc = cv2.minMaxLoc(dist_transform)

    return max_loc, mask_for_insertion
