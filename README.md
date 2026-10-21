# systemc-tlm-visualizer (`v0.1.0`)

A non-intrusive simulation profiler and interactive post-simulation visualizer for **IEEE 1666 SystemC / TLM-2.0 (LT / AT / DMI / `sc_fifo`)**, compiled and verified against official Accellera SystemC 3.0.2 reference models (`lt_temporal_decouple`, `lt_dmi`, `at_mixed_targets`).

---

## 1. Key Features

- **Header-Only C++17 TLM-2.0 Probe ([`include/sc_tlm_heatmap.hpp`](include/sc_tlm_heatmap.hpp))**:
  - Transparently intercepts `b_transport` (Loosely-Timed & QuantumKeeper temporal decoupling), `nb_transport_fw` / `nb_transport_bw` (Approximately-Timed 4-phase handshakes: `BEGIN_REQ`, `END_REQ`, `BEGIN_RESP`, `END_RESP`), and `get_direct_mem_ptr` / `invalidate_direct_mem_ptr` (DMI grant and invalidation).
  - Automatically traverses the `sc_core::sc_get_top_level_objects()` hierarchy to infer module roles (`Master`, `Interconnect`, `Bridge`, `Memory`) and periodically samples `sc_fifo` depths.
  - Captures `tlm_generic_payload::get_data_ptr()` read/write payloads (Hex & byte dump) and intercepts `sc_report_handler` (`SC_REPORT_INFO`) simulation messages.
- **Zero-Dependency Single-Page Visualizer ([`web/index.html`](web/index.html))**:
  - **Events**: Discrete event swimlane Gantt chart with single-step navigation (`⏮ Prev` / `Next ⏭`), fine time stepping (`-10ns` / `+10ns`), timeline scrubbing, zoom controls (`🔍+` / `🔍-` / `100%`), and a unified playback speed combo-box (preset dropdown + custom numeric input).
  - **Topology**: Universal SoC auto-layout engine supporting Single Bus, Multi-Subsystem (NUMA / Dual-Cluster), Multi-Tier Hierarchical Bus & Cache (L1/L2/AXI/APB), Point-to-Point Pipeline, and 2D Mesh / Ring NoC architectures, with hover-to-preview and click-to-pin inspection on in-flight packets.
  - **Messages**: Real-time synchronized terminal output viewer displaying simulation logs up to the current playback timestamp.

---

## 2. Repository Structure

- [`include/sc_tlm_heatmap.hpp`](include/sc_tlm_heatmap.hpp): Header-only C++17 TLM-2.0 socket probe and trace recorder (`TlmSocketProbe`, `HeatmapRecorder`).
- [`models/verify_accellera_models.cpp`](models/verify_accellera_models.cpp): Dual-bus verification platform integrating official Accellera LT, DMI, and AT reference models.
- [`models/accellera_tlm/`](models/accellera_tlm/): Official Accellera SystemC TLM-2.0 example model sources.
- [`tools/build_systemc_lib.py`](tools/build_systemc_lib.py): Automated script to download and build the Accellera SystemC 3.0.2 core static library (`vendor/libsystemc.a`).
- [`tools/run_accellera_verification.py`](tools/run_accellera_verification.py): Compiles and executes the SystemC verification binary to export [`web/accellera_verified_trace.json`](web/accellera_verified_trace.json).
- [`tools/update_web_with_verified_trace.py`](tools/update_web_with_verified_trace.py): Bundles the verified trace and generates the standalone web visualizer [`web/index.html`](web/index.html).
- [`web/index.html`](web/index.html): Self-contained interactive HTML5/SVG visualizer.

---

## 3. Quick Start

```powershell
# 1. (First-time setup) Download and build SystemC 3.0.2 static library into vendor/libsystemc.a
python tools/build_systemc_lib.py

# 2. Compile and run the Accellera SystemC 3.0 verification suite to generate web/accellera_verified_trace.json
python tools/run_accellera_verification.py

# 3. Regenerate the standalone visualizer web/index.html
python tools/update_web_with_verified_trace.py
```

Open [`web/index.html`](web/index.html) directly in any modern browser, or click **"📂 Load Trace"** in the top-right corner of the UI to load any custom `.json` trace file.

---

## 4. License

Licensed under the **Apache License, Version 2.0** (see [`LICENSE`](LICENSE)).  
Reference SystemC TLM-2.0 models under [`models/accellera_tlm/`](models/accellera_tlm/) are licensed by Accellera Systems Initiative Inc. under the Apache License, Version 2.0.

