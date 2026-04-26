# ADR-0002: No NVLink on RTX 6000 Ada; pivot to two-GPU parallel racing

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** Ken Rollins

## Context

The planning assumption was NVLink between the two GPUs in the workstation (Dell Precision 7960). NVLink would have allowed peer-to-peer VRAM pooling and pushed multi-GPU statevector simulation from ~30 qubits to ~33 qubits. The previous-generation NVIDIA RTX A6000 supported NVLink via an optional bridge, which is what the assumption was based on.

The recon was definitive on two fronts:

```
$ nvidia-smi nvlink --status        # empty output
$ nvidia-smi nvlink --capabilities  # empty output
$ nvidia-smi topo -m
       GPU0  GPU1  CPU Affinity ...
GPU0   X     SYS   ...
GPU1   SYS   X     ...
```

`SYS` indicates the link traverses PCIe and the NUMA interconnect — no NVLink path. NVIDIA's own datasheet and developer-forum threads confirm that the RTX 6000 Ada Generation does not support NVLink at all; the connector was removed from the silicon. There is no bridge to add.

## Decision

**Accept the no-NVLink reality and pivot the architecture to two-GPU parallel racing.** Each GPU-bound backend runs in its own GPU lane (GPU0 or GPU1). The dispatcher assigns lanes; both GPUs run different backends in parallel. The Backend Bake-off panel shows literal parallel races — same problem dispatched to two backends, each on its own card, finish-line wall-time visible.

Multi-GPU statevector simulation caps at ~30 qubits on a single card (48 GB at the QAOA depths we run). We do not attempt to pool across PCIe — peer-to-peer over PCIe without NVLink would add complexity without yielding the qubit headroom that motivated the original plan.

## Alternatives considered

- **Pool VRAM via cuStateVec multi-GPU over PCIe.** Technically possible. Real performance impact (PCIe Gen 4/5 vs NVLink is roughly a 5-10× bandwidth difference for peer-to-peer) and added orchestration complexity. The qubit headroom gain (30 → ~32) is not worth the PCIe contention cost. Rejected.
- **Use cuTensorNet for tensor-network simulation across host RAM (502 GiB available).** This is a real Phase 2 option for problems where tensor-network sim is the right approach. It is *not* a substitute for state-vector at the small-distance / shallow-depth regime where Phase 1's QAOA demos live. Deferred to Phase 2; not the answer for this ADR.
- **Find a workstation with NVLink.** Dell does not currently sell an Ada-generation workstation with NVLink. Pre-built NVLink configurations (DGX, etc.) are out of scope for this demo. Rejected.

## Consequences

### Positive

- The two-GPU racing visual *is* hybrid orchestration — the Backend Bake-off panel literalizes the thesis. No memory-pooled illusion of unity; each card runs a different solver, results race to the finish line.
- Simpler dispatcher logic: GPU lanes are first-class (`gpu_lane: int`), assignment is explicit, no pooled-memory edge cases.
- Honest framing in the demo: when we say "two backends in parallel," the audience sees two GPUs lit up, not one card pretending to be two.

### Negative / accepted trade-offs

- ~30 qubit cap on single-GPU statevector. For QAOA at the depths Phase 1 cares about (mission_assignment with 96 binary vars QAOA, qec_decode at distance 7 = 97 qubits via Stim, not statevector), this is not the binding constraint.
- "We could go bigger if we had NVLink" becomes a slide moment rather than a demo capability. We address this with the cuTensorNet Phase 2 backend, which scales further at low depth.
- Backend race fairness needs careful instrumentation: warm-up iterations before timed runs, otherwise the first-dispatched backend looks slower for tooling reasons rather than algorithmic ones. Phase 1 instrumentation requirement.

## References

- Plan: [`../plan.md`](../plan.md), §3 (Hardware), §6 (Backends)
- Host setup: [`../host-setup.md`](../host-setup.md)
- NVIDIA developer forum (RTX A6000 ADA NVLink discussion): https://forums.developer.nvidia.com/t/rtx-a6000-ada-no-more-nv-link-even-on-pro-gpus/230874
- NVIDIA RTX 6000 Ada datasheet: https://www.nvidia.com/content/dam/en-zz/Solutions/design-visualization/rtx-6000/proviz-print-rtx6000-datasheet-web-2504660.pdf
- Journey: [`../journal/journey/00-origin.md`](../journal/journey/00-origin.md)
