from diff_gaussian_rasterization import compute_relocation
import torch
import math

# Provide a fallback for math.comb for Python versions < 3.8
try:
    _comb = math.comb
except AttributeError:
    def _comb(n, k):
        return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))

N_max = 51
binoms = torch.zeros((N_max, N_max)).float().cuda()
for n in range(N_max):
    for k in range(n + 1):
        binoms[n, k] = _comb(n, k)


def compute_relocation_cuda(opacity_old, scale_old, N):
    N.clamp_(min=1, max=N_max - 1)
    return compute_relocation(opacity_old, scale_old, N, binoms, N_max)