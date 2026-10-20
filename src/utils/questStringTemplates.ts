import type { Objective, QuestObjective } from './questFile/questTypeFlags';
import type { QuestStrings } from './questFile/questStrings';

type ObjectiveField = 'main_objective' | 'sub_a_objective' | 'sub_b_objective';
export interface TargetNames {
  monster: (id: number) => string | undefined;
  item: (id: number) => string | undefined;
}
export interface TextSuggestion {
  value?: string;
  warning?: string;
}
export type FailurePolicy = 'preserve' | 'faints' | 'reward';

function objectiveText(objective: Objective, names: TargetNames): TextSuggestion {
  if (objective.quest_objective === 0) return { value: 'None' };
  const verbs: Record<number, string> = { 1: 'Hunt', 257: 'Capture', 513: 'Slay', 2: 'Deliver' };
  const verb = verbs[objective.quest_objective];
  if (!verb) return { warning: `Objective type ${objective.quest_objective} needs manual text.` };
  if (!Number.isInteger(objective.quantity) || objective.quantity <= 0 || objective.quantity > 65535) {
    return { warning: 'Invalid objective quantity; existing text was preserved.' };
  }
  // The Rust model exposes the on-disk uint16 target as two uint8 fields.
  const bytes = [objective.monster_id, objective.unk];
  if (bytes.some(value => !Number.isInteger(value) || value < 0 || value > 255)) {
    return { warning: 'Invalid target ID; existing text was preserved.' };
  }
  const targetId = objective.monster_id + objective.unk * 256;
  const target = objective.quest_objective === 2 ? names.item(targetId) : names.monster(targetId);
  if (!targetId || !target?.trim() || /^(none|unknown|unk|dummy)\b/i.test(target) || target.includes('?')) {
    return { warning: `Target ${targetId} needs a verified English name.` };
  }
  return { value: `${verb} ${objective.quantity} ${target}` };
}

export function suggestObjectives(objectives: QuestObjective, names: TargetNames) {
  const fields: [ObjectiveField, Objective, string][] = [
    ['main_objective', objectives.objective1, 'Main objective'],
    ['sub_a_objective', objectives.objective2, 'Sub-objective A'],
    ['sub_b_objective', objectives.objective3, 'Sub-objective B'],
  ];
  const values: Partial<Pick<QuestStrings, ObjectiveField>> = {};
  const warnings: string[] = [];
  for (const [field, objective, label] of fields) {
    const result = objectiveText(objective, names);
    if (result.value !== undefined) values[field] = result.value;
    if (result.warning) warnings.push(`${label}: ${result.warning}`);
  }
  return { values, warnings };
}

/** Templates follow this editor's requirement_to_finish labels, not quest categories. */
export function suggestSuccess(mode: number, objectives: QuestObjective): TextSuggestion {
  if (objectives.objective1.quest_objective === 0) {
    return { warning: 'No main objective; check success conditions manually.' };
  }
  const subA = objectives.objective2.quest_objective !== 0;
  const subB = objectives.objective3.quest_objective !== 0;
  switch (mode) {
    case 1: {
      const sub = subA && subB ? 'A or B' : subA ? 'A' : subB ? 'B' : undefined;
      return { value: sub ? `Complete the main objective\nor sub-objective ${sub}.` : 'Complete the main objective.' };
    }
    case 2:
      return { value: 'Complete the main objective.' };
    case 3:
      return subA ? { value: 'Complete the main objective\nand sub-objective A.' }
        : { warning: 'This success mode requires sub-objective A, but none is set.' };
    case 4:
      return { value: 'Complete all objectives.' };
    default:
      return { warning: `Success mode ${mode} needs manual text.` };
  }
}

/** Failure policy must be chosen by the user; the G-rank bit is not a death-policy flag. */
export function suggestFailure(policy: FailurePolicy, faintCount: number): TextSuggestion {
  if (policy === 'preserve') return {};
  if (policy === 'reward') return { value: 'Reward falls to 0z.\nTime runs out.' };
  if (!Number.isInteger(faintCount) || faintCount < 1 || faintCount > 255) {
    return { warning: 'Choose a valid faint limit before generating failure text.' };
  }
  return { value: `Faint ${faintCount} ${faintCount === 1 ? 'time' : 'times'}.\nTime runs out.` };
}
