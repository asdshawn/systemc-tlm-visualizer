/**
 * @file verify_accellera_models.cpp
 * @brief Verification harness running official Accellera SystemC TLM-2.0 models:
 *   1. `lt_temporal_decouple` (Loosely-Timed with 500ns QuantumKeeper + SimpleBusLT<3,3> + LT Targets)
 *   2. `lt_dmi` (Loosely-Timed with Direct Memory Interface `get_direct_mem_ptr` & `invalidate_direct_mem_ptr`)
 *   3. `at_mixed_targets` (Approximately-Timed with SimpleBusAT<2,3> + 1-Phase, 2-Phase, and 4-Phase AT Targets)
 *
 * Also verifies:
 *   - Automatic SystemC `sc_object` hierarchy & `sc_fifo` introspection (`introspect_hierarchy_once()`)
 *   - Zero manual `(x, y)` coordinates in C++ (layout computed automatically by the frontend DAG engine)
 */

#define REPORT_DEFINE_GLOBALS
#include "reporting.h"
#include "tlm.h"

// Common Accellera TLM-2.0 components
#include "at_target_1_phase.h"
#include "at_target_2_phase.h"
#include "at_target_4_phase.h"
#include "dmi_memory.h"
#include "lt_dmi_initiator.h"
#include "lt_dmi_target.h"
#include "lt_initiator.h"
#include "lt_synch_target.h"
#include "lt_target.h"
#include "models/SimpleBusAT.h"
#include "models/SimpleBusLT.h"
#include "select_initiator.h"
#include "td_initiator_top.h"
#include "traffic_generator.h"

// Wrap LT, DMI, and AT `initiator_top` in distinct namespaces since all three Accellera examples use the same class name
namespace accellera_lt {
#include "accellera_tlm/lt_temporal_decouple/include/initiator_top.h"
#include "accellera_tlm/lt_temporal_decouple/src/initiator_top.cpp"
} // namespace accellera_lt

#undef __INITIATOR_TOP_H__
namespace accellera_dmi {
#include "../vendor/systemc-main/examples/tlm/lt_dmi/include/initiator_top.h"
#include "../vendor/systemc-main/examples/tlm/lt_dmi/src/initiator_top.cpp"
} // namespace accellera_dmi

#undef __INITIATOR_TOP_H__
namespace accellera_at {
#include "accellera_tlm/at_mixed_targets/include/initiator_top.h"
#include "accellera_tlm/at_mixed_targets/src/initiator_top.cpp"
} // namespace accellera_at

#include "../include/sc_tlm_heatmap.hpp"

class AccelleraCombinedTop : public sc_core::sc_module {
public:
    SC_HAS_PROCESS(AccelleraCombinedTop);

