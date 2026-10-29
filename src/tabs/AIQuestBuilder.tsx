import { useEffect, useState } from "react";
import { convertFileSrc, invoke } from "@tauri-apps/api/tauri";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/api/dialog";

interface Overview { path: string; label: string; notes?: string; review_state?: string; display_crop?: number[]; width?: number; height?: number; }
interface MapChoice { id: string; name: string; references: number; overviews: Overview[]; }
interface Flag { key: string; name: string; description: string; editable: boolean; }
interface Question {
  kind: string; text?: string; title?: string; label?: string; control?: string; previous?: string;
  provider?: string; model?: string; default?: string | number | null; minimum?: number; maximum?: number;
  proposed_id?: number; maps?: MapChoice[]; flags?: Flag[]; options?: { value: string; label: string }[];
}
const steps = ["AI account", "Map", "Description", "Parameters", "Quest ID", "Review / export"];
const field = "w-full p-3 rounded border dark:border-slate-600 bg-white dark:bg-slate-800 dark:text-white";
const button = "px-4 py-3 rounded border dark:border-slate-500 hover:border-emerald-400 disabled:opacity-40";
const primary = `${button} bg-emerald-500 text-slate-900 font-semibold`;

function phase(question: Question | null) {
  if (!question || question.control === "provider" || question.label === "Login method" || question.control === "secret") return 0;
  if (question.control === "map") return 1;
  if (question.control === "description") return 2;
  if (question.control === "quest_id") return 4;
  if (["stat_table", "flags"].includes(question.control || "") || ["Position", "Rewards", "Area/position requirements"].includes(question.label || "")) return 3;
  return 5;
}

