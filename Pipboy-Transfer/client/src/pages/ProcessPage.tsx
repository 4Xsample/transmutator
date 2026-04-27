import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useLocation } from "wouter";
import { ArrowLeft, Play, Pause, Square, ChevronRight, GripVertical } from "lucide-react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  formatBackendCategory,
  getStatus,
  pausePipeline,
  PipelineStatus,
  reorderPipeline,
  resumePipeline,
  startPipeline,
  stopPipeline,
} from "@/lib/api";

const FileProgressText = ({ text, progress, isSource }: { text: string, progress: number, isSource: boolean }) => {
  const splitIndex = Math.floor(text.length * (progress / 100));

  const transferredPart = text.slice(0, splitIndex);
  const currentPart = text.slice(splitIndex, splitIndex + 1);
  const remainingPart = text.slice(splitIndex + 1);

  if (isSource) {
    // Origen: text en clar inicialment (hi es tot) -> s'enfosqueix a mesura que es buida
    return (
      <span className="font-mono tracking-wider font-bold">
        <span className="text-primary/20 transition-colors duration-300">{transferredPart}</span>
        <span className="text-primary animate-pulse">{currentPart}</span>
        <span className="text-primary glow-text transition-colors duration-300">{remainingPart}</span>
      </span>
    );
  } else {
    // Destí: text fosc inicialment (buit) -> s'aclareix a mesura que s'omple
    return (
      <span className="font-mono tracking-wider font-bold">
        <span className="text-primary glow-text transition-colors duration-300">{transferredPart}</span>
        <span className="text-primary animate-pulse">{currentPart}</span>
        <span className="text-primary/20 transition-colors duration-300">{remainingPart}</span>
      </span>
    );
  }
};

