#!/usr/bin/env python3
"""
Generates a realistic post-simulation SystemC TLM-2.0 (mixed LT + AT) trace JSON
matching the schema exported by `include/sc_tlm_heatmap.hpp`.

Scenario modeled (0 ns -> 6000 ns, 60 frames @ 100 ns window):
- Phase 1 (0 - 1800 ns): RISC-V Cluster (LT with Quantum Keeper) boots from Boot ROM
  and warms up L2 Cache via AXI Interconnect.
- Phase 2 (1800 - 4200 ns): NPU Tensor DMA (AT) & Vision DSP (AT) launch heavy burst
  transfers to DDR5 Memory Controller (AT), causing severe AT 4-phase Request Backpressure
  (BEGIN_REQ -> END_REQ stall) on `noc_to_ddr` and saturating the DDR5 Read/Write Queue!
- Phase 3 (4200 - 6000 ns): QoS throttler activates, bank conflict subsides, and traffic
  drains smoothly back to steady state.
"""

import json
import math
import os
import random

random.seed(42)

NODES = [
    {
        "id": "rv_core0",
        "label": "RISC-V Core 0",
        "sub": "ISS + QuantumKeeper",
        "type": "master",
        "abstraction": "LT",
        "max_outstanding": 4,
        "max_bandwidth_gbps": 12.8,
        "x": 90,
        "y": 90,
    },
    {
        "id": "rv_core1",
        "label": "RISC-V Core 1",
        "sub": "ISS + DMI Enabled",
        "type": "master",
        "abstraction": "LT",
        "max_outstanding": 4,
        "max_bandwidth_gbps": 12.8,
        "x": 90,
        "y": 230,
    },
    {
        "id": "npu_dma",
        "label": "NPU Tensor DMA",
        "sub": "4-Phase AT Burst Initiator",
        "type": "master",
        "abstraction": "AT",
        "max_outstanding": 32,
        "max_bandwidth_gbps": 64.0,
        "x": 90,
        "y": 380,
    },
    {
        "id": "v_dsp",
        "label": "Vision DSP",
        "sub": "AT Pipelined Master",
        "type": "master",
        "abstraction": "AT",
        "max_outstanding": 16,
        "max_bandwidth_gbps": 32.0,
        "x": 90,
        "y": 520,
    },
    {
        "id": "lt_at_bridge",
        "label": "LT-to-AT Bridge",
        "sub": "Temporal Sync & Transactor",
        "type": "bridge",
        "abstraction": "LT/AT",
        "max_outstanding": 8,
        "max_bandwidth_gbps": 25.6,
        "x": 380,
        "y": 160,
    },
    {
        "id": "axi_noc",
        "label": "AXI4 Coherent NoC",
        "sub": "AT PeQ Matrix Router",
        "type": "interconnect",
        "abstraction": "AT",
        "max_outstanding": 48,
        "max_bandwidth_gbps": 96.0,
        "x": 420,
        "y": 390,
    },
    {
        "id": "boot_sram",
        "label": "Boot SRAM",
        "sub": "LT b_transport + DMI",
        "type": "memory",
        "abstraction": "LT",
        "max_outstanding": 4,
        "max_bandwidth_gbps": 16.0,
        "x": 740,
        "y": 110,
    },
    {
        "id": "l2_cache",
        "label": "Shared L2 Cache",
        "sub": "AT 4-Bank Tag/Data Array",
        "type": "memory",
        "abstraction": "AT",
        "max_outstanding": 24,
        "max_bandwidth_gbps": 64.0,
        "x": 740,
        "y": 280,
    },
    {
        "id": "ddr5_ctrl",
        "label": "DDR5 Memory Ctrl",
        "sub": "AT Scheduler & Cmd Queue",
        "type": "memory",
        "abstraction": "AT",
        "max_outstanding": 32,
        "max_bandwidth_gbps": 51.2,
        "x": 740,
        "y": 470,
    },
]

