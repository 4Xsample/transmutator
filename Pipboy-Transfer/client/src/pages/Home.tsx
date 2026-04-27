import { useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { Music, Film, Tv, Settings, Play } from "lucide-react";
import Layout from "@/components/Layout";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { getConfig, saveConfig, selectionFromApi, selectionToApi, startPipeline, UiCategory } from "@/lib/api";

type ActionKey = 'import' | 'convert' | 'send';

interface CategoryState {
  import: boolean;
  convert: boolean;
  send: boolean;
}

export default function Home() {
  const [, setLocation] = useLocation();
  const [selections, setSelections] = useState<Record<UiCategory, CategoryState>>({
    music: { import: false, convert: false, send: false },
    series: { import: false, convert: false, send: false },
    movies: { import: false, convert: false, send: false },
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const categories = [
    { id: "music", title: "MUSICA", icon: Music },
    { id: "series", title: "SERIES", icon: Tv },
    { id: "movies", title: "PELICULES", icon: Film },
  ] as const;

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((config) => {
        if (!cancelled) {
          setSelections(selectionFromApi(config.pipeline_selection));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleSelection = (catId: UiCategory, action: ActionKey) => {
    setSelections(prev => ({
      ...prev,
      [catId]: {
        ...prev[catId],
        [action]: !prev[catId][action]
      }
    }));
  };

  const toggleAllInCategory = (catId: UiCategory) => {
    setSelections(prev => {
      const allActive = prev[catId].import && prev[catId].convert && prev[catId].send;
      return {
        ...prev,
        [catId]: {
          import: !allActive,
          convert: !allActive,
          send: !allActive,
        }
      };
    });
  };

  const handleStart = async () => {
    setSaving(true);
    try {
      const pipelineSelection = selectionToApi(selections);
      await saveConfig({ pipeline_selection: pipelineSelection });
      await startPipeline(pipelineSelection);
      setLocation("/process/all/all");
    } finally {
      setSaving(false);
    }
  };

  const hasAnySelection = Object.values(selections).some(cat => 
    cat.import || cat.convert || cat.send
  );

  return (
    <Layout>
      <div className="flex flex-col h-full min-h-0 max-w-4xl mx-auto py-8 overflow-y-auto overflow-x-hidden pr-2">
        <h2 className="text-4xl font-display glow-text mb-12 tracking-tighter border-b border-primary/20 pb-4">
          MAIN CONTROL TERMINAL
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-12">
          {categories.map((cat) => (
            <div key={cat.id} className="space-y-6">
              <button 
                onClick={() => toggleAllInCategory(cat.id)}
                className="w-full flex items-center gap-3 border-b border-primary/40 pb-2 hover:bg-primary/10 transition-colors group cursor-pointer text-left"
              >
                <cat.icon className="w-6 h-6 group-hover:glow-text" />
                <h3 className="text-2xl font-display tracking-widest group-hover:glow-text">{cat.title}</h3>
                <span className="ml-auto text-[10px] text-primary/40 uppercase group-hover:text-primary">Toggle All</span>
              </button>
              
              <ul className="space-y-4">
                {(['import', 'convert', 'send'] as ActionKey[]).map((action) => (
                  <li key={action} className="flex items-center justify-between group">
                    <span className="text-sm uppercase tracking-widest group-hover:text-primary transition-colors">
                      {action === 'import' ? 'Importar' : action === 'convert' ? 'Convertir' : 'Enviar'}
                    </span>
                    <Switch 
                      checked={selections[cat.id][action]}
                      onCheckedChange={() => toggleSelection(cat.id, action)}
                      disabled={loading || saving}
                      className="data-[state=checked]:bg-primary data-[state=unchecked]:bg-primary/20 border border-primary/40"
                    />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-auto flex justify-between items-end border-t border-primary/20 pt-8">
          <div className="border border-primary/30 bg-black/80 p-4 text-xs font-mono max-w-sm">
            <p className="typing-effect">{">"} CONFIGURE MODULES AND INITIALIZE SEQUENCE.</p>
            <p className="text-primary/50 mt-1">{">"} MULTI-THREADING CAPABILITIES ACTIVE.</p>
          </div>

          <div className="flex flex-col items-end gap-4">
            <Link href="/settings">
              <button className="text-xs uppercase tracking-[0.2em] text-primary/60 hover:text-primary transition-all">
                [ EDIT SYSTEM CONFIG ]
              </button>
            </Link>
            
            <Button 
              disabled={!hasAnySelection || loading || saving}
              onClick={handleStart}
              className="bg-primary text-black hover:bg-primary/80 font-bold uppercase tracking-widest px-12 py-6 text-xl rounded-none disabled:opacity-30 transition-all shadow-[0_0_20px_rgba(16,255,16,0.2)]"
            >
              <Play className="w-6 h-6 mr-2 fill-current" /> {saving ? "Saving..." : "Initialize Operation"}
            </Button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