export default function ProcessPage() {
  const params = useParams();
  const [, setLocation] = useLocation();
  const category = params.category || "unknown";
  const action = params.action || "unknown";
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [draggedId, setDraggedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const next = await getStatus();
      if (!cancelled) {
        setStatus(next);
      }
    };
    void load();
    const interval = window.setInterval(() => {
      void load();
    }, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const files = status?.files ?? [];
  const isRunning = status?.pipeline === "running";
  const isPaused = status?.pipeline === "paused";
  const isFinished = status?.pipeline === "completed";
  const isTerminal = status?.pipeline === "completed" || status?.pipeline === "stopped" || status?.pipeline === "error";
  const displayFiles = useMemo(() => {
    if (!isFinished) return files;
    return files.map((file) => ({
      ...file,
      status: "done",
      progress: 100,
    }));
  }, [files, isFinished]);
  const globalProgress = useMemo(() => {
    if (isFinished) return 100;
    if (!files.length) return status?.current_progress ?? 0;
    const queueAverage = files.reduce((acc, file) => acc + file.progress, 0) / files.length;
    return Math.max(queueAverage, status?.current_progress ?? 0);
  }, [files, isFinished, status?.current_progress]);
  const footerText = useMemo(() => {
    if (status?.last_error) return status.last_error;
    if (isFinished) return `${status?.results.ok ?? 0} COMPLETED / ${status?.results.fail ?? 0} ERRORS`;
    return status?.current_eta || "READY";
  }, [isFinished, status]);

  const canReorder = status?.phase === "transform" && (status?.pipeline === "running" || status?.pipeline === "paused");

  const handleStart = async () => {
    setBusy(true);
    try {
      const next = await startPipeline();
      setStatus(next);
    } finally {
      setBusy(false);
    }
  };

  const handlePauseResume = async () => {
    setBusy(true);
    try {
      const next = isPaused ? await resumePipeline() : await pausePipeline();
      setStatus(next);
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    setBusy(true);
    try {
      const next = await stopPipeline();
      setStatus(next);
    } finally {
      setBusy(false);
    }
  };

  const handleDrop = async (targetId: string) => {
    if (!draggedId || draggedId === targetId || !status || !canReorder) {
      setDraggedId(null);
      return;
    }

    const pendingRows = displayFiles.filter((file) => file.status === "pending");
    const pendingIds = pendingRows.map((file) => file.id);
    if (!pendingIds.includes(draggedId) || !pendingIds.includes(targetId)) {
      setDraggedId(null);
      return;
    }

    const reorderedIds = [...pendingIds];
    const fromIndex = reorderedIds.indexOf(draggedId);
    const toIndex = reorderedIds.indexOf(targetId);
    const [moved] = reorderedIds.splice(fromIndex, 1);
    reorderedIds.splice(toIndex, 0, moved);

    setBusy(true);
    try {
      const next = await reorderPipeline(reorderedIds);
      setStatus(next);
    } finally {
      setBusy(false);
      setDraggedId(null);
    }
  };

  return (
    <Layout>
      <div className="h-full min-h-0 flex flex-col">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-primary/30">
          <div className="flex items-center gap-4">
            <Link href="/">
              <button className="hover:bg-primary/20 p-2 rounded-full transition-colors">
                <ArrowLeft className="w-6 h-6" />
              </button>
            </Link>
            <div>
              <h1 className="text-2xl font-display tracking-widest glow-text uppercase text-primary">
                {action} SEQUENCE // {category}
              </h1>
              <div className="text-xs uppercase text-primary/60 tracking-widest mt-1">
                <span>
                  PHASE: {status?.phase ?? "idle"} | QUEUE: {files.length} ITEMS | STATE: {status?.pipeline ?? "idle"}
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex gap-2">
            {!isTerminal ? (
              <>
                {isRunning || isPaused ? (
                  <Button onClick={handlePauseResume} disabled={busy} className="bg-primary text-black hover:bg-primary/80 font-bold uppercase tracking-wider">
                    {isPaused ? <><Play className="w-4 h-4 mr-2" /> Resume</> : <><Pause className="w-4 h-4 mr-2" /> Pause</>}
                  </Button>
                ) : (
                  <Button onClick={handleStart} disabled={busy} className="bg-primary text-black hover:bg-primary/80 font-bold uppercase tracking-wider">
                    <Play className="w-4 h-4 mr-2" /> Initialize
                  </Button>
                )}
                <Button onClick={handleStop} disabled={busy || (!isRunning && !isPaused)} variant="destructive" className="bg-destructive/80 hover:bg-destructive font-bold uppercase tracking-wider">
                  <Square className="w-4 h-4 mr-2" /> Abort
                </Button>
              </>
            ) : (
               <Link href="/report">
                 <Button className="bg-primary text-black hover:bg-primary/80 font-bold uppercase tracking-wider animate-pulse">
                   Generate Receipt <ChevronRight className="w-4 h-4 ml-2" />
                 </Button>
               </Link>
            )}
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-hidden flex flex-col gap-4">
          <div className="grid grid-cols-[2fr_1fr_2fr] gap-4 text-xs uppercase tracking-widest text-primary/50 px-4 shrink-0">
            <div>Local Origin</div>
            <div className="text-center">Throughput</div>
            <div className="text-right">Network Target</div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden border border-primary/20 bg-black/30 p-2 space-y-2 relative">
             <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent,transparent_19px,rgba(16,255,16,0.05)_20px)] pointer-events-none" />

            {displayFiles.map((file) => {
              const draggable = canReorder && file.status === "pending" && !busy;
              return (
              <div
                key={file.id}
                draggable={draggable}
                onDragStart={() => {
                  if (draggable) setDraggedId(file.id);
                }}
                onDragOver={(event) => {
                  if (draggable) event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  void handleDrop(file.id);
                }}
                onDragEnd={() => setDraggedId(null)}
                className={`grid grid-cols-[auto_2fr_1fr_2fr] gap-4 p-3 items-center border border-primary/10 transition-colors relative z-10 ${file.status === 'active' ? 'bg-primary/5 border-primary/30 shadow-[inset_0_0_20px_rgba(16,255,16,0.05)]' : ''} ${draggedId === file.id ? 'opacity-40' : ''} ${draggable ? 'cursor-grab' : ''}`}
              >
                <div className="flex justify-center text-primary/35">
                  {file.status === "pending" ? <GripVertical className={`w-4 h-4 ${draggable ? "text-primary/55" : "text-primary/20"}`} /> : <span className="w-4" />}
                </div>
                <div className="truncate">
                  <FileProgressText text={file.name} progress={file.progress} isSource={true} />
                </div>

                <div className="flex flex-col items-center justify-center gap-1">
                  <div className="w-full h-1 bg-primary/10 relative overflow-hidden">
                    <div className="absolute left-0 top-0 bottom-0 bg-primary shadow-[0_0_10px_rgba(16,255,16,0.5)] transition-all duration-300" style={{ width: `${file.progress}%` }} />
                  </div>
                  <div className="flex justify-between w-full text-[10px] text-primary/70 font-mono uppercase">
                    <span>{file.progress.toFixed(0)}%</span>
                    <span>{formatBackendCategory(file.category)}</span>
                  </div>
                </div>

                <div className="text-right truncate">
                   <FileProgressText text={file.name} progress={file.progress} isSource={false} />
                </div>
              </div>
            )})}
          </div>

          <div className="border border-primary/30 p-4 bg-black/50 mt-2 shrink-0 sticky bottom-0">
            <div className="flex justify-between text-sm uppercase mb-2 font-bold tracking-widest">
              <span>Overall Integrity Progress</span>
              <span className="glow-text">{globalProgress.toFixed(1)}%</span>
            </div>
            <Progress value={globalProgress} className="h-4 bg-black border border-primary rounded-none [&>div]:bg-primary" />
            <div className="mt-3 flex justify-between text-xs uppercase tracking-widest text-primary/60">
              <span>{isFinished ? "PIPELINE COMPLETED" : (status?.current_file || "NO ACTIVE FILE")}</span>
              <span>{footerText}</span>
            </div>
            {canReorder && (
              <div className="mt-2 text-[10px] uppercase tracking-[0.2em] text-primary/45">
                Drag pending files to change the next processing order.
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
