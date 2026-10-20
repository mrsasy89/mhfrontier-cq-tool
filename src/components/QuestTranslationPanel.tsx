import { useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api';
import { toast } from 'react-toastify';
import { Button } from './Button';
import { GroupCard } from './CardGroup';
import { useQuestEditor } from '../context/QuestEditorContext';
import { translationFields, translationLabels, translationEntries, translateEntries, validateEndpoint, wrapTranslation } from '../utils/questTranslation';
import type { TranslationField, TranslatedEntry } from '../utils/questTranslation';
import { BatchTranslationPanel } from './translation/BatchTranslationPanel';

export function QuestTranslationPanel() {
  const { form, isLoadedFile } = useQuestEditor();
  const [enabled, setEnabled] = useState(false);
  const [endpoint, setEndpoint] = useState('http://localhost:5000');
  const [apiKey, setApiKey] = useState('');
  const [selected, setSelected] = useState<TranslationField[]>(['title', 'contractor', 'description']);
  const [japaneseOnly, setJapaneseOnly] = useState(true);
  const [columns, setColumns] = useState(28);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ source: string; entries: TranslatedEntry[] }>();
  const cancelled = useRef(false);
  const memory = useRef(new Map<string, string>());
  const snapshot = () => JSON.stringify([form.getValues('quest_type_flags.main_quest_prop'), form.getValues('strings')]);
  const request = (texts: string[]) => invoke<string[]>('translate_quest_text', { endpoint: validateEndpoint(endpoint), texts, apiKey: apiKey || null });

  const translate = async () => {
    setPreview(undefined);
    cancelled.current = false;
    setBusy(true);
    try {
      const source = snapshot();
      const entries = translationEntries(form.getValues('strings'), selected, japaneseOnly);
      if (!entries.length) { toast.info('No matching non-empty fields to translate.'); return; }
      const result = await translateEntries(entries, request, memory.current, validateEndpoint(endpoint), () => cancelled.current);
      setPreview({ source, entries: result.map(entry => ({ ...entry, translation: wrapTranslation(entry.translation, columns, entry.maxLines || 1).text })) });
    } catch (error) { toast.error(String(error)); }
    finally { setBusy(false); }
  };

  const apply = async () => {
    if (!preview) return;
    if (preview.source !== snapshot()) { toast.warn('The quest changed. Generate a new translation preview.'); setPreview(undefined); return; }
    if (!preview.entries.every(entry => wrapTranslation(entry.translation, columns, entry.maxLines || 1).fits)) {
      toast.warn('Shorten overflowing text before applying. No text was truncated.'); return;
    }
    const values = preview.entries.map(entry => wrapTranslation(entry.translation, columns, entry.maxLines || 1).text);
    const allStrings = { ...form.getValues('strings') };
    preview.entries.forEach((entry, index) => { allStrings[entry.field] = values[index]; });
    try {
      await invoke('validate_translation_texts', { texts: translationFields.map(field => allStrings[field]) });
    } catch (error) { toast.error(String(error)); return; }
    if (preview.source !== snapshot()) { toast.warn('The quest changed. Generate a new translation preview.'); return; }
    preview.entries.forEach((entry, index) => form.setValue(`strings.${entry.field}`, values[index], { shouldDirty: true }));
    setPreview(undefined);
    toast.success('Translation applied to the form. Review it before saving.');
  };

  return <GroupCard title="LibreTranslate (optional)" contentClass="flex flex-col gap-2">
    <label><input type="checkbox" checked={enabled} disabled={busy} onChange={event => {
      setEnabled(event.target.checked); setPreview(undefined); memory.current.clear(); if (!event.target.checked) setApiKey('');
    }} /> Enable automatic translation</label>
    <p>Manual editing and offline auto-fill always work without this service.</p>
    {enabled && <>
      <p>Only selected text is sent to your LibreTranslate server. Self-hosting is free; hosted services may require a key, charge fees or limit requests. Japanese-to-English models must be installed on that server.</p>
      <label className="flex flex-col">Server base URL<input className="text-black" value={endpoint} disabled={busy} onChange={event => { setEndpoint(event.target.value); setPreview(undefined); memory.current.clear(); }} /></label>
      <label className="flex flex-col">API key (optional, kept in memory only)<input className="text-black" type="password" autoComplete="off" value={apiKey} disabled={busy} onChange={event => setApiKey(event.target.value)} /></label>
      <fieldset disabled={busy}><legend>Fields to translate</legend>{translationFields.map(field => <label key={field} className="block">
        <input type="checkbox" checked={selected.includes(field)} onChange={event => { setSelected(previous => event.target.checked ? [...previous, field] : previous.filter(value => value !== field)); setPreview(undefined); }} /> {translationLabels[field]}
      </label>)}</fieldset>
      <label><input type="checkbox" checked={japaneseOnly} disabled={busy} onChange={event => { setJapaneseOnly(event.target.checked); setPreview(undefined); }} /> Only translate fields containing Japanese (preserve existing English)</label>
      <label>Estimated characters per line <input className="text-black w-20" type="number" min={1} max={200} value={columns} disabled={busy} onChange={event => setColumns(Math.min(200, Math.max(1, Math.round(Number(event.target.value)) || 28)))} /></label>
      <p>Description line budget follows the source text. Width is an estimate, not a game-font preview. LibreTranslate does not summarize: overflowing text must be shortened manually.</p>
      <Button type="button" disabled={busy || !isLoadedFile || !selected.length || !Number.isInteger(columns) || columns < 1 || columns > 200} onClick={translate}>Translate current quest — preview</Button>
      {busy && <Button type="button" onClick={() => { cancelled.current = true; }}>Cancel after current request</Button>}
      {preview && <>
        {preview.entries.map((entry, index) => {
          const layout = wrapTranslation(entry.translation, columns, entry.maxLines || 1);
          return <label key={entry.field} className="flex flex-col">{translationLabels[entry.field]} — {layout.lines}/{entry.maxLines} lines {layout.fits ? '' : '(too long: shorten manually)'}
            <span className="whitespace-pre-wrap">Original: {entry.source}</span>
            <textarea className="text-black" rows={entry.field === 'description' ? 8 : 2} value={entry.translation} onChange={event => setPreview(previous => previous && ({ ...previous, entries: previous.entries.map((value, i) => i === index ? { ...value, translation: event.target.value } : value) }))} />
          </label>;
        })}
        <Button type="button" onClick={apply}>Apply translated text</Button>
        <Button type="button" onClick={() => setPreview(undefined)}>Discard translation</Button>
      </>}
      <BatchTranslationPanel endpoint={endpoint} apiKey={apiKey} selected={selected} japaneseOnly={japaneseOnly} columns={columns} memory={memory.current} busy={busy} setBusy={setBusy} />
    </>}
  </GroupCard>;
}
