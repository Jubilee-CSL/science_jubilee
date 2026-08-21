/*
 * Copyright (C) 2023, Inria
 * GRAPHDECO research group, https://team.inria.fr/graphdeco
 * All rights reserved.
 *
 * This software is free for non-commercial, research and evaluation use
 * under the terms of the LICENSE.md file.
 *
 * For inquiries contact  george.drettakis@inria.fr
 */

#include "spatial.h"
#include "simple_knn.h"

torch::Tensor
distCUDA2(const torch::Tensor& points)
{
  const int P = points.size(0);

  auto float_opts = points.options().dtype(torch::kFloat32);
  torch::Tensor means = torch::full({P}, 0.0, float_opts);

  // Ensure contiguous tensors live for the duration of the call
  torch::Tensor points_contig = points.contiguous();
  torch::Tensor means_contig = means.contiguous();

  SimpleKNN::knn(P, (float3*)points_contig.data_ptr<float>(), means_contig.data_ptr<float>());

  return means_contig;
}