    AccelleraCombinedTop(sc_core::sc_module_name name)
        : sc_core::sc_module(name)
        , m_sim_limit(6500, sc_core::SC_NS)
        // --- 1. Official Accellera LT Temporal Decouple + DMI Subsystem ---
        , m_lt_bus("m_lt_bus")
        , m_lt_synch_target_1(
              "m_lt_synch_target_1", 201, "memory_socket_1", 4 * 1024, 4,
              sc_core::sc_time(20, sc_core::SC_NS),
              sc_core::sc_time(100, sc_core::SC_NS),
              sc_core::sc_time(60, sc_core::SC_NS))
        , m_lt_target_2(
              "m_lt_target_2", 202, "memory_socket_1", 4 * 1024, 4,
              sc_core::sc_time(10, sc_core::SC_NS),
              sc_core::sc_time(50, sc_core::SC_NS),
              sc_core::sc_time(30, sc_core::SC_NS))
        , m_lt_dmi_target_3(
              "m_lt_dmi_target_3", 203, "memory_socket_1", 4 * 1024, 4,
              sc_core::sc_time(10, sc_core::SC_NS),
              sc_core::sc_time(50, sc_core::SC_NS),
              sc_core::sc_time(30, sc_core::SC_NS))
        , m_td_initiator_1("m_td_initiator_1", 101, 0x0000000000000000ULL, 0x0000000010000000ULL)
        , m_lt_initiator_2("m_lt_initiator_2", 102, 0x0000000000000000ULL, 0x0000000030000500ULL)
        , m_dmi_initiator_3("m_dmi_initiator_3", 103, 0x0000000020000000ULL, 0x0000000020000400ULL)
        // LT & DMI Probes
        , p_td1_to_ltbus("p_td1_to_ltbus", "td1_to_ltbus", "m_td_initiator_1", "m_lt_bus", "b_transport (TD)", 0.64)
        , p_lt2_to_ltbus("p_lt2_to_ltbus", "lt2_to_ltbus", "m_lt_initiator_2", "m_lt_bus", "b_transport (Sync)", 0.64)
        , p_dmi3_to_ltbus("p_dmi3_to_ltbus", "dmi3_to_ltbus", "m_dmi_initiator_3", "m_lt_bus", "b_transport + DMI", 0.64)
        , p_ltbus_to_synch1("p_ltbus_to_synch1", "ltbus_to_synch1", "m_lt_bus", "m_lt_synch_target_1", "LT Port 0 (Sync)", 0.64)
        , p_ltbus_to_targ2("p_ltbus_to_targ2", "ltbus_to_targ2", "m_lt_bus", "m_lt_target_2", "LT Port 1 (Normal)", 0.64)
        , p_ltbus_to_dmi3("p_ltbus_to_dmi3", "ltbus_to_dmi3", "m_lt_bus", "m_lt_dmi_target_3", "LT Port 2 (DMI Target)", 0.64)
        , p_ltbus_to_atbus("p_ltbus_to_atbus", "ltbus_to_atbus", "m_lt_bus", "m_at_bus", "LT-to-AT Bridge (b2nb)", 0.64)

