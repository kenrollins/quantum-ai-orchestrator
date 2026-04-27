"""Mission Assignment skill: Asset-to-task assignment optimization.

This skill handles QUBO assignment problems using multiple backends:
- classical_ortools: Google OR-Tools CP-SAT solver
- neal: D-Wave neal simulated annealing
- cudaq_qaoa: CUDA-Q QAOA variational solver

The Evaluator scores by objective value ratio: quality = obj / bound.
"""
