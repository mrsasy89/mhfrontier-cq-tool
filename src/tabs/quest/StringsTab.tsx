import { useState } from "react";
import { toast } from "react-toastify";
import { Button } from "../../components/Button";
import { GroupCard } from "../../components/CardGroup";
import { InputField } from "../../components/Input";
import { TextAreaField } from "../../components/TextArea";
import { useQuestEditor } from "../../context/QuestEditorContext";
import { monsters } from "../../utils/monsters";
import { items } from "../../utils/items";
import { suggestObjectives, suggestSuccess, suggestFailure } from "../../utils/questStringTemplates";
import type { FailurePolicy } from "../../utils/questStringTemplates";
import type { QuestStrings } from "../../utils/questFile/questStrings";

type GeneratedField = 'main_objective' | 'sub_a_objective' | 'sub_b_objective' | 'clear_reqs' | 'fail_reqs';
type GeneratedText = Partial<Pick<QuestStrings, GeneratedField>>;
const generatedLabels: Record<GeneratedField, string> = {
    main_objective: 'Main objective', sub_a_objective: 'Sub-objective A',
    sub_b_objective: 'Sub-objective B', clear_reqs: 'Success', fail_reqs: 'Failure',
};
const itemNames = new Map(items.map(item => [item.id, item.name_en]));

export function QuestStringTab() {
    const { form, isLoadedFile } = useQuestEditor();
    const [failurePolicy, setFailurePolicy] = useState<FailurePolicy>('preserve');
    const [preview, setPreview] = useState<{ values: GeneratedText; source: string; warnings: string[] }>();

    const generate = (kind: 'objectives' | 'conditions') => {
        const props = form.getValues('quest_type_flags.main_quest_prop');
        if (!props) return;
        if (kind === 'objectives') {
            const result = suggestObjectives(props.objectives, {
                monster: id => monsters[id], item: id => itemNames.get(id),
            });
            setPreview({ ...result, source: JSON.stringify(props) });
            return;
        }
        const success = suggestSuccess(props.requirement_to_finish, props.objectives);
        const failure = suggestFailure(failurePolicy, props.max_death);
        const values: GeneratedText = {};
        if (success.value !== undefined) values.clear_reqs = success.value;
        if (failure.value !== undefined) values.fail_reqs = failure.value;
        setPreview({ values, source: JSON.stringify(props), warnings: [success.warning, failure.warning].filter((value): value is string => !!value) });
    };

    const applyPreview = () => {
        if (!preview) return;
        if (preview.source !== JSON.stringify(form.getValues('quest_type_flags.main_quest_prop'))) {
            toast.warn('Quest parameters changed. Generate a new preview before applying it.');
            setPreview(undefined);
            return;
        }
        for (const field of Object.keys(generatedLabels) as GeneratedField[]) {
            const value = preview.values[field];
            if (value !== undefined) form.setValue(`strings.${field}`, value, { shouldDirty: true });
        }
        setPreview(undefined);
    };
    return (
    <div className="flex flex-row flex-wrap gap-2">
        <GroupCard title="English text templates" contentClass="flex flex-col gap-2">
            <p>Preview text from the current quest parameters. Unsupported objectives keep their existing text.</p>
            <Button type="button" disabled={!isLoadedFile} onClick={() => generate('objectives')}>Preview objectives</Button>
            <label htmlFor="failure-template">Failure template (choose after checking the quest rules)</label>
            <select id="failure-template" className="text-black" value={failurePolicy} onChange={event => {
                const value = event.target.value;
                if (value === 'preserve' || value === 'faints' || value === 'reward') setFailurePolicy(value);
                setPreview(undefined);
            }}>
                <option value="preserve">Keep current failure text</option>
                <option value="faints">Faint limit and time limit</option>
                <option value="reward">Reward reaches 0z and time limit</option>
            </select>
            <Button type="button" disabled={!isLoadedFile} onClick={() => generate('conditions')}>Preview success/failure</Button>
            {preview && <>
                {preview.warnings.map(warning => <p key={warning} role="status">{warning}</p>)}
                {(Object.keys(generatedLabels) as GeneratedField[]).filter(field => preview.values[field] !== undefined).map(field => (
                    <label key={field} className="flex flex-col">{generatedLabels[field]}
                        <textarea className="text-black" readOnly rows={2} value={preview.values[field]} />
                    </label>
                ))}
                <p>Apply changes to the form, then use Save Quest when ready. Review special quest conditions manually.</p>
                <Button type="button" disabled={!Object.keys(preview.values).length || !isLoadedFile} onClick={applyPreview}>Apply generated text</Button>
                <Button type="button" onClick={() => setPreview(undefined)}>Discard preview</Button>
            </>}
        </GroupCard>
        <GroupCard title="Text" contentClass="grid grid-cols-4">
            <TextAreaField
                label="Title"
                type="text"
                className="col-span-2"
                name="strings.title"
                control={form.control}
            />
            <InputField
                label="Main Objective"
                type="text"
                className="col-span-2"
                name="strings.main_objective"
                control={form.control}
            />
            <InputField
                label="Sub A"
                type="text"
                className="col-span-2"
                name="strings.sub_a_objective"
                control={form.control}
            />
            <InputField
                label="Sub B"
                type="text"
                className="col-span-2"
                name="strings.sub_b_objective"
                control={form.control}
            />
            <TextAreaField
                label="Success"
                type="text"
                className="col-span-2"
                name="strings.clear_reqs"
                control={form.control}
            />
            <TextAreaField
                label="Fail"
                type="text"
                className="col-span-2"
                name="strings.fail_reqs"
                control={form.control}
            />
            <InputField
                label="Contractor"
                type="text"
                className="col-span-2"
                name="strings.contractor"
                control={form.control}
            />
            <TextAreaField
                label="Description"
                type="text"
                className="col-span-2"
                name="strings.description"
                control={form.control}
            />
        </GroupCard>
    </div>
  );
}

