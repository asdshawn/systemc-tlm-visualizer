#ifndef SC_TLM_HEATMAP_HPP
#define SC_TLM_HEATMAP_HPP

/**
 * @file sc_tlm_heatmap.hpp
 * @brief Header-only SystemC TLM-2.0 (LT / AT / DMI / sc_fifo) Post-Simulation Heatmap & Token Trace Recorder
 *
 * Verified against official Accellera SystemC TLM-2.0 models:
 * - `lt_temporal_decouple` (Loosely-Timed + `tlm_quantumkeeper` local time offset)
 * - `lt_dmi` (Direct Memory Interface grant `get_direct_mem_ptr` & invalidation `invalidate_direct_mem_ptr`)
 * - `at_mixed_targets` (Approximately-Timed 1-Phase `TLM_COMPLETED`, 2-Phase `TLM_UPDATED`, 4-Phase `TLM_ACCEPTED`)
 * - Automatic SystemC `sc_object` hierarchy & `sc_fifo` introspection at `start_of_simulation()`.
 */

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace sc_viz {

enum class AbstractionLevel {
    LT, // Loosely-Timed (b_transport, temporal decoupling, DMI)
    AT  // Approximately-Timed (nb_transport_fw/bw, 1/2/4-phase)
};

inline std::string to_string(AbstractionLevel lvl) {
    return (lvl == AbstractionLevel::LT) ? "LT" : "AT";
}

struct ChildObjectInfo {
    std::string name;      // Local basename, e.g. "m_request_fifo"
    std::string full_name; // Full SystemC hierarchical path
    std::string kind;      // e.g. "sc_fifo", "sc_module", "tlm_initiator_socket", "sc_thread_process"
    int fifo_capacity = 0;
    int fifo_peak_used = 0;
    uint32_t fifo_samples_nonempty = 0;
    sc_core::sc_fifo<tlm::tlm_generic_payload*>* fifo_ptr = nullptr;
};

struct NodeMeta {
    std::string id;
    std::string label;
    std::string sub;
    std::string type; // "master", "interconnect", "memory", "bridge"
    AbstractionLevel abstraction = AbstractionLevel::AT;
    uint32_t max_outstanding = 4;
    double max_bandwidth_gbps = 1.6;
    int x = -1; // -1 means auto-layout in frontend DAG engine
    int y = -1;
    std::string sc_full_name;
    std::string sc_kind;
    std::vector<ChildObjectInfo> children;
};

struct LinkMeta {
    std::string id;
    std::string source;
    std::string target;
    std::string label;
    AbstractionLevel abstraction = AbstractionLevel::AT;
    double max_bandwidth_gbps = 1.6;
};

struct WindowMetrics {
    double bytes_transferred = 0.0;
    double backpressure_ns = 0.0;      // AT: sum of (END_REQ - BEGIN_REQ) in window
    double inflight_integral_ns = 0.0; // Integrated (in_flight_count * dt)
    uint32_t peak_inflight = 0;
    uint32_t tx_count = 0;
    double max_quantum_offset_ns = 0.0; // LT: temporal decoupling local time offset
    bool dmi_active = false;            // LT/AT: Direct Memory Interface grant active in window
    uint32_t peak_fifo_used = 0;        // Max sc_fifo occupancy observed on source node during window
};

struct TokenEvent {
    uint64_t id = 0;
    std::string link_id;
    std::string cmd; // "RD", "WR", "DMI_GRANT", "DMI_INV"
    uint64_t address = 0;
    uint32_t data_length = 0;
    AbstractionLevel abstraction = AbstractionLevel::AT;
    std::string protocol_note; // e.g., "AT 4-Phase", "AT 2-Phase", "AT 1-Phase", "LT-TD", "DMI Grant", "DMI Invalidate"
    std::string data_hex;      // Actual payload bytes from trans.get_data_ptr()
    std::string resp_status;   // Actual response status from trans.get_response_string()
    double t1_req_start_ns = 0.0;
    double t2_req_end_ns = 0.0;
    double t3_resp_start_ns = 0.0;
    double t4_resp_end_ns = 0.0;
    double q_offset_ns = 0.0;
};

struct DmiState {
    bool active = false;
    double grant_start_ns = 0.0;
    uint64_t start_addr = 0;
    uint64_t end_addr = 0;
};

struct ReportLogEntry {
    double time_ns = 0.0;
    std::string text;
};

class HeatmapRecorder {
public:
    static HeatmapRecorder& instance() {
        static HeatmapRecorder inst;
        return inst;
    }

    void configure(const std::string& title, double base_window_ns = 100.0, bool record_tokens = true) {
        m_title = title;
        m_window_ns = base_window_ns;
        m_record_tokens = record_tokens;
    }

    void register_node(const NodeMeta& node) {
        if (m_nodes.find(node.id) == m_nodes.end()) {
            m_node_order.push_back(node.id);
        }
        m_nodes[node.id] = node;
    }

    void register_link(const LinkMeta& link) {
        if (m_links.find(link.id) == m_links.end()) {
            m_link_order.push_back(link.id);
        }
        m_links[link.id] = link;
    }

    /**
     * @brief Automatically walks `sc_core::sc_get_top_level_objects()` to discover module hierarchy,
     * child sub-modules (`traffic_generator`, `peq_with_get`, etc.), internal `sc_fifo` channels,
     * TLM sockets, and SystemC processes. Also auto-registers any nodes referenced by links that
     * were not manually registered.
     */
    void introspect_hierarchy_once() {
        if (m_introspected) return;
        m_introspected = true;

        // 1. Ensure all link endpoints exist in m_nodes (auto-infer role from degree if not manually registered)
        std::unordered_map<std::string, int> out_deg;
        std::unordered_map<std::string, int> in_deg;
        std::unordered_map<std::string, AbstractionLevel> inferred_abs;
        for (const auto& lid : m_link_order) {
            const auto& l = m_links[lid];
            out_deg[l.source] += 1;
            in_deg[l.target] += 1;
            inferred_abs[l.source] = l.abstraction;
            inferred_abs[l.target] = l.abstraction;
        }
        for (const auto& lid : m_link_order) {
            const auto& l = m_links[lid];
            for (const std::string& nid : {l.source, l.target}) {
                if (m_nodes.find(nid) == m_nodes.end()) {
                    NodeMeta nm;
                    nm.id = nid;
                    nm.label = nid;
                    nm.sub = "硬體模組";
                    int od = out_deg[nid];
                    int idg = in_deg[nid];
                    if (od > 0 && idg > 0) {
                        nm.type = (od + idg >= 3) ? "interconnect" : "bridge";
                    } else if (od > 0) {
                        nm.type = "master";
                    } else {
                        nm.type = "memory";
                    }
                    nm.abstraction = inferred_abs[nid];
                    register_node(nm);
                }
            }
        }

        // 2. Walk SystemC object tree and map sc_objects by basename and full name
        std::unordered_map<std::string, sc_core::sc_object*> found_objects;
        const std::vector<sc_core::sc_object*>& tops = sc_core::sc_get_top_level_objects();
        for (sc_core::sc_object* top_obj : tops) {
            index_sc_objects_recursive(top_obj, found_objects);
        }

        // 3. Populate each registered NodeMeta with its real SystemC children & bind live sc_fifo pointers
        for (const std::string& nid : m_node_order) {
            NodeMeta& n = m_nodes[nid];
            auto it = found_objects.find(nid);
            if (it == found_objects.end()) continue;

            sc_core::sc_object* mod_obj = it->second;
            n.sc_full_name = mod_obj->name();
            n.sc_kind = mod_obj->kind();
            n.children.clear();
            collect_module_children_recursive(mod_obj, mod_obj->name(), n.children, 0);
        }
    }

    /**
     * @brief Samples all auto-discovered `sc_fifo<tlm_generic_payload*>` instances across nodes.
     */
    void sample_fifos(double now_ns) {
        size_t w = static_cast<size_t>(std::floor(now_ns / m_window_ns));
        for (const std::string& nid : m_node_order) {
            NodeMeta& n = m_nodes[nid];
            uint32_t node_peak_in_sample = 0;
            for (auto& child : n.children) {
                if (child.fifo_ptr != nullptr) {
                    int avail = child.fifo_ptr->num_available();
                    if (avail > child.fifo_peak_used) {
                        child.fifo_peak_used = avail;
                    }
                    if (avail > 0) {
                        child.fifo_samples_nonempty += 1;
                    }
                    if (static_cast<uint32_t>(avail) > node_peak_in_sample) {
                        node_peak_in_sample = static_cast<uint32_t>(avail);
                    }
                }
            }
            if (node_peak_in_sample > 0) {
                for (const std::string& lid : m_link_order) {
                    if (m_links[lid].source == nid) {
                        WindowMetrics& wm = m_window_data[lid][w];
                        wm.peak_fifo_used = std::max(wm.peak_fifo_used, node_peak_in_sample);
                    }
                }
            }
        }
    }

    /**
     * @brief Records a Loosely-Timed (LT) blocking transaction with Temporal Decoupling offset.
     */
    void record_lt_transport(
        const std::string& link_id,
        const tlm::tlm_generic_payload& trans,
        const sc_core::sc_time& delay_before,
        const sc_core::sc_time& delay_after,
        uint64_t original_addr)
    {
        double sc_now_ns = sc_core::sc_time_stamp().to_seconds() * 1e9;
        double d_in_ns = delay_before.to_seconds() * 1e9;
        double d_out_ns = delay_after.to_seconds() * 1e9;

        double t_start_ns = sc_now_ns + d_in_ns;
        double t_end_ns = sc_now_ns + d_out_ns;
        if (t_end_ns <= t_start_ns) {
            t_end_ns = t_start_ns + 10.0;
        }

        sample_fifos(t_start_ns);

        m_max_time_ns = std::max(m_max_time_ns, t_end_ns);
        double bytes = static_cast<double>(trans.get_data_length());
        double q_offset_ns = d_out_ns;
        double op_dur = t_end_ns - t_start_ns;
        double stall_est = (op_dur > 80.0) ? (op_dur - 80.0) : 0.0;

        distribute_to_windows(link_id, t_start_ns, t_end_ns, bytes, stall_est, 1.0, q_offset_ns);

        if (m_record_tokens) {
            TokenEvent ev;
            ev.id = ++m_next_token_id;
            ev.link_id = link_id;
            ev.cmd = trans.is_write() ? "WR" : "RD";
            ev.address = original_addr;
            ev.data_length = trans.get_data_length();
            ev.abstraction = AbstractionLevel::LT;
            ev.protocol_note = (d_in_ns > 0.0) ? "LT-TD (QuantumKeeper)" : "LT-Sync";
            ev.data_hex = extract_payload_data(trans);
            ev.resp_status = trans.get_response_string();
            ev.t1_req_start_ns = t_start_ns;
            ev.t2_req_end_ns = t_start_ns + stall_est;
            ev.t3_resp_start_ns = t_end_ns;
            ev.t4_resp_end_ns = t_end_ns;
            ev.q_offset_ns = q_offset_ns;
            m_tokens.push_back(ev);
        }
    }

    /**
     * @brief Records a Direct Memory Interface (DMI) pointer grant (`get_direct_mem_ptr`).
     */
    void record_dmi_grant(
        const std::string& link_id,
        uint64_t req_addr,
        const tlm::tlm_dmi& dmi_data)
    {
        double now_ns = sc_core::sc_time_stamp().to_seconds() * 1e9;
        sample_fifos(now_ns);
        m_max_time_ns = std::max(m_max_time_ns, now_ns + 20.0);

        DmiState& st = m_dmi_state[link_id];
        st.active = true;
        st.grant_start_ns = now_ns;
        st.start_addr = dmi_data.get_start_address();
        st.end_addr = dmi_data.get_end_address();

        size_t w = static_cast<size_t>(std::floor(now_ns / m_window_ns));
        m_window_data[link_id][w].dmi_active = true;

        if (m_record_tokens) {
            TokenEvent ev;
            ev.id = ++m_next_token_id;
            ev.link_id = link_id;
            ev.cmd = "DMI_GRANT";
            ev.address = req_addr;
            ev.data_length = static_cast<uint32_t>(
                (st.end_addr >= st.start_addr) ? (st.end_addr - st.start_addr + 1) : 4096);
            ev.abstraction = AbstractionLevel::LT;
            ev.protocol_note = "DMI Grant (get_direct_mem_ptr)";
            if (dmi_data.get_dmi_ptr() != nullptr) {
                uint64_t offset = (req_addr >= st.start_addr && req_addr + 4 <= st.end_addr) ? (req_addr - st.start_addr) : 0;
                uint32_t word = 0;
                std::memcpy(&word, dmi_data.get_dmi_ptr() + offset, 4);
                std::ostringstream oss;
                oss << "DMI* 0x" << std::hex << std::uppercase << std::setw(8) << std::setfill('0') << word
                    << (dmi_data.is_read_write_allowed() ? " (RW)" : " (RO)");
                ev.data_hex = oss.str();
            } else {
                ev.data_hex = "DMI_PTR (RW)";
            }
            ev.resp_status = "DMI_GRANTED";
            ev.t1_req_start_ns = now_ns;
            ev.t2_req_end_ns = now_ns + 5.0;
            ev.t3_resp_start_ns = now_ns + 15.0;
            ev.t4_resp_end_ns = now_ns + 20.0;
            m_tokens.push_back(ev);
        }
    }

    /**
     * @brief Records a Direct Memory Interface (DMI) pointer invalidation (`invalidate_direct_mem_ptr`).
     */
    void record_dmi_invalidate(
        const std::string& link_id,
        uint64_t start_range,
        uint64_t end_range)
    {
        auto it = m_dmi_state.find(link_id);
        if (it == m_dmi_state.end() || !it->second.active) {
            return; // Ignore broadcast invalidations on links that never requested DMI
        }

        double now_ns = sc_core::sc_time_stamp().to_seconds() * 1e9;
        sample_fifos(now_ns);
        m_max_time_ns = std::max(m_max_time_ns, now_ns + 20.0);

        double start_ns = it->second.grant_start_ns;
        it->second.active = false;

        // Mark all windows between DMI_GRANT and DMI_INVALIDATE as dmi_active
        size_t w_first = static_cast<size_t>(std::floor(start_ns / m_window_ns));
        size_t w_last = static_cast<size_t>(std::floor(now_ns / m_window_ns));
        for (size_t w = w_first; w <= w_last; ++w) {
            m_window_data[link_id][w].dmi_active = true;
        }

        if (m_record_tokens) {
            TokenEvent ev;
            ev.id = ++m_next_token_id;
            ev.link_id = link_id;
            ev.cmd = "DMI_INV";
            ev.address = start_range;
            ev.data_length = static_cast<uint32_t>(
                (end_range >= start_range) ? (end_range - start_range + 1) : 4096);
            ev.abstraction = AbstractionLevel::LT;
            ev.protocol_note = "DMI Invalidate (invalidate_direct_mem_ptr)";
            std::ostringstream oss;
            oss << "INV [0x" << std::hex << std::uppercase << start_range << "..0x" << end_range << "]";
            ev.data_hex = oss.str();
            ev.resp_status = "DMI_INVALIDATED";
            ev.t1_req_start_ns = now_ns;
            ev.t2_req_end_ns = now_ns + 5.0;
            ev.t3_resp_start_ns = now_ns + 15.0;
            ev.t4_resp_end_ns = now_ns + 20.0;
            m_tokens.push_back(ev);
        }
    }

    /**
     * @brief Records forward path `nb_transport_fw` call and its return status (`TLM_ACCEPTED/UPDATED/COMPLETED`).
     */
    void record_at_fw(
        const std::string& link_id,
        const tlm::tlm_generic_payload& trans,
        const tlm::tlm_phase& phase_in,
        const tlm::tlm_phase& phase_out,
        tlm::tlm_sync_enum status,
        const sc_core::sc_time& delay_in,
        const sc_core::sc_time& delay_out,
        uint64_t original_addr)
    {
        double now_ns = sc_core::sc_time_stamp().to_seconds() * 1e9;
        double t_in_ns = now_ns + delay_in.to_seconds() * 1e9;
        double t_out_ns = now_ns + delay_out.to_seconds() * 1e9;
        sample_fifos(now_ns);
        m_max_time_ns = std::max(m_max_time_ns, std::max(t_in_ns, t_out_ns));

        uintptr_t key = reinterpret_cast<uintptr_t>(&trans);

        if (phase_in == tlm::BEGIN_REQ) {
            TokenEvent& active = m_active_at[link_id][key];
            active.id = ++m_next_token_id;
            active.link_id = link_id;
            active.cmd = trans.is_write() ? "WR" : "RD";
            active.address = original_addr;
            active.data_length = trans.get_data_length();
            active.abstraction = AbstractionLevel::AT;
            active.data_hex = extract_payload_data(trans);
            active.resp_status = trans.get_response_string();
            active.t1_req_start_ns = t_in_ns;
            active.t2_req_end_ns = t_in_ns;
            active.t3_resp_start_ns = t_in_ns;
            active.t4_resp_end_ns = t_in_ns;

            if (status == tlm::TLM_COMPLETED) {
                active.protocol_note = "AT 1-Phase (TLM_COMPLETED)";
                double accept_part = std::min(10.0, (t_out_ns - t_in_ns) * 0.25);
                active.t2_req_end_ns = t_in_ns + accept_part;
                active.t3_resp_start_ns = t_out_ns;
                active.t4_resp_end_ns = t_out_ns;
                active.data_hex = extract_payload_data(trans);
                active.resp_status = trans.get_response_string();
                finalize_at_transaction(active);
                m_active_at[link_id].erase(key);
            } else if (status == tlm::TLM_UPDATED) {
                if (phase_out == tlm::END_REQ) {
                    active.protocol_note = "AT 2-Phase (TLM_UPDATED)";
                    active.t2_req_end_ns = std::max(active.t1_req_start_ns, t_out_ns);
                } else if (phase_out == tlm::BEGIN_RESP) {
                    active.protocol_note = "AT 2-Phase FastResp";
                    active.t2_req_end_ns = t_in_ns;
                    active.t3_resp_start_ns = std::max(active.t2_req_end_ns, t_out_ns);
                    active.data_hex = extract_payload_data(trans);
                    active.resp_status = trans.get_response_string();
                }
            } else {
                active.protocol_note = "AT 4-Phase (Explicit)";
            }
        } else if (phase_in == tlm::END_RESP) {
            auto it = m_active_at[link_id].find(key);
            if (it != m_active_at[link_id].end()) {
                it->second.t4_resp_end_ns = std::max(it->second.t3_resp_start_ns, t_out_ns);
                it->second.data_hex = extract_payload_data(trans);
                it->second.resp_status = trans.get_response_string();
                finalize_at_transaction(it->second);
                m_active_at[link_id].erase(it);
            }
        }
    }

    /**
     * @brief Records backward path `nb_transport_bw` call and its return status.
     */
    void record_at_bw(
        const std::string& link_id,
        const tlm::tlm_generic_payload& trans,
        const tlm::tlm_phase& phase_in,
        const tlm::tlm_phase& phase_out,
        tlm::tlm_sync_enum status,
        const sc_core::sc_time& delay_in,
        const sc_core::sc_time& delay_out)
    {
        double now_ns = sc_core::sc_time_stamp().to_seconds() * 1e9;
        double t_in_ns = now_ns + delay_in.to_seconds() * 1e9;
        double t_out_ns = now_ns + delay_out.to_seconds() * 1e9;
        sample_fifos(now_ns);
        m_max_time_ns = std::max(m_max_time_ns, std::max(t_in_ns, t_out_ns));

        uintptr_t key = reinterpret_cast<uintptr_t>(&trans);
        auto it = m_active_at[link_id].find(key);
        if (it == m_active_at[link_id].end()) return;

        TokenEvent& active = it->second;
        if (phase_in == tlm::END_REQ) {
            active.t2_req_end_ns = std::max(active.t1_req_start_ns, t_in_ns);
        } else if (phase_in == tlm::BEGIN_RESP) {
            if (active.t2_req_end_ns <= active.t1_req_start_ns) {
                active.t2_req_end_ns = t_in_ns;
            }
            active.t3_resp_start_ns = std::max(active.t2_req_end_ns, t_in_ns);
            active.data_hex = extract_payload_data(trans);
            active.resp_status = trans.get_response_string();

            if (status == tlm::TLM_COMPLETED || phase_out == tlm::END_RESP) {
                active.t4_resp_end_ns = std::max(active.t3_resp_start_ns, t_out_ns);
                finalize_at_transaction(active);
                m_active_at[link_id].erase(it);
            }
        }
    }

    bool export_json(const std::string& filepath) {
        introspect_hierarchy_once();

        // Flush any remaining in-flight transactions at simulation stop
        for (auto& link_kv : m_active_at) {
            for (auto& tx_kv : link_kv.second) {
                TokenEvent& ev = tx_kv.second;
                if (ev.t2_req_end_ns <= ev.t1_req_start_ns) ev.t2_req_end_ns = m_max_time_ns;
                if (ev.t3_resp_start_ns <= ev.t2_req_end_ns) ev.t3_resp_start_ns = m_max_time_ns;
                if (ev.t4_resp_end_ns <= ev.t3_resp_start_ns) ev.t4_resp_end_ns = m_max_time_ns;
                finalize_at_transaction(ev);
            }
        }
        m_active_at.clear();

        size_t num_windows = static_cast<size_t>(std::ceil(m_max_time_ns / m_window_ns));
        if (num_windows == 0) num_windows = 1;

        // If any DMI grant remained active until end of simulation, mark its windows
        for (auto& dmi_kv : m_dmi_state) {
            if (dmi_kv.second.active) {
                size_t w_first = static_cast<size_t>(std::floor(dmi_kv.second.grant_start_ns / m_window_ns));
                for (size_t w = w_first; w < num_windows; ++w) {
                    m_window_data[dmi_kv.first][w].dmi_active = true;
                }
            }
        }

        std::ofstream out(filepath);
        if (!out.is_open()) return false;

        out << std::fixed << std::setprecision(3);
        out << "{\n";
        out << "  \"meta\": {\n";
        out << "    \"title\": \"" << m_title << "\",\n";
        out << "    \"window_ns\": " << m_window_ns << ",\n";
        out << "    \"total_time_ns\": " << (num_windows * m_window_ns) << ",\n";
        out << "    \"num_frames\": " << num_windows << ",\n";
        out << "    \"auto_layout\": true,\n";
        out << "    \"hierarchy_introspected\": true\n";
        out << "  },\n";

        // 1. Nodes (with auto-discovered SystemC hierarchy & sc_fifo watermarks)
        out << "  \"nodes\": [\n";
        for (size_t i = 0; i < m_node_order.size(); ++i) {
            const auto& n = m_nodes[m_node_order[i]];
            out << "    {\"id\": \"" << n.id << "\", \"label\": \"" << n.label
                << "\", \"sub\": \"" << n.sub
                << "\", \"type\": \"" << n.type
                << "\", \"abstraction\": \"" << to_string(n.abstraction)
                << "\", \"max_outstanding\": " << n.max_outstanding
                << ", \"max_bandwidth_gbps\": " << n.max_bandwidth_gbps
                << ", \"sc_full_name\": \"" << n.sc_full_name
                << "\", \"sc_kind\": \"" << n.sc_kind
                << "\", \"x\": " << n.x << ", \"y\": " << n.y
                << ", \"children\": [";
            for (size_t c = 0; c < n.children.size(); ++c) {
                const auto& ch = n.children[c];
                out << "{\"name\": \"" << ch.name
                    << "\", \"full_name\": \"" << ch.full_name
                    << "\", \"kind\": \"" << ch.kind
                    << "\", \"fifo_capacity\": " << ch.fifo_capacity
                    << ", \"fifo_peak_used\": " << ch.fifo_peak_used
                    << ", \"fifo_samples\": " << ch.fifo_samples_nonempty << "}"
                    << (c + 1 < n.children.size() ? ", " : "");
            }
            out << "]}" << (i + 1 < m_node_order.size() ? "," : "") << "\n";
        }
        out << "  ],\n";

        // 2. Links
        out << "  \"links\": [\n";
        for (size_t i = 0; i < m_link_order.size(); ++i) {
            const auto& l = m_links[m_link_order[i]];
            out << "    {\"id\": \"" << l.id << "\", \"source\": \"" << l.source
                << "\", \"target\": \"" << l.target << "\", \"label\": \"" << l.label
                << "\", \"abstraction\": \"" << to_string(l.abstraction)
                << "\", \"max_bandwidth_gbps\": " << l.max_bandwidth_gbps << "}"
                << (i + 1 < m_link_order.size() ? "," : "") << "\n";
        }
        out << "  ],\n";

        // 3. Windowed Heatmap Frames
        out << "  \"frames\": [\n";
        for (size_t w = 0; w < num_windows; ++w) {
            out << "    {\"frame\": " << w << ", \"time_ns\": " << (w * m_window_ns) << ", \"links\": {";
            for (size_t i = 0; i < m_link_order.size(); ++i) {
                const std::string& lid = m_link_order[i];
                const LinkMeta& lmeta = m_links[lid];
                const WindowMetrics& wm = m_window_data[lid][w];

                double max_bytes = lmeta.max_bandwidth_gbps * (m_window_ns * 0.125);
                double util = (max_bytes > 0.0) ? std::min(1.0, wm.bytes_transferred / max_bytes) : 0.0;
                double cong = std::min(1.0, wm.backpressure_ns / m_window_ns);
                double avg_inflight = wm.inflight_integral_ns / m_window_ns;

                uint32_t target_max_out = 4;
                if (m_nodes.count(lmeta.target)) {
                    target_max_out = std::max(1u, m_nodes[lmeta.target].max_outstanding);
                }
                double occ = std::min(1.0, avg_inflight / static_cast<double>(target_max_out));
                double bw_gbps = (wm.bytes_transferred * 8.0) / m_window_ns;

                out << "\"" << lid << "\": {\"util\": " << util
                    << ", \"cong\": " << cong
                    << ", \"occ\": " << occ
                    << ", \"bw_gbps\": " << bw_gbps
                    << ", \"tx_count\": " << wm.tx_count
                    << ", \"q_offset_ns\": " << wm.max_quantum_offset_ns
                    << ", \"dmi_active\": " << (wm.dmi_active ? "true" : "false")
                    << ", \"fifo_peak\": " << wm.peak_fifo_used << "}"
                    << (i + 1 < m_link_order.size() ? ", " : "");
            }
            out << "}}" << (w + 1 < num_windows ? "," : "") << "\n";
        }
        out << "  ],\n";

        // 4. Discrete Token Stream
        out << "  \"tokens\": [\n";
        for (size_t i = 0; i < m_tokens.size(); ++i) {
            const auto& t = m_tokens[i];
            out << "    {\"id\": " << t.id << ", \"link\": \"" << t.link_id
                << "\", \"cmd\": \"" << t.cmd << "\", \"addr\": \"0x"
                << std::hex << std::uppercase << t.address << std::dec << "\", \"len\": " << t.data_length
                << ", \"mode\": \"" << to_string(t.abstraction)
                << "\", \"note\": \"" << t.protocol_note
                << "\", \"data\": \"" << t.data_hex
                << "\", \"status\": \"" << t.resp_status
                << "\", \"t1\": " << t.t1_req_start_ns
                << ", \"t2\": " << t.t2_req_end_ns
                << ", \"t3\": " << t.t3_resp_start_ns
                << ", \"t4\": " << t.t4_resp_end_ns
                << ", \"q_offset\": " << t.q_offset_ns << "}"
                << (i + 1 < m_tokens.size() ? "," : "") << "\n";
        }
        out << "  ],\n";
        out << "  \"logs\": [\n";
        for (size_t i = 0; i < m_report_logs.size(); ++i) {
            const auto& lg = m_report_logs[i];
            out << "    {\"t\": " << lg.time_ns << ", \"text\": \"" << escape_json(lg.text) << "\"}"
                << (i + 1 < m_report_logs.size() ? "," : "") << "\n";
        }
        out << "  ]\n";
        out << "}\n";
        return true;
    }

private:
    HeatmapRecorder() {
        sc_core::sc_report_handler::set_handler(&HeatmapRecorder::custom_report_handler);
    }

    static void custom_report_handler(const sc_core::sc_report& rep, const sc_core::sc_actions& actions) {
        if (actions & sc_core::SC_DISPLAY) {
            std::string composed = sc_core::sc_report_compose_message(rep);
            double t_ns = rep.get_time().to_seconds() * 1e9;
            HeatmapRecorder::instance().m_report_logs.push_back({t_ns, composed});
        }
        if (rep.get_severity() != sc_core::SC_INFO) {
            sc_core::sc_report_handler::default_handler(rep, actions);
        } else {
            sc_core::sc_report_handler::default_handler(rep, actions & ~sc_core::SC_DISPLAY);
        }
    }

    static std::string escape_json(const std::string& s) {
        std::ostringstream oss;
        for (unsigned char c : s) {
            switch (c) {
                case '\"': oss << "\\\""; break;
                case '\\': oss << "\\\\"; break;
                case '\b': oss << "\\b"; break;
                case '\f': oss << "\\f"; break;
                case '\n': oss << "\\n"; break;
                case '\r': break;
                case '\t': oss << "  "; break;
                default:
                    if (c >= 0x20) oss << c;
                    break;
            }
        }
        return oss.str();
    }

    static std::string extract_payload_data(const tlm::tlm_generic_payload& trans) {
        const unsigned char* ptr = trans.get_data_ptr();
        unsigned int len = trans.get_data_length();
        if (!ptr || len == 0) return "N/A";
        std::ostringstream oss;
        if (len >= 4) {
            uint32_t word = 0;
            std::memcpy(&word, ptr, 4);
            oss << "0x" << std::hex << std::uppercase << std::setw(8) << std::setfill('0') << word;
            oss << " [";
            unsigned int show_bytes = std::min(len, 4u);
            for (unsigned int i = 0; i < show_bytes; ++i) {
                oss << std::hex << std::uppercase << std::setw(2) << std::setfill('0')
                    << static_cast<unsigned int>(ptr[i]) << (i + 1 < show_bytes ? " " : "");
            }
            if (len > 4) oss << " ..";
            oss << "]";
        } else {
            oss << "[";
            for (unsigned int i = 0; i < len; ++i) {
                oss << std::hex << std::uppercase << std::setw(2) << std::setfill('0')
                    << static_cast<unsigned int>(ptr[i]) << (i + 1 < len ? " " : "");
            }
            oss << "]";
        }
        return oss.str();
    }

    void index_sc_objects_recursive(
        sc_core::sc_object* obj,
        std::unordered_map<std::string, sc_core::sc_object*>& out_map)
    {
        if (!obj) return;
        out_map[obj->basename()] = obj;
        out_map[obj->name()] = obj;
        const std::vector<sc_core::sc_object*>& children = obj->get_child_objects();
        for (sc_core::sc_object* ch : children) {
            index_sc_objects_recursive(ch, out_map);
        }
    }

    void collect_module_children_recursive(
        sc_core::sc_object* obj,
        const std::string& root_full_name,
        std::vector<ChildObjectInfo>& out_children,
        int depth)
    {
        if (!obj || depth > 2) return;
        const std::vector<sc_core::sc_object*>& children = obj->get_child_objects();
        for (sc_core::sc_object* ch : children) {
            if (!ch) continue;
            std::string k = ch->kind();
            // Keep meaningful architectural objects: modules, sc_fifos, TLM sockets, and SystemC processes
            bool keep = (k == "sc_module" || k == "sc_fifo" ||
                         k == "tlm_initiator_socket" || k == "tlm_target_socket" ||
                         k == "sc_thread_process" || k == "sc_method_process");
            if (keep) {
                ChildObjectInfo info;
                std::string full = ch->name();
                if (full.rfind(root_full_name + ".", 0) == 0) {
                    info.name = full.substr(root_full_name.size() + 1);
                } else {
                    info.name = ch->basename();
                }
                info.full_name = full;
                info.kind = k;

                if (k == "sc_fifo") {
                    auto* gp_fifo = dynamic_cast<sc_core::sc_fifo<tlm::tlm_generic_payload*>*>(ch);
                    if (gp_fifo != nullptr) {
                        info.fifo_ptr = gp_fifo;
                        info.fifo_capacity = gp_fifo->num_available() + gp_fifo->num_free();
                        info.fifo_peak_used = gp_fifo->num_available();
                    }
                }
                out_children.push_back(info);
            }
            if (k == "sc_module") {
                collect_module_children_recursive(ch, root_full_name, out_children, depth + 1);
            }
        }
    }

    void finalize_at_transaction(const TokenEvent& ev) {
        double stall_dur = std::max(0.0, ev.t2_req_end_ns - ev.t1_req_start_ns);
        double bytes = static_cast<double>(ev.data_length);

        distribute_to_windows(ev.link_id, ev.t1_req_start_ns, ev.t4_resp_end_ns, bytes, 0.0, 1.0, 0.0);
        if (stall_dur > 0.0) {
            distribute_to_windows(ev.link_id, ev.t1_req_start_ns, ev.t2_req_end_ns, 0.0, stall_dur, 0.0, 0.0);
        }
        if (m_record_tokens) {
            m_tokens.push_back(ev);
        }
    }

    void distribute_to_windows(
        const std::string& link_id,
        double t_start,
        double t_end,
        double total_bytes,
        double total_backpressure_ns,
        double inflight_weight,
        double quantum_offset_ns)
    {
        if (t_end <= t_start) return;
        double span = t_end - t_start;
        size_t w_first = static_cast<size_t>(std::floor(t_start / m_window_ns));
        size_t w_last = static_cast<size_t>(std::floor((t_end - 1e-9) / m_window_ns));

        for (size_t w = w_first; w <= w_last; ++w) {
            double win_s = w * m_window_ns;
            double win_e = (w + 1) * m_window_ns;
            double overlap = std::max(0.0, std::min(t_end, win_e) - std::max(t_start, win_s));
            double ratio = overlap / span;

            WindowMetrics& wm = m_window_data[link_id][w];
            wm.bytes_transferred += total_bytes * ratio;
            wm.backpressure_ns += total_backpressure_ns * ratio;
            wm.inflight_integral_ns += overlap * inflight_weight;
            wm.max_quantum_offset_ns = std::max(wm.max_quantum_offset_ns, quantum_offset_ns);
            if (w == w_first && total_bytes > 0.0) {
                wm.tx_count += 1;
            }
        }
    }

    std::string m_title = "SystemC TLM-2.0 Trace";
    double m_window_ns = 100.0;
    double m_max_time_ns = 0.0;
    bool m_record_tokens = true;
    bool m_introspected = false;
    uint64_t m_next_token_id = 0;

    std::vector<std::string> m_node_order;
    std::vector<std::string> m_link_order;
    std::map<std::string, NodeMeta> m_nodes;
    std::map<std::string, LinkMeta> m_links;
    std::unordered_map<std::string, std::unordered_map<size_t, WindowMetrics>> m_window_data;
    std::unordered_map<std::string, std::unordered_map<uintptr_t, TokenEvent>> m_active_at;
    std::unordered_map<std::string, DmiState> m_dmi_state;
    std::vector<TokenEvent> m_tokens;
    std::vector<ReportLogEntry> m_report_logs;
};

/**
 * @brief Transparent TLM-2.0 Loosely-Timed (LT + DMI) Socket Probe
 */
class LtSocketProbe : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<LtSocketProbe> target_socket;
    tlm_utils::simple_initiator_socket<LtSocketProbe> initiator_socket;

    LtSocketProbe(
        sc_core::sc_module_name name,
        const std::string& link_id,
        const std::string& src_node,
        const std::string& dst_node,
        const std::string& label,
        double max_bw_gbps = 0.8)
        : sc_core::sc_module(name)
        , target_socket("target_socket")
        , initiator_socket("initiator_socket")
        , m_link_id(link_id)
    {
        target_socket.register_b_transport(this, &LtSocketProbe::b_transport);
        target_socket.register_get_direct_mem_ptr(this, &LtSocketProbe::get_direct_mem_ptr);
        target_socket.register_transport_dbg(this, &LtSocketProbe::transport_dbg);
        initiator_socket.register_invalidate_direct_mem_ptr(this, &LtSocketProbe::invalidate_direct_mem_ptr);

        LinkMeta lm{link_id, src_node, dst_node, label, AbstractionLevel::LT, max_bw_gbps};
        HeatmapRecorder::instance().register_link(lm);
    }

protected:
    void start_of_simulation() override {
        HeatmapRecorder::instance().introspect_hierarchy_once();
    }

private:
    void b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay) {
        uint64_t orig_addr = trans.get_address();
        sc_core::sc_time d_before = delay;
        initiator_socket->b_transport(trans, delay);
        sc_core::sc_time d_after = delay;
        HeatmapRecorder::instance().record_lt_transport(m_link_id, trans, d_before, d_after, orig_addr);
    }

    bool get_direct_mem_ptr(tlm::tlm_generic_payload& trans, tlm::tlm_dmi& dmi_data) {
        uint64_t orig_addr = trans.get_address();
        bool granted = initiator_socket->get_direct_mem_ptr(trans, dmi_data);
        if (granted) {
            HeatmapRecorder::instance().record_dmi_grant(m_link_id, orig_addr, dmi_data);
        }
        return granted;
    }

    unsigned int transport_dbg(tlm::tlm_generic_payload& trans) {
        return initiator_socket->transport_dbg(trans);
    }

    void invalidate_direct_mem_ptr(sc_dt::uint64 start_range, sc_dt::uint64 end_range) {
        HeatmapRecorder::instance().record_dmi_invalidate(m_link_id, start_range, end_range);
        target_socket->invalidate_direct_mem_ptr(start_range, end_range);
    }

    std::string m_link_id;
};