LINKS = [
    {
        "id": "c0_to_br",
        "source": "rv_core0",
        "target": "lt_at_bridge",
        "label": "b_transport (LT)",
        "abstraction": "LT",
        "max_bandwidth_gbps": 12.8,
    },
    {
        "id": "c1_to_br",
        "source": "rv_core1",
        "target": "lt_at_bridge",
        "label": "b_transport + DMI (LT)",
        "abstraction": "LT",
        "max_bandwidth_gbps": 12.8,
    },
    {
        "id": "br_to_sram",
        "source": "lt_at_bridge",
        "target": "boot_sram",
        "label": "b_transport (LT)",
        "abstraction": "LT",
        "max_bandwidth_gbps": 16.0,
    },
    {
        "id": "br_to_noc",
        "source": "lt_at_bridge",
        "target": "axi_noc",
        "label": "nb_transport (AT)",
        "abstraction": "AT",
        "max_bandwidth_gbps": 25.6,
    },
    {
        "id": "npu_to_noc",
        "source": "npu_dma",
        "target": "axi_noc",
        "label": "AXI4 512b (AT)",
        "abstraction": "AT",
        "max_bandwidth_gbps": 64.0,
    },
    {
        "id": "dsp_to_noc",
        "source": "v_dsp",
        "target": "axi_noc",
        "label": "AXI4 256b (AT)",
        "abstraction": "AT",
        "max_bandwidth_gbps": 32.0,
    },
    {
        "id": "noc_to_l2",
        "source": "axi_noc",
        "target": "l2_cache",
        "label": "Coherent Port (AT)",
        "abstraction": "AT",
        "max_bandwidth_gbps": 64.0,
    },
    {
        "id": "noc_to_ddr",
        "source": "axi_noc",
        "target": "ddr5_ctrl",
        "label": "MEM Channel 0 (AT)",
        "abstraction": "AT",
        "max_bandwidth_gbps": 51.2,
    },
]


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, round(v, 3)))