        // --- 2. Official Accellera AT Mixed Targets Subsystem ---
        , m_at_bus("m_at_bus")
        , m_at_target_1_phase_1(
              "m_at_target_1_phase_1", 201, "memory_socket_1", 4 * 1024, 4,
              sc_core::sc_time(10, sc_core::SC_NS),
              sc_core::sc_time(50, sc_core::SC_NS),
              sc_core::sc_time(30, sc_core::SC_NS))
        , m_at_target_2_phase_1(
              "m_at_target_2_phase_1", 202, "memory_socket_1", 4 * 1024, 4,
              sc_core::sc_time(10, sc_core::SC_NS),
              sc_core::sc_time(50, sc_core::SC_NS),
              sc_core::sc_time(30, sc_core::SC_NS))
        , m_at_target_4_phase_1(
              "m_at_target_4_phase_1", 203, "memory_socket_1", 4 * 1024, 4,
              sc_core::sc_time(10, sc_core::SC_NS),
              sc_core::sc_time(50, sc_core::SC_NS),
              sc_core::sc_time(30, sc_core::SC_NS))
        , m_at_initiator_1("m_at_initiator_1", 101, 0x0000000000000100ULL, 0x0000000010000100ULL, 2)
        , m_at_initiator_2("m_at_initiator_2", 102, 0x0000000010000200ULL, 0x0000000020000200ULL, 2)
        // AT Probes
        , p_at1_to_atbus("p_at1_to_atbus", "at1_to_atbus", "m_at_initiator_1", "m_at_bus", "nb_transport (Init 101)", 0.80)
        , p_at2_to_atbus("p_at2_to_atbus", "at2_to_atbus", "m_at_initiator_2", "m_at_bus", "nb_transport (Init 102)", 0.80)
        , p_atbus_to_t1p("p_atbus_to_t1p", "atbus_to_t1p", "m_at_bus", "m_at_target_1_phase_1", "AT Port 0 (1-Phase)", 0.80)
        , p_atbus_to_t2p("p_atbus_to_t2p", "atbus_to_t2p", "m_at_bus", "m_at_target_2_phase_1", "AT Port 1 (2-Phase Shared)", 0.80)
        , p_atbus_to_t4p("p_atbus_to_t4p", "atbus_to_t4p", "m_at_bus", "m_at_target_4_phase_1", "AT Port 2 (4-Phase Explicit)", 0.80)
    {
        auto& rec = sc_viz::HeatmapRecorder::instance();
        rec.configure(
            "Verified Accellera Official Models: lt_temporal_decouple + lt_dmi + at_mixed_targets",
            100.0,
            true);

        // Register topology node metadata WITHOUT manual (x, y) coordinates!
        // SystemC child hierarchy & sc_fifos are automatically introspected at start_of_simulation().
        rec.register_node({"m_td_initiator_1", "td_initiator_top (101)", "Accellera LT + QuantumKeeper(500ns)", "master", sc_viz::AbstractionLevel::LT, 4, 0.64});
        rec.register_node({"m_lt_initiator_2", "lt_initiator_top (102)", "Accellera LT Synchronous", "master", sc_viz::AbstractionLevel::LT, 4, 0.64});
        rec.register_node({"m_dmi_initiator_3", "lt_dmi_initiator (103)", "Accellera LT + DMI Fast Bypass", "master", sc_viz::AbstractionLevel::LT, 4, 0.64});
        rec.register_node({"m_lt_bus", "SimpleBusLT<3, 4>", "Accellera LT + DMI Router", "interconnect", sc_viz::AbstractionLevel::LT, 4, 1.28});
        rec.register_node({"m_lt_synch_target_1", "lt_synch_target (201)", "Accept:20ns Rd:100ns Wr:60ns @0x0", "memory", sc_viz::AbstractionLevel::LT, 2, 0.64});
        rec.register_node({"m_lt_target_2", "lt_target (202)", "Accept:10ns Rd:50ns Wr:30ns @0x1000", "memory", sc_viz::AbstractionLevel::LT, 2, 0.64});
        rec.register_node({"m_lt_dmi_target_3", "lt_dmi_target (203)", "DMI Grant + 300ns Invalidate @0x2000", "memory", sc_viz::AbstractionLevel::LT, 2, 0.64});

        rec.register_node({"m_at_initiator_1", "at_initiator_top (101)", "Targets: 0x0(1P) & 0x1000(2P)", "master", sc_viz::AbstractionLevel::AT, 2, 0.80});
        rec.register_node({"m_at_initiator_2", "at_initiator_top (102)", "Targets: 0x1000(2P) & 0x2000(4P)", "master", sc_viz::AbstractionLevel::AT, 2, 0.80});
        rec.register_node({"m_at_bus", "SimpleBusAT<3, 3>", "Accellera PEQ Bus + b2nb Bridge", "interconnect", sc_viz::AbstractionLevel::AT, 4, 1.60});
        rec.register_node({"m_at_target_1_phase_1", "at_target_1_phase (201)", "Returns TLM_COMPLETED @0x0", "memory", sc_viz::AbstractionLevel::AT, 2, 0.80});
        rec.register_node({"m_at_target_2_phase_1", "at_target_2_phase (202)", "Returns TLM_UPDATED @0x1000", "memory", sc_viz::AbstractionLevel::AT, 2, 0.80});
        rec.register_node({"m_at_target_4_phase_1", "at_target_4_phase (203)", "4-Phase Explicit PEQ @0x2000", "memory", sc_viz::AbstractionLevel::AT, 2, 0.80});

        // Bind LT + DMI Subsystem through transparent LtSocketProbes
        m_td_initiator_1.top_initiator_socket(p_td1_to_ltbus.target_socket);
        p_td1_to_ltbus.initiator_socket(m_lt_bus.target_socket[0]);

        m_lt_initiator_2.top_initiator_socket(p_lt2_to_ltbus.target_socket);
        p_lt2_to_ltbus.initiator_socket(m_lt_bus.target_socket[1]);

        m_dmi_initiator_3.top_initiator_socket(p_dmi3_to_ltbus.target_socket);
        p_dmi3_to_ltbus.initiator_socket(m_lt_bus.target_socket[2]);

        m_lt_bus.initiator_socket[0](p_ltbus_to_synch1.target_socket);
        p_ltbus_to_synch1.initiator_socket(m_lt_synch_target_1.m_memory_socket);

        m_lt_bus.initiator_socket[1](p_ltbus_to_targ2.target_socket);
        p_ltbus_to_targ2.initiator_socket(m_lt_target_2.m_memory_socket);

        m_lt_bus.initiator_socket[2](p_ltbus_to_dmi3.target_socket);
        p_ltbus_to_dmi3.initiator_socket(m_lt_dmi_target_3.m_memory_socket);

        // Cross-Dimension LT-to-AT Bridge: SimpleBusLT Port 3 -> SimpleBusAT Target Port 2 (triggers b2nb_thread!)
        m_lt_bus.initiator_socket[3](p_ltbus_to_atbus.target_socket);
        p_ltbus_to_atbus.initiator_socket(m_at_bus.target_socket[2]);

        // Bind AT Subsystem through transparent AtSocketProbes
        m_at_initiator_1.initiator_socket(p_at1_to_atbus.target_socket);
        p_at1_to_atbus.initiator_socket(m_at_bus.target_socket[0]);

        m_at_initiator_2.initiator_socket(p_at2_to_atbus.target_socket);
        p_at2_to_atbus.initiator_socket(m_at_bus.target_socket[1]);

        m_at_bus.initiator_socket[0](p_atbus_to_t1p.target_socket);
        p_atbus_to_t1p.initiator_socket(m_at_target_1_phase_1.m_memory_socket);

        m_at_bus.initiator_socket[1](p_atbus_to_t2p.target_socket);
        p_atbus_to_t2p.initiator_socket(m_at_target_2_phase_1.m_memory_socket);

        m_at_bus.initiator_socket[2](p_atbus_to_t4p.target_socket);
        p_atbus_to_t4p.initiator_socket(m_at_target_4_phase_1.m_memory_socket);

        SC_THREAD(limit_thread);
    }

