# systemc-tlm-visualizer (`v0.1.0`)

一套針對 **IEEE 1666 SystemC / TLM-2.0（LT / AT / DMI / `sc_fifo`）** 的無侵入式模擬紀錄與互動視覺化工具，已透過 Accellera SystemC 3.0.2 官方範例模型（`lt_temporal_decouple`、`lt_dmi`、`at_mixed_targets`）完成實機編譯與驗證。

---

## 1. 核心特色

- **無侵入式 Header-Only C++17 探針（[`include/sc_tlm_heatmap.hpp`](include/sc_tlm_heatmap.hpp)）**：
  - 完整攔截 `b_transport`（LT 鬆散時間與 QuantumKeeper 時間解耦）、`nb_transport_fw` / `nb_transport_bw`（AT 四階段交握：`BEGIN_REQ`、`END_REQ`、`BEGIN_RESP`、`END_RESP`）與 `get_direct_mem_ptr` / `invalidate_direct_mem_ptr`（DMI 直連授權與失效）。
  - 自動透過 `sc_core::sc_get_top_level_objects()` 探索硬體階層、自動推論節點角色（Master / Interconnect / Bridge / Memory）並取樣 `sc_fifo` 佇列深度。
  - 擷取 `tlm_generic_payload::get_data_ptr()` 實際讀寫資料（Hex 與 Byte Dump）及 `sc_report_handler`（`SC_REPORT_INFO`）終端機訊息。
- **零後端依賴單頁互動視覺化介面（[`web/index.html`](web/index.html)）**：
  - **Events**：支援單步事件跳轉（`⏮ Prev` / `Next ⏭`）、時間微調（`-10ns` / `+10ns`）、拉桿拖曳、縮放（`🔍+` / `🔍-` / `100%`）與整合式播放速度 Combo-Box（支援下拉選單與自訂數值輸入）。
  - **Topology**：通用 SoC 拓樸自動排版引擎，支援單一匯流排、多子系統（NUMA / 雙叢集）、多層階層匯流排與快取（L1/L2/AXI/APB）、點對點資料流管線（Pipeline）與 2D Mesh / Ring NoC，並提供在途封包懸浮預覽與點擊釘選。
  - **Messages**：隨模擬時間軸即時同步過濾並印出硬體模擬終端機輸出訊息。

---

## 2. 專案目錄結構

- [`include/sc_tlm_heatmap.hpp`](include/sc_tlm_heatmap.hpp)：Header-Only C++17 探針與紀錄器（`TlmSocketProbe`、`HeatmapRecorder`）。
- [`models/verify_accellera_models.cpp`](models/verify_accellera_models.cpp)：串聯 Accellera 官方 LT / DMI / AT 範例模型之雙匯流排驗證平台。
- [`models/accellera_tlm/`](models/accellera_tlm/)：Accellera SystemC TLM-2.0 官方範例模型原始碼。
- [`tools/build_systemc_lib.py`](tools/build_systemc_lib.py)：自動下載並編譯 Accellera SystemC 3.0.2 核心靜態庫（`vendor/libsystemc.a`）。
- [`tools/run_accellera_verification.py`](tools/run_accellera_verification.py)：編譯並執行 SystemC 驗證模擬，匯出 [`web/accellera_verified_trace.json`](web/accellera_verified_trace.json)。
- [`tools/update_web_with_verified_trace.py`](tools/update_web_with_verified_trace.py)：將最新驗證紀錄打包並生成前端視覺化介面 [`web/index.html`](web/index.html)。
- [`web/index.html`](web/index.html)：零後端依賴的獨立單頁互動視覺化介面。

---

## 3. 快速建置與執行流程

```powershell
# 1. (首次執行) 下載並建置 SystemC 3.0.2 靜態庫至 vendor/libsystemc.a
python tools/build_systemc_lib.py

# 2. 編譯並執行 Accellera SystemC 3.0 官方模型驗證，產生 web/accellera_verified_trace.json
python tools/run_accellera_verification.py

# 3. 更新獨立前端視覺化網頁 web/index.html
python tools/update_web_with_verified_trace.py
```

完成後可直接用瀏覽器開啟 [`web/index.html`](web/index.html)，或透過介面右上角 **「📂 Load Trace」** 載入任意 `.json` 模擬紀錄。