def generate():
    window_ns = 100.0
    num_frames = 60
    frames = []
    tokens = []
    tid = 1

    for f in range(num_frames):
        t_ns = f * window_ns
        # Bell curve centered at frame 30 (3000ns) for NPU/DSP burst congestion
        burst = math.exp(-((f - 30) ** 2) / (2 * (7.5 ** 2)))
        boot_wave = math.exp(-((f - 8) ** 2) / (2 * (5.0 ** 2)))
        l2_wave = 0.35 + 0.45 * math.sin(f * 0.22) ** 2

        link_stats = {}

        # 1. LT Links (RISC-V Cores -> Bridge -> Boot SRAM)
        c0_util = clamp(0.25 + 0.55 * boot_wave + 0.1 * math.sin(f * 0.5))
        c1_util = clamp(0.20 + 0.35 * boot_wave + 0.15 * math.cos(f * 0.4))
        sram_util = clamp(0.65 * boot_wave + 0.08)

        # Quantum offset oscillates as local time accumulates before sync every 500ns
        q_offset = ((f % 5) + 1) * 85.0

        link_stats["c0_to_br"] = {
            "util": c0_util,
            "cong": clamp(0.05 * boot_wave),
            "occ": clamp(c0_util * 0.6),
            "bw_gbps": round(c0_util * 12.8, 2),
            "tx_count": int(4 + c0_util * 18),
            "q_offset_ns": round(q_offset, 1),
        }
        link_stats["c1_to_br"] = {
            "util": c1_util,
            "cong": 0.0,
            "occ": clamp(c1_util * 0.4),
            "bw_gbps": round(c1_util * 12.8, 2),
            "tx_count": int(3 + c1_util * 14),
            "q_offset_ns": round(q_offset * 0.8, 1),
        }
        link_stats["br_to_sram"] = {
            "util": sram_util,
            "cong": 0.0,
            "occ": clamp(sram_util * 0.5),
            "bw_gbps": round(sram_util * 16.0, 2),
            "tx_count": int(2 + sram_util * 20),
            "q_offset_ns": round(q_offset * 0.5, 1),
        }

        # 2. AT Links
        br_noc_util = clamp(0.18 + 0.25 * l2_wave)
        npu_util = clamp(0.15 + 0.82 * burst)
        dsp_util = clamp(0.12 + 0.68 * burst)

        # DDR5 Controller experiences heavy AT Request Backpressure (BEGIN_REQ -> END_REQ stall)
        # when combined NPU + DSP traffic exceeds DDR5 schedule rate around frames 22..38
        ddr_cong = clamp(max(0.0, (burst - 0.32) * 1.45))
        ddr_occ = clamp(0.20 + 0.78 * burst)
        ddr_util = clamp(0.22 + 0.72 * burst * (1.0 - 0.22 * ddr_cong))

        # Upstream NoC and NPU links feel cascading backpressure from DDR5!
        npu_cong = clamp(ddr_cong * 0.82)
        dsp_cong = clamp(ddr_cong * 0.65)
        noc_occ = clamp(0.25 + 0.70 * burst)

        link_stats["br_to_noc"] = {
            "util": br_noc_util,
            "cong": clamp(ddr_cong * 0.30),
            "occ": clamp(0.20 + 0.35 * burst),
            "bw_gbps": round(br_noc_util * 25.6, 2),
            "tx_count": int(4 + br_noc_util * 16),
            "q_offset_ns": 0.0,
        }
        link_stats["npu_to_noc"] = {
            "util": npu_util,
            "cong": npu_cong,
            "occ": clamp(0.18 + 0.75 * burst),
            "bw_gbps": round(npu_util * 64.0, 2),
            "tx_count": int(6 + npu_util * 32),
            "q_offset_ns": 0.0,
        }
        link_stats["dsp_to_noc"] = {
            "util": dsp_util,
            "cong": dsp_cong,
            "occ": clamp(0.15 + 0.65 * burst),
            "bw_gbps": round(dsp_util * 32.0, 2),
            "tx_count": int(4 + dsp_util * 22),
            "q_offset_ns": 0.0,
        }
        link_stats["noc_to_l2"] = {
            "util": clamp(l2_wave),
            "cong": clamp(0.12 * burst),
            "occ": clamp(0.30 + 0.40 * l2_wave),
            "bw_gbps": round(clamp(l2_wave) * 64.0, 2),
            "tx_count": int(8 + l2_wave * 28),
            "q_offset_ns": 0.0,
        }
        link_stats["noc_to_ddr"] = {
            "util": ddr_util,
            "cong": ddr_cong,
            "occ": ddr_occ,
            "bw_gbps": round(ddr_util * 51.2, 2),
            "tx_count": int(5 + ddr_util * 26),
            "q_offset_ns": 0.0,
        }

        frames.append({"frame": f, "time_ns": t_ns, "links": link_stats})

        # Generate sample discrete tokens for the micro-inspector & 4-phase viewer
        # LT Token sample
        tokens.append(
            {
                "id": tid,
                "link": "c0_to_br",
                "cmd": "RD",
                "addr": f"0x1000_{f * 64:04x}",
                "len": 64,
                "mode": "LT",
                "t1": round(t_ns + 10.0, 1),
                "t2": round(t_ns + 10.0, 1),
                "t3": round(t_ns + 28.0, 1),
                "t4": round(t_ns + 28.0, 1),
                "q_offset": round(q_offset, 1),
            }
        )
        tid += 1

        # AT Token sample on NPU -> NoC -> DDR5 showing 4-Phase timing (t1..t4)
        req_stall = round(4.0 + ddr_cong * 52.0, 1)  # BEGIN_REQ -> END_REQ stall
        mem_lat = round(18.0 + ddr_occ * 30.0, 1)  # END_REQ -> BEGIN_RESP
        resp_hold = 6.0  # BEGIN_RESP -> END_RESP
        t1 = round(t_ns + 12.0, 1)
        t2 = round(t1 + req_stall, 1)
        t3 = round(t2 + mem_lat, 1)
        t4 = round(t3 + resp_hold, 1)
        tokens.append(
            {
                "id": tid,
                "link": "noc_to_ddr",
                "cmd": "WR" if (f % 3 == 0) else "RD",
                "addr": f"0x8040_{f * 256:04x}",
                "len": 256,
                "mode": "AT",
                "t1": t1,
                "t2": t2,
                "t3": t3,
                "t4": t4,
                "q_offset": 0.0,
            }
        )
        tid += 1

    payload = {
        "meta": {
            "title": "Heterogeneous AI SoC (SystemC TLM-2.0 LT + AT Hybrid Trace)",
            "window_ns": window_ns,
            "total_time_ns": num_frames * window_ns,
            "num_frames": num_frames,
        },
        "nodes": NODES,
        "links": LINKS,
        "frames": frames,
        "tokens": tokens,
    }

    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "demo_soc_trace.json")
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
    print(f"Generated {out_path} ({len(frames)} frames, {len(tokens)} tokens)")


if __name__ == "__main__":
    generate()
