import { useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api';
import { open } from '@tauri-apps/api/dialog';
import { toast } from 'react-toastify';
import { Button } from '../Button';
import { translationEntries, translateEntries, validateEndpoint, wrapTranslation, translationLabels } from '../../utils/questTranslation';
import type { StringValues, TranslationField, TranslatedEntry } from '../../utils/questTranslation';

interface BatchQuest {
  path: string; name: string; quest_id?: number; variant?: string; source_stamp?: string;
  strings?: StringValues; wrappers: string[]; error?: string;
}
interface BatchReport { path: string; output?: string; repacked_jpk3: boolean; error?: string }
interface Row { quest: BatchQuest; entries?: TranslatedEntry[]; error?: string }
interface Props {
  endpoint: string; apiKey: string; selected: TranslationField[]; japaneseOnly: boolean;
  columns: number; memory: Map<string, string>; busy: boolean; setBusy: (value: boolean) => void;
}

export function BatchTranslationPanel(props: Props) {
  const [rows, setRows] = useState<Row[]>([]);
  const [reports, setReports] = useState<BatchReport[]>([]);
  const [status, setStatus] = useState('');
  const [repack, setRepack] = useState(false);
  const [sourceSettings, setSourceSettings] = useState('');
  const cancelled = useRef(false);
  const settings = () => JSON.stringify([props.endpoint, props.selected, props.japaneseOnly]);

  const load = async () => {
    props.setBusy(true);
    try {
      const paths = await open({ multiple: true, filters: [{ name: 'Quest BIN files', extensions: ['bin'] }] });
      if (!paths) return;
      const quests = await invoke<BatchQuest[]>('inspect_translation_quests', { filepaths: Array.isArray(paths) ? paths : [paths] });
      setRows(quests.map(quest => ({ quest }))); setReports([]); setSourceSettings('');
      setStatus(`Inspected ${quests.length} files. Originals remain unchanged.`);
    } catch (error) { toast.error(String(error)); }
    finally { props.setBusy(false); }
  };

  const translate = async () => {
    cancelled.current = false; props.setBusy(true); setReports([]);
    const output: Row[] = [];
    const sources: Row[] = rows.map(row => ({ quest: row.quest }));
    try {
      const provider = validateEndpoint(props.endpoint);
      setSourceSettings(settings());
      for (let index = 0; index < rows.length; index++) {
        if (cancelled.current) { output.push(...sources.slice(index)); break; }
        const { quest } = sources[index];
        setStatus(`Translating ${index + 1}/${rows.length}: ${quest.name}`);
        if (quest.error || !quest.strings) { output.push({ quest }); continue; }
        try {
          const entries = translationEntries(quest.strings, props.selected, props.japaneseOnly);
          const translated = await translateEntries(entries, texts => invoke<string[]>('translate_quest_text', { endpoint: provider, texts, apiKey: props.apiKey || null }), props.memory, provider, () => cancelled.current);
          output.push({ quest, entries: translated.map(entry => ({ ...entry, translation: wrapTranslation(entry.translation, props.columns, entry.maxLines || 1).text })) });
        } catch (error) {
          output.push({ quest, error: String(error) });
          // Stop on service failure; a new preview can reuse completed translations.
          output.push(...sources.slice(index + 1)); break;
        }
      }
      setRows(output);
      setStatus(cancelled.current ? 'Cancelled after current request. Completed previews are preserved.' : 'Preview ready. Review all fields before exporting.');
    } catch (error) { toast.error(String(error)); }
    finally { props.setBusy(false); }
  };

  const exportFiles = async () => {
    if (sourceSettings !== settings()) { toast.warn('Translation settings changed. Generate a new batch preview.'); return; }
    const candidates = rows.filter(row => row.entries?.length && !row.error && !row.quest.error && row.quest.strings && row.quest.source_stamp);
    if (!candidates.length) { toast.info('No translated files to export.'); return; }
    if (candidates.some(row => row.entries!.some(entry => !wrapTranslation(entry.translation, props.columns, entry.maxLines || 1).fits))) {
      toast.warn('Shorten overflowing translations before exporting.'); return;
    }
    props.setBusy(true);
    try {
      const directory = await open({ directory: true, multiple: false });
      if (!directory || Array.isArray(directory)) return;
      const quests = candidates.map(row => {
        const strings = { ...row.quest.strings! };
        for (const entry of row.entries!) strings[entry.field] = wrapTranslation(entry.translation, props.columns, entry.maxLines || 1).text;
        return { path: row.quest.path, source_stamp: row.quest.source_stamp, original_strings: row.quest.strings, strings };
      });
      const result = await invoke<BatchReport[]>('export_translation_quests', { quests, outputDirectory: directory, repackJpk3: repack });
      setReports(result); setStatus(`Exported ${result.filter(report => report.output).length}/${result.length} translated files. See report below.`);
    } catch (error) { toast.error(String(error)); }
    finally { props.setBusy(false); }
  };

  const groups = new Map<number, Set<string>>();
  rows.forEach(({ quest }) => { if (quest.quest_id !== undefined && quest.quest_id !== null && quest.variant) {
    const variants = groups.get(quest.quest_id) || new Set<string>(); variants.add(quest.variant); groups.set(quest.quest_id, variants);
  } });
  return <section className="flex flex-col gap-2 border-t pt-2">
    <h3>Batch translation — text only</h3>
    <p>Select the d0/d1/d2/n0/n1/n2 files you have. Missing variants are reported, never invented. Matching text reuses this session’s translation memory.</p>
    <Button type="button" disabled={props.busy} onClick={load}>Select quest BIN files</Button>
    {[...groups].map(([id, variants]) => <p key={id}>{id}: {variants.size}/6 variants; missing: {['d0', 'd1', 'd2', 'n0', 'n1', 'n2'].filter(value => !variants.has(value)).join(', ') || 'none'}</p>)}
    <Button type="button" disabled={props.busy || !rows.length || !props.selected.length} onClick={translate}>Translate selected files — preview</Button>
    {props.busy && <Button type="button" onClick={() => { cancelled.current = true; }}>Cancel batch after current request</Button>}
    <p role="status">{status}</p>
    {rows.map((row, index) => <details key={row.quest.path}>
      <summary>{row.quest.name} — {row.quest.wrappers.join(' → ') || 'raw'} {row.quest.error || row.error || (row.entries ? `${row.entries.length} translated fields` : 'not translated')}</summary>
      {row.entries?.map((entry, fieldIndex) => {
        const layout = wrapTranslation(entry.translation, props.columns, entry.maxLines || 1);
        return <label className="flex flex-col" key={entry.field}>{translationLabels[entry.field]}: {layout.lines}/{entry.maxLines} lines {layout.fits ? '' : '— too long'}
          <span className="whitespace-pre-wrap">Original: {entry.source}</span>
          <textarea className="text-black" rows={entry.field === 'description' ? 8 : 2} value={entry.translation} disabled={props.busy} onChange={event => setRows(previous => previous.map((value, i) => i === index ? { ...value, entries: value.entries?.map((field, j) => j === fieldIndex ? { ...field, translation: event.target.value } : field) } : value))} />
        </label>;
      })}
    </details>)}
    <label><input type="checkbox" checked={repack} disabled={props.busy} onChange={event => setRepack(event.target.checked)} /> Allow conversion of supported decoded JPK compression to JPK3 when original compression cannot be encoded. Output is round-trip checked; verify a sample in game before deployment.</label>
    <p>Exports create new files and preserve gameplay bytes. Existing output names are refused. Files with errors are excluded; text over the estimated layout limit blocks export.</p>
    <Button type="button" disabled={props.busy || !rows.some(row => row.entries?.length)} onClick={exportFiles}>Export translated BIN copies</Button>
    {reports.map(report => <p key={report.path}>{report.path}: {report.output || report.error}{report.repacked_jpk3 ? ' (repacked as JPK3)' : ''}</p>)}
  </section>;
}
