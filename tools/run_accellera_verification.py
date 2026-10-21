#!/usr/bin/env python3
"""
Compiles each Accellera TLM-2.0 source file to .o and links with `vendor/libsystemc.a`,
then runs `vendor/verify_accellera.exe` to generate `web/accellera_verified_trace.json`.
"""
import json
import os
import subprocess
import sys

COMMON_SRC = "models/accellera_tlm/common/src"
LT_TD_SRC = "models/accellera_tlm/lt_temporal_decouple/src"

MODEL_SRCS = [
    f"{COMMON_SRC}/at_target_1_phase.cpp",
    f"{COMMON_SRC}/at_target_2_phase.cpp",
    f"{COMMON_SRC}/at_target_4_phase.cpp",
    f"{COMMON_SRC}/dmi_memory.cpp",
    f"{COMMON_SRC}/lt_dmi_initiator.cpp",
    f"{COMMON_SRC}/lt_dmi_target.cpp",
    f"{COMMON_SRC}/lt_synch_target.cpp",
    f"{COMMON_SRC}/lt_target.cpp",
    f"{COMMON_SRC}/lt_td_initiator.cpp",
    f"{COMMON_SRC}/lt_initiator.cpp",
    f"{COMMON_SRC}/select_initiator.cpp",
    f"{COMMON_SRC}/traffic_generator.cpp",
    f"{COMMON_SRC}/memory.cpp",
    f"{COMMON_SRC}/report.cpp",
    f"{LT_TD_SRC}/td_initiator_top.cpp",
    "models/verify_accellera_models.cpp",
]

OBJ_DIR = "vendor/model_obj"
EXE_OUT = "vendor/verify_accellera.exe"


def main():
    os.makedirs(OBJ_DIR, exist_ok=True)
    objs = []
    for src in MODEL_SRCS:
        base = os.path.basename(src).replace(".cpp", ".o")
        obj = os.path.join(OBJ_DIR, base)
        if os.path.exists(obj) and os.path.getmtime(obj) >= os.path.getmtime(src) and src != "models/verify_accellera_models.cpp":
            objs.append(obj)
            continue
        cmd = [
            sys.executable,
            "-m",
            "ziglang",
            "c++",
            "-std=c++17",
            "-O2",
            "-w",
            "-Iinclude",
            "-Ivendor/systemc-main/src",
            "-Imodels/accellera_tlm/common/include",
            "-Imodels/accellera_tlm/lt_temporal_decouple/include",
            "-Imodels/accellera_tlm/at_mixed_targets/include",
            "-Ivendor/systemc-main/examples/tlm/lt_dmi/include",
            "-c",
            src,
            "-o",
            obj,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Compile Error on {src}:\n", res.stderr)
            sys.exit(1)
        objs.append(obj)

    print("Linking verify_accellera.exe...")
    link_cmd = [
        sys.executable,
        "-m",
        "ziglang",
        "c++",
        "-O2",
        "-w",
        *objs,
        "vendor/libsystemc.a",
        "-o",
        EXE_OUT,
    ]
    res = subprocess.run(link_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Link Error:\n", res.stderr)
        sys.exit(1)

    print("Running SystemC simulation (verify_accellera.exe)...")
    sim = subprocess.run([EXE_OUT], capture_output=True, text=True)
    print(sim.stdout[-1500:] if len(sim.stdout) > 1500 else sim.stdout)
    if sim.returncode != 0:
        print("Sim stderr:\n", sim.stderr)
        sys.exit(1)

    with open("web/accellera_verified_trace.json", "r", encoding="utf-8") as fp:
        trace = json.load(fp)
    print(
        f"Verified Trace Summary: {trace['meta']['num_frames']} frames "
        f"(0 -> {trace['meta']['total_time_ns']} ns), "
        f"{len(trace['nodes'])} nodes, {len(trace['links'])} links, "
        f"{len(trace['tokens'])} discrete transactions recorded!"
    )


if __name__ == "__main__":
    main()
