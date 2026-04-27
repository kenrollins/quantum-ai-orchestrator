"""Backend implementations.

Each backend module exposes:

    def run(backend_input: BackendInput, gpu_lane: int | None = None) -> Solution

Phase 1 backends:
- pymatching: classical MWPM decoder (CPU)
- classical_ortools: OR-Tools CP-SAT (CPU)
- neal: D-Wave neal SA (CPU)
- ising_speed / ising_accuracy: NVIDIA Ising decoder (GPU)
- cudaq_qaoa: CUDA-Q QAOA (GPU)

Phase 2+: cutensornet, pennylane_var.
"""