export function AIQuestBuilder() {
  const [question, setQuestion] = useState<Question | null>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [answer, setAnswer] = useState("");
  const [provider, setProvider] = useState("codex");
  const [model, setModel] = useState("");
  const [description, setDescription] = useState("");
  const [selectedMap, setSelectedMap] = useState("");
  const [search, setSearch] = useState("");
  const [flags, setFlags] = useState<Record<string, string>>({});
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState("");
  const [activeStep, setActiveStep] = useState(0);
  const [work, setWork] = useState<{ text: string; since: number } | null>(null);
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    if (!work || question || !running) return;
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [work, question, running]);
  useEffect(() => {
    let mounted = true;
    let started = false;
    const subscriptions = [
      listen<string>("ai-message", event => {
        if (!mounted) return;
        try {
          const message: Question = JSON.parse(event.payload);
          if (message.kind === "question") {
            setWork(null);
            if (message.control === "map") setCompleted(false);
            setActiveStep(phase(message));
            setQuestion(message); setAnswer(message.default == null ? "" : String(message.default));
            if (message.control === "provider") { setProvider(message.provider || "codex"); setModel(message.model || ""); }
            if (message.control === "description" && message.previous) setDescription(message.previous);
            if (message.control === "flags") setFlags({});
          } else if (message.kind === "progress") { const since = Date.now(); setClock(since); setWork({ text: message.text || "Working", since }); }
          else if (message.kind === "complete") { setCompleted(true); setWork(null); }
          else if (message.kind === "error") { setError(message.text || "Unable to continue"); setWork(null); }
          else if (message.kind === "screen") { setMessages([]); if (message.title === "AI account") setActiveStep(0); }
          else if (message.text) { setMessages(previous => [...previous, message.text || ""]); }
        } catch { setError("Unreadable wizard response"); }
      }),
      listen("ai-ended", () => { if (mounted) { setRunning(false); setQuestion(null); setWork(null); } }),
    ];
    Promise.all(subscriptions).then(async () => {
      if (!mounted) return;
      started = true; setRunning(true);
      try { await invoke("ai_start"); }
      catch (failure) { if (mounted) { setRunning(false); setError(String(failure)); } }
    });
    return () => {
      mounted = false;
      subscriptions.forEach(subscription => subscription.then(unlisten => unlisten()));
      if (started) invoke("ai_stop").catch(() => undefined);
    };
  }, []);
  async function send(value: string) {
    if (!question) return;
    const pending = question; setQuestion(null); setError("");
    try { await invoke("ai_answer", { answer: value }); }
    catch (failure) { setQuestion(pending); setError(String(failure)); }
  }
  async function back() {
    if (question?.control === "provider") {
      await invoke("ai_stop"); setRunning(false); setQuestion(null);
    } else await send("b");
  }
  async function stop() {
    await invoke("ai_stop"); setRunning(false); setQuestion(null);
    setMessages(previous => [...previous, "Session stopped. Existing session files are preserved. No automatic model retry."]);
  }
  async function restart() {
    setCompleted(false); setError(""); setRunning(true); setQuestion(null); setWork(null);
    try { await invoke("ai_start"); }
    catch (failure) { setRunning(false); setError(String(failure)); }
  }
  async function browse() {
    try {
      const value = await open({ directory: /directory/i.test(question?.label || ""), multiple: false });
      if (typeof value === "string") setAnswer(value);
    } catch (failure) { setError(String(failure)); }
  }
  function submit() {
    if (!question) return;
    if (question.control === "provider") return send(JSON.stringify({ kind: provider, model }));
    if (question.control === "map") return send(selectedMap);
    if (question.control === "description") return send(description);
    if (question.control === "flags") return send(Object.entries(flags).filter(([, value]) => value).map(([key, value]) => `${value}${key}`).join(" "));
    if (question.control === "quest_id") { if (!answer) setActiveStep(5); return send(answer || "yes"); }
    return send(answer);
  }
  const map = question?.maps?.find(item => item.id === selectedMap);
  const currentPhase = completed ? 5 : activeStep;
  const providerOptions = [
    { id: "codex", name: "Codex / ChatGPT", description: "Use your own account. Existing official CLI login is reused; otherwise choose browser or device-code sign-in." },
    { id: "gemini", name: "Gemini API", description: "Use your own API key. Free-tier availability and quotas depend on your Google project." },
    { id: "openai", name: "OpenAI API", description: "Separate API key and billing. This does not use your ChatGPT subscription." },
  ];
  return <div className="space-y-5 max-w-7xl p-5 dark:text-white">
    <header>
      <h2 className="text-2xl font-semibold">Create a quest with AI</h2>
      <span className="text-xs opacity-60">AI integration beta - development build</span>
      <p className="mt-2 opacity-75">Choose your AI, explore the maps, then describe the quest. Existing quest files remain read-only.</p>
    </header>
    <ol className="flex flex-wrap gap-2" aria-label="Authoring steps">
      {steps.map((name, index) => <li key={name} className={`rounded px-3 py-2 text-sm ${index === currentPhase ? "bg-emerald-400 text-slate-900 font-semibold" : "border dark:border-slate-600 opacity-75"}`}>{index + 1}. {name}</li>)}
    </ol>
    {error && <div role="alert" className="border border-red-400 rounded p-4">{error}</div>}
    {running && <div role="status" aria-live="polite" className="border dark:border-slate-600 rounded p-3">
      {question ? "Waiting for your response" : work ? <>
        <span aria-hidden="true">⌛ </span>{work.text} · {Math.max(0, Math.floor((clock - work.since) / 1000))}s elapsed
        {(clock - work.since) > 30000 && <span className="block text-sm opacity-70">No new phase reported yet. The provider may still be processing; elapsed time alone does not confirm progress.</span>}
      </> : "⌛ Preparing the next step…"}
    </div>}
    {question ? <form onSubmit={event => { event.preventDefault(); submit(); }} className="border dark:border-slate-600 rounded p-5 space-y-5">
      <h3 className="text-xl font-semibold">{question.label}</h3>
      {question.control === "provider" ? <>
        <div className="grid lg:grid-cols-3 gap-4">
          {providerOptions.map(option => <button key={option.id} type="button" aria-pressed={provider === option.id} onClick={() => { setProvider(option.id); if (provider !== option.id) setModel(""); }}
            className={`text-left p-5 rounded border ${provider === option.id ? "border-emerald-400 bg-emerald-500/10" : "dark:border-slate-600"}`}>
            <strong>{option.name}</strong><p className="text-sm mt-3 opacity-80">{option.description}</p>
          </button>)}
        </div>
        <label className="block">Model (optional; blank uses provider default)<input className={field} value={model} onChange={event => setModel(event.target.value)} /></label>
        <details className="space-y-3"><summary className="cursor-pointer">Library / diagnostics</summary><div className="flex flex-wrap gap-3 mt-3">
          <button className={button} type="button" onClick={() => send(JSON.stringify({ kind: provider, model, action: "paths" }))}>Quest library / paths</button>
          <button className={button} type="button" onClick={() => send(JSON.stringify({ kind: provider, model, action: "quest_fix" }))}>Quest Fix</button>
          <button className={button} type="button" onClick={() => send(JSON.stringify({ kind: provider, model, action: "index" }))}>Analyze references</button>
        </div></details>
      </> : question.control === "map" ? <div className="grid lg:grid-cols-3 gap-5">
        <div className="space-y-3">
          <input className={field} type="search" placeholder="Search a map name or ID" aria-label="Search maps" value={search} onChange={event => setSearch(event.target.value)} />
          <div className="max-h-96 overflow-y-auto space-y-2" role="listbox" aria-label="Available maps">
            {question.maps?.filter(item => `${item.id} ${item.name}`.toLowerCase().includes(search.toLowerCase())).map(item =>
              <button className={`block w-full text-left p-3 rounded border ${selectedMap === item.id ? "border-emerald-400 bg-emerald-500/10" : "dark:border-slate-600"}`} type="button" role="option" aria-selected={selectedMap === item.id} key={item.id} onClick={() => setSelectedMap(item.id)}>
                {item.name}<span className="block text-xs opacity-70">Map {item.id} · {item.references} references</span>
              </button>)}
          </div>
        </div>
        <div className="lg:col-span-2 rounded p-4 bg-slate-900 text-white space-y-5">
          <h4 className="font-semibold">{map?.name || "Select a map to see its full overview"}</h4>
          {map?.overviews.map((view, index) => <figure key={`${view.path}-${index}`} className="space-y-2">
            <div style={view.display_crop && view.width ? { position: "relative", overflow: "hidden", aspectRatio: `${view.width} / ${view.display_crop[3]}` } : undefined}>
              <img alt={view.label} src={convertFileSrc(view.path)} style={{ width: "100%", height: "auto", imageRendering: "pixelated", ...(view.display_crop ? { position: "absolute", top: 0, left: 0 } : {}) }} />
            </div>
            <figcaption className="text-sm"><strong>{view.label}</strong><p>{view.review_state?.replaceAll("_", " ")}</p><p className="opacity-70">{view.notes}</p></figcaption>
          </figure>)}
          {map && !map.overviews.length && <p>A verified local overview has not been associated with this map yet.</p>}
          <p className="text-xs opacity-70">All associated views/layers are shown. Visual previews do not certify spawn coordinates or area transitions.</p>
        </div>
      </div> : question.control === "description" ?
        <textarea autoFocus className={field} rows={8} value={description} onChange={event => setDescription(event.target.value)} placeholder="Describe the monster, rank, objectives, duration and title. Multiple lines are supported." /> :
        question.control === "flags" ? <>
          <p>Keep preserves the native value. Known labels come from the editor; special modes require compatible native data. Unknown flags cannot be changed here.</p>
          <div className="grid md:grid-cols-2 gap-3 max-h-96 overflow-y-auto">{question.flags?.map(flag =>
            <div className="border dark:border-slate-600 rounded p-3" key={flag.key}>
              <label className="font-semibold">{flag.key} · {flag.name}
                <select className={field} disabled={!flag.editable} value={flags[flag.key] || ""} onChange={event => setFlags(previous => ({ ...previous, [flag.key]: event.target.value }))}>
                  <option value="">Keep native value</option><option value="+">Enable</option><option value="-">Disable</option>
                </select>
              </label><p className="text-sm opacity-75 mt-2">{flag.description}</p>
            </div>)}</div>
        </> : question.control === "choice" ? <div className="grid md:grid-cols-2 gap-3">{question.options?.map(option =>
          <button className={button} type="button" key={option.value} onClick={() => send(option.value)}>{option.label}</button>)}</div> :
          question.control === "quest_id" ? <>
            <p className="text-2xl font-semibold">Proposed ID: {question.proposed_id}</p>
            <p>Unused in the checked folders. Database availability is not checked.</p>
            <label className="block">Choose another ID (optional)<input className={field} type="number" min={65001} max={65535} value={answer} onChange={event => setAnswer(event.target.value)} /></label>
          </> : <>
            {question.control === "stat_table" && <p>Leave blank to preserve the native Monster Status table. This is a table index, not an HP value.</p>}
            <input autoFocus autoComplete="off" className={field} type={question.control === "secret" ? "password" : ["number", "stat_table"].includes(question.control || "") ? "number" : "text"}
              min={question.minimum} max={question.maximum} value={answer} onChange={event => setAnswer(event.target.value)} aria-label={question.label} />
            {question.control === "text" && /path|directory|executable/i.test(question.label || "") && <button className={button} type="button" onClick={browse}>Browse…</button>}
          </>}
      <div className="flex flex-wrap gap-3">
        <button className={button} type="button" onClick={back}>Back</button>
        {question.control !== "choice" && <button className={primary} type="submit" disabled={(question.control === "description" && !description.trim()) || (question.control === "map" && !selectedMap)}>
          {question.control === "provider" ? "Continue / sign in" : question.control === "quest_id" ? (answer ? "Propose this ID" : "Confirm proposed ID") : "Continue"}
        </button>}
        {question.control === "map" && <button className={button} type="button" onClick={() => send("")}>Let the description choose the map</button>}
      </div>
    </form> : <div className="border dark:border-slate-600 rounded p-5">
      <p>{running ? "Preparing the next step…" : completed ? "Session saved. You can inspect the exported BINs in QuestEditor." : "Ready to start."}</p>
      {running && <button className={`${button} mt-4`} onClick={stop}>Back / stop session</button>}
      {!running && <button className={`${primary} mt-4`} onClick={restart}>Start again</button>}
    </div>}
    {messages.length > 0 && <details className="border dark:border-slate-600 rounded p-4" open={currentPhase === 5 || (!question && running)}>
      <summary className="cursor-pointer">Account status / reference details / results</summary>
      <pre className="whitespace-pre-wrap text-sm mt-4 max-h-80 overflow-y-auto">{messages.join("\n")}</pre>
    </details>}
  </div>;
}
