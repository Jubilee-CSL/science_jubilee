import open3d as o3d
import numpy as np

def extract_leaf_clusters(pcd, distance_threshold=0.01, min_points=50, 
                          size_threshold=0.005, shape_threshold=0.85, 
                          height_ratio=0.2):
    """
    Extrait les clusters de feuilles d'un nuage de points de plante.
    
    Paramètres:
    - pcd: Objet Open3D PointCloud (le nuage de points complet).
    - distance_threshold: Distance maximale entre deux points pour appartenir au même cluster.
    - min_points: Nombre minimum de points pour former un cluster valide.
    - size_threshold: Valeur minimale pour la valeur propre maximale (taille).
    - shape_threshold: Ratio maximal (Eval_max / Eval_sum) pour discriminer les feuilles des tiges.
    - height_ratio: Hauteur relative minimale (0 à 1) sur l'axe Z.
    
    Retourne:
    - Une liste d'objets Open3D PointCloud, chacun représentant une feuille isolée.
    """
    
    # Voxel Grid Downsampling pour accélérer les calculs
    pcd = pcd.voxel_down_sample(voxel_size=0.005)
    
    # 2. Clustering Euclidien par condition sur la proximitée 
    labels = np.array(pcd.cluster_dbscan(eps=distance_threshold, min_points=min_points, print_progress=False))

    if len(labels) == 0:
        return []
    
    max_label = labels.max()
    
    # Récupérer les coordonnées Z pour calculer la hauteur totale de la plante
    points = np.asarray(pcd.points)
    z_min = points[:, 2].min()
    z_max = points[:, 2].max()
    total_height = z_max - z_min
    
    leaf_clusters = []

    # 3. Évaluation et classification de chaque cluster par la méthode 
    for i in range(max_label + 1):
        # Isoler les points du cluster actuel
        cluster_indices = np.where(labels == i)[0]
        cluster_points = points[cluster_indices]
        
        # Créer un objet PointCloud pour ce cluster spécifique
        cluster_pcd = o3d.geometry.PointCloud()
        cluster_pcd.points = o3d.utility.Vector3dVector(cluster_points)
        
        # --- Extraction des caractéristiques géométriques ---
        
        centroid = cluster_pcd.get_center()
        z_centroid = centroid[2]
        
        # valeurs propres
        covariance_matrix = np.cov(cluster_points.T)
        eigenvalues, _ = np.linalg.eigh(covariance_matrix)
        
        # np.linalg.eigh renvoie les valeurs en ordre croissant
        eval_max = eigenvalues[-1] 
        eval_sum = np.sum(eigenvalues)
        
        # --- Application des conditions de classification ---
        
        # Condition 1 : Le cluster est-il assez grand ? 
        cond_size = eval_max > size_threshold
        
        # Condition 2 : Le cluster a-t-il la forme d'une feuille ?
        # Une tige a une dimension dominante (ratio proche de 1). 
        # Une feuille est plus plane/distribuée (ratio plus faible).
        if eval_sum > 0:
            cond_shape = (eval_max / eval_sum) < shape_threshold
        else:
            cond_shape = False
            
        # Condition 3 : Le cluster est-il placé assez haut ? 
        relative_height = z_centroid - z_min
        cond_position = relative_height > (total_height * height_ratio)
        
        # 4. Validation
        if cond_size and cond_shape and cond_position:
            leaf_clusters.append(cluster_pcd)

    return leaf_clusters

def compute_leaf_normals(leaf_clusters):
    """Cacul des normales graçe à la méthode PCA (estimation du hyperplan le plus proche)"""
    normals=[]
    for leaf in leaf_clusters:
        points = np.asarray(leaf.points)
        if len(points) < 3:
            normals.append(np.nan)
            continue

        covariance = np.cov(points.T)
        _, eigenvectors = np.linalg.eigh(covariance)
        normal = eigenvectors[:, 0]
        normal /= np.linalg.norm(normal)
        normals.append(normal)

    return normals


def extract_normal_leafs(leaf_clusters, horizontal_threshold=0.8):
    """
        Estimation de l'horizontalité en regardant le produit scalaire avec l'axe Z dans le référentiel de la plante

    """
    horizontal_leafs = []
    z_axis = np.array([0.0, 1.0, 0.0])  #Pour open 3D il s'agit de l'axe y qui est changé en z dans blender
    normals = compute_leaf_normals(leaf_clusters)
    for i in range(len(leaf_clusters)):
        if not np.any(np.isnan(normals[i])) and abs(np.dot(normals[i], z_axis)) >= horizontal_threshold:
            horizontal_leafs.append(leaf_clusters[i])
    return horizontal_leafs
    