/**
 * @brief Transparent TLM-2.0 Approximately-Timed (AT + DMI) Socket Probe
 */
class AtSocketProbe : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<AtSocketProbe> target_socket;
    tlm_utils::simple_initiator_socket<AtSocketProbe> initiator_socket;

    AtSocketProbe(
        sc_core::sc_module_name name,
        const std::string& link_id,
        const std::string& src_node,
        const std::string& dst_node,
        const std::string& label,
        double max_bw_gbps = 0.8)
        : sc_core::sc_module(name)
        , target_socket("target_socket")
        , initiator_socket("initiator_socket")
        , m_link_id(link_id)
    {
        target_socket.register_nb_transport_fw(this, &AtSocketProbe::nb_transport_fw);
        target_socket.register_b_transport(this, &AtSocketProbe::b_transport);
        target_socket.register_get_direct_mem_ptr(this, &AtSocketProbe::get_direct_mem_ptr);
        target_socket.register_transport_dbg(this, &AtSocketProbe::transport_dbg);
        initiator_socket.register_nb_transport_bw(this, &AtSocketProbe::nb_transport_bw);
        initiator_socket.register_invalidate_direct_mem_ptr(this, &AtSocketProbe::invalidate_direct_mem_ptr);

        LinkMeta lm{link_id, src_node, dst_node, label, AbstractionLevel::AT, max_bw_gbps};
        HeatmapRecorder::instance().register_link(lm);
    }

