import { useEffect, useState } from "react";
import { Link } from "wouter";
import { Printer, RefreshCw } from "lucide-react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import {
  formatBackendCategory,
  formatBytes,
  formatDuration,
  formatPercent,
  formatTimestamp,
  getLatestReport,
  getReportById,
  getReportHistory,
  getStatus,
  PersistedReport,
  ReportHistoryItem,
} from "@/lib/api";

export default function ReportPage() {
  const [report, setReport] = useState<PersistedReport | null>(null);
  const [history, setHistory] = useState<ReportHistoryItem[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [statusFallback, setStatusFallback] = useState<Awaited<ReturnType<typeof getStatus>> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([getLatestReport(), getReportHistory(12)])
      .then(async ([latestResult, historyResult]) => {
        if (cancelled) return;

        if (historyResult.status === "fulfilled") {
          setHistory(historyResult.value);
        }

        if (latestResult.status === "fulfilled") {
          setReport(latestResult.value);
          return;
        }

        const status = await getStatus().catch(() => null);
        if (!cancelled) {
          setStatusFallback(status);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedReportId) return;
    let cancelled = false;
    setLoading(true);
    getReportById(selectedReportId)
      .then((payload) => {
        if (!cancelled) setReport(payload);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedReportId]);

  const latestError = report?.runtime?.last_error || statusFallback?.last_error || "NONE";
  const lastPhase = report?.runtime?.pipeline_state || statusFallback?.pipeline || "idle";
  const visibleCount = report?.summary.total_results ?? statusFallback?.files_count ?? 0;
  const okCount = report?.summary.successes ?? statusFallback?.results.ok ?? 0;
  const failCount = report?.summary.failures ?? statusFallback?.results.fail ?? 0;
  const currentFile = report?.results[report.results.length - 1]?.name || statusFallback?.current_file || "-";
  const progressText = statusFallback ? `${statusFallback.current_progress.toFixed(1)}%` : "100.0%";
  const savedText = report ? formatBytes(report.summary.space_saved) : "0.0 B";
  const runtimeSeconds =
    report?.runtime?.started_at && report?.runtime?.finished_at
      ? Math.max(0, report.runtime.finished_at - report.runtime.started_at)
      : null;

  return (
    <Layout>
      <div className="h-full min-h-0 flex flex-col p-4 overflow-hidden">
        <div className="w-full max-w-6xl mx-auto flex-1 min-h-0 overflow-y-auto overflow-x-hidden pr-2">
        <div className="bg-[#1a2d1a] text-primary p-8 border-2 border-primary/40 shadow-[0_0_30px_rgba(16,255,16,0.1)] max-w-lg w-full font-mono relative mx-auto">
          <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-5 pointer-events-none"></div>

          <pre className="text-sm leading-tight whitespace-pre">
{`========================================
             SCRIPT REPORT
========================================
 Client: Transmutator Web UI
 Data:   ${report?.timestamp ? formatTimestamp(report.timestamp) : "IN PROGRESS"}
----------------------------------------

            TASQUES COMPLETADES
----------------------------------------
 Estat pipeline:            ${String(lastPhase).toUpperCase()}
 Fase final:                ${String(statusFallback?.phase ?? "none").toUpperCase()}
 Arxius visibles:           ${String(visibleCount).padStart(4, " ")}
 Arxius correctes:          ${String(okCount).padStart(4, " ")}
 Arxius amb error:          ${String(failCount).padStart(4, " ")}

----------------------------------------
              RESUM GLOBAL
----------------------------------------
 Arxiu actual:               ${currentFile.slice(0, 24)}
 Progrés actual:             ${progressText.padStart(8, " ")}
 Ratio d'èxit:              ${(report ? formatPercent(report.summary.success_rate) : "0.0%").padStart(8, " ")}
 Temps runtime:             ${runtimeSeconds ? formatDuration(runtimeSeconds) : "—"}
 Espai estalviat:            ${savedText}
 Última categoria:           ${report?.results.length ? formatBackendCategory(report.results[report.results.length - 1].category) : "-"}
 ETA / error:                `}
<span className="text-red-500 font-bold bg-red-950/30 px-1">{latestError.slice(0, 28)}</span>
{`

========================================
        GRÀCIES PER UTILITZAR-ME!
========================================`}
          </pre>

          <div className="absolute -bottom-2 left-0 right-0 h-4 bg-[repeating-linear-gradient(45deg,transparent,transparent_5px,#1a2d1a_5px,#1a2d1a_10px)]"></div>
        </div>

        {report && (
          <div className="mt-8 w-full max-w-6xl grid gap-6 lg:grid-cols-[1.1fr_0.9fr] mx-auto">
            <div className="grid gap-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="border border-primary/30 bg-black/60 p-5">
                  <h3 className="text-lg uppercase tracking-widest glow-text mb-4">Category Breakdown</h3>
                  <div className="space-y-3 text-sm font-mono">
                    {Object.entries(report.by_category).map(([category, stats]) => (
                      <div key={category} className="border-b border-primary/10 pb-2">
                        <div className="flex items-center justify-between">
                          <span>{formatBackendCategory(category as "lidarr" | "tv-sonarr" | "radarr")}</span>
                          <span>{stats.successes} OK / {stats.failures} ERR</span>
                        </div>
                        <div className="mt-1 text-[11px] text-primary/60">
                          {formatBytes(stats.original_size)} → {formatBytes(stats.output_size)} | {formatDuration(stats.duration_seconds)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border border-primary/30 bg-black/60 p-5">
                  <h3 className="text-lg uppercase tracking-widest glow-text mb-4">Runtime</h3>
                  <div className="text-sm font-mono space-y-3">
                    <div className="flex justify-between"><span>Extract</span><span>{report.extract_done}/{report.extract_total || 0}</span></div>
                    <div className="flex justify-between"><span>Load</span><span>{report.load_done}/{report.load_total || 0}</span></div>
                    <div className="flex justify-between"><span>Compression</span><span>{formatPercent(report.summary.compression_ratio)}</span></div>
                    <div className="flex justify-between"><span>Media types</span><span>{Object.entries(report.media_types).map(([kind, count]) => `${kind}:${count}`).join(" ") || "—"}</span></div>
                    <div className="flex justify-between"><span>Total duration</span><span>{formatDuration(report.summary.total_duration)}</span></div>
                  </div>
                </div>
              </div>

              <div className="border border-primary/30 bg-black/60 p-5">
                <h3 className="text-lg uppercase tracking-widest glow-text mb-4">qBittorrent</h3>
                <div className="text-sm font-mono space-y-3">
                  <div className="flex justify-between"><span>Integration</span><span>{report.qbittorrent.enabled ? "ACTIVE" : "OFF"}</span></div>
                  <div className="flex justify-between"><span>Category changes</span><span>{report.qbittorrent.successes} OK / {report.qbittorrent.failures} ERR</span></div>
                  {report.qbittorrent.actions.length === 0 && (
                    <div className="text-primary/60 text-xs">No qBittorrent actions recorded for this run.</div>
                  )}
                  {report.qbittorrent.actions.map((action, index) => (
                    <div key={`${action.media_name}-${index}`} className="border-t border-primary/10 pt-2 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <div className="truncate">{action.media_name}</div>
                        <div className={action.success ? "text-primary" : "text-red-400"}>{action.success ? "OK" : "ERR"}</div>
                      </div>
                      <div className="text-primary/60">{action.source_category} → {action.target_category}</div>
                      {action.torrent_name && <div className="text-primary/50 truncate">{action.torrent_name}</div>}
                      {!action.success && <div className="text-red-400">{action.error || "ERROR"}</div>}
                    </div>
                  ))}
                </div>
              </div>

              <div className="border border-primary/30 bg-black/60 p-5">
                <h3 className="text-lg uppercase tracking-widest glow-text mb-4">Processed Files</h3>
                <div className="space-y-2 text-xs font-mono max-h-96 overflow-auto">
                  {report.results.map((item, index) => (
                    <div key={`${item.name}-${index}`} className="grid grid-cols-[2.3fr_1fr_0.8fr_1fr_1fr] gap-3 border-b border-primary/10 pb-2">
                      <div className="truncate">{item.name}</div>
                      <div>{formatBackendCategory(item.category)}</div>
                      <div>{item.success ? "OK" : "ERROR"}</div>
                      <div>{formatDuration(item.duration_seconds || 0)}</div>
                      <div>{item.success ? formatBytes(item.output_size || 0) : (item.error || "—")}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="border border-primary/30 bg-black/60 p-5 h-fit max-h-[70vh] overflow-y-auto">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h3 className="text-lg uppercase tracking-widest glow-text">Report History</h3>
                <div className="text-xs font-mono text-primary/60">{history.length} runs</div>
              </div>
              <div className="space-y-2">
                {history.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setSelectedReportId(entry.id)}
                    className={`w-full text-left border px-3 py-3 font-mono text-xs transition-colors ${
                      selectedReportId === entry.id || (!selectedReportId && report?.timestamp === entry.timestamp)
                        ? "border-primary bg-primary/10"
                        : "border-primary/20 bg-black/30 hover:bg-primary/5"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span>{formatTimestamp(entry.timestamp)}</span>
                      <span className={entry.pipeline_state === "completed" ? "text-primary" : "text-red-400"}>
                        {entry.pipeline_state.toUpperCase()}
                      </span>
                    </div>
                    <div className="mt-2 text-primary/70">
                      {entry.successes} OK / {entry.failures} ERR | {formatBytes(entry.space_saved)} saved
                    </div>
                    <div className="mt-1 text-primary/50">
                      {entry.extract_done}/{entry.extract_total || 0} extract | {entry.load_done}/{entry.load_total || 0} load | {formatDuration(entry.total_duration)}
                    </div>
                  </button>
                ))}
                {!loading && history.length === 0 && (
                  <div className="text-xs font-mono text-primary/60">No persisted reports yet.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {!report && !loading && (
          <div className="mt-8 text-sm font-mono text-primary/60">No report available yet.</div>
        )}

        <div className="mt-12 flex gap-4 justify-center">
          <Link href="/">
            <Button variant="outline" className="border-primary text-primary hover:bg-primary hover:text-black uppercase tracking-widest font-bold">
              <RefreshCw className="w-4 h-4 mr-2" /> New Sequence
            </Button>
          </Link>
          <Button disabled className="bg-primary text-black hover:bg-primary/80 font-bold uppercase tracking-widest px-8">
            <Printer className="w-4 h-4 mr-2" /> Print Ticket
          </Button>
        </div>
        </div>
      </div>
    </Layout>
  );
}
