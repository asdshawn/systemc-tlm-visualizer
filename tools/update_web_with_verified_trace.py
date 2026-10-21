#!/usr/bin/env python3
"""
Generates the streamlined Production UI (`web/index.html` and `vendor/artifact_preview.html`)
with clean, human-readable Chinese UI labels (no raw code, function names, or internal filenames):
1. Top header bar with title and file loader only (removed the 3 legacy mode buttons).
2. Full-width Hardware SoC Bus-Trunk Schematic Canvas (hover on in-flight WR/RD data block to preview data, move away to hide; click to pin persistently, click again to close).
3. Playback / Speed / Single-Step Controls + Synchronized Discrete TLM Call Swimlane Gantt Chart.
4. Bottom Plain-Text Terminal Box printing the terminal stdout messages from the simulation.
"""
import json

with open("web/accellera_verified_trace.json", "r", encoding="utf-8") as fp:
    accellera_trace = json.load(fp)

accellera_json_str = json.dumps(accellera_trace, separators=(",", ":"))

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" __HTML_CLASS__>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SystemC TLM-2.0 Visualizer</title>
  <script src="__TAILWIND_SRC__"></script>
  <style>
__ROOT_VARS__
    @keyframes pulseGlow {
      0%, 100% { filter: drop-shadow(0 0 4px rgba(239, 68, 68, 0.6)); }
      50% { filter: drop-shadow(0 0 12px rgba(239, 68, 68, 0.95)); }
    }
    .stall-pulse {
      animation: pulseGlow 1.1s infinite ease-in-out;
    }
    .node-box {
      cursor: grab;
      user-select: none;
    }
    .node-box:active {
      cursor: grabbing;
    }
    input[type="number"]::-webkit-inner-spin-button,
    input[type="number"]::-webkit-outer-spin-button {
      -webkit-appearance: none;
      margin: 0;
    }
    input[type="number"] {
      -moz-appearance: textfield;
    }
  </style>