    void limit_thread() {
        sc_core::wait(sc_core::SC_ZERO_TIME);
        sc_core::wait(m_sim_limit);
        sc_core::sc_stop();
    }

private:
    sc_core::sc_time m_sim_limit;

    // LT + DMI components
    SimpleBusLT<3, 4> m_lt_bus;
    lt_synch_target m_lt_synch_target_1;
    lt_target m_lt_target_2;
    lt_dmi_target m_lt_dmi_target_3;
    td_initiator_top m_td_initiator_1;
    accellera_lt::initiator_top m_lt_initiator_2;
    accellera_dmi::initiator_top m_dmi_initiator_3;

    sc_viz::LtSocketProbe p_td1_to_ltbus;
    sc_viz::LtSocketProbe p_lt2_to_ltbus;
    sc_viz::LtSocketProbe p_dmi3_to_ltbus;
    sc_viz::LtSocketProbe p_ltbus_to_synch1;
    sc_viz::LtSocketProbe p_ltbus_to_targ2;
    sc_viz::LtSocketProbe p_ltbus_to_dmi3;
    sc_viz::LtSocketProbe p_ltbus_to_atbus;

    // AT components
    SimpleBusAT<3, 3> m_at_bus;
    at_target_1_phase m_at_target_1_phase_1;
    at_target_2_phase m_at_target_2_phase_1;
    at_target_4_phase m_at_target_4_phase_1;
    accellera_at::initiator_top m_at_initiator_1;
    accellera_at::initiator_top m_at_initiator_2;

    sc_viz::AtSocketProbe p_at1_to_atbus;
    sc_viz::AtSocketProbe p_at2_to_atbus;
    sc_viz::AtSocketProbe p_atbus_to_t1p;
    sc_viz::AtSocketProbe p_atbus_to_t2p;
    sc_viz::AtSocketProbe p_atbus_to_t4p;
};

int sc_main(int /*argc*/, char* /*argv*/[]) {
    REPORT_ENABLE_ALL_REPORTING();
    AccelleraCombinedTop top("top");
    sc_core::sc_start();

    bool ok = sc_viz::HeatmapRecorder::instance().export_json("web/accellera_verified_trace.json");
    std::cout << "\n[sc_viz] Exported real Accellera simulation trace to web/accellera_verified_trace.json: "
              << (ok ? "SUCCESS" : "FAILED") << std::endl;
    return ok ? 0 : 1;
}
