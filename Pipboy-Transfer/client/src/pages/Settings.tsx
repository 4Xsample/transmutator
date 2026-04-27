import { useEffect, useState } from "react";
import { Link } from "wouter";
import { ArrowLeft, Save, FolderOpen } from "lucide-react";
import Layout from "@/components/Layout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { getConfig, QBittorrentTestResult, saveConfig, testQBittorrent } from "@/lib/api";

export default function SettingsPage() {
  const [form, setForm] = useState({
    torrent_base: "",
    tmp_staging: "",
    output_base: "",
    plex_destination: "",
    enabled: false,
    host: "",
    port: "8080",
    url: "",
    username: "",
    password: "",
    api_key: "",
    api_key_header: "X-API-Key",
    processed_category: "",
    modify_torrent_category: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<QBittorrentTestResult | null>(null);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((config) => {
        if (cancelled) return;
        setForm({
          torrent_base: config.paths.torrent_base,
          tmp_staging: config.paths.tmp_staging,
          output_base: config.paths.output_base,
          plex_destination: config.paths.plex_destination,
          enabled: config.qbittorrent.enabled,
          host: config.qbittorrent.host,
          port: String(config.qbittorrent.port || 8080),
          url: config.qbittorrent.url,
          username: config.qbittorrent.username,
          password: config.qbittorrent.password,
          api_key: config.qbittorrent.api_key,
          api_key_header: config.qbittorrent.api_key_header,
          processed_category: config.qbittorrent.processed_category,
          modify_torrent_category: config.qbittorrent.modify_torrent_category,
        });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const updateField = (key: keyof typeof form, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveConfig({
        paths: {
          torrent_base: form.torrent_base,
          tmp_staging: form.tmp_staging,
          output_base: form.output_base,
          plex_destination: form.plex_destination,
        },
        qbittorrent: {
          enabled: form.enabled,
          host: form.host,
          port: form.port || "8080",
          url: form.url,
          username: form.username,
          password: form.password,
          api_key: form.api_key,
          api_key_header: form.api_key_header,
          processed_category: form.processed_category,
          modify_torrent_category: form.modify_torrent_category,
        },
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await testQBittorrent({
        enabled: form.enabled,
        host: form.host,
        port: Number(form.port || 8080),
        url: form.url,
        username: form.username,
        password: form.password,
        api_key: form.api_key,
        api_key_header: form.api_key_header,
        processed_category: form.processed_category,
        modify_torrent_category: form.modify_torrent_category,
      });
      setTestResult(result);
      setAvailableCategories(result.categories || []);
    } finally {
      setTesting(false);
    }
  };

  return (
    <Layout>
      <div className="h-full min-h-0 max-w-3xl mx-auto overflow-y-auto overflow-x-hidden pr-2">
        <div className="flex items-center gap-4 mb-8 pb-4 border-b border-primary/30">
          <Link href="/">
            <button className="hover:bg-primary/20 p-2 rounded-full transition-colors">
              <ArrowLeft className="w-6 h-6" />
            </button>
          </Link>
          <h1 className="text-3xl font-display tracking-widest glow-text uppercase">
            SYSTEM CONFIGURATION
          </h1>
        </div>

        <div className="space-y-8 font-mono pb-6">
          <div className="space-y-4">
            <h2 className="text-xl font-bold border-l-4 border-primary pl-3 uppercase">File Directories</h2>
            <div className="grid gap-4 bg-primary/5 p-6 border border-primary/20">
              <div className="grid gap-2">
                <Label htmlFor="source" className="uppercase text-xs tracking-widest">Source Path (Torrent Download)</Label>
                <div className="flex gap-2">
                  <Input id="source" value={form.torrent_base} onChange={(e) => updateField("torrent_base", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                  <Button variant="outline" className="border-primary/50 hover:bg-primary hover:text-black"><FolderOpen className="w-4 h-4" /></Button>
                </div>
              </div>
              
              <div className="grid gap-2">
                <Label htmlFor="temp" className="uppercase text-xs tracking-widest">Temporary Path (Local Processing)</Label>
                <div className="flex gap-2">
                  <Input id="temp" value={form.tmp_staging} onChange={(e) => updateField("tmp_staging", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                  <Button variant="outline" className="border-primary/50 hover:bg-primary hover:text-black"><FolderOpen className="w-4 h-4" /></Button>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="dest" className="uppercase text-xs tracking-widest">Destination Path (Network Share)</Label>
                <div className="flex gap-2">
                  <Input id="dest" value={form.plex_destination} onChange={(e) => updateField("plex_destination", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                  <Button variant="outline" className="border-primary/50 hover:bg-primary hover:text-black"><FolderOpen className="w-4 h-4" /></Button>
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="output" className="uppercase text-xs tracking-widest">Processed Output Path</Label>
                <div className="flex gap-2">
                  <Input id="output" value={form.output_base} onChange={(e) => updateField("output_base", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                  <Button variant="outline" className="border-primary/50 hover:bg-primary hover:text-black"><FolderOpen className="w-4 h-4" /></Button>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-xl font-bold border-l-4 border-primary pl-3 uppercase">qBittorrent</h2>
            <div className="grid gap-4 bg-primary/5 p-6 border border-primary/20">
              <div className="flex items-center justify-between border border-primary/20 bg-black/30 px-4 py-3">
                <div>
                  <div className="uppercase text-xs tracking-widest text-primary/70">Enable Integration</div>
                  <div className="text-[11px] text-primary/50 mt-1">Allow backend lookup and optional category changes after successful processing.</div>
                </div>
                <Switch checked={form.enabled} onCheckedChange={(checked) => updateField("enabled", checked)} disabled={loading || saving} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="qbt-host" className="uppercase text-xs tracking-widest">Host / URL</Label>
                  <Input id="qbt-host" value={form.host} onChange={(e) => updateField("host", e.target.value)} disabled={loading || saving} placeholder="http://localhost" className="bg-black/50 border-primary/50 text-primary font-mono" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="qbt-port" className="uppercase text-xs tracking-widest">Port</Label>
                  <Input id="qbt-port" value={form.port} onChange={(e) => updateField("port", e.target.value)} disabled={loading || saving} placeholder="8080" className="bg-black/50 border-primary/50 text-primary font-mono" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="qbt-user" className="uppercase text-xs tracking-widest">Username</Label>
                  <Input id="qbt-user" value={form.username} onChange={(e) => updateField("username", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="qbt-pass" className="uppercase text-xs tracking-widest">Password</Label>
                  <Input id="qbt-pass" type="password" value={form.password} onChange={(e) => updateField("password", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="qbt-api-key" className="uppercase text-xs tracking-widest">API Key</Label>
                  <Input id="qbt-api-key" value={form.api_key} onChange={(e) => updateField("api_key", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="qbt-api-key-header" className="uppercase text-xs tracking-widest">API Key Header</Label>
                  <Input id="qbt-api-key-header" value={form.api_key_header} onChange={(e) => updateField("api_key_header", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="processed-category" className="uppercase text-xs tracking-widest">Processed Category</Label>
                  <Input id="processed-category" value={form.processed_category} onChange={(e) => updateField("processed_category", e.target.value)} disabled={loading || saving} className="bg-black/50 border-primary/50 text-primary font-mono" />
                  {availableCategories.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {availableCategories.map((category) => (
                        <button
                          key={category}
                          type="button"
                          onClick={() => updateField("processed_category", category)}
                          className={`border px-2 py-1 text-[10px] uppercase tracking-widest ${
                            form.processed_category === category
                              ? "border-primary bg-primary/20 text-primary"
                              : "border-primary/30 text-primary/70 hover:bg-primary/10"
                          }`}
                        >
                          {category}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-end justify-between border border-primary/20 bg-black/30 px-4 py-3">
                  <div>
                    <div className="uppercase text-xs tracking-widest text-primary/70">Auto-change Category</div>
                    <div className="text-[11px] text-primary/50 mt-1">Try to move matching torrents to the processed category after a successful pipeline run.</div>
                  </div>
                  <Switch checked={form.modify_torrent_category} onCheckedChange={(checked) => updateField("modify_torrent_category", checked)} disabled={loading || saving || !form.enabled} />
                </div>
              </div>
              <div className="text-[11px] uppercase tracking-widest text-primary/50 border-t border-primary/10 pt-3">
                If port is empty, backend falls back to 8080. API key is optional; if empty, username/password auth is used.
              </div>
              <div className="flex items-center justify-between gap-4 border-t border-primary/10 pt-4">
                <Button onClick={handleTest} disabled={loading || saving || testing} variant="outline" className="border-primary text-primary hover:bg-primary hover:text-black uppercase tracking-widest font-bold">
                  {testing ? "Testing..." : "Test qBittorrent"}
                </Button>
                {testResult && (
                  <div className={`text-xs font-mono ${testResult.success ? "text-primary" : "text-red-400"}`}>
                    {testResult.success
                      ? `OK ${testResult.version} | API ${testResult.api_version} | ${testResult.categories_count} categories`
                      : `ERROR: ${testResult.error}`}
                  </div>
                )}
              </div>
              {availableCategories.length > 0 && (
                <div className="text-[11px] font-mono text-primary/60 border-t border-primary/10 pt-3">
                  Categories discovered from qBittorrent: {availableCategories.join(", ")}
                </div>
              )}
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-4">
            <Button variant="outline" className="border-primary text-primary hover:bg-primary/20 uppercase tracking-widest font-bold">
              Reset Defaults
            </Button>
            <Button onClick={handleSave} disabled={loading || saving} className="bg-primary text-black hover:bg-primary/80 uppercase tracking-widest font-bold px-8">
              <Save className="w-4 h-4 mr-2" /> {saving ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