</head>
<body class="bg-[var(--background)] text-[var(--foreground)] antialiased p-3 select-none space-y-2.5">

  <!-- 1. Events Section (Moved to Very Top) -->
  <div class="flex flex-wrap items-center justify-between gap-2">
    <div class="flex flex-wrap items-center gap-2">
      <h2 class="text-sm font-bold tracking-wide text-[var(--foreground)] mr-1">Events</h2>

      <button id="playPauseBtn" class="px-3.5 py-1 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] font-semibold text-xs flex items-center gap-1.5 shadow-sm hover:opacity-90 transition">
        <span id="playIcon">▶</span>
        <span id="playLabel">Play</span>
      </button>

      <div id="speedComboBox" class="relative inline-flex items-center bg-[var(--card)] border border-[var(--border)] rounded-lg focus-within:border-sky-500/70 transition">
        <input id="speedInput" type="number" min="0.01" max="100" step="0.05" value="0.25" class="w-12 bg-transparent pl-2 pr-0.5 py-1 text-xs font-mono text-right text-[var(--foreground)] focus:outline-none select-text" />
        <span class="text-xs font-mono text-[var(--muted-foreground)] pr-1.5 select-none pointer-events-none">x</span>
        <button id="speedDropdownBtn" type="button" class="px-1.5 py-1 text-[10px] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-l border-[var(--border)] transition">▾</button>
        <div id="speedDropdownMenu" class="hidden absolute left-0 top-full mt-1 w-full min-w-[76px] bg-slate-900 border border-slate-700 rounded-lg shadow-xl py-1 z-50">
          <button type="button" data-speed="0.05" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300">0.05x</button>
          <button type="button" data-speed="0.1" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300">0.1x</button>
          <button type="button" data-speed="0.25" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-sky-300 bg-sky-500/10 hover:bg-sky-500/20">0.25x</button>
          <button type="button" data-speed="0.5" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300">0.5x</button>
          <button type="button" data-speed="1.0" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300">1.0x</button>
          <button type="button" data-speed="2.5" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300">2.5x</button>
          <button type="button" data-speed="6.0" class="speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300">6.0x</button>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-1.5">
      <button onclick="zoomGantt(0.6)" class="px-2.5 py-1 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-xs font-medium transition">🔍+</button>
      <button onclick="zoomGantt(1.5)" class="px-2.5 py-1 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-xs font-medium transition">🔍-</button>
      <button onclick="resetGanttZoom()" class="px-2.5 py-1 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-xs font-mono transition">100%</button>

      <label class="px-3 py-1 text-xs font-semibold rounded-lg border border-cyan-500/40 bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 cursor-pointer transition flex items-center gap-1.5 ml-1">
        <span>📂 Load Trace</span>
        <input id="jsonFileInput" type="file" accept=".json" class="hidden" />
      </label>
    </div>
  </div>

  <div class="w-full bg-slate-950/95 border border-[var(--border)] rounded-lg overflow-hidden">
    <svg id="swimlaneSvg" viewBox="0 0 920 180" class="w-full cursor-crosshair" style="height: 180px;"></svg>
  </div>

  <div class="flex flex-wrap items-center gap-2">
    <button onclick="stepDiscreteEvent(-1)" class="px-2.5 py-1 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs font-medium shrink-0 transition">
      ⏮ Prev
    </button>
    <button onclick="stepDiscreteEvent(1)" class="px-2.5 py-1 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs font-medium shrink-0 transition">
      Next ⏭
    </button>

    <button onclick="stepTimeNs(-10)" class="px-2 py-1 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-xs font-mono shrink-0 transition">-10ns</button>
    <button onclick="stepTimeNs(10)" class="px-2 py-1 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-xs font-mono shrink-0 transition">+10ns</button>

    <div class="flex items-center gap-2 flex-1 min-w-[200px] ml-1">
      <span class="text-xs font-mono text-[var(--muted-foreground)] shrink-0">0.0 ns</span>
      <input id="timeSlider" type="range" min="0" max="5000" step="1" value="2016" class="w-full accent-amber-400 cursor-pointer h-1.5 bg-slate-700 rounded-lg" />
      <span id="maxTimeLabel" class="text-xs font-mono text-[var(--muted-foreground)] shrink-0">5000.0 ns</span>
    </div>
  </div>

  <hr class="border-t border-[var(--border)] my-3" />

  <!-- 2. Topology Section -->
  <div class="flex flex-wrap items-center justify-between gap-2">
    <h2 class="text-sm font-bold tracking-wide text-[var(--foreground)]">Topology</h2>

    <div class="flex flex-wrap items-center gap-2">
      <button id="clearPinnedBtn" onclick="clearAllPinnedTokens()" class="hidden px-2.5 py-1 rounded-lg border border-amber-500/40 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 text-xs font-medium transition">
        📌 Clear Pinned (0)
      </button>

      <button onclick="resetAutoLayout()" class="px-2.5 py-1 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-xs text-cyan-300 transition">
        ✨ Reset Layout
      </button>
    </div>
  </div>

  <div class="w-full rounded-lg border border-[var(--border)] bg-slate-950/95 relative overflow-hidden" style="height: 460px;">
    <svg id="socSvg" viewBox="0 0 960 600" class="w-full h-full">
      <defs>
        <pattern id="gridPattern" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(148, 163, 184, 0.07)" stroke-width="1" />
        </pattern>
      </defs>

      <rect width="960" height="600" fill="url(#gridPattern)" />

      <g id="domainsLayer"></g>
      <g id="linksLayer"></g>
      <g id="nodesLayer"></g>
      <g id="particlesLayer"></g>
      <g id="popoversLayer" pointer-events="none"></g>
    </svg>

    <div class="absolute top-3 right-3 bg-slate-900/95 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs flex items-center gap-3 shadow-md">
      <div>
        <span class="text-slate-400">Time:</span>
        <span id="simTimeBadge" class="font-mono font-bold text-amber-300 ml-0.5">2016.0 ns</span>
      </div>
      <div class="h-3 w-px bg-slate-700"></div>
      <div>
        <span class="text-slate-400">Active:</span>
        <span id="inflightCountBadge" class="font-mono font-bold text-cyan-300 ml-0.5">2</span>
      </div>
      <div class="h-3 w-px bg-slate-700"></div>
      <div>
        <span class="text-slate-400">Window:</span>
        <span id="frameBadge" class="font-mono font-semibold text-slate-200 ml-0.5">2000 - 2100 ns</span>
      </div>
    </div>
  </div>

  <hr class="border-t border-[var(--border)] my-3" />

  <!-- 3. Messages Section -->
  <div>
    <h2 class="text-sm font-bold tracking-wide text-[var(--foreground)] mb-1.5">Messages</h2>
    <pre id="terminalLogBox" class="w-full h-48 bg-black text-slate-200 border border-slate-800 rounded-lg p-3 font-mono text-xs overflow-y-auto whitespace-pre-wrap leading-relaxed select-text"></pre>
  </div>

  <script>
    const DEFAULT_TRACE = __ACCELLERA_JSON__;

    const NODE_UI_TEXT = {
      m_td_initiator_1: { label: "Processor 101" },
      m_lt_initiator_2: { label: "Processor 102" },
      m_dmi_initiator_3: { label: "Processor 103" },
      m_lt_bus: { label: "LT Interconnect Matrix" },
      m_lt_synch_target_1: { label: "Sync Memory 201" },
      m_lt_target_2: { label: "Memory 202" },
      m_lt_dmi_target_3: { label: "DMI Memory 203" },
      m_at_initiator_1: { label: "Controller 101" },
      m_at_initiator_2: { label: "Controller 102" },
      m_at_bus: { label: "AT Interconnect Matrix" },
      m_at_target_1_phase_1: { label: "1-Phase Memory 201" },
      m_at_target_2_phase_1: { label: "2-Phase Memory 202" },
      m_at_target_4_phase_1: { label: "4-Phase Memory 203" }
    };

    const LINK_UI_TEXT = {
      td1_to_ltbus: "Processor 101 → LT Bus",
      lt2_to_ltbus: "Processor 102 → LT Bus",
      dmi3_to_ltbus: "Processor 103 → LT Bus",
      ltbus_to_synch1: "LT Bus → Sync Memory 201",
      ltbus_to_targ2: "LT Bus → Memory 202",
      ltbus_to_dmi3: "LT Bus → DMI Memory 203",
      ltbus_to_atbus: "LT Bus → AT Bridge",
      at1_to_atbus: "Controller 101 → AT Bus",
      at2_to_atbus: "Controller 102 → AT Bus",
      atbus_to_t1p: "AT Bus → 1-Phase Mem 201",
      atbus_to_t2p: "AT Bus → 2-Phase Mem 202",
      atbus_to_t4p: "AT Bus → 4-Phase Mem 203"
    };

    function getNodeDisplay(node) {
      if (NODE_UI_TEXT[node.id]) return NODE_UI_TEXT[node.id];
      return {
        label: String(node.label || node.id).replace(/<[^>]+>/g, "")
      };
    }

    function getLinkDisplay(link) {
      if (LINK_UI_TEXT[link.id]) return LINK_UI_TEXT[link.id];
      return String(link.label || link.id);
    }

    function getCmdDisplay(cmd) {
      if (cmd === "WR") return "Write";
      if (cmd === "RD") return "Read";
      if (cmd === "DMI_GRANT") return "DMI Grant";
      if (cmd === "DMI_INV") return "DMI Invalidate";
      return cmd;
    }

    function getStatusDisplay(status) {
      if (!status || status === "TLM_OK_RESPONSE" || status === "TLM_OK") return "OK";
      if (status === "TLM_INCOMPLETE_RESPONSE") return "Incomplete";
      return "OK";
    }

    let traceData = JSON.parse(JSON.stringify(DEFAULT_TRACE));
    let currentTimeNs = 2016.0;
    let currentFrame = 20;
    let lastRenderedTopoKey = "";
    let lastRenderedLogCount = -1;
    let selectedKind = "link";
    let selectedId = "atbus_to_t2p";
    let hoveredTokenId = null;
    const pinnedTokenIds = new Set();
    const packetDomMap = new Map();
    let isPlaying = false;
    let lastRafTime = null;
    let sortedEventTimes = [];
    let ganttSpanNs = 600;

    function rebuildEventTimestamps() {
      const set = new Set();
      (traceData.tokens || []).forEach((tk) => {
        set.add(+tk.t1.toFixed(1));
        set.add(+tk.t2.toFixed(1));
        set.add(+tk.t3.toFixed(1));
        set.add(+tk.t4.toFixed(1));
      });
      sortedEventTimes = Array.from(set).sort((a, b) => a - b);
    }

    function getMaxSimTimeNs() {
      const winNs = traceData.meta.window_ns || 100;
      return (traceData.frames.length || 50) * winNs;
    }

    function setSimTimeNs(tNs) {
      const maxT = getMaxSimTimeNs();
      currentTimeNs = Math.max(0, Math.min(maxT - 0.1, +tNs.toFixed(1)));
      const winNs = traceData.meta.window_ns || 100;
      currentFrame = Math.max(0, Math.min(traceData.frames.length - 1, Math.floor(currentTimeNs / winNs)));
    }

    function updatePinnedBadgeUI() {
      const btn = document.getElementById("clearPinnedBtn");
      if (!btn) return;
      if (pinnedTokenIds.size > 0) {
        btn.classList.remove("hidden");
        btn.textContent = `📌 Clear Pinned (${pinnedTokenIds.size})`;
      } else {
        btn.classList.add("hidden");
      }
    }

    function clearAllPinnedTokens() {
      pinnedTokenIds.clear();
      hoveredTokenId = null;
      updatePinnedBadgeUI();
      renderParticles();
      renderSwimlaneGantt();
    }

    function onHoverToken(tokenId) {
      if (hoveredTokenId !== tokenId) {
        hoveredTokenId = tokenId;
        renderParticles();
      }
    }

    function onLeaveToken(tokenId) {
      if (hoveredTokenId === tokenId) {
        hoveredTokenId = null;
        renderParticles();
      }
    }

    function onTogglePinToken(evt, tokenId, linkId) {
      if (evt) evt.stopPropagation();
      if (pinnedTokenIds.has(tokenId)) {
        pinnedTokenIds.delete(tokenId);
        if (hoveredTokenId === tokenId) {
          hoveredTokenId = null;
        }
      } else {
        pinnedTokenIds.add(tokenId);
        if (linkId) {
          selectedKind = "link";
          selectedId = linkId;
        }
      }
      updatePinnedBadgeUI();
      renderAll();
    }

    function getRawLinkTelemetry(linkId, frameIdx) {
      const winNs = traceData.meta.window_ns || 100;
      const tStart = frameIdx * winNs;
      const tEnd = tStart + winNs;
      const fObj = traceData.frames[frameIdx] || traceData.frames[0];
      const stat = (fObj.links && fObj.links[linkId]) || { util: 0, cong: 0, occ: 0, bw_gbps: 0, tx_count: 0, q_offset_ns: 0, dmi_active: false, fifo_peak: 0 };

      const overlappingTokens = (traceData.tokens || []).filter(
        (tk) => tk.link === linkId && tk.t1 < tEnd && tk.t4 > tStart
      );

      let rawReqWaitNs = 0;
      let rawExecNs = 0;
      let rawBytes = 0;
      overlappingTokens.forEach((tk) => {
        const w1 = Math.max(tStart, tk.t1);
        const w2 = Math.min(tEnd, tk.t2);
        if (w2 > w1) rawReqWaitNs += (w2 - w1);

        const e1 = Math.max(tStart, tk.t2);
        const e2 = Math.min(tEnd, tk.t3);
        if (e2 > e1) rawExecNs += (e2 - e1);

        if (tk.t1 >= tStart && tk.t1 < tEnd && !tk.cmd.includes("DMI")) {
          rawBytes += tk.len || 4;
        }
      });

      const callCount = overlappingTokens.length || stat.tx_count || 0;
      if (overlappingTokens.length === 0 && stat.cong > 0) {
        rawReqWaitNs = Math.round(stat.cong * winNs);
      }

      return {
        callCount,
        overlappingTokens,
        rawReqWaitNs: +rawReqWaitNs.toFixed(1),
        rawExecNs: +rawExecNs.toFixed(1),
        rawBytes: rawBytes || (stat.tx_count || 0) * 4,
        qOffsetNs: stat.q_offset_ns || 0,
        dmiActive: !!stat.dmi_active,
        fifoPeak: stat.fifo_peak || 0,
        stat
      };
    }

    /**
     * Universal SoC Topology Layout Engine:
     * Automatically detects and lays out:
     * 1. Single Shared Bus / Crossbar (Masters -> Bus -> Slaves)
     * 2. Multi-Subsystem / NUMA / Split-Bus (Peer Subsystems with Cross-Bus Bridges)
     * 3. Hierarchical Multi-Layer Bus & Cache (CPU -> L1/L2 Cache -> AXI Bus -> APB Bridge -> APB Bus -> Peripherals)
     * 4. Point-to-Point / Streaming Dataflow Pipeline (Source -> Stage 1 -> Stage 2 -> Sink, zero buses)
     * 5. 2D Mesh / Ring Network-on-Chip (NoC Routers + Local Processing Elements)
     */
    function ensureSocBusLayout(trace, forceReset = false) {
      const nodes = trace.nodes || [];
      const links = trace.links || [];
      if (!nodes.length) return;

      const nodeById = {};
      const inLinks = {};
      const outLinks = {};
      nodes.forEach((n) => {
        nodeById[n.id] = n;
        inLinks[n.id] = [];
        outLinks[n.id] = [];
      });
      links.forEach((l) => {
        if (nodeById[l.source] && nodeById[l.target]) {
          outLinks[l.source].push(l.target);
          inLinks[l.target].push(l.source);
        }
      });

      // Classify each node's degree & structural role
      nodes.forEach((n) => {
        const idg = inLinks[n.id].length;
        const odg = outLinks[n.id].length;
        n._inDeg = idg;
        n._outDeg = odg;
        const totalDeg = idg + odg;
        n.isBusTrunk =
          n.type === "interconnect" ||
          (n.type !== "master" && n.type !== "memory" && n.type !== "router" && idg >= 1 && odg >= 1 && totalDeg >= 3);
      });

      // Detect 2D Mesh / Ring NoC topology
      const explicitGridNodes = nodes.filter((n) => typeof n.row === "number" && typeof n.col === "number");
      const swNodes = nodes.filter((n) => n.type === "router" || n.type === "interconnect");
      let swPeerEdges = 0;
      links.forEach((l) => {
        const s = nodeById[l.source];
        const t = nodeById[l.target];
        if (s && t && (s.type === "router" || s.type === "interconnect") && (t.type === "router" || t.type === "interconnect")) {
          swPeerEdges++;
        }
      });
      const isNoCMesh = explicitGridNodes.length >= 4 || (swNodes.length >= 4 && swPeerEdges >= swNodes.length);

      const needsLayout = forceReset || nodes.some((n) => typeof n.x !== "number" || n.x < 0 || typeof n.y !== "number" || n.y < 0);
      if (!needsLayout) return;

      trace._domainsMeta = [];

      // --- Layout Mode A: 2D Mesh / Ring NoC ---
      if (isNoCMesh) {
        const routers = explicitGridNodes.length >= 4 ? explicitGridNodes : swNodes;
        const cols = Math.max(2, Math.ceil(Math.sqrt(routers.length)));
        const rows = Math.max(1, Math.ceil(routers.length / cols));
        const xPad = 150;
        const yPad = 110;
        const gridW = Math.max(240, 960 - xPad * 2);
        const gridH = Math.max(200, 600 - yPad * 2);

        routers.forEach((rNode, idx) => {
          rNode.isBusTrunk = false;
          const r = typeof rNode.row === "number" ? rNode.row : Math.floor(idx / cols);
          const c = typeof rNode.col === "number" ? rNode.col : (idx % cols);
          rNode.x = Math.round(xPad + (cols > 1 ? (c * gridW) / (cols - 1) : gridW / 2));
          rNode.y = Math.round(yPad + (rows > 1 ? (r * gridH) / (rows - 1) : gridH / 2));
        });

        // Place attached local PEs (Masters / Memories) next to their Router
        const routerSet = new Set(routers.map((r) => r.id));
        const peCountPerRouter = {};
        nodes.forEach((n) => {
          if (routerSet.has(n.id)) return;
          n.isBusTrunk = false;
          const neighborRouterId = [...outLinks[n.id], ...inLinks[n.id]].find((id) => routerSet.has(id));
          if (neighborRouterId && nodeById[neighborRouterId]) {
            const rn = nodeById[neighborRouterId];
            const k = peCountPerRouter[neighborRouterId] || 0;
            peCountPerRouter[neighborRouterId] = k + 1;
            const angle = (k % 2 === 0 ? -1 : 1);
            n.x = Math.max(78, Math.min(882, rn.x + angle * 95));
            n.y = Math.max(58, Math.min(542, rn.y + (k < 2 ? -64 : 64)));
          } else {
            n.x = 120;
            n.y = 80;
          }
        });

        trace._domainsMeta = [{
          x: 24,
          y: 22,
          w: 912,
          h: 552,
          isLt: false,
          title: `晶片內網路區域（${rows}×${cols} NoC 網格拓撲）`
        }];
        return;
      }

      // --- Layout Mode B: Universal Multi-Subsystem & Multi-Tier Layered SoC ---
      // 1. Identify Root Buses (buses fed by top-level sources without passing through another bus first)
      const busNodes = nodes.filter((n) => n.isBusTrunk);
      busNodes.sort((a, b) => (String(a.abstraction).includes("LT") ? 0 : 1) - (String(b.abstraction).includes("LT") ? 0 : 1));

      const rootBuses = busNodes.filter((bus) => {
        // BFS backwards from bus; if it can reach an inDeg===0 source without crossing another bus, it's a root bus
        const visited = new Set([bus.id]);
        const q = [...inLinks[bus.id]];
        while (q.length > 0) {
          const currId = q.shift();
          if (visited.has(currId)) continue;
          visited.add(currId);
          const curr = nodeById[currId];
          if (!curr) continue;
          if (curr._inDeg === 0) return true;
          if (!curr.isBusTrunk) {
            inLinks[currId].forEach((prevId) => {
              if (!visited.has(prevId)) q.push(prevId);
            });
          }
        }
        return false;
      });

      const domainSeeds = rootBuses.length >= 2 ? rootBuses : (busNodes.length >= 1 ? [busNodes[0]] : []);
      const numDomains = Math.max(1, domainSeeds.length);
      const nodeDomain = {};

      if (numDomains === 1) {
        nodes.forEach((n) => {
          nodeDomain[n.id] = 0;
        });
      } else {
        // Assign each seed bus to its own peer domain
        const rootBusSet = new Set(domainSeeds.map((b) => b.id));
        domainSeeds.forEach((b, idx) => {
          nodeDomain[b.id] = idx;
        });

        // Multi-source BFS from domainSeeds without crossing other rootBuses first
        const queue = domainSeeds.map((b, idx) => ({ id: b.id, dom: idx }));
        while (queue.length > 0) {
          const { id, dom } = queue.shift();
          const neighbors = [...inLinks[id], ...outLinks[id]];
          neighbors.forEach((nbId) => {
            if (nodeDomain[nbId] !== undefined) return;
            if (rootBusSet.has(nbId)) return;
            nodeDomain[nbId] = dom;
            queue.push({ id: nbId, dom });
          });
        }
        nodes.forEach((n) => {
          if (nodeDomain[n.id] === undefined) nodeDomain[n.id] = 0;
        });
      }

      // 2. Partition nodes into domains and compute topological tiers (Ranks 0..K) within each domain
      const canvasMargin = 24;
      const interDomainGap = numDomains > 1 ? 80 : 0;
      const totalAvailW = 960 - canvasMargin * 2 - interDomainGap * (numDomains - 1);
      const domainW = totalAvailW / numDomains;

      for (let dIdx = 0; dIdx < numDomains; dIdx++) {
        const domNodes = nodes.filter((n) => nodeDomain[n.id] === dIdx);
        const domSet = new Set(domNodes.map((n) => n.id));
        const xStart = Math.round(canvasMargin + dIdx * (domainW + interDomainGap));
        const xEnd = Math.round(xStart + domainW);

        // Internal directed edges within this domain
        const domIn = {};
        const domOut = {};
        domNodes.forEach((n) => {
          domIn[n.id] = inLinks[n.id].filter((id) => domSet.has(id));
          domOut[n.id] = outLinks[n.id].filter((id) => domSet.has(id));
        });

        // Longest-path DAG rank assignment (cycle-safe)
        const rank = {};
        domNodes.forEach((n) => {
          rank[n.id] = 0;
        });
        for (let iter = 0; iter < domNodes.length; iter++) {
          let changed = false;
          domNodes.forEach((u) => {
            domOut[u.id].forEach((vId) => {
              // Avoid infinite cycle inflation on bidirectional links
              if (domOut[vId] && domOut[vId].includes(u.id) && u.id > vId) return;
              if (rank[vId] < rank[u.id] + 1) {
                rank[vId] = rank[u.id] + 1;
                changed = true;
              }
            });
          });
          if (!changed) break;
        }

        // Align pure leaf sinks directly below their deepest parent
        domNodes.forEach((n) => {
          if (domOut[n.id].length === 0 && domIn[n.id].length > 0) {
            const maxParentRank = Math.max(...domIn[n.id].map((pId) => rank[pId] || 0));
            rank[n.id] = maxParentRank + 1;
          }
        });

        // Compress ranks into contiguous tiers 0 .. numTiers-1
        const uniqueRanks = Array.from(new Set(domNodes.map((n) => rank[n.id]))).sort((a, b) => a - b);
        const tiers = uniqueRanks.map((rk) => domNodes.filter((n) => rank[n.id] === rk));
        const numTiers = Math.max(1, tiers.length);
        const domBuses = domNodes.filter((n) => n.isBusTrunk);
        const maxTierWidth = Math.max(...tiers.map((t) => t.length));

        // Pure horizontal P2P pipeline mode: 0 buses, >= 3 stages, <= 2 nodes per stage
        const isHorizontalPipeline = numDomains === 1 && domBuses.length === 0 && numTiers >= 3 && maxTierWidth <= 2;

        if (isHorizontalPipeline) {
          tiers.forEach((tierNodes, tIdx) => {
            const stageX = Math.round(xStart + 70 + ((xEnd - xStart - 140) * tIdx) / Math.max(1, numTiers - 1));
            tierNodes.forEach((n, i) => {
              n.x = stageX;
              n.y = tierNodes.length === 1 ? 295 : Math.round(190 + i * 210);
            });
          });
        } else {
          // Vertical Multi-Tier Layout (Supports 2, 3, 4, 5+ tiers)
          const tierY = (tIdx) => {
            if (numTiers === 1) return 295;
            if (numTiers === 2) return tIdx === 0 ? 175 : 425;
            if (numTiers === 3) return tIdx === 0 ? 112 : (tIdx === 1 ? 295 : 482);
            const yTop = 88;
            const yBot = 508;
            return Math.round(yTop + ((yBot - yTop) * tIdx) / (numTiers - 1));
          };

          // Place Tier 0 first, then apply Barycenter ordering for subsequent tiers to minimize wire crossings
          tiers.forEach((tierNodes, tIdx) => {
            if (tIdx > 0) {
              tierNodes.sort((a, b) => {
                const aParents = domIn[a.id].map((id) => nodeById[id]?.x).filter((x) => typeof x === "number" && x > 0);
                const bParents = domIn[b.id].map((id) => nodeById[id]?.x).filter((x) => typeof x === "number" && x > 0);
                const aAvg = aParents.length ? aParents.reduce((s, v) => s + v, 0) / aParents.length : 0;
                const bAvg = bParents.length ? bParents.reduce((s, v) => s + v, 0) / bParents.length : 0;
                return aAvg - bAvg;
              });
            }

            const yPos = tierY(tIdx);
            const padX = 14;
            const spanW = (xEnd - padX) - (xStart + padX);
            tierNodes.forEach((n, i) => {
              n.x = Math.round(xStart + padX + (spanW * (i + 0.5)) / Math.max(1, tierNodes.length));
              n.y = yPos;
            });
          });

          // Compute Bus-Trunk horizontal spans (root buses span domain; child buses span their connected neighborhood)
          domBuses.forEach((bus, bIdx) => {
            const connectedIds = [...domIn[bus.id], ...domOut[bus.id]];
            const connXs = connectedIds.map((id) => nodeById[id]?.x).filter((x) => typeof x === "number");
            if (bIdx === 0 || domBuses.length === 1) {
              bus.x = Math.round((xStart + xEnd) / 2);
              bus.busX1 = Math.round(xStart + 14);
              bus.busX2 = Math.round(xEnd - 14);
            } else if (connXs.length > 0) {
              const minX = Math.min(...connXs);
              const maxX = Math.max(...connXs);
              bus.busX1 = Math.max(xStart + 18, Math.round(minX - 65));
              bus.busX2 = Math.min(xEnd - 18, Math.round(maxX + 65));
              if (bus.busX2 - bus.busX1 < 200) {
                const mid = Math.round((minX + maxX) / 2);
                bus.busX1 = Math.max(xStart + 18, mid - 105);
                bus.busX2 = Math.min(xEnd - 18, mid + 105);
              }
              bus.x = Math.round((bus.busX1 + bus.busX2) / 2);
            }
          });
        }

        // Record domain backdrop metadata
        const primaryBus = domBuses[0];
        const isLt = primaryBus
          ? String(primaryBus.abstraction).includes("LT")
          : domNodes.some((n) => String(n.abstraction).includes("LT"));
        const domLetter = String.fromCharCode(65 + dIdx);
        let domTitle = "";
        if (isHorizontalPipeline) {
          domTitle = `點對點串流管線架構（${numTiers} 階資料流管線）`;
        } else if (numTiers >= 4 && domBuses.length >= 2) {
          domTitle = `子系統 ${domLetter}：多層階匯流排架構（${numTiers} 層階層拓撲）`;
        } else if (numTiers >= 4) {
          domTitle = `子系統 ${domLetter}：多層快取與匯流排架構（${numTiers} 層階層拓撲）`;
        } else if (isLt) {
          domTitle = `子系統 ${domLetter}：LT 高速匯流排區域（鬆散時間模型）`;
        } else {
          domTitle = `子系統 ${domLetter}：AT 管線匯流排區域（近似時間模型）`;
        }

        trace._domainsMeta.push({
          x: xStart,
          y: 22,
          w: xEnd - xStart,
          h: 552,
          isLt,
          title: domTitle
        });
      }
    }

    function resetAutoLayout() {
      ensureSocBusLayout(traceData, true);
      renderTopology();
    }

    function heatColorFromRaw(raw) {
      if (raw.dmiActive && raw.callCount === 0) return "#c084fc";
      if (raw.callCount === 0 && raw.stat.util === 0 && raw.stat.cong === 0) return "#334155";
      if (raw.rawReqWaitNs >= 60) return "#f43f5e";
      if (raw.rawReqWaitNs >= 35) return "#fb923c";
      if (raw.callCount >= 3) return "#f59e0b";
      if (raw.callCount >= 2) return "#10b981";
      return "#0ea5e9";
    }

    function getNodeMap() {
      ensureSocBusLayout(traceData, false);
      const map = {};
      traceData.nodes.forEach((n) => {
        map[n.id] = n;
      });
      return map;
    }

    function computeLinkGeometry(src, dst) {
      const NODE_W = 136;
      const NODE_H = 68;
      const BUS_H = 48;
      const srcIsBus = Boolean(src.isBusTrunk);
      const dstIsBus = Boolean(dst.isBusTrunk);

      // 1. Module Box -> Bus Trunk (Vertical Tap into Bus)
      if (!srcIsBus && dstIsBus) {
        const bx1 = typeof dst.busX1 === "number" ? dst.busX1 : (dst.x - 160);
        const bx2 = typeof dst.busX2 === "number" ? dst.busX2 : (dst.x + 160);
        const tapX = Math.max(bx1 + 20, Math.min(bx2 - 20, src.x));
        const goingDown = src.y <= dst.y;
        const sy = goingDown ? (src.y + NODE_H / 2) : (src.y - NODE_H / 2);
        const ty = goingDown ? (dst.y - BUS_H / 2) : (dst.y + BUS_H / 2);
        const midY = Math.round((sy + ty) / 2);
        return {
          d: `M ${src.x} ${sy} L ${src.x} ${midY} L ${tapX} ${midY} L ${tapX} ${ty}`,
          labelX: tapX,
          labelY: goingDown ? (midY - 6) : (midY + 12)
        };
      }

      // 2. Bus Trunk -> Module Box (Vertical Tap out of Bus)
      if (srcIsBus && !dstIsBus) {
        const bx1 = typeof src.busX1 === "number" ? src.busX1 : (src.x - 160);
        const bx2 = typeof src.busX2 === "number" ? src.busX2 : (src.x + 160);
        const tapX = Math.max(bx1 + 20, Math.min(bx2 - 20, dst.x));
        const goingDown = src.y <= dst.y;
        const sy = goingDown ? (src.y + BUS_H / 2) : (src.y - BUS_H / 2);
        const ty = goingDown ? (dst.y - NODE_H / 2) : (dst.y + NODE_H / 2);
        const midY = Math.round((sy + ty) / 2);
        return {
          d: `M ${tapX} ${sy} L ${tapX} ${midY} L ${dst.x} ${midY} L ${dst.x} ${ty}`,
          labelX: tapX,
          labelY: goingDown ? (midY + 12) : (midY - 6)
        };
      }

      // 3. Bus Trunk <-> Bus Trunk (Either Peer Horizontal Bridge OR Hierarchical Vertical Bus Bridge)
      if (srcIsBus && dstIsBus) {
        if (Math.abs(src.y - dst.y) < 45) {
          const sx = src.x < dst.x ? (src.busX2 || src.x + 150) : (src.busX1 || src.x - 150);
          const tx = src.x < dst.x ? (dst.busX1 || dst.x - 150) : (dst.busX2 || dst.x + 150);
          return {
            d: `M ${sx} ${src.y} L ${tx} ${dst.y}`,
            labelX: Math.round((sx + tx) / 2),
            labelY: Math.round((src.y + dst.y) / 2) - 14
          };
        } else {
          const goingDown = src.y < dst.y;
          const overlapX1 = Math.max(src.busX1 || src.x - 120, dst.busX1 || dst.x - 120);
          const overlapX2 = Math.min(src.busX2 || src.x + 120, dst.busX2 || dst.x + 120);
          const tapX = overlapX2 > overlapX1 ? Math.round((overlapX1 + overlapX2) / 2) : dst.x;
          const sy = goingDown ? (src.y + BUS_H / 2) : (src.y - BUS_H / 2);
          const ty = goingDown ? (dst.y - BUS_H / 2) : (dst.y + BUS_H / 2);
          return {
            d: `M ${tapX} ${sy} L ${tapX} ${ty}`,
            labelX: tapX,
            labelY: Math.round((sy + ty) / 2)
          };
        }
      }

      // 4. Module Box <-> Module Box (Multi-Tier Cache / Bridge / P2P Pipeline / NoC Mesh)
      const dx = dst.x - src.x;
      const dy = dst.y - src.y;
      if (Math.abs(dy) >= 52) {
        const goingDown = dy > 0;
        const sy = goingDown ? (src.y + NODE_H / 2) : (src.y - NODE_H / 2);
        const ty = goingDown ? (dst.y - NODE_H / 2) : (dst.y + NODE_H / 2);
        const midY = Math.round((sy + ty) / 2);
        return {
          d: `M ${src.x} ${sy} L ${src.x} ${midY} L ${dst.x} ${midY} L ${dst.x} ${ty}`,
          labelX: Math.round((src.x + dst.x) / 2),
          labelY: midY - 6
        };
      } else {
        const goingRight = dx >= 0;
        const sx = goingRight ? (src.x + NODE_W / 2) : (src.x - NODE_W / 2);
        const tx = goingRight ? (dst.x - NODE_W / 2) : (dst.x + NODE_W / 2);
        const midX = Math.round((sx + tx) / 2);
        return {
          d: `M ${sx} ${src.y} L ${midX} ${src.y} L ${midX} ${dst.y} L ${tx} ${dst.y}`,
          labelX: midX,
          labelY: Math.round((src.y + dst.y) / 2) - 10
        };
      }
    }

    function renderDomainBackdrops() {
      const domainsLayer = document.getElementById("domainsLayer");
      if (domainsLayer) domainsLayer.innerHTML = "";
    }

    function renderTopology() {
      const nodeMap = getNodeMap();
      renderDomainBackdrops();

      const linksLayer = document.getElementById("linksLayer");
      const nodesLayer = document.getElementById("nodesLayer");
      linksLayer.innerHTML = "";
      nodesLayer.innerHTML = "";

      traceData.links.forEach((link) => {
        const src = nodeMap[link.source];
        const dst = nodeMap[link.target];
        if (!src || !dst) return;

        const raw = getRawLinkTelemetry(link.id, currentFrame);
        const col = heatColorFromRaw(raw);
        const isSelected = selectedKind === "link" && selectedId === link.id;
        const isDmiBypass = raw.dmiActive && raw.callCount === 0;
        const isStall = raw.rawReqWaitNs >= 40;
        const geom = computeLinkGeometry(src, dst);

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.style.cursor = "pointer";
        g.onclick = (e) => {
          e.stopPropagation();
          selectedKind = "link";
          selectedId = link.id;
          renderAll(true);
        };

        if (isSelected || isStall || isDmiBypass) {
          const halo = document.createElementNS("http://www.w3.org/2000/svg", "path");
          halo.setAttribute("d", geom.d);
          halo.setAttribute("fill", "none");
          halo.setAttribute("stroke", isSelected ? "#fbbf24" : (isDmiBypass ? "#c084fc" : "#f43f5e"));
          halo.setAttribute("stroke-width", isSelected ? "10" : "8");
          halo.setAttribute("stroke-opacity", isSelected ? "0.35" : "0.24");
          halo.setAttribute("stroke-linejoin", "round");
          g.appendChild(halo);
        }

        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("id", `path_${link.id}`);
        path.setAttribute("d", geom.d);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", col);
        path.setAttribute("stroke-linejoin", "round");
        const strokeW = isDmiBypass ? 4.0 : Math.min(8.5, 2.5 + raw.callCount * 1.4);
        path.setAttribute("stroke-width", strokeW.toFixed(1));
        if (isDmiBypass) {
          path.setAttribute("stroke-dasharray", "3 5");
        } else if (link.abstraction === "LT") {
          path.setAttribute("stroke-dasharray", "8 4");
        }
        if (isStall) {
          path.setAttribute("class", "stall-pulse");
        }
        g.appendChild(path);

        let badgeStr = "";
        if (isDmiBypass) {
          badgeStr = "⚡ DMI";
        } else if (raw.rawReqWaitNs >= 20) {
          badgeStr = `${raw.callCount} tx | Wait ${Math.round(raw.rawReqWaitNs)}ns`;
        } else {
          badgeStr = `${raw.callCount} tx (${raw.rawBytes}B)`;
        }

        const badgeW = Math.max(66, badgeStr.length * 6.0 + 12);
        const pill = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        pill.setAttribute("x", geom.labelX - badgeW / 2);
        pill.setAttribute("y", geom.labelY - 9);
        pill.setAttribute("width", badgeW);
        pill.setAttribute("height", "16");
        pill.setAttribute("rx", "4");
        pill.setAttribute("fill", "#0f172a");
        pill.setAttribute("fill-opacity", "0.92");
        pill.setAttribute("stroke", isSelected ? "#fbbf24" : col);
        pill.setAttribute("stroke-width", isSelected ? "1.6" : "1");
        g.appendChild(pill);

        const lbl = document.createElementNS("http://www.w3.org/2000/svg", "text");
        lbl.setAttribute("x", geom.labelX);
        lbl.setAttribute("y", geom.labelY + 2);
        lbl.setAttribute("text-anchor", "middle");
        lbl.setAttribute("fill", isSelected ? "#fde047" : (isDmiBypass ? "#d8b4fe" : "#e2e8f0"));
        lbl.setAttribute("font-size", "9.5");
        lbl.setAttribute("font-family", "monospace");
        lbl.textContent = badgeStr;
        g.appendChild(lbl);

        linksLayer.appendChild(g);
      });

      const NODE_W = 136;
      const NODE_H = 68;
      const BUS_H = 48;

      traceData.nodes.forEach((node) => {
        let totalCalls = 0;
        let maxWaitNs = 0;
        let totalBytes = 0;
        let maxQuantum = 0;
        let hasDmi = false;
        let maxFifo = 0;

        traceData.links.forEach((l) => {
          if (l.source === node.id || l.target === node.id) {
            const r = getRawLinkTelemetry(l.id, currentFrame);
            totalCalls = Math.max(totalCalls, r.callCount);
            maxWaitNs = Math.max(maxWaitNs, r.rawReqWaitNs);
            totalBytes += r.rawBytes;
            maxQuantum = Math.max(maxQuantum, r.qOffsetNs);
            if (r.dmiActive) hasDmi = true;
            if (l.source === node.id) maxFifo = Math.max(maxFifo, r.fifoPeak);
          }
        });

        const borderCol = maxWaitNs >= 45
          ? "#f43f5e"
          : (hasDmi && totalCalls === 0 ? "#c084fc" : (node.abstraction === "LT" ? "#38bdf8" : "#f59e0b"));
        const isSelected = selectedKind === "node" && selectedId === node.id;
        const isBus = Boolean(node.isBusTrunk);
        const disp = getNodeDisplay(node);

        if (isBus) {
          const bx1 = typeof node.busX1 === "number" ? node.busX1 : (node.x - 170);
          const bx2 = typeof node.busX2 === "number" ? node.busX2 : (node.x + 170);
          const bw = Math.max(180, bx2 - bx1);
          const by = node.y - BUS_H / 2;

          const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
          g.setAttribute("class", "node-box");
          g.onclick = (e) => {
            e.stopPropagation();
            selectedKind = "node";
            selectedId = node.id;
            renderAll(true);
          };

          const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          rect.setAttribute("x", bx1);
          rect.setAttribute("y", by);
          rect.setAttribute("width", bw);
          rect.setAttribute("height", BUS_H);
          rect.setAttribute("rx", "8");
          rect.setAttribute("fill", "#0f172a");
          rect.setAttribute("stroke", isSelected ? "#fbbf24" : borderCol);
          rect.setAttribute("stroke-width", isSelected ? "3" : "2.2");
          if (maxWaitNs >= 50) rect.setAttribute("class", "stall-pulse");
          g.appendChild(rect);

          const busTitle = document.createElementNS("http://www.w3.org/2000/svg", "text");
          busTitle.setAttribute("x", bx1 + 14);
          busTitle.setAttribute("y", node.y + 4);
          busTitle.setAttribute("fill", "#f8fafc");
          busTitle.setAttribute("font-size", "12");
          busTitle.setAttribute("font-weight", "bold");
          busTitle.textContent = `══ ${disp.label} ══`;
          g.appendChild(busTitle);

          const busBadge = document.createElementNS("http://www.w3.org/2000/svg", "text");
          busBadge.setAttribute("x", bx1 + bw - 14);
          busBadge.setAttribute("y", node.y + 4);
          busBadge.setAttribute("text-anchor", "end");
          busBadge.setAttribute("fill", maxWaitNs >= 45 ? "#fda4af" : (hasDmi ? "#d8b4fe" : "#38bdf8"));
          busBadge.setAttribute("font-size", "10.5");
          busBadge.setAttribute("font-family", "monospace");
          busBadge.setAttribute("font-weight", "bold");
          busBadge.textContent = maxWaitNs >= 40
            ? `Wait ${Math.round(maxWaitNs)}ns`
            : (hasDmi && totalCalls === 0 ? `⚡ DMI` : `${totalCalls} tx (${totalBytes}B)`);
          g.appendChild(busBadge);

          nodesLayer.appendChild(g);
          return;
        }

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "node-box");
        g.setAttribute("transform", `translate(${node.x - NODE_W / 2}, ${node.y - NODE_H / 2})`);

        g.onmousedown = (e) => startDragNode(e, node);
        g.onclick = (e) => {
          e.stopPropagation();
          selectedKind = "node";
          selectedId = node.id;
          renderAll(true);
        };

        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", NODE_W);
        rect.setAttribute("height", NODE_H);
        rect.setAttribute("rx", node.type === "master" ? "8" : "6");
        rect.setAttribute("fill", "#0f172a");
        rect.setAttribute("stroke", isSelected ? "#fbbf24" : borderCol);
        rect.setAttribute("stroke-width", isSelected ? "3" : (maxWaitNs >= 50 ? "2.5" : "1.8"));
        if (maxWaitNs >= 50) rect.setAttribute("class", "stall-pulse");
        g.appendChild(rect);

        const topBar = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        topBar.setAttribute("x", "2");
        topBar.setAttribute("y", "2");
        topBar.setAttribute("width", NODE_W - 4);
        topBar.setAttribute("height", "16");
        topBar.setAttribute("rx", "6");
        topBar.setAttribute("fill", borderCol);
        topBar.setAttribute("fill-opacity", "0.22");
        g.appendChild(topBar);

        const isIntermediate = node.type === "bridge" || node.type === "router" || node.type === "cache" || (node._inDeg > 0 && node._outDeg > 0);
        const roleIcon = isIntermediate ? "🔀" : (node.type === "master" ? "⚙️" : "▤");
        const tag = document.createElementNS("http://www.w3.org/2000/svg", "text");
        tag.setAttribute("x", "6");
        tag.setAttribute("y", "13");
        tag.setAttribute("fill", hasDmi ? "#d8b4fe" : (node.abstraction.includes("LT") ? "#38bdf8" : "#fbbf24"));
        tag.setAttribute("font-size", "9");
        tag.setAttribute("font-weight", "bold");
        const fifoTag = maxFifo > 0 ? ` Q:${maxFifo}` : "";
        tag.textContent = `${roleIcon}[${node.abstraction}]${fifoTag}`;
        g.appendChild(tag);

        const pct = document.createElementNS("http://www.w3.org/2000/svg", "text");
        pct.setAttribute("x", NODE_W - 6);
        pct.setAttribute("y", "13");
        pct.setAttribute("text-anchor", "end");
        pct.setAttribute("fill", maxWaitNs >= 40 ? "#fda4af" : (hasDmi && totalCalls === 0 ? "#d8b4fe" : "#e2e8f0"));
        pct.setAttribute("font-size", "9");
        pct.setAttribute("font-family", "monospace");
        if (maxWaitNs >= 35) {
          pct.textContent = `Wait:${Math.round(maxWaitNs)}ns`;
        } else if (hasDmi && totalCalls === 0) {
          pct.textContent = `⚡DMI`;
        } else if (node.abstraction === "LT" && maxQuantum > 0) {
          pct.textContent = `Q+${Math.round(maxQuantum)}`;
        } else {
          pct.textContent = `${totalCalls} tx`;
        }
        g.appendChild(pct);

        const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
        title.setAttribute("x", "6");
        title.setAttribute("y", "38");
        title.setAttribute("fill", "#f8fafc");
        title.setAttribute("font-size", "11");
        title.setAttribute("font-weight", "bold");
        title.textContent = disp.label;
        g.appendChild(title);

        const barBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        barBg.setAttribute("x", "6");
        barBg.setAttribute("y", "55");
        barBg.setAttribute("width", NODE_W - 12);
        barBg.setAttribute("height", "5");
        barBg.setAttribute("rx", "2.5");
        barBg.setAttribute("fill", "#1e293b");
        g.appendChild(barBg);

        const barFg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        barFg.setAttribute("x", "6");
        barFg.setAttribute("y", "55");
        const barRatio = hasDmi && totalCalls === 0 ? 0.85 : Math.min(1, Math.max(totalCalls / 3, maxWaitNs / 100));
        barFg.setAttribute("width", Math.max(3, (NODE_W - 12) * barRatio));
        barFg.setAttribute("height", "5");
        barFg.setAttribute("rx", "2.5");
        barFg.setAttribute("fill", hasDmi && totalCalls === 0 ? "#c084fc" : (node.abstraction === "LT" ? "#38bdf8" : (maxWaitNs >= 50 ? "#f43f5e" : "#f59e0b")));
        g.appendChild(barFg);

        nodesLayer.appendChild(g);
      });

      renderParticles();
    }

    function renderParticles() {
      const particlesLayer = document.getElementById("particlesLayer");
      const popoversLayer = document.getElementById("popoversLayer");
      if (!particlesLayer || !popoversLayer) return;

      const activeNow = (traceData.tokens || []).filter(
        (tk) => currentTimeNs >= tk.t1 - 1.5 && currentTimeNs <= tk.t4 + 1.5
      );

      const inflightBadge = document.getElementById("inflightCountBadge");
      if (inflightBadge) {
        inflightBadge.textContent = `${activeNow.length}`;
      }

      const activeIdSet = new Set(activeNow.map((tk) => tk.id));

      for (const [id, domObj] of packetDomMap.entries()) {
        if (!activeIdSet.has(id)) {
          if (domObj.g && domObj.g.parentNode) {
            domObj.g.parentNode.removeChild(domObj.g);
          }
          packetDomMap.delete(id);
        }
      }

      let popoversHtml = "";

      activeNow.forEach((tk) => {
        const pathEl = document.getElementById(`path_${tk.link}`);
        if (!pathEl) return;
        const totalLen = pathEl.getTotalLength();
        if (totalLen <= 0) return;

        let ratio = 0.5;
        let phaseCol = "#38bdf8";
        let phaseShort = "LT Transport";

        if (tk.cmd.includes("DMI")) {
          ratio = 0.5;
          phaseCol = "#c084fc";
          phaseShort = getCmdDisplay(tk.cmd);
        } else if (tk.mode === "LT") {
          const dur = Math.max(2, tk.t4 - tk.t1);
          const p = Math.max(0, Math.min(1, (currentTimeNs - tk.t1) / dur));
          ratio = p <= 0.5 ? (0.15 + p * 1.4) : (0.85 - (p - 0.5) * 1.4);
          phaseCol = "#0ea5e9";
          phaseShort = "LT Transport";
        } else {
          if (currentTimeNs <= tk.t2) {
            const dur1 = Math.max(1, tk.t2 - tk.t1);
            const p1 = Math.max(0, Math.min(1, (currentTimeNs - tk.t1) / dur1));
            ratio = 0.20 + 0.62 * p1;
            phaseCol = "#f43f5e";
            phaseShort = "Request Wait";
          } else if (currentTimeNs <= tk.t3) {
            ratio = 0.86;
            phaseCol = "#fbbf24";
            phaseShort = "Target Exec";
          } else {
            const dur3 = Math.max(1, tk.t4 - tk.t3);
            const p3 = Math.max(0, Math.min(1, (currentTimeNs - tk.t3) / dur3));
            ratio = 0.84 - 0.68 * p3;
            phaseCol = "#10b981";
            phaseShort = "Response";
          }
        }

        const pt = pathEl.getPointAtLength(ratio * totalLen);
        const isPinned = pinnedTokenIds.has(tk.id);
        const isHovered = hoveredTokenId === tk.id;
        const showCard = isPinned || isHovered;

        let domObj = packetDomMap.get(tk.id);
        if (!domObj) {
          const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
          g.style.cursor = "pointer";

          g.addEventListener("mouseenter", () => {
            onHoverToken(tk.id);
          });
          g.addEventListener("mouseleave", () => {
            onLeaveToken(tk.id);
          });
          g.addEventListener("click", (e) => {
            onTogglePinToken(e, tk.id, tk.link);
          });

          const hitRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          hitRect.setAttribute("x", "-17");
          hitRect.setAttribute("y", "-13");
          hitRect.setAttribute("width", "34");
          hitRect.setAttribute("height", "26");
          hitRect.setAttribute("fill", "transparent");
          g.appendChild(hitRect);

          const halo = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          halo.setAttribute("x", "-14");
          halo.setAttribute("y", "-10");
          halo.setAttribute("width", "28");
          halo.setAttribute("height", "20");
          halo.setAttribute("rx", "5");
          g.appendChild(halo);

          const box = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          box.setAttribute("x", "-12");
          box.setAttribute("y", "-8");
          box.setAttribute("width", "24");
          box.setAttribute("height", "16");
          box.setAttribute("rx", "3.5");
          g.appendChild(box);

          const lbl = document.createElementNS("http://www.w3.org/2000/svg", "text");
          lbl.setAttribute("x", "0");
          lbl.setAttribute("y", "3");
          lbl.setAttribute("text-anchor", "middle");
          lbl.setAttribute("fill", "#020617");
          lbl.setAttribute("font-size", "8.5");
          lbl.setAttribute("font-family", "monospace");
          lbl.setAttribute("font-weight", "bold");
          lbl.setAttribute("pointer-events", "none");
          lbl.textContent = tk.cmd.includes("DMI") ? "DMI" : tk.cmd;
          g.appendChild(lbl);

          particlesLayer.appendChild(g);
          domObj = { g, halo, box, lbl };
          packetDomMap.set(tk.id, domObj);
        }

        domObj.g.setAttribute("transform", `translate(${pt.x.toFixed(1)}, ${pt.y.toFixed(1)})`);
        domObj.halo.setAttribute("fill", isPinned ? "#fde047" : (isHovered ? "#38bdf8" : phaseCol));
        domObj.halo.setAttribute("fill-opacity", showCard ? "0.5" : "0.24");
        domObj.box.setAttribute("fill", phaseCol);
        domObj.box.setAttribute("stroke", isPinned ? "#fde047" : (isHovered ? "#ffffff" : "#0f172a"));
        domObj.box.setAttribute("stroke-width", isPinned ? "2.2" : "1.5");

        if (showCard) {
          const cardW = 224;
          const cardH = 56;
          const preferAbove = pt.y > 85;
          const cardX = Math.max(8, Math.min(952 - cardW, pt.x - cardW / 2));
          const cardY = preferAbove ? (pt.y - cardH - 14) : (pt.y + 14);
          const strokeCol = isPinned ? "#fde047" : "#38bdf8";

          const anchorY = preferAbove ? (cardY + cardH) : cardY;
          popoversHtml += `<line x1="${pt.x.toFixed(1)}" y1="${pt.y.toFixed(1)}" x2="${(cardX + cardW / 2).toFixed(1)}" y2="${anchorY.toFixed(1)}" stroke="${strokeCol}" stroke-width="1.5" stroke-dasharray="2 2" />`;
          popoversHtml += `<rect x="${cardX.toFixed(1)}" y="${cardY.toFixed(1)}" width="${cardW}" height="${cardH}" rx="6" fill="#020617" fill-opacity="0.96" stroke="${strokeCol}" stroke-width="${isPinned ? '2' : '1.4'}" />`;
          popoversHtml += `<text x="${(cardX + 8).toFixed(1)}" y="${(cardY + 15).toFixed(1)}" fill="#f8fafc" font-size="9.5" font-family="monospace" font-weight="bold">Packet #${tk.id} [${getCmdDisplay(tk.cmd)} @ ${tk.addr}] (${tk.len}B)</text>`;
          if (isPinned) {
            popoversHtml += `<text x="${(cardX + cardW - 8).toFixed(1)}" y="${(cardY + 15).toFixed(1)}" text-anchor="end" fill="#fde047" font-size="9" font-weight="bold">📌</text>`;
          }
          popoversHtml += `<text x="${(cardX + 8).toFixed(1)}" y="${(cardY + 33).toFixed(1)}" fill="#fbbf24" font-size="10" font-family="monospace" font-weight="bold">Data: ${tk.data || "N/A"}</text>`;
          popoversHtml += `<text x="${(cardX + 8).toFixed(1)}" y="${(cardY + 49).toFixed(1)}" fill="#94a3b8" font-size="8.5">${phaseShort} | ${getStatusDisplay(tk.status)}</text>`;
        }
      });

      popoversLayer.innerHTML = popoversHtml;
    }

    function renderSwimlaneGantt() {
      const svg = document.getElementById("swimlaneSvg");
      if (!svg) return;

      const maxSimTime = getMaxSimTimeNs();
      const span = Math.min(maxSimTime, ganttSpanNs || 600);
      let viewStart = Math.max(0, Math.floor((currentTimeNs - span * 0.3) / 50) * 50);
      let viewEnd = viewStart + span;
      if (viewEnd > maxSimTime) {
        viewEnd = maxSimTime;
        viewStart = Math.max(0, viewEnd - span);
      }
      const viewSpan = Math.max(50, viewEnd - viewStart);

      const LEFT_LABEL_W = 190;
      const W = 920;
      const H = 180;
      const PLOT_W = W - LEFT_LABEL_W - 14;

      const activeLinks = traceData.links.slice(0, 12);
      const rowH = Math.min(17, (H - 22) / Math.max(1, activeLinks.length));

      let html = "";

      const tickStep = viewSpan <= 200 ? 20 : (viewSpan <= 600 ? 50 : (viewSpan <= 1500 ? 150 : 500));
      const firstTick = Math.ceil(viewStart / tickStep) * tickStep;
      for (let t = firstTick; t <= viewEnd; t += tickStep) {
        const x = LEFT_LABEL_W + ((t - viewStart) / viewSpan) * PLOT_W;
        html += `<line x1="${x.toFixed(1)}" y1="16" x2="${x.toFixed(1)}" y2="${H}" stroke="rgba(148, 163, 184, 0.14)" stroke-width="1" />`;
        html += `<text x="${x.toFixed(1)}" y="12" text-anchor="middle" fill="#94a3b8" font-size="9.5" font-family="monospace">${t}ns</text>`;
      }

      activeLinks.forEach((link, idx) => {
        const yTop = 18 + idx * rowH;
        const isSel = selectedKind === "link" && selectedId === link.id;
        if (isSel) {
          html += `<rect x="0" y="${yTop}" width="${W}" height="${rowH}" fill="rgba(56, 189, 248, 0.1)" />`;
        }
        html += `<line x1="0" y1="${(yTop + rowH).toFixed(1)}" x2="${W}" y2="${(yTop + rowH).toFixed(1)}" stroke="rgba(30, 41, 59, 0.8)" stroke-width="1" />`;

        const lblCol = isSel ? "#fde047" : (link.abstraction === "LT" ? "#38bdf8" : "#cbd5e1");
        html += `<text x="6" y="${(yTop + rowH - 3.5).toFixed(1)}" fill="${lblCol}" font-size="9.5" font-weight="${isSel ? "bold" : "normal"}" style="cursor:pointer" onclick="selectLink('${link.id}')">${getLinkDisplay(link)}</text>`;

        const laneTokens = (traceData.tokens || []).filter(
          (tk) => tk.link === link.id && tk.t4 > viewStart && tk.t1 < viewEnd
        );

        laneTokens.forEach((tk) => {
          const xStart = LEFT_LABEL_W + (Math.max(0, tk.t1 - viewStart) / viewSpan) * PLOT_W;
          const xReqEnd = LEFT_LABEL_W + (Math.max(0, Math.min(viewSpan, tk.t2 - viewStart)) / viewSpan) * PLOT_W;
          const xRespStart = LEFT_LABEL_W + (Math.max(0, Math.min(viewSpan, tk.t3 - viewStart)) / viewSpan) * PLOT_W;
          const xEnd = LEFT_LABEL_W + (Math.max(0, Math.min(viewSpan, tk.t4 - viewStart)) / viewSpan) * PLOT_W;
          const barY = yTop + 2;
          const barH = Math.max(6, rowH - 4);
          const isPinned = pinnedTokenIds.has(tk.id);
          const isHovered = hoveredTokenId === tk.id;
          const hiStroke = isPinned
            ? `stroke="#fde047" stroke-width="1.8"`
            : (isHovered ? `stroke="#ffffff" stroke-width="1.4"` : "");
          const evAttrs = `style="cursor:pointer" onmouseenter="onHoverToken(${tk.id})" onmouseleave="onLeaveToken(${tk.id})" onclick="onTogglePinToken(event, ${tk.id}, '${link.id}')"`;

          if (tk.cmd.includes("DMI")) {
            html += `<rect x="${xStart.toFixed(1)}" y="${barY}" width="${Math.max(8, xEnd - xStart).toFixed(1)}" height="${barH}" rx="2" fill="#c084fc" ${hiStroke} ${evAttrs}></rect>`;
          } else if (tk.mode === "LT") {
            html += `<rect x="${xStart.toFixed(1)}" y="${barY}" width="${Math.max(4, xEnd - xStart).toFixed(1)}" height="${barH}" rx="2" fill="#0ea5e9" ${hiStroke} ${evAttrs}></rect>`;
          } else {
            if (xReqEnd > xStart + 0.5) {
              html += `<rect x="${xStart.toFixed(1)}" y="${barY}" width="${Math.max(2, xReqEnd - xStart).toFixed(1)}" height="${barH}" fill="#f43f5e" ${hiStroke} ${evAttrs}></rect>`;
            }
            if (xRespStart > xReqEnd + 0.5) {
              html += `<rect x="${xReqEnd.toFixed(1)}" y="${barY}" width="${Math.max(2, xRespStart - xReqEnd).toFixed(1)}" height="${barH}" fill="#fbbf24" ${hiStroke} ${evAttrs}></rect>`;
            }
            if (xEnd > xRespStart + 0.5) {
              html += `<rect x="${xRespStart.toFixed(1)}" y="${barY}" width="${Math.max(2, xEnd - xRespStart).toFixed(1)}" height="${barH}" fill="#10b981" ${hiStroke} ${evAttrs}></rect>`;
            }
          }
        });
      });

      const curX = LEFT_LABEL_W + ((currentTimeNs - viewStart) / viewSpan) * PLOT_W;
      html += `<line x1="${curX.toFixed(1)}" y1="14" x2="${curX.toFixed(1)}" y2="${H}" stroke="#fde047" stroke-width="2" pointer-events="none" />`;
      html += `<rect x="${(curX - 28).toFixed(1)}" y="1" width="56" height="13" rx="3" fill="#fde047" pointer-events="none" />`;
      html += `<text x="${curX.toFixed(1)}" y="10.5" text-anchor="middle" fill="#020617" font-size="8.5" font-family="monospace" font-weight="bold" pointer-events="none">${currentTimeNs.toFixed(0)}ns</text>`;

      svg.innerHTML = html;

      svg.onclick = (e) => {
        if (e.target && e.target.tagName === "rect" && e.target.getAttribute("onclick")) return;
        const rect = svg.getBoundingClientRect();
        const svgX = ((e.clientX - rect.left) / rect.width) * W;
        if (svgX >= LEFT_LABEL_W) {
          const ratio = Math.max(0, Math.min(1, (svgX - LEFT_LABEL_W) / PLOT_W));
          const clickedNs = viewStart + ratio * viewSpan;
          setSimTimeNs(clickedNs);
          renderAll();
        }
      };
    }

    function updateTerminalLogBox() {
      const box = document.getElementById("terminalLogBox");
      if (!box) return;

      const logs = traceData.logs || [];
      if (!logs.length) {
        box.textContent = "";
        return;
      }

      const visibleLogs = logs.filter((lg) => lg.t <= currentTimeNs + 0.05);
      if (visibleLogs.length === lastRenderedLogCount) return;
      lastRenderedLogCount = visibleLogs.length;

      const tailLogs = visibleLogs.slice(-120);
      box.textContent = tailLogs.map((lg) => lg.text.trimEnd()).join(String.fromCharCode(10, 10));
      box.scrollTop = box.scrollHeight;
    }

    function selectLink(linkId) {
      selectedKind = "link";
      selectedId = linkId;
      renderAll(true);
    }

    function stepTimeNs(deltaNs) {
      setSimTimeNs(currentTimeNs + deltaNs);
      renderAll();
    }

    function stepDiscreteEvent(dir) {
      if (!sortedEventTimes.length) return;
      if (dir > 0) {
        const nextT = sortedEventTimes.find((t) => t > currentTimeNs + 0.05);
        setSimTimeNs(nextT !== undefined ? nextT : sortedEventTimes[0]);
      } else {
        let prevT = sortedEventTimes[sortedEventTimes.length - 1];
        for (let i = sortedEventTimes.length - 1; i >= 0; i--) {
          if (sortedEventTimes[i] < currentTimeNs - 0.05) {
            prevT = sortedEventTimes[i];
            break;
          }
        }
        setSimTimeNs(prevT);
      }
      renderAll();
    }

    function updateTimelinePlayhead() {
      const maxT = getMaxSimTimeNs();
      const slider = document.getElementById("timeSlider");
      slider.max = maxT;
      slider.value = Math.round(currentTimeNs);

      const winNs = traceData.meta.window_ns || 100;
      const fObj = traceData.frames[currentFrame] || { time_ns: 0 };
      document.getElementById("simTimeBadge").textContent = `${currentTimeNs.toFixed(1)} ns`;
      document.getElementById("frameBadge").textContent = `${fObj.time_ns} - ${fObj.time_ns + winNs} ns`;
      document.getElementById("maxTimeLabel").textContent = `${maxT.toFixed(1)} ns`;
    }

    function renderAll(forceTopo = false) {
      updateTimelinePlayhead();
      const topoKey = `${currentFrame}_${selectedKind}_${selectedId}`;
      if (forceTopo || topoKey !== lastRenderedTopoKey) {
        lastRenderedTopoKey = topoKey;
        renderTopology();
      } else {
        renderParticles();
      }
      renderSwimlaneGantt();
      updateTerminalLogBox();
    }

    let dragNode = null;
    function startDragNode(evt, node) {
      evt.stopPropagation();
      dragNode = node;
      const svg = document.getElementById("socSvg");

      function onMove(moveEvt) {
        if (!dragNode) return;
        const pt = svg.createSVGPoint();
        pt.x = moveEvt.clientX;
        pt.y = moveEvt.clientY;
        const cursorPt = pt.matrixTransform(svg.getScreenCTM().inverse());
        dragNode.x = Math.max(75, Math.min(885, Math.round(cursorPt.x)));
        dragNode.y = Math.max(65, Math.min(535, Math.round(cursorPt.y)));
        renderTopology();
      }

      function onUp() {
        dragNode = null;
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      }

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    }

    function zoomGantt(factor) {
      ganttSpanNs = Math.max(50, Math.min(getMaxSimTimeNs(), Math.round((ganttSpanNs || 600) * factor)));
      renderSwimlaneGantt();
    }

    function resetGanttZoom() {
      ganttSpanNs = 600;
      renderSwimlaneGantt();
    }

    function syncSpeedHighlight() {
      const val = parseFloat(document.getElementById("speedInput").value);
      document.querySelectorAll("#speedDropdownMenu .speed-opt").forEach((btn) => {
        const optVal = parseFloat(btn.getAttribute("data-speed"));
        const active = Math.abs(val - optVal) < 1e-6;
        btn.className = active
          ? "speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-sky-300 bg-sky-500/15 hover:bg-sky-500/25"
          : "speed-opt w-full text-left px-2.5 py-1 text-xs font-mono text-slate-200 hover:bg-sky-500/20 hover:text-sky-300";
      });
    }

    document.getElementById("speedDropdownBtn").addEventListener("click", (e) => {
      e.stopPropagation();
      const menu = document.getElementById("speedDropdownMenu");
      syncSpeedHighlight();
      menu.classList.toggle("hidden");
    });

    document.querySelectorAll("#speedDropdownMenu .speed-opt").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        document.getElementById("speedInput").value = btn.getAttribute("data-speed");
        syncSpeedHighlight();
        document.getElementById("speedDropdownMenu").classList.add("hidden");
      });
    });

    document.getElementById("speedInput").addEventListener("focus", (e) => {
      document.getElementById("speedDropdownMenu").classList.add("hidden");
      e.target.select();
    });

    window.addEventListener("click", (e) => {
      const box = document.getElementById("speedComboBox");
      if (box && !box.contains(e.target)) {
        document.getElementById("speedDropdownMenu").classList.add("hidden");
      }
    });

    document.getElementById("timeSlider").addEventListener("input", (e) => {
      setSimTimeNs(parseFloat(e.target.value));
      renderAll();
    });

    function togglePlay() {
      isPlaying = !isPlaying;
      document.getElementById("playIcon").textContent = isPlaying ? "⏸" : "▶";
      document.getElementById("playLabel").textContent = isPlaying ? "Pause" : "Play";
      if (isPlaying) {
        lastRafTime = performance.now();
        requestAnimationFrame(playbackLoop);
      }
    }

    function playbackLoop(now) {
      if (!isPlaying) return;
      const dtSec = Math.min(0.1, (now - (lastRafTime || now)) / 1000.0);
      lastRafTime = now;
      const mult = Math.max(0.01, parseFloat(document.getElementById("speedInput").value) || 0.25);
      const speedNsPerSec = mult * 100.0;
      const maxT = getMaxSimTimeNs();
      let nextT = currentTimeNs + dtSec * speedNsPerSec;
      if (nextT >= maxT) nextT = 0;
      setSimTimeNs(nextT);
      renderAll();
      requestAnimationFrame(playbackLoop);
    }

    document.getElementById("playPauseBtn").addEventListener("click", togglePlay);

    window.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        stepDiscreteEvent(1);
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        stepDiscreteEvent(-1);
      }
    });

    document.getElementById("jsonFileInput").addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const parsed = JSON.parse(ev.target.result);
          if (parsed.nodes && parsed.links && parsed.frames) {
            packetDomMap.clear();
            document.getElementById("particlesLayer").innerHTML = "";
            document.getElementById("popoversLayer").innerHTML = "";
            pinnedTokenIds.clear();
            hoveredTokenId = null;
            lastRenderedLogCount = -1;
            updatePinnedBadgeUI();

            traceData = parsed;
            rebuildEventTimestamps();
            setSimTimeNs(0);
            selectedKind = "link";
            selectedId = parsed.links[0] ? parsed.links[0].id : "";
            renderAll(true);
          } else {
            alert("Invalid trace file format.");
          }
        } catch (err) {
          alert("Failed to parse file: " + err.message);
        }
      };
      reader.readAsText(file);
    });

    rebuildEventTimestamps();
    renderAll(true);
  </script>
