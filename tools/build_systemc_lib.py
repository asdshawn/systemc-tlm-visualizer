#!/usr/bin/env python3
"""
Builds the official Accellera SystemC + TLM-2.0 kernel static library (`vendor/libsystemc.a`)
using `python -m ziglang c++` and `python -m ziglang ar`.
"""
import concurrent.futures
import glob
import os
import subprocess
import sys

SRC_ROOT = "vendor/systemc-main/src"
OBJ_DIR = "vendor/obj"
LIB_OUT = "vendor/libsystemc.a"


def compile_one(cpp_path):
    rel = os.path.relpath(cpp_path, SRC_ROOT).replace("\\", "_").replace("/", "_")
    obj_path = os.path.join(OBJ_DIR, rel + ".o")
    if os.path.exists(obj_path):
        return obj_path
    cmd = [
        sys.executable,
        "-m",
        "ziglang",
        "c++",
        "-std=c++17",
        "-O2",
        "-w",
        f"-I{SRC_ROOT}",
        "-c",
        cpp_path,
        "-o",
        obj_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed on {cpp_path}:\n{res.stderr}")
    return obj_path


def main():
    os.makedirs(OBJ_DIR, exist_ok=True)
    cpp_files = sorted(glob.glob(f"{SRC_ROOT}/**/*.cpp", recursive=True))
    print(f"Compiling {len(cpp_files)} SystemC kernel source files...")
    objs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for obj in ex.map(compile_one, cpp_files):
            objs.append(obj)

    print(f"Archiving {len(objs)} objects into {LIB_OUT}...")
    if os.path.exists(LIB_OUT):
        os.remove(LIB_OUT)
    ar_cmd = [sys.executable, "-m", "ziglang", "ar", "rcs", LIB_OUT] + objs
    subprocess.run(ar_cmd, check=True)
    print(f"Successfully built {LIB_OUT} ({os.path.getsize(LIB_OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
