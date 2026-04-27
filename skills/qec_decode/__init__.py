"""QEC Decode skill: Quantum Error Correction syndrome decoding.

This skill handles decoding surface code syndromes using multiple backends:
- ising_speed: NVIDIA AI decoder (speed-optimized)
- ising_accuracy: NVIDIA AI decoder (accuracy-optimized)
- pymatching: Classical MWPM decoder

The Evaluator scores by Logical Error Rate (LER): quality = 1 - LER.
"""