</body>
</html>
"""

# 1. Write standalone web/index.html
standalone_html = (
    HTML_TEMPLATE.replace("__HTML_CLASS__", 'class="dark"')
    .replace("__TAILWIND_SRC__", "https://cdn.tailwindcss.com")
    .replace(
        "__ROOT_VARS__",
        """    :root {
      --background: #020617;
      --foreground: #f8fafc;
      --card: #0f172a;
      --border: #1e293b;
      --muted-foreground: #94a3b8;
      --primary: #0ea5e9;
      --primary-foreground: #082f49;
      --accent: #1e293b;
    }""",
    )
    .replace("__ACCELLERA_JSON__", accellera_json_str)
)

with open("web/index.html", "w", encoding="utf-8") as fp:
    fp.write(standalone_html)

# 2. Write artifact HTML to vendor/artifact_preview.html
artifact_html = (
    HTML_TEMPLATE.replace("__HTML_CLASS__", "")
    .replace("__TAILWIND_SRC__", "https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js")
    .replace("__ROOT_VARS__", "")
    .replace("__ACCELLERA_JSON__", accellera_json_str)
)

with open("vendor/artifact_preview.html", "w", encoding="utf-8") as fp:
    fp.write(artifact_html)

print("Generated clean UI without code/function/filename labels!")
