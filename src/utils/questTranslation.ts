import type { QuestStrings } from './questFile/questStrings';

export const translationFields = ['title', 'main_objective', 'sub_a_objective', 'sub_b_objective', 'clear_reqs', 'fail_reqs', 'contractor', 'description'] as const;
export type TranslationField = typeof translationFields[number];
export type StringValues = Pick<QuestStrings, TranslationField>;
export const translationLabels: Record<TranslationField, string> = {
  title: 'Title', main_objective: 'Main objective', sub_a_objective: 'Sub-objective A',
  sub_b_objective: 'Sub-objective B', clear_reqs: 'Success', fail_reqs: 'Failure',
  contractor: 'Quest giver', description: 'Description',
};
export interface TranslationEntry { field: TranslationField; source: string; maxLines?: number }
export interface TranslatedEntry extends TranslationEntry { translation: string }

export function validateEndpoint(input: string): string {
  const url = new URL(input.trim());
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) || url.username || url.password || url.search || url.hash) {
    throw new Error('Use HTTPS, or HTTP for localhost. Do not put credentials, query parameters or fragments in the URL.');
  }
  return url.toString().replace(/\/+$/, '');
}

export function translationEntries(strings: Partial<StringValues>, selected: readonly TranslationField[], japaneseOnly: boolean): TranslationEntry[] {
  return selected.flatMap(field => {
    const source = strings[field] || '';
    if (!source.trim() || (japaneseOnly && !/[\u3040-\u30ff\u3400-\u9fff]/u.test(source))) return [];
    const defaultLines = field === 'title' || field === 'clear_reqs' || field === 'fail_reqs' ? 2 : 1;
    const maxLines = field === 'description' ? source.replace(/\r\n?/g, '\n').split('\n').length : defaultLines;
    return [{ field, source, maxLines }];
  });
}

/** Conservative character-width estimate, not a calibrated rendering of the game font. */
export function wrapTranslation(input: string, columns: number, maxLines: number) {
  if (!Number.isInteger(columns) || columns < 1 || columns > 200 || !Number.isInteger(maxLines) || maxLines < 1 || maxLines > 100) {
    throw new Error('Choose 1–200 columns and 1–100 lines.');
  }
  const words = input.trim().split(/\s+/u).filter(Boolean);
  const lines: string[] = [];
  let line = '';
  for (const word of words) {
    if (line && [...`${line} ${word}`].length > columns) { lines.push(line); line = word; }
    else line = line ? `${line} ${word}` : word;
  }
  if (line) lines.push(line);
  return { text: lines.join('\n'), fits: lines.length <= maxLines && lines.every(value => [...value].length <= columns), lines: lines.length };
}

export async function translateEntries(
  entries: TranslationEntry[], request: (texts: string[]) => Promise<string[]>,
  memory: Map<string, string>, provider: string, cancelled: () => boolean = () => false,
): Promise<TranslatedEntry[]> {
  const key = (source: string) => JSON.stringify([provider, 'ja', 'en', source]);
  const unique = [...new Set(entries.map(entry => entry.source))].filter(source => !memory.has(key(source)));
  for (let start = 0; start < unique.length; start += 8) {
    if (cancelled()) throw new Error('Translation cancelled.');
    const texts = unique.slice(start, start + 8);
    const translated = await request(texts);
    if (cancelled()) throw new Error('Translation cancelled.');
    if (!Array.isArray(translated) || translated.length !== texts.length || translated.some(value => typeof value !== 'string' || !value.trim() || value.includes('\0'))) {
      throw new Error('Invalid translation response. Existing text was not changed.');
    }
    texts.forEach((source, index) => memory.set(key(source), translated[index]));
  }
  return entries.map(entry => ({ ...entry, translation: memory.get(key(entry.source))! }));
}