protected:
    void start_of_simulation() override {
        HeatmapRecorder::instance().introspect_hierarchy_once();
    }

private:
    tlm::tlm_sync_enum nb_transport_fw(
        tlm::tlm_generic_payload& trans,
        tlm::tlm_phase& phase,
        sc_core::sc_time& delay)
    {
        uint64_t orig_addr = trans.get_address();
        tlm::tlm_phase phase_in = phase;
        sc_core::sc_time delay_in = delay;

        tlm::tlm_sync_enum status = initiator_socket->nb_transport_fw(trans, phase, delay);

        HeatmapRecorder::instance().record_at_fw(
            m_link_id, trans, phase_in, phase, status, delay_in, delay, orig_addr);
        return status;
    }

    tlm::tlm_sync_enum nb_transport_bw(
        tlm::tlm_generic_payload& trans,
        tlm::tlm_phase& phase,
        sc_core::sc_time& delay)
    {
        tlm::tlm_phase phase_in = phase;
        sc_core::sc_time delay_in = delay;

        tlm::tlm_sync_enum status = target_socket->nb_transport_bw(trans, phase, delay);

        HeatmapRecorder::instance().record_at_bw(
            m_link_id, trans, phase_in, phase, status, delay_in, delay);
        return status;
    }

    void b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay) {
        uint64_t orig_addr = trans.get_address();
        sc_core::sc_time d_before = delay;
        initiator_socket->b_transport(trans, delay);
        sc_core::sc_time d_after = delay;
        HeatmapRecorder::instance().record_lt_transport(m_link_id, trans, d_before, d_after, orig_addr);
    }

    bool get_direct_mem_ptr(tlm::tlm_generic_payload& trans, tlm::tlm_dmi& dmi_data) {
        uint64_t orig_addr = trans.get_address();
        bool granted = initiator_socket->get_direct_mem_ptr(trans, dmi_data);
        if (granted) {
            HeatmapRecorder::instance().record_dmi_grant(m_link_id, orig_addr, dmi_data);
        }
        return granted;
    }

    unsigned int transport_dbg(tlm::tlm_generic_payload& trans) {
        return initiator_socket->transport_dbg(trans);
    }

    void invalidate_direct_mem_ptr(sc_dt::uint64 start_range, sc_dt::uint64 end_range) {
        HeatmapRecorder::instance().record_dmi_invalidate(m_link_id, start_range, end_range);
        target_socket->invalidate_direct_mem_ptr(start_range, end_range);
    }

    std::string m_link_id;
};

} // namespace sc_viz

#endif // SC_TLM_HEATMAP_HPP